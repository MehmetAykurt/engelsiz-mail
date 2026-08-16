# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import base64
import re

from .errors import MailHatasi
from .logger import hata_kaydet

SISTEM_KLASORLERI = [
    "Gelen Kutusu",
    "Tüm Postalar",
    "Gönderilen E-postalar",
    "Taslaklar",
    "Çöp Kutusu",
    "Spam",
]

VARSAYILAN_KLASOR_HARITASI = {
    "Gelen Kutusu": "INBOX",
    "Tüm Postalar": '"[Gmail]/All Mail"',
    "Gönderilen E-postalar": '"[Gmail]/Sent Mail"',
    "Taslaklar": '"[Gmail]/Drafts"',
    "Çöp Kutusu": '"[Gmail]/Trash"',
    "Spam": '"[Gmail]/Spam"',
}


def klasor_gorunen_adi(kategori_adi):
    """İç sistem klasörü anahtarını yalnız görünüm katmanında yerelleştirir."""
    ad = str(kategori_adi or "").strip()
    return {
        "Gelen Kutusu": _("Gelen Kutusu"),
        "Tüm Postalar": _("Tüm Postalar"),
        "Gönderilen E-postalar": _("Gönderilen E-postalar"),
        "Taslaklar": _("Taslaklar"),
        "Çöp Kutusu": _("Çöp Kutusu"),
        "Spam": _("Spam"),
    }.get(ad, ad)


def encode_mutf7(metin):
    if not metin:
        return ""
    sonuc = []
    ascii_olmayan = []

    def bosalt():
        if ascii_olmayan:
            veri = "".join(ascii_olmayan).encode("utf-16-be")
            kod = base64.b64encode(veri).decode("ascii").replace("/", ",").rstrip("=")
            sonuc.append("&" + kod + "-")
            ascii_olmayan.clear()

    for karakter in metin:
        if karakter == "&":
            bosalt()
            sonuc.append("&-")
        elif 0x20 <= ord(karakter) <= 0x7E:
            bosalt()
            sonuc.append(karakter)
        else:
            ascii_olmayan.append(karakter)
    bosalt()
    return "".join(sonuc)


def decode_mutf7(metin):
    if not metin or "&" not in metin:
        return metin
    sonuc = []
    parcalar = metin.split("&")
    sonuc.append(parcalar[0])
    for parca in parcalar[1:]:
        if "-" in parca:
            kod, kalan = parca.split("-", 1)
            if not kod:
                sonuc.append("&" + kalan)
            else:
                b64 = kod.replace(",", "/")
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                try:
                    sonuc.append(base64.b64decode(b64).decode("utf-16-be") + kalan)
                except Exception:
                    sonuc.append("&" + parca)
        else:
            sonuc.append("&" + parca)
    return "".join(sonuc)


def imap_tirnakli_ham_ad(raw_ad):
    """LIST komutundan gelen ham IMAP klasör adını yeniden kodlamadan güvenle tırnaklar."""
    raw_ad = str(raw_ad or "").strip()
    if raw_ad.upper() == "INBOX":
        return "INBOX"
    if raw_ad.startswith('"') and raw_ad.endswith('"'):
        return raw_ad
    raw_ad = raw_ad.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{raw_ad}"'


def imap_klasor_adi_hazirla(klasor_adi):
    """Kullanıcının yazdığı görünen klasör adını IMAP klasör adına dönüştürür."""
    klasor_adi = str(klasor_adi or "").strip()
    if klasor_adi.upper() == "INBOX":
        return "INBOX"
    if klasor_adi.startswith('"') and klasor_adi.endswith('"'):
        return klasor_adi
    kodlu = encode_mutf7(klasor_adi)
    kodlu = kodlu.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{kodlu}"'


def arsiv_klasor_adini_dogrula(klasor_adi, mevcut_adlar=None, eski_ad=None):
    """Arşiv klasörü adını IMAP komutuna gitmeden önce güvenli kurallarla doğrular."""
    ad = str(klasor_adi or "").strip()
    if not ad:
        raise MailHatasi(_("Arşiv adı boş olamaz."))
    if len(ad) > 80:
        raise MailHatasi(_("Arşiv adı çok uzun. Lütfen en çok 80 karakterlik bir ad yazın."))
    if any(ord(karakter) < 32 for karakter in ad):
        raise MailHatasi(_("Arşiv adında satır sonu, sekme veya denetim karakteri bulunamaz."))
    if ad in (".", "..") or not ad.strip(" ."):
        raise MailHatasi(_("Lütfen harf veya rakam içeren geçerli bir arşiv adı yazın."))
    if "/" in ad or "\\" in ad:
        raise MailHatasi(_("Arşiv adında eğik çizgi veya ters eğik çizgi kullanılamaz."))
    if '"' in ad:
        raise MailHatasi(_("Arşiv adında çift tırnak kullanılamaz."))

    ad_kucuk = ad.lower()
    sistem_adlari = {str(oge).lower() for oge in SISTEM_KLASORLERI}
    sistem_adlari.update({"inbox", "[gmail]", "[google mail]"})
    if ad_kucuk in sistem_adlari or ad_kucuk.startswith("[gmail]") or ad_kucuk.startswith("[google mail]"):
        raise MailHatasi(_("Bu ad Gmail sistem klasörü için ayrılmıştır. Lütfen farklı bir arşiv adı yazın."))

    eski_kucuk = str(eski_ad or "").strip().lower()
    mevcut_kucuk = {str(oge or "").strip().lower() for oge in (mevcut_adlar or [])}
    mevcut_kucuk.discard(eski_kucuk)
    if ad_kucuk in mevcut_kucuk:
        raise MailHatasi(_("Bu adla bir arşiv klasörü zaten var."))
    return ad


def imap_liste_satiri_ayristir(satir):
    try:
        if isinstance(satir, bytes):
            satir = satir.decode("utf-8", errors="replace")
        satir = satir.strip()
        eslesme = re.match(r'^(?:\* LIST )?\((?P<flags>.*?)\) (?P<delim>NIL|".*?") (?P<name>.+)$', satir)
        if not eslesme:
            return None
        bayraklar = eslesme.group("flags").upper()
        ad = eslesme.group("name").strip()
        if ad.startswith('"') and ad.endswith('"'):
            ad = ad[1:-1]
            ad = ad.replace('\\"', '"').replace('\\\\', '\\')
        return bayraklar, ad, decode_mutf7(ad)
    except Exception as e:
        hata_kaydet("IMAP klasör satırı ayrıştırılamadı.", e)
        return None


def imap_klasor_haritasi_olustur(list_sonucu):
    """IMAP LIST çıktısından sistem ve özel klasörleri tanır."""
    yeni_harita = dict(VARSAYILAN_KLASOR_HARITASI)
    ozel_klasorler = []
    for satir in list_sonucu or []:
        sonuc = imap_liste_satiri_ayristir(satir)
        if not sonuc:
            continue
        bayraklar, imap_adi, gorunen_ad = sonuc
        imap_degeri = imap_tirnakli_ham_ad(imap_adi)
        if "\\SENT" in bayraklar:
            yeni_harita["Gönderilen E-postalar"] = imap_degeri
        elif "\\DRAFTS" in bayraklar:
            yeni_harita["Taslaklar"] = imap_degeri
        elif "\\TRASH" in bayraklar:
            yeni_harita["Çöp Kutusu"] = imap_degeri
        elif "\\JUNK" in bayraklar or "\\SPAM" in bayraklar:
            yeni_harita["Spam"] = imap_degeri
        elif "\\ALL" in bayraklar:
            yeni_harita["Tüm Postalar"] = imap_degeri
        elif imap_adi.upper() == "INBOX":
            yeni_harita["Gelen Kutusu"] = "INBOX"
        elif "\\NOSELECT" not in bayraklar and "[GMAIL]" not in imap_adi.upper():
            if gorunen_ad not in ozel_klasorler and gorunen_ad not in SISTEM_KLASORLERI:
                ozel_klasorler.append(gorunen_ad)
                yeni_harita[gorunen_ad] = imap_degeri
    return yeni_harita, ozel_klasorler


def taslak_klasor_adaylarini_temizle(adaylar=None):
    temiz = []

    def ekle(deger):
        deger = str(deger or "").strip()
        if deger and deger not in temiz:
            temiz.append(deger)

    for aday in adaylar or []:
        ekle(aday)
    ekle(VARSAYILAN_KLASOR_HARITASI.get("Taslaklar"))
    ekle('"[Gmail]/Drafts"')
    ekle('"[Google Mail]/Drafts"')
    ekle(imap_klasor_adi_hazirla("Taslaklar"))
    ekle(imap_klasor_adi_hazirla("Drafts"))
    return temiz
