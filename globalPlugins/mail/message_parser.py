# -*- coding: utf-8 -*-

import base64
import email
import email.utils
from email import policy as email_policy
import quopri
import re

from .logger import hata_kaydet
from .text_utils import (
    eposta_basligi_tek_satir_yap,
    guvenli_coz,
    html_icerik_gibi_gorunuyor_mu,
    html_temizle,
    metin_kodlama_bozulmasini_duzelt,
)
from .validators import eposta_adresi_gecerli_mi

ONIZLEME_KARAKTER_SINIRI = 280


RE_GRUP_ARACI_GONDEREN = re.compile(
    r"\s+via\s+(groups\.io|google\s+groups|groups\.google\.com)\s*$",
    re.IGNORECASE,
)
RE_GROUPS_IO_DONUSTURULMUS_ADRES = re.compile(
    r"^(?P<yerel>[^@\s<>]+)=(?P<alan>[^@\s<>]+\.[^@\s<>]+)@groups\.io$",
    re.IGNORECASE,
)


def grup_araci_gonderen_bilgisini_temizle(metin):
    """Grup e-postalarında gönderen adındaki aracı servis bilgisini yalnızca görünüm için temizler."""
    metin = str(metin or "").strip()
    if not metin:
        return metin

    temiz = RE_GRUP_ARACI_GONDEREN.sub("", metin).strip()
    return temiz or metin


def grup_araci_adresini_temizle(adres):
    """Groups.io'nun dönüştürdüğü user=domain.com@groups.io adresini görünümde düzeltir."""
    adres = str(adres or "").strip()
    eslesme = RE_GROUPS_IO_DONUSTURULMUS_ADRES.match(adres)
    if eslesme:
        return f"{eslesme.group('yerel')}@{eslesme.group('alan')}"
    return adres




def gonderen_gosterimini_al(deger, varsayilan="Bilinmiyor"):
    """From başlığından görünen adı öncelikli, yoksa e-posta adresini döndürür."""
    kaynak = guvenli_coz(deger or "").strip()
    if not kaynak:
        return varsayilan
    ad, adres = email.utils.parseaddr(kaynak)
    ad = grup_araci_gonderen_bilgisini_temizle(guvenli_coz(ad).strip())
    adres = grup_araci_adresini_temizle(adres)
    return ad or adres or kaynak or varsayilan

def adres_basligini_duzenle(deger):
    """Taslaklardaki alıcı başlıklarını tek satırlık düzenlenebilir metne çevirir."""
    adresler = []
    gorulen = set()
    kaynak = str(deger or "").replace(";", ",")
    kaynak = eposta_basligi_tek_satir_yap(kaynak)
    for ad, adres in email.utils.getaddresses([kaynak]):
        adres = grup_araci_adresini_temizle(adres)
        ad = guvenli_coz(ad).strip()
        if not eposta_adresi_gecerli_mi(adres):
            continue
        anahtar = adres.lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if ad:
            # formataddr Unicode görünen adı yeniden =?utf-8?...?= biçimine
            # kodlar. Bu işlev arayüz metni ürettiği için adı okunur tut.
            ad = re.sub(r"[\r\n]+", " ", ad).strip()
            if re.search(r'[,;"<>]', ad):
                ad = '"' + ad.replace("\\", "\\\\").replace('"', '\\"') + '"'
            bicimli = f"{ad} <{adres}>"
        else:
            bicimli = adres
        adresler.append(bicimli)
    return ", ".join(adresler)


def ad_ve_adresi_goster(ad, adres, varsayilan=""):
    """Görünen adı ve adresi ekran okuyucu için `Ad - adres` biçimine getirir."""
    ad = guvenli_coz(ad).strip()
    adres = grup_araci_adresini_temizle(adres)
    if adres:
        # Bazı göndericiler görünen ad alanına adresi de ekler. Aynı adresi
        # iki kez okutma; geride kalan virgül ve tırnakları da temizle.
        ad = re.sub(re.escape(adres), "", ad, flags=re.IGNORECASE)
        ad = ad.strip(" \t,;-\"'<>())(")
    if ad and adres and ad.casefold() != adres.casefold():
        return f"{ad} - {adres}"
    return adres or ad or str(varsayilan or "")


def adres_basligini_gosterime_hazirla(
    deger, varsayilan="", hesap_epostasi="", hesap_gorunen_adi=""
):
    """Bir veya daha çok adresi kodlama kalıntısı olmadan okunur biçime getirir."""
    kaynak = eposta_basligi_tek_satir_yap(str(deger or "").replace(";", ","))
    hesap_epostasi = str(hesap_epostasi or "").strip().casefold()
    hesap_gorunen_adi = guvenli_coz(hesap_gorunen_adi).strip()
    sonuc = []
    gorulen = set()
    for ad, adres in email.utils.getaddresses([kaynak]):
        adres = grup_araci_adresini_temizle(adres)
        if not eposta_adresi_gecerli_mi(adres):
            continue
        anahtar = adres.casefold()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if hesap_gorunen_adi and adres.casefold() == hesap_epostasi:
            ad = hesap_gorunen_adi
        sonuc.append(ad_ve_adresi_goster(ad, adres))
    return "; ".join(sonuc) or str(varsayilan or "")


def gonderen_basligini_gosterime_hazirla(deger, varsayilan="Bilinmiyor"):
    """From başlığını aracı grup adını temizleyerek `Ad - adres` biçiminde döndürür."""
    kaynak = guvenli_coz(deger or "").strip()
    ad, adres = email.utils.parseaddr(kaynak)
    ad = grup_araci_gonderen_bilgisini_temizle(guvenli_coz(ad))
    adres = grup_araci_adresini_temizle(adres)
    return ad_ve_adresi_goster(ad, adres, kaynak or varsayilan)


def yanit_adresini_bul(mesaj):
    """Yanıt penceresi için doğru alıcı başlığını seçer. Reply-To varsa önceliklidir."""
    try:
        for baslik in ("Reply-To", "From"):
            deger = adres_basligini_duzenle(mesaj.get(baslik, ""))
            if deger:
                return deger
        kimden = guvenli_coz(mesaj.get("From", ""))
        _ad, adres = email.utils.parseaddr(kimden)
        return adres or kimden
    except Exception as e:
        hata_kaydet("Yanıt adresi belirlenemedi.", e)
        return ""


def ham_mesaj_verisi_al(fetch_sonucu):
    ham = b""
    for parca in fetch_sonucu or []:
        if isinstance(parca, tuple) and len(parca) >= 2 and isinstance(parca[1], bytes):
            ham += parca[1]
    return ham


def fetch_sonucunda_ek_var_mi(fetch_sonucu):
    """FETCH yanıtındaki BODYSTRUCTURE bilgisinden ek varlığını güvenli biçimde tahmin eder."""
    try:
        parcalar = []
        for parca in fetch_sonucu or []:
            if isinstance(parca, tuple):
                for oge in parca:
                    if isinstance(oge, bytes):
                        parcalar.append(oge)
                    elif oge is not None:
                        parcalar.append(str(oge).encode("utf-8", errors="ignore"))
            elif isinstance(parca, bytes):
                parcalar.append(parca)
            elif parca is not None:
                parcalar.append(str(parca).encode("utf-8", errors="ignore"))
        ham = b" ".join(parcalar)
        if not ham:
            return False
        return bool(re.search(br"\b(ATTACHMENT|FILENAME)\b", ham, flags=re.IGNORECASE))
    except Exception as e:
        hata_kaydet("E-posta ek bilgisi çözümlenemedi.", e)
        return False


def seen_bayragi_var_mi(fetch_sonucu):
    try:
        for parca in fetch_sonucu or []:
            baslik = parca[0] if isinstance(parca, tuple) else parca
            if isinstance(baslik, bytes) and b"\\seen" in baslik.lower():
                return True
            if isinstance(baslik, str) and "\\seen" in baslik.lower():
                return True
    except Exception:
        pass
    return False


def yanit_basliklari_hazirla(mesaj_verisi):
    message_id = eposta_basligi_tek_satir_yap(mesaj_verisi.get("message_id", ""))
    onceki_references = eposta_basligi_tek_satir_yap(mesaj_verisi.get("references", ""))

    if not message_id:
        return {}

    if onceki_references:
        parcalar = onceki_references.split()
        if message_id not in parcalar:
            references = onceki_references + " " + message_id
        else:
            references = onceki_references
    else:
        references = message_id

    return {
        "In-Reply-To": message_id,
        "References": references,
    }


def onizleme_metnini_kisalt(metin, sinir=ONIZLEME_KARAKTER_SINIRI):
    """Liste içinde okunacak ön izleme metnini kısa ve tek satırlık hâle getirir."""
    metin = str(metin or "")
    metin = metin.replace("\x0b", " ")
    metin = re.sub(r"\s+", " ", metin).strip()
    if not metin:
        return ""
    if len(metin) > sinir:
        return metin[:sinir].rstrip() + "..."
    return metin



def quoted_printable_gibi_gorunuyor_mu(metin):
    """Metinde quoted-printable izleri olup olmadığını denetler."""
    metin = str(metin or "")
    return bool(re.search(r"=[0-9A-Fa-f]{2}", metin) or "=\r\n" in metin or "=\n" in metin)



def onizleme_karakter_kumesi_bul(ham_veri):
    """Kısmi gövdeden veya başlıktan karakter kümesini tahmin eder."""
    try:
        baslik_metni = ham_veri.decode("ascii", errors="ignore")
        eslesme = re.search(r'charset=["\']?([^;"\'>\s]+)', baslik_metni, flags=re.IGNORECASE)
        if eslesme:
            return eslesme.group(1).strip()
    except Exception:
        pass
    return "utf-8"



def onizleme_verisini_metin_yap(veri, karakter_kumesi="utf-8"):
    """Ham ön izleme verisini Türkçe karakterleri koruyarak metne çevirir.

    Önce hatasız çözen kodlamalar denenir. Bu olmazsa bozuk karakteri en az
    üreten sonuç seçilir. Böylece başlıksız UTF-8 Türkçe metinler, latin-1
    gibi kodlamalara erken düşüp bozulmaz.
    """
    if isinstance(veri, str):
        return veri

    denenecekler = []
    karakter_kumesi = str(karakter_kumesi or "").strip()
    if karakter_kumesi:
        denenecekler.append(karakter_kumesi)
    denenecekler.extend(["utf-8", "iso-8859-9", "windows-1254", "latin-1"])

    benzersiz = []
    for kodlama in denenecekler:
        kodlama = str(kodlama or "").strip()
        if kodlama and kodlama.lower() not in [k.lower() for k in benzersiz]:
            benzersiz.append(kodlama)

    yedekler = []
    for kodlama in benzersiz:
        try:
            metin = veri.decode(kodlama, errors="strict")
            if metin:
                return metin
        except Exception:
            pass
        try:
            metin = veri.decode(kodlama, errors="replace")
            if metin:
                yedekler.append((metin.count("\ufffd"), kodlama.lower() not in ("utf-8", "utf8"), metin))
        except Exception:
            continue

    if yedekler:
        yedekler.sort(key=lambda oge: (oge[0], oge[1]))
        return yedekler[0][2]
    return veri.decode("utf-8", errors="replace")



def onizleme_metnini_temizle(metin):
    """Ön izleme adayından MIME ve HTML kalıntılarını temizler."""
    metin = metin_kodlama_bozulmasini_duzelt(str(metin or ""))

    # BODY.PEEK[TEXT] çoğu zaman doğrudan gövde döndürür.
    # Bu yüzden ilk boş satıra kadar silme yapılmaz; aksi hâlde e-postanın ilk paragrafı kaybolabilir.
    satirlar = []
    for satir in metin.splitlines():
        temiz_satir = satir.strip()
        if re.match(r"(?i)^(Content-|MIME-Version:|charset=|boundary=)", temiz_satir):
            continue
        if re.match(r"(?i)^--[A-Za-z0-9=_.,+/\-]+", temiz_satir):
            continue
        satirlar.append(satir)

    metin = "\n".join(satirlar)
    if "<" in metin and ">" in metin:
        metin = html_temizle(metin)
    metin = metin_kodlama_bozulmasini_duzelt(metin)
    return onizleme_metnini_kisalt(metin)



def onizleme_bozuk_karakter_orani(metin):
    """Çözme sonucu oluşan bozuk karakter oranını hesaplar."""
    metin = str(metin or "")
    if not metin:
        return 0.0
    return metin.count("\ufffd") / max(1, len(metin))



def onizleme_metin_guvenli_mi(metin):
    """Ön izleme metninin kullanıcıya ham kodlama olarak okutulup okutulmayacağını denetler."""
    metin = str(metin or "").strip()
    if not metin:
        return False
    if onizleme_bozuk_karakter_orani(metin) > 0.02:
        return False
    if quoted_printable_gibi_gorunuyor_mu(metin):
        return False
    if base64_gibi_gorunuyor_mu(metin):
        return False

    temiz = re.sub(r"\s+", "", metin)
    if len(temiz) >= 32 and re.fullmatch(r"[A-Za-z0-9+/=]+", temiz):
        # Çözme sezgisi tam emin olamasa bile ham Base64 benzeri metni kullanıcıya okutma.
        base64_isareti_var = any(karakter in temiz for karakter in "+/=")
        cok_satirli_base64 = len([satir for satir in metin.splitlines() if satir.strip()]) >= 2
        if base64_isareti_var or cok_satirli_base64:
            return False
    return True



def base64_gibi_gorunuyor_mu(metin):
    """Ön izleme adayının Base64 kodlu gövde olup olmadığını güvenli biçimde tahmin eder."""
    metin = str(metin or "").strip()
    if not metin:
        return False

    satirlar = [satir.strip() for satir in metin.splitlines() if satir.strip()]
    temiz = re.sub(r"\s+", "", metin)
    if len(temiz) < 8:
        return False

    if not re.fullmatch(r"[A-Za-z0-9+/=]+", temiz):
        return False

    # Normal düz metin yalnızca harf ve rakamlardan oluştuğunda da yanlışlıkla
    # Base64 gibi görünebilir. Başlık bilgisi yokken sezgisel çözmeyi ancak
    # güçlü Base64 işaretleri varsa uygula. Gerçek Content-Transfer-Encoding:
    # base64 başlığı bulunan parçalarda çözme zaten onizleme_transfer_coz ile yapılır.
    base64_isareti_var = any(karakter in temiz for karakter in "+/=")
    cok_satirli_base64 = len(satirlar) >= 2 and all(len(satir) % 4 == 0 for satir in satirlar[:4])
    if not base64_isareti_var and not cok_satirli_base64:
        return False

    if len(temiz) % 4 == 1:
        return False
    if len(temiz) % 4 != 0:
        temiz += "=" * ((4 - len(temiz) % 4) % 4)

    try:
        cozulmus = base64.b64decode(temiz.encode("ascii"), validate=False)
    except Exception:
        return False

    if not cozulmus or len(cozulmus) < 4:
        return False

    metin_cozulmus = onizleme_verisini_metin_yap(cozulmus, "utf-8")
    if not metin_cozulmus.strip():
        return False
    if "\x00" in metin_cozulmus:
        return False
    if metin_cozulmus.count("\ufffd") / max(1, len(metin_cozulmus)) > 0.05:
        return False

    okunabilir = 0
    for karakter in metin_cozulmus[:500]:
        if karakter in "\t\r\n" or karakter.isprintable():
            okunabilir += 1
    return okunabilir / max(1, min(len(metin_cozulmus), 500)) > 0.90



def base64_onizleme_coz(metin, karakter_kumesi="utf-8"):
    """Base64 kodlu görünen ön izleme metnini çözer; uygun değilse boş döndürür."""
    metin = str(metin or "").strip()
    temiz = re.sub(r"\s+", "", metin)
    temiz = re.sub(r"[^A-Za-z0-9+/=]", "", temiz)
    if len(temiz) < 4:
        return ""

    # Kısmi alınan Base64 verilerinde son grup eksik olabilir.
    # Önce uygun dolgu ile dene; olmazsa en yakın dörtlü sınıra kırp.
    adaylar = []
    dolgu = temiz + ("=" * ((4 - len(temiz) % 4) % 4))
    adaylar.append(dolgu)
    kirpilmis = temiz[: len(temiz) - (len(temiz) % 4)]
    if kirpilmis and kirpilmis not in adaylar:
        adaylar.append(kirpilmis)

    for aday in adaylar:
        try:
            veri = base64.b64decode(aday.encode("ascii"), validate=False)
            metin = onizleme_verisini_metin_yap(veri, karakter_kumesi)
            if metin.strip():
                return metin
        except Exception:
            continue
    return ""



def onizleme_kodlamasini_coz(metin, karakter_kumesi="utf-8"):
    """Ön izleme metninde quoted-printable veya Base64 kodlaması varsa çözer."""
    metin = str(metin or "")

    if quoted_printable_gibi_gorunuyor_mu(metin):
        try:
            metin = onizleme_verisini_metin_yap(
                quopri.decodestring(metin.encode("utf-8", errors="replace")),
                karakter_kumesi,
            )
        except Exception:
            pass

    if base64_gibi_gorunuyor_mu(metin):
        cozulmus = base64_onizleme_coz(metin, karakter_kumesi)
        if cozulmus:
            metin = cozulmus

    return metin



def onizleme_mime_basliklarini_ayir(parca):
    """Kısmi MIME parçasını başlık ve gövde olarak ayırır."""
    if b"\r\n\r\n" in parca:
        return parca.split(b"\r\n\r\n", 1)
    if b"\n\n" in parca:
        return parca.split(b"\n\n", 1)
    return b"", parca



def onizleme_baslik_degeri_al(basliklar, ad):
    eslesme = re.search(r"(?im)^" + re.escape(ad) + r":\s*(.+)$", basliklar)
    if eslesme:
        return eslesme.group(1).strip()
    return ""



def onizleme_baslik_parametresi_al(baslik_degeri, parametre, varsayilan=""):
    eslesme = re.search(parametre + r'=["\']?([^;"\'>\s]+)', baslik_degeri, flags=re.IGNORECASE)
    if eslesme:
        return eslesme.group(1).strip()
    return varsayilan



def onizleme_transfer_coz(govde, transfer_kodlamasi, karakter_kumesi):
    """MIME parçasının gövdesini transfer kodlamasına göre çözer."""
    transfer_kodlamasi = str(transfer_kodlamasi or "").lower().strip()

    if transfer_kodlamasi == "base64":
        metin = govde.decode("ascii", errors="ignore")
        return base64_onizleme_coz(metin, karakter_kumesi)

    if transfer_kodlamasi in ("quoted-printable", "quotedprintable"):
        try:
            veri = quopri.decodestring(govde)
            return onizleme_verisini_metin_yap(veri, karakter_kumesi)
        except Exception:
            return ""

    try:
        return onizleme_verisini_metin_yap(govde, karakter_kumesi)
    except Exception:
        return ""



def onizleme_email_parca_metni_al(parca):
    """Python email paketinin çözdüğü bir MIME parçasından güvenli metin çıkarır."""
    try:
        if parca.is_multipart():
            return ""
        if str(parca.get_content_disposition() or "").lower() == "attachment":
            return ""
        if parca.get_filename():
            return ""

        icerik_turu = str(parca.get_content_type() or "").lower()
        if icerik_turu not in ("text/plain", "text/html"):
            return ""

        try:
            metin = parca.get_content()
        except Exception:
            payload = parca.get_payload(decode=True)
            if payload is None:
                payload = parca.get_payload()
                if isinstance(payload, str):
                    metin = payload
                else:
                    return ""
            else:
                karakter_kumesi = parca.get_content_charset() or "utf-8"
                metin = onizleme_verisini_metin_yap(payload, karakter_kumesi)

        if not isinstance(metin, str):
            metin = str(metin or "")

        karakter_kumesi = parca.get_content_charset() or onizleme_karakter_kumesi_bul(metin.encode("utf-8", errors="ignore"))
        transfer_basligi = str(parca.get("Content-Transfer-Encoding", "") or "").strip()
        # get_content() gerçek MIME başlığı varsa transfer kodlamasını zaten çözer.
        # Başlıksız BODY.PEEK kırpıklarında ise quoted-printable ham kalabilir.
        if not transfer_basligi:
            metin = onizleme_kodlamasini_coz(metin, karakter_kumesi)
        if icerik_turu == "text/html" or html_icerik_gibi_gorunuyor_mu(metin):
            metin = html_temizle(metin)
        return onizleme_metnini_temizle(metin)
    except Exception:
        return ""



def onizleme_email_mesajindan_metne(mesaj):
    """EmailMessage içinden önce text/plain, yoksa text/html ön izleme üretir."""
    try:
        parcalar = mesaj.walk() if mesaj.is_multipart() else [mesaj]
    except Exception:
        parcalar = [mesaj]

    duz_metin_adaylari = []
    html_adaylari = []
    for parca in parcalar:
        metin = onizleme_email_parca_metni_al(parca)
        if not metin or not onizleme_metin_guvenli_mi(metin):
            continue
        icerik_turu = str(parca.get_content_type() or "").lower()
        if icerik_turu == "text/plain":
            duz_metin_adaylari.append(metin)
        elif icerik_turu == "text/html":
            html_adaylari.append(metin)

    for aday in duz_metin_adaylari + html_adaylari:
        if aday:
            return onizleme_metnini_kisalt(aday)
    return ""



def onizleme_email_icin_sahte_baslik_ekle(ham_veri):
    """BODY.PEEK[TEXT] çıktısında dış Content-Type yoksa ilk MIME sınırından geçici başlık üretir."""
    try:
        ascii_metin = ham_veri.decode("ascii", errors="ignore")
    except Exception:
        return ham_veri

    eslesme = re.search(r"(?m)^--([A-Za-z0-9=_.,+/\-]+)", ascii_metin)
    if not eslesme:
        return ham_veri
    sinir = eslesme.group(1).strip()
    if not sinir:
        return ham_veri
    baslik = (
        'MIME-Version: 1.0\r\n'
        f'Content-Type: multipart/mixed; boundary="{sinir}"\r\n'
        '\r\n'
    )
    return baslik.encode("ascii", errors="ignore") + ham_veri



def onizleme_email_paketiyle_coz(ham_veri):
    """Ön izlemeyi önce Python email paketiyle MIME/encoding kurallarına göre çözmeye çalışır."""
    if not ham_veri:
        return ""

    denemeler = [ham_veri]
    sahte = onizleme_email_icin_sahte_baslik_ekle(ham_veri)
    if sahte != ham_veri:
        denemeler.insert(0, sahte)

    for veri in denemeler:
        try:
            mesaj = email.message_from_bytes(veri, policy=email_policy.default)
            onizleme = onizleme_email_mesajindan_metne(mesaj)
            if onizleme and onizleme_metin_guvenli_mi(onizleme):
                return onizleme
        except Exception:
            continue
    return ""



def onizleme_multipart_govde_coz(ham_veri, derinlik=0):
    """BODY.PEEK[TEXT] ile gelen multipart gövdeden ilk okunabilir text/plain veya text/html bölümünü çıkarır.

    Bazı iletilerde yapı iç içe olabilir:
    multipart/mixed -> multipart/alternative -> text/plain(base64).
    Bu nedenle multipart alt parçalarına sınırlı derinlikte özyinelemeli olarak iner.
    """
    if not ham_veri or derinlik > 4:
        return ""

    try:
        ascii_metin = ham_veri.decode("ascii", errors="ignore")
    except Exception:
        ascii_metin = ""

    eslesme = re.search(r"(?m)^--([A-Za-z0-9=_.,+/\-]+)", ascii_metin)
    if not eslesme:
        return ""

    sinir = eslesme.group(1).strip()
    ayirici = ("--" + sinir).encode("ascii", errors="ignore")
    parcalar = ham_veri.split(ayirici)

    adaylar = []
    for parca in parcalar[1:]:
        parca = parca.strip(b"\r\n")
        if not parca or parca.startswith(b"--"):
            continue

        baslik_baytlari, govde = onizleme_mime_basliklarini_ayir(parca)
        basliklar = baslik_baytlari.decode("ascii", errors="ignore")

        icerik_turu_basligi = onizleme_baslik_degeri_al(basliklar, "Content-Type")
        if not icerik_turu_basligi:
            # Başlıksız ama içinde boundary bulunan parçalarda yine bir alt deneme yapılabilir.
            alt_onizleme = onizleme_multipart_govde_coz(parca, derinlik + 1)
            if alt_onizleme:
                adaylar.append((2, alt_onizleme))
            continue

        icerik_turu = icerik_turu_basligi.split(";", 1)[0].strip().lower()
        if icerik_turu.startswith("multipart/"):
            alt_onizleme = onizleme_multipart_govde_coz(govde, derinlik + 1)
            if alt_onizleme:
                adaylar.append((2, alt_onizleme))
            continue

        if icerik_turu not in ("text/plain", "text/html"):
            continue

        karakter_kumesi = onizleme_baslik_parametresi_al(icerik_turu_basligi, "charset", "utf-8")
        transfer = onizleme_baslik_degeri_al(basliklar, "Content-Transfer-Encoding")
        cozulmus = onizleme_transfer_coz(govde, transfer, karakter_kumesi)

        if icerik_turu == "text/html":
            cozulmus = html_temizle(cozulmus)

        cozulmus = onizleme_kodlamasini_coz(cozulmus, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(cozulmus)
        if onizleme and onizleme_metin_guvenli_mi(onizleme):
            oncelik = 0 if icerik_turu == "text/plain" else 1
            adaylar.append((oncelik, onizleme))

    if not adaylar:
        return ""

    adaylar.sort(key=lambda oge: oge[0])
    return adaylar[0][1]
