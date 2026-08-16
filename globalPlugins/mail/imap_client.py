# -*- coding: utf-8 -*-
# Engelsiz Mail - IMAP yardımcıları


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import re
import socket
import ssl
import threading
import time

from .errors import MailHatasi
from .logger import hata_kaydet
from .vendor import imaplib


GMAIL_IMAP_SUNUCU = "imap.gmail.com"


GMAIL_IMAP_PORT = 993
IMAP_BAGLANTI_ZAMAN_ASIMI = 20


class ImapBaglantisi:
    """CPython imaplib ile IMAP bağlantısını güvenli biçimde yönetir."""

    def __init__(self, ayarlar, timeout=IMAP_BAGLANTI_ZAMAN_ASIMI):
        self.ayarlar = ayarlar
        self.timeout = timeout
        self.imap = None
        self._durum_kilidi = threading.Lock()

    def _imap_nesnesini_ayarla(self, imap):
        with self._durum_kilidi:
            self.imap = imap

    def _imap_nesnesini_cikar(self):
        with self._durum_kilidi:
            imap = self.imap
            self.imap = None
        return imap

    def __enter__(self):
        eposta = self.ayarlar.get("eposta", "")
        sifre = self.ayarlar.get("sifre", "")
        if not eposta or not sifre:
            raise MailHatasi(_("Hesap bilgileri eksik."))
        try:
            ssl_baglami = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                GMAIL_IMAP_SUNUCU,
                GMAIL_IMAP_PORT,
                ssl_context=ssl_baglami,
                timeout=self.timeout,
            )
            self._imap_nesnesini_ayarla(imap)
            tip, _veri = imap.login(eposta, sifre)
            if tip != "OK":
                raise MailHatasi(_("Gmail hesabına giriş yapılamadı. E-posta adresi veya uygulama şifresi hatalı olabilir."))
            return imap
        except imaplib.IMAP4.error as e:
            self._basarisiz_baglantiyi_kapat()
            raise MailHatasi(_("Gmail hesabına giriş yapılamadı. E-posta adresi veya uygulama şifresi hatalı olabilir.")) from e
        except socket.timeout as e:
            self._basarisiz_baglantiyi_kapat()
            raise MailHatasi(_("IMAP sunucusu zamanında yanıt vermedi. İnternet bağlantınızı veya kurum ağı kısıtlamalarını denetleyin.")) from e
        except ssl.SSLError as e:
            self._basarisiz_baglantiyi_kapat()
            raise MailHatasi(_("IMAP sunucusuyla güvenli bağlantı kurulamadı. Kurum ağı, güvenlik yazılımı veya sertifika denetimi bağlantıyı kesiyor olabilir.")) from e
        except OSError as e:
            self._basarisiz_baglantiyi_kapat()
            raise MailHatasi(_("IMAP sunucusuna bağlantı kurulamadı. İnternet bağlantınızı, güvenlik duvarınızı veya kurum ağı ayarlarınızı denetleyin.")) from e
        except Exception:
            self._basarisiz_baglantiyi_kapat()
            raise

    def _basarisiz_baglantiyi_kapat(self):
        imap = self._imap_nesnesini_cikar()
        if not imap:
            return
        try:
            imap.logout()
        except Exception as e:
            hata_kaydet("Başarısız IMAP girişi sonrası oturum kapatılamadı.", e)
            try:
                imap.shutdown()
            except Exception:
                pass

    def shutdown(self):
        """Etkin ağ oturumunu beklemeden keser ve sonraki çıkışı etkisiz kılar."""
        imap = self._imap_nesnesini_cikar()
        if not imap:
            return False
        try:
            imap.shutdown()
        except Exception as e:
            hata_kaydet("Etkin IMAP bağlantısı denetimli kapanışta kesilemedi.", e)
        return True

    def __exit__(self, exc_type, exc, tb):
        imap = self._imap_nesnesini_cikar()
        if not imap:
            return
        try:
            imap.logout()
        except Exception as e:
            hata_kaydet("IMAP oturumu kapatılırken hata oluştu.", e)
            try:
                imap.shutdown()
            except Exception:
                pass


def imap_ok_mu(tip, hata_mesaji):
    """IMAP komut sonucunu denetler; OK değilse kullanıcıya uygun hata üretir."""
    if str(tip or "").upper() != "OK":
        raise MailHatasi(hata_mesaji)


def imap_yeteneklerini_ayristir(capability_sonucu):
    """IMAP CAPABILITY yanıtını büyük harfli yetenek kümesine çevirir."""
    yetenekler = set()
    try:
        for parca in capability_sonucu or []:
            if isinstance(parca, tuple):
                parcaciklar = []
                for oge in parca:
                    if isinstance(oge, bytes):
                        parcaciklar.append(oge.decode("ascii", errors="ignore"))
                    else:
                        parcaciklar.append(str(oge or ""))
                metin = " ".join(parcaciklar)
            elif isinstance(parca, bytes):
                metin = parca.decode("ascii", errors="ignore")
            else:
                metin = str(parca or "")
            metin = metin.replace("* CAPABILITY", " ")
            for oge in metin.split():
                oge = oge.strip().upper()
                if oge and oge not in ("CAPABILITY", "OK"):
                    yetenekler.add(oge)
    except Exception as e:
        hata_kaydet("IMAP yetenekleri ayrıştırılamadı.", e)
    return yetenekler


def imap_yeteneklerini_al(imap):
    """Sunucunun IMAP yeteneklerini güvenli biçimde döndürür."""
    tip, veri = imap.capability()
    imap_ok_mu(tip, _("IMAP sunucu yetenekleri alınamadı."))
    return imap_yeteneklerini_ayristir(veri)


def imap_gmail_etiket_destegini_dogrula(imap):
    """Gmail X-GM-LABELS desteği yoksa güvenli taşıma/silme işlemlerini durdurur."""
    yetenekler = imap_yeteneklerini_al(imap)
    if "X-GM-EXT-1" not in yetenekler:
        raise MailHatasi(
            _("Gmail etiket desteği algılanamadı. Güvenli taşıma, arşivleme veya Çöp Kutusuna taşıma işlemi yapılamadı. "
            "Lütfen bağlantıyı denetleyin ve hesabın Gmail IMAP desteğini denetleyin.")
        )
    return True


def uid_kumesi_hazirla(ids, bos_hata_mesaji="İşlem yapılacak e-posta bulunamadı."):
    """IMAP UID listesini yalnızca sayısal değerlerden oluşan güvenli kümeye çevirir."""
    uidler = []
    gorulen = set()
    for uid in ids or []:
        uid = str(uid or "").strip()
        if not uid:
            continue
        if not uid.isdigit():
            raise MailHatasi(_("Geçersiz e-posta kimliği algılandı. İşlem güvenlik nedeniyle durduruldu."))
        if uid not in gorulen:
            uidler.append(uid)
            gorulen.add(uid)
    if not uidler:
        raise MailHatasi(bos_hata_mesaji)
    return ",".join(uidler)


def imap_gmail_etiket_store(imap, uidler, islem, etiket, hata_mesaji):
    """Gmail X-GM-LABELS ile seçili UID'lere etiket ekler veya etiketi kaldırır."""
    uidler = str(uidler or "").strip()
    etiket = str(etiket or "").strip()
    if not uidler:
        raise MailHatasi(_("İşlem yapılacak e-posta bulunamadı."))
    if not etiket:
        return False
    if islem not in ("+", "-"):
        raise MailHatasi(_("Geçersiz Gmail etiket işlemi."))
    tip, _veri = imap.uid("STORE", uidler, f"{islem}X-GM-LABELS", f"({etiket})")
    imap_ok_mu(tip, hata_mesaji)
    return True


def imap_uidleri_kaynak_klasorden_cikar(imap, uidler, hata_mesaji="E-postalar kaynak klasörden kaldırılamadı."):
    """Seçili UID'leri yalnızca seçili kaynak klasörden çıkarır.

    Gmail'de özel klasörler etiket gibi çalışır. X-GM-LABELS ile hedef etiketi
    ekledikten sonra seçili kaynak klasörde UID EXPUNGE kullanmak, genel EXPUNGE
    yerine yalnızca belirtilen iletileri kaynak görünümden kaldırır. Bu işlev
    Çöp Kutusu, Tüm Postalar ve Taslaklar için çağrılmamalıdır.
    """
    uidler = str(uidler or "").strip()
    if not uidler:
        raise MailHatasi(_("Kaynak klasörden kaldırılacak e-posta bulunamadı."))
    tip, _veri = imap.uid("STORE", uidler, "+FLAGS.SILENT", "(\\Deleted)")
    imap_ok_mu(tip, _("E-postalar kaynak klasörden kaldırılmak üzere işaretlenemedi."))
    tip, _veri = imap.uid("EXPUNGE", uidler)
    if tip != "OK":
        try:
            imap.uid("STORE", uidler, "-FLAGS.SILENT", "(\\Deleted)")
        except Exception as e:
            hata_kaydet("Kaynak klasörden kaldırma başarısızlığı sonrası Deleted bayrağı geri alınamadı.", e)
        raise MailHatasi(hata_mesaji)
    return True


def imap_uidleri_kalici_sil(imap, uidler, hata_mesaji="E-posta kalıcı olarak silinemedi."):
    """Seçili UID'leri güvenli biçimde kalıcı siler; toplu EXPUNGE yedeğine düşmez."""
    uidler = str(uidler or "").strip()
    if not uidler:
        raise MailHatasi(_("Silinecek e-posta bulunamadı."))
    tip, _veri = imap.uid("STORE", uidler, "+FLAGS.SILENT", "(\\Deleted)")
    imap_ok_mu(tip, _("E-posta kalıcı silme için işaretlenemedi."))
    tip, _veri = imap.uid("EXPUNGE", uidler)
    if tip != "OK":
        try:
            imap.uid("STORE", uidler, "-FLAGS.SILENT", "(\\Deleted)")
        except Exception as e:
            hata_kaydet("Kalıcı silme başarısızlığı sonrası Deleted bayrağı geri alınamadı.", e)
        raise MailHatasi(hata_mesaji)
    return True


def imap_fetch_metin_satirlari(fetch_sonucu):
    """IMAP FETCH sonucundaki kısa metin yanıtlarını ayrıştırılabilir satırlara çevirir."""
    satirlar = []
    for parca in fetch_sonucu or []:
        ogeler = parca if isinstance(parca, tuple) else (parca,)
        for oge in ogeler:
            if isinstance(oge, bytes):
                satirlar.append(oge.decode("ascii", errors="ignore"))
            elif oge is not None:
                satirlar.append(str(oge))
    return satirlar


def imap_x_gm_msgid_haritasi_al(imap, uidler):
    """Gmail X-GM-MSGID değerlerini UID bazında döndürür."""
    uid_listesi = [str(uid).strip() for uid in uidler or [] if str(uid).strip()]
    if not uid_listesi:
        raise MailHatasi(_("Kalıcı silinecek e-posta bulunamadı."))

    sonuc = {}
    for uid_parcasi in uid_listesini_parcala(uid_listesi, 50):
        uid_kumesi = uid_kumesi_hazirla(uid_parcasi, _("Kalıcı silinecek e-posta bulunamadı."))
        tip, veri = imap.uid("FETCH", uid_kumesi, "(X-GM-MSGID)")
        imap_ok_mu(tip, _("E-postaların Gmail ileti kimlikleri alınamadı."))
        for satir in imap_fetch_metin_satirlari(veri):
            uid_eslesme = re.search(r"\bUID\s+(\d+)\b", satir, flags=re.IGNORECASE)
            mesaj_eslesme = re.search(r"\bX-GM-MSGID\s+(\d+)\b", satir, flags=re.IGNORECASE)
            if uid_eslesme and mesaj_eslesme:
                sonuc[uid_eslesme.group(1)] = mesaj_eslesme.group(1)

    eksikler = [uid for uid in uid_listesi if uid not in sonuc]
    if eksikler:
        raise MailHatasi(_("E-postaların Gmail ileti kimliği doğrulanamadı. Kalıcı silme güvenlik nedeniyle durduruldu."))
    return sonuc


def imap_uid_search_sonucu_uidleri_al(search_sonucu):
    """UID SEARCH yanıtındaki UID değerlerini döndürür."""
    uidler = []
    gorulen = set()
    for satir in imap_fetch_metin_satirlari(search_sonucu):
        eslesme = re.search(r"\bSEARCH\b(.*)$", satir, flags=re.IGNORECASE)
        if not eslesme:
            for uid in re.findall(r"\b\d+\b", satir):
                if uid not in gorulen:
                    uidler.append(uid)
                    gorulen.add(uid)
            continue
        for uid in re.findall(r"\b\d+\b", eslesme.group(1)):
            if uid not in gorulen:
                uidler.append(uid)
                gorulen.add(uid)
    return uidler


def imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru):
    """X-GM-MSGID değerlerini Çöp Kutusundaki UID değerlerine çevirir."""
    tip, _veri = imap.select(cop_klasoru, readonly=False)
    imap_ok_mu(tip, _("Çöp Kutusu kalıcı silme için açılamadı."))

    uidler = []
    bulunan_msgidler = set()
    for msgid in msgidleri or []:
        msgid = str(msgid or "").strip()
        if not msgid.isdigit():
            continue
        tip, veri = imap.uid("SEARCH", "X-GM-MSGID", msgid)
        imap_ok_mu(tip, _("E-posta Çöp Kutusunda kalıcı silme için bulunamadı."))
        bulunan_uidler = imap_uid_search_sonucu_uidleri_al(veri)
        if bulunan_uidler:
            bulunan_msgidler.add(msgid)
            uidler.extend(bulunan_uidler)

    beklenen_msgidler = {str(msgid).strip() for msgid in msgidleri or [] if str(msgid).strip().isdigit()}
    if not uidler or bulunan_msgidler != beklenen_msgidler:
        raise MailHatasi(_("E-posta Çöp Kutusunda doğrulanamadı. Kalıcı silme güvenlik nedeniyle tamamlanmadı."))
    return uidler


def imap_gmail_msgidleri_kalici_sil(imap, msgidleri, cop_klasoru, hata_mesaji="E-posta kalıcı olarak silinemedi."):
    """Gmail ileti kimliklerini Çöp Kutusu üzerinden kalıcı olarak siler."""
    try:
        cop_uidleri = imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru)
    except MailHatasi:
        # Gmail etiketi yeni eklendiyse Çöp Kutusu görünümünün aynı oturumda güncellenmesi kısa gecikebilir.
        time.sleep(0.5)
        cop_uidleri = imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru)

    uid_kumesi = uid_kumesi_hazirla(cop_uidleri, "Kalıcı silinecek e-posta Çöp Kutusunda bulunamadı.")
    return imap_uidleri_kalici_sil(imap, uid_kumesi, hata_mesaji)


def uidleri_ayristir(search_sonucu):
    uidler = []
    try:
        for parca in search_sonucu or []:
            if isinstance(parca, tuple):
                continue
            if isinstance(parca, bytes):
                metin = parca.decode("ascii", errors="ignore")
            else:
                metin = str(parca)
            metin = metin.strip()
            if not metin:
                continue
            bolumler = metin.split()
            if len(bolumler) >= 2 and bolumler[0] == "*" and bolumler[1].upper() == "SEARCH":
                adaylar = bolumler[2:]
            else:
                adaylar = bolumler
            for aday in adaylar:
                if aday.isdigit() and aday not in uidler:
                    uidler.append(aday)
    except Exception as e:
        hata_kaydet("UID listesi ayrıştırılamadı.", e)
    return uidler


def imap_status_sayilarini_ayristir(status_sonucu):
    """IMAP STATUS yanıtından MESSAGES ve UNSEEN sayılarını çıkarır."""
    sayilar = {}
    try:
        for parca in status_sonucu or []:
            if isinstance(parca, tuple):
                parca = b" ".join(oge for oge in parca if isinstance(oge, bytes))
            if isinstance(parca, bytes):
                metin = parca.decode("utf-8", errors="replace")
            else:
                metin = str(parca or "")
            eslesme = re.search(r"\(([^()]*)\)", metin)
            if not eslesme:
                continue
            bolumler = eslesme.group(1).split()
            i = 0
            while i + 1 < len(bolumler):
                anahtar = bolumler[i].upper()
                deger = bolumler[i + 1]
                if anahtar in ("MESSAGES", "UNSEEN") and str(deger).isdigit():
                    sayilar[anahtar.lower()] = int(deger)
                i += 2
    except Exception as e:
        hata_kaydet("IMAP STATUS yanıtı ayrıştırılamadı.", e)
    return sayilar


def fetch_sonuclarini_uidlere_ayir(fetch_sonucu):
    """Toplu IMAP FETCH yanıtını UID değerine göre parçalar.

    imaplib, her ileti için çoğunlukla (başlık, içerik) biçiminde tuple döndürür.
    Başlık bölümündeki UID değeri korunursa, tek ağ isteğiyle gelen sonuçlar
    özgün UID sırasına göre güvenle eşleştirilebilir.
    """
    uid_haritasi = {}
    try:
        for parca in fetch_sonucu or []:
            if not isinstance(parca, tuple) or not parca:
                continue
            baslik = parca[0]
            if isinstance(baslik, bytes):
                baslik_bytes = baslik
            else:
                baslik_bytes = str(baslik or "").encode("ascii", errors="ignore")
            eslesme = re.search(br"\bUID\s+(\d+)\b", baslik_bytes, flags=re.IGNORECASE)
            if not eslesme:
                continue
            uid = eslesme.group(1).decode("ascii", errors="ignore")
            uid_haritasi.setdefault(uid, []).append(parca)
    except Exception as e:
        hata_kaydet("Toplu IMAP FETCH yanıtı UID değerlerine ayrılamadı.", e)
    return uid_haritasi


def uid_listesini_parcala(uidler, parca_boyutu=50):
    """Uzun UID listelerini IMAP komut satırını şişirmeyecek güvenli parçalara böler."""
    uidler = [str(uid) for uid in uidler or [] if str(uid).strip()]
    parca_boyutu = max(1, int(parca_boyutu or 50))
    for baslangic in range(0, len(uidler), parca_boyutu):
        yield uidler[baslangic:baslangic + parca_boyutu]


def imap_toplu_uid_fetch(imap, uidler, fetch_komutu, parca_boyutu=50):
    """Birden fazla UID için FETCH komutunu parçalı toplu isteklerle çalıştırır."""
    tum_sonuclar = {}
    if not uidler:
        return tum_sonuclar
    for uid_parcasi in uid_listesini_parcala(uidler, parca_boyutu):
        uid_kumesi = ",".join(uid_parcasi)
        tip, veri = imap.uid("FETCH", uid_kumesi, fetch_komutu)
        if tip != "OK":
            hata_kaydet(f"Toplu IMAP FETCH başarısız oldu: {uid_kumesi}")
            continue
        tum_sonuclar.update(fetch_sonuclarini_uidlere_ayir(veri))
    return tum_sonuclar


def imap_uidvalidity_ayristir(select_sonucu):
    """IMAP SELECT/EXAMINE yanıtından UIDVALIDITY değerini çıkarır."""
    try:
        for parca in select_sonucu or []:
            if isinstance(parca, tuple):
                metin = b" ".join(oge for oge in parca if isinstance(oge, bytes)).decode("utf-8", errors="replace")
            elif isinstance(parca, bytes):
                metin = parca.decode("utf-8", errors="replace")
            else:
                metin = str(parca or "")
            eslesme = re.search(r"\bUIDVALIDITY\s+(\d+)\b", metin, flags=re.IGNORECASE)
            if eslesme:
                return int(eslesme.group(1))
            if metin.strip().isdigit():
                return int(metin.strip())
    except Exception as e:
        hata_kaydet("IMAP UIDVALIDITY değeri ayrıştırılamadı.", e)
    return 0


def imap_uidvalidity_al(imap):
    """Standart imaplib oturumundan seçili klasörün UIDVALIDITY değerini alır."""
    try:
        _kod, veri = imap.response("UIDVALIDITY")
        return imap_uidvalidity_ayristir(veri)
    except Exception as e:
        hata_kaydet("IMAP UIDVALIDITY değeri alınamadı.", e)
        return 0


def imap_eposta_boyutunu_denetle(imap, uid, azami_boyut, islem_adi="E-posta"):
    """Tam gövde indirilmeden önce RFC822.SIZE değerini güvenli sınırla karşılaştırır."""
    uid = str(uid or "").strip()
    if not uid.isdigit():
        raise MailHatasi(_("Geçersiz e-posta kimliği algılandı."))
    try:
        azami_boyut = int(azami_boyut)
    except (TypeError, ValueError) as e:
        raise MailHatasi(_("E-posta boyut sınırı geçersiz.")) from e
    if azami_boyut <= 0:
        raise MailHatasi(_("E-posta boyut sınırı geçersiz."))

    tip, veri = imap.uid("FETCH", uid, "(RFC822.SIZE)")
    imap_ok_mu(tip, _('{0} boyutu alınamadı.').format(islem_adi))
    for satir in imap_fetch_metin_satirlari(veri):
        eslesme = re.search(r"\bRFC822\.SIZE\s+(\d+)\b", satir, flags=re.IGNORECASE)
        if not eslesme:
            continue
        boyut = int(eslesme.group(1))
        if boyut > azami_boyut:
            sinir_mb = azami_boyut / (1024 * 1024)
            raise MailHatasi(
                _('{0} çok büyük. Bu işlem için en çok {1:.1f} MB boyutunda e-posta işlenebilir. E-postayı Gmail web arayüzünden veya başka bir posta istemcisinden açmayı deneyin.').format(islem_adi, sinir_mb)
            )
        return boyut
    raise MailHatasi(_('{0} boyutu doğrulanamadı. İşlem güvenlik nedeniyle durduruldu.').format(islem_adi))
