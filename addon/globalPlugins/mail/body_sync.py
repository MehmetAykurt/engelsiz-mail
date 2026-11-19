# -*- coding: utf-8 -*-
"""IMAP gövdelerini paketler halinde yerel SQLite önbelleğine eşitler."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import email
import re
import threading
from email import policy as email_policy

from .attachments import (
    mesaj_metni_ve_ekleri_cikar,
    AZAMI_EPOSTA_ISLEME_BOYUTU,
)
from .errors import MailHatasi
from .imap_client import uid_listesini_parcala
from .logger import hata_kaydet, uyari_kaydet
from .mail_store import govdesi_eksik_uidleri_al, mesaj_govdesini_kaydet
from .message_parser import ham_mesaj_verisi_al
from .cache_limits import OnbellekSiniriHatasi, onbellek_kotasi_denetle
from .text_utils import html_temizle, duz_metni_ekran_okuyucu_icin_temizle


GOVDE_PAKET_BOYUTU = 100
_GOVDE_SENKRONIZASYON_KILIDI = threading.Lock()


def _bodystructure_ogelerini_ayristir(metin):
    """BODYSTRUCTURE yanıtını yalnızca metin bölümlerini bulacak kadar ayrıştırır."""
    simgeler = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', metin or "")
    kok = []
    yigin = [kok]
    for simge in simgeler:
        if simge == "(":
            yeni = []
            yigin[-1].append(yeni)
            yigin.append(yeni)
        elif simge == ")":
            if len(yigin) > 1:
                yigin.pop()
        else:
            if simge.startswith('"') and simge.endswith('"'):
                simge = re.sub(r'\\(.)', lambda eslesme: eslesme.group(1), simge[1:-1])
            yigin[-1].append(simge)
    return kok[0] if len(kok) == 1 and isinstance(kok[0], list) else kok


def _bodystructure_metnini_al(veri):
    parcalar = [parca[0] if isinstance(parca, tuple) else parca for parca in (veri or [])]
    ham = " ".join(parca.decode("utf-8", errors="replace") if isinstance(parca, bytes) else str(parca) for parca in parcalar)
    baslangic = ham.upper().find("BODYSTRUCTURE")
    baslangic = ham.find("(", baslangic)
    if baslangic < 0:
        return ""
    derinlik = 0
    tirnak = False
    kacis = False
    for konum in range(baslangic, len(ham)):
        karakter = ham[konum]
        if tirnak:
            if kacis:
                kacis = False
            elif karakter == "\\":
                kacis = True
            elif karakter == '"':
                tirnak = False
        elif karakter == '"':
            tirnak = True
        elif karakter == "(":
            derinlik += 1
        elif karakter == ")":
            derinlik -= 1
            if derinlik == 0:
                return ham[baslangic:konum + 1]
    return ""


def _bodystructure_ek_mi(yapi):
    if not isinstance(yapi, list) or not yapi:
        return False
    if isinstance(yapi[0], list):
        ilk_atom = next((i for i, oge in enumerate(yapi) if not isinstance(oge, list)), len(yapi))
        uzantilar = yapi[ilk_atom + 1:]
    else:
        uzantilar = yapi[2:3] + yapi[7:]
    def ek_parametresi(oge):
        if not isinstance(oge, list):
            return False
        if oge and str(oge[0]).upper() == "ATTACHMENT":
            return True
        return any(str(alt).upper() in ("NAME", "FILENAME") if not isinstance(alt, list)
                   else ek_parametresi(alt) for alt in oge)
    return any(ek_parametresi(oge) for oge in uzantilar)


def _metin_parcalarini_bul(yapi, yol=""):
    if not isinstance(yapi, list) or not yapi:
        return []
    if _bodystructure_ek_mi(yapi):
        return []
    if isinstance(yapi[0], list):
        sonuc = []
        sira = 0
        for oge in yapi:
            if not isinstance(oge, list):
                break
            sira += 1
            sonuc.extend(_metin_parcalarini_bul(oge, str(sira) if not yol else f"{yol}.{sira}"))
        alt_tur = str(yapi[sira] or "").upper() if sira < len(yapi) else ""
        if alt_tur == "ALTERNATIVE":
            secilen = []
            duz = [parca for parca in sonuc if parca[1] == "PLAIN"]
            html = [parca for parca in sonuc if parca[1] == "HTML"]
            if duz:
                secilen.append(duz[0])
            if html:
                secilen.append(html[0])
            return secilen or sonuc
        return sonuc
    tur = str(yapi[0] or "").upper()
    alt_tur = str(yapi[1] or "").upper() if len(yapi) > 1 else ""
    if tur == "TEXT" and alt_tur in ("PLAIN", "HTML"):
        return [(yol, alt_tur)]
    return []


def _bodystructure_yapraklarini_bul(yapi):
    """Geçerli bir BODYSTRUCTURE ağacındaki MIME yaprak türlerini döndürür."""
    if not isinstance(yapi, list) or not yapi:
        return None
    if _bodystructure_ek_mi(yapi):
        return []
    if isinstance(yapi[0], list):
        yapraklar = []
        alt_yapi_var = False
        for oge in yapi:
            if not isinstance(oge, list):
                break
            alt_yapi_var = True
            alt_yapraklar = _bodystructure_yapraklarini_bul(oge)
            if alt_yapraklar is None:
                return None
            yapraklar.extend(alt_yapraklar)
        return yapraklar if alt_yapi_var else None
    if len(yapi) < 2:
        return None
    tur = str(yapi[0] or "").upper()
    alt_tur = str(yapi[1] or "").upper()
    metin = " ".join(str(oge or "").upper() for oge in yapi)
    ek_mi = "ATTACHMENT" in metin or " FILENAME" in metin or " NAME" in metin
    return [(tur, alt_tur, ek_mi)]


def yeni_ileti_govdesini_ek_indirmeden_kaydet(imap, eposta, uid, imap_klasoru="INBOX"):
    """Yalnızca metin MIME parçalarını indirir; ek dosyalarına hiç istek göndermez."""
    tip, veri = imap.uid("FETCH", str(uid), "(BODYSTRUCTURE)")
    if tip != "OK":
        raise MailHatasi(_("E-posta yapısı sunucudan alınamadı."))
    bodystructure_metni = _bodystructure_metnini_al(veri)
    yapi = _bodystructure_ogelerini_ayristir(bodystructure_metni)
    yapraklar = _bodystructure_yapraklarini_bul(yapi)
    if not bodystructure_metni or yapraklar is None:
        raise MailHatasi(_("E-posta MIME yapısı çözümlenemedi; gövde boş olarak kaydedilmedi."))
    parcalar = _metin_parcalarini_bul(yapi)
    # Bazı iletiler okunabilir bir text/plain veya text/html gövdesinin yanında
    # text/calendar ya da inline message/rfc822 gibi ek MIME yaprakları taşır.
    # Bu ek yaprakları indirmiyoruz; güvenli bir metin parçası bulunduğu sürece
    # yalnızca o parçayı alarak iletinin tamamını gereksiz yere reddetmeyiz.
    if not parcalar and any(
        not ek_mi and (
            tur == "MESSAGE" and alt_tur == "RFC822"
            or tur == "TEXT" and alt_tur not in ("PLAIN", "HTML")
        )
        for tur, alt_tur, ek_mi in yapraklar
    ):
        raise MailHatasi(_("E-posta MIME yapısı ek indirmeden güvenle çözümlenemedi."))
    # Representation selection is confined to each multipart/alternative node.
    # Mixed siblings may contain independent content and must all survive.
    def bildirilen_metin_boyutu(dugum):
        if not isinstance(dugum, list) or not dugum or _bodystructure_ek_mi(dugum):
            return 0
        if isinstance(dugum[0], list):
            return sum(bildirilen_metin_boyutu(alt) for alt in dugum if isinstance(alt, list))
        try:
            return max(0, int(dugum[6])) if str(dugum[0]).upper() == "TEXT" else 0
        except (IndexError, TypeError, ValueError):
            raise MailHatasi(_("E-posta bölüm boyutu doğrulanamadı."))
    if bildirilen_metin_boyutu(yapi) > AZAMI_EPOSTA_ISLEME_BOYUTU:
        raise MailHatasi(_("E-posta metni güvenli boyut sınırını aşıyor."))
    if not parcalar:
        # Yalnız ek içeren iletiler de açılabilmelidir. Metin boş kaydedilir;
        # ileti penceresi yine "Ekleri Kaydet" düğmesini gösterebilir.
        return bool(mesaj_govdesini_kaydet(
            eposta, imap_klasoru, uid, "", 0, ""
        ))
    metinler = []
    html_metinler = []
    toplam_boyut = 0
    tarih = ""
    basarisiz_parca_var = False
    icerik_bayti_var = False
    for yol, _alt_tur in parcalar:
        kesim = yol or "TEXT"
        baslik_kesimi = (yol + ".MIME") if yol else "HEADER"
        tip, baslik_veri = imap.uid("FETCH", str(uid), f"(BODY.PEEK[{baslik_kesimi}])")
        kalan_sinir = AZAMI_EPOSTA_ISLEME_BOYUTU - toplam_boyut
        tip2, govde_veri = imap.uid("FETCH", str(uid), f"(BODY.PEEK[{kesim}]<0.{kalan_sinir + 1}>)")
        if tip != "OK" or tip2 != "OK":
            basarisiz_parca_var = True
            continue
        ham_baslik = ham_mesaj_verisi_al(baslik_veri)
        ham_govde = ham_mesaj_verisi_al(govde_veri)
        if len(ham_baslik or b"") + len(ham_govde or b"") > kalan_sinir:
            raise MailHatasi(_("E-posta metni güvenli boyut sınırını aşıyor."))
        if not ham_govde:
            continue
        icerik_bayti_var = True
        mesaj = email.message_from_bytes((ham_baslik or b"") + b"\r\n" + ham_govde, policy=email_policy.default)
        try:
            cikti = mesaj_metni_ve_ekleri_cikar(mesaj, ayrintili=True, html_dahil=True)
            if len(cikti) == 4:
                icerik, _ekler, _atlanan, html_icerik = cikti
            elif len(cikti) == 3:
                icerik, _ekler, html_icerik = cikti
            else:
                icerik, _ekler = cikti[:2]
                html_icerik = ""
        except TypeError:
            cikti = mesaj_metni_ve_ekleri_cikar(mesaj, ayrintili=True)
            if len(cikti) == 3:
                icerik, _ekler, _atlanan = cikti
            else:
                icerik, _ekler = cikti[:2]
            html_icerik = ""
        if _alt_tur == "PLAIN":
            if icerik:
                metinler.append(icerik)
        elif _alt_tur == "HTML":
            if html_icerik:
                html_metinler.append(html_icerik)
            elif icerik:
                html_metinler.append(icerik)
            if not metinler and icerik:
                metinler.append(icerik)
        else:
            if icerik:
                metinler.append(icerik)
            if html_icerik:
                html_metinler.append(html_icerik)
        toplam_boyut += len(ham_baslik or b"") + len(ham_govde)
        tarih = tarih or mesaj.get("Date", "")
    if basarisiz_parca_var:
        raise MailHatasi(_("E-posta metninin bazı bölümleri alınamadı; eksik içerik tamamlanmış olarak kaydedilmedi."))
    if not metinler and html_metinler:
        for h in html_metinler:
            try:
                duz = duz_metni_ekran_okuyucu_icin_temizle(html_temizle(h)).strip()
            except Exception:
                duz = ""
            if duz:
                metinler.append(duz)
        if not metinler:
            metinler.append(_("(Görsel veya biçimlendirilmiş içerik)"))
    if not metinler:
        bos_metin = _("(Metin içeriği bulunamadı)") if icerik_bayti_var else ""
        birlestirilmis_html = "\n<hr>\n".join(html_metinler) if html_metinler else ""
        try:
            return bool(mesaj_govdesini_kaydet(
                eposta, imap_klasoru, uid, bos_metin, toplam_boyut, tarih,
                html_metin=birlestirilmis_html,
            ))
        except TypeError:
            return bool(mesaj_govdesini_kaydet(
                eposta, imap_klasoru, uid, bos_metin, toplam_boyut, tarih
            ))
    onbellek_kotasi_denetle(toplam_boyut)
    birlestirilmis_duz_metin = "\n\n".join(metinler)
    birlestirilmis_html = "\n<hr>\n".join(html_metinler) if html_metinler else ""
    try:
        return bool(mesaj_govdesini_kaydet(
            eposta, imap_klasoru, uid, birlestirilmis_duz_metin, toplam_boyut, tarih,
            html_metin=birlestirilmis_html,
        ))
    except TypeError:
        return bool(mesaj_govdesini_kaydet(
            eposta, imap_klasoru, uid, birlestirilmis_duz_metin, toplam_boyut, tarih
        ))


def _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
    return yeni_ileti_govdesini_ek_indirmeden_kaydet(
        imap, eposta, uid, imap_klasoru
    )


def klasor_govdelerini_senkronize_et(
    imap,
    eposta,
    imap_klasoru,
    sunucu_uidleri,
    iptal_edildi_mi=None,
):
    """Başlığı kayıtlı iletilerin eksik gövdelerini 100'lük paketlerle önbelleğe alır."""
    if not _GOVDE_SENKRONIZASYON_KILIDI.acquire(blocking=False):
        return {"atlandi": True, "iptal_edildi": False, "kaydedilen": 0, "hatali": 0}
    try:
        eksik_uidler = govdesi_eksik_uidleri_al(eposta, imap_klasoru, sunucu_uidleri)
        kaydedilen = 0
        hatali = 0
        for uid_parcasi in uid_listesini_parcala(eksik_uidler, GOVDE_PAKET_BOYUTU):
            if callable(iptal_edildi_mi) and iptal_edildi_mi():
                return {
                    "toplam": len(eksik_uidler),
                    "kaydedilen": kaydedilen,
                    "hatali": hatali,
                    "iptal_edildi": True,
                }
            for uid in uid_parcasi:
                if callable(iptal_edildi_mi) and iptal_edildi_mi():
                    return {
                        "toplam": len(eksik_uidler),
                        "kaydedilen": kaydedilen,
                        "hatali": hatali,
                        "iptal_edildi": True,
                    }
                try:
                    if _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
                        kaydedilen += 1
                except OnbellekSiniriHatasi as e:
                    uyari_kaydet(
                        "E-posta gövdesi eşitlemesi güvenli önbellek sınırına ulaştığı için durduruldu.",
                        e,
                    )
                    return {
                        "toplam": len(eksik_uidler),
                        "kaydedilen": kaydedilen,
                        "hatali": hatali,
                        "sinira_ulasti": True,
                        "iptal_edildi": False,
                    }
                except Exception as e:
                    hatali += 1
                    hata_kaydet(f"E-posta gövdesi önbelleğe alınamadı: UID {uid}", e)
        return {
            "toplam": len(eksik_uidler),
            "kaydedilen": kaydedilen,
            "hatali": hatali,
            "iptal_edildi": False,
        }
    finally:
        _GOVDE_SENKRONIZASYON_KILIDI.release()


def secili_govdeleri_dogrudan_senkronize_et(imap, eposta, imap_klasoru, uidler):
    """Genel eşitleme meşgulse kullanıcı tarafından açılan iletileri bekletmeden indirir."""
    eksik_uidler = govdesi_eksik_uidleri_al(eposta, imap_klasoru, uidler)
    kaydedilen = 0
    hatali = 0
    for uid in eksik_uidler:
        try:
            if _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
                kaydedilen += 1
        except Exception as e:
            hatali += 1
            hata_kaydet(f"Açılan konuşmanın e-posta gövdesi alınamadı: UID {uid}", e)
    return {
        "toplam": len(eksik_uidler),
        "kaydedilen": kaydedilen,
        "hatali": hatali,
        "iptal_edildi": False,
    }
