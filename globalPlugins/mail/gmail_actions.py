# -*- coding: utf-8 -*-
# Engelsiz Mail - Gmail eylem yardımcıları

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

from .folders import VARSAYILAN_KLASOR_HARITASI, imap_klasor_adi_hazirla
from .imap_client import imap_gmail_etiket_store, imap_uidleri_kaynak_klasorden_cikar


def kategori_adini_klasorden_bul(klasor, klasor_haritasi, secili_kategori, aktif_klasor_degeri=None):
    """IMAP klasör değerinden kullanıcıya görünen kategori adını bulur."""
    klasor = str(klasor or "").strip()
    for ad, deger in klasor_haritasi.items():
        if str(deger) == klasor:
            return ad
    try:
        if aktif_klasor_degeri is not None and klasor == str(aktif_klasor_degeri):
            return secili_kategori
    except Exception:
        pass
    return ""


def gmail_etiket_ifadesi(kategori_adi=None, klasor=None, klasor_haritasi=None, secili_kategori="", aktif_klasor_degeri=None):
    """Kullanıcıya görünen klasörü Gmail X-GM-LABELS etiket ifadesine çevirir."""
    klasor_haritasi = klasor_haritasi or {}
    kategori_adi = str(kategori_adi or "").strip() or kategori_adini_klasorden_bul(
        klasor,
        klasor_haritasi,
        secili_kategori,
        aktif_klasor_degeri,
    )
    klasor = str(klasor or "").strip()

    if kategori_adi == "Gelen Kutusu" or klasor.upper() == "INBOX":
        return "\\Inbox"
    if kategori_adi == "Çöp Kutusu":
        return "\\Trash"
    if kategori_adi == "Spam":
        return "\\Spam"
    if kategori_adi == "Gönderilen E-postalar":
        return "\\Sent"
    if kategori_adi == "Taslaklar":
        return "\\Draft"
    if kategori_adi == "Tüm Postalar":
        return ""
    if kategori_adi:
        return imap_klasor_adi_hazirla(kategori_adi)
    return ""


def cop_klasoru_mu(klasor, klasor_haritasi):
    cop_klasoru = klasor_haritasi.get("Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"])
    return str(klasor) == str(cop_klasoru)


def tum_postalar_klasoru_mu(klasor, klasor_haritasi):
    tum_postalar = klasor_haritasi.get("Tüm Postalar", VARSAYILAN_KLASOR_HARITASI["Tüm Postalar"])
    return str(klasor) == str(tum_postalar)


def taslak_klasoru_mu(klasor, klasor_haritasi, secili_kategori=""):
    taslaklar = klasor_haritasi.get("Taslaklar", VARSAYILAN_KLASOR_HARITASI["Taslaklar"])
    return str(klasor) == str(taslaklar) or secili_kategori == "Taslaklar"


def spam_klasoru_mu(klasor, klasor_haritasi, secili_kategori=""):
    spam = klasor_haritasi.get("Spam", VARSAYILAN_KLASOR_HARITASI["Spam"])
    return str(klasor) == str(spam) or secili_kategori == "Spam"


def kaynak_etiketi_kaldirilabilir_mi(kaynak_klasor, klasor_haritasi, ozel_klasorler, kaynak_kategori=None, secili_kategori=""):
    """Kaynak klasörden güvenli biçimde etiket kaldırılıp kaldırılamayacağını belirler."""
    kaynak_kategori = str(kaynak_kategori or "").strip() or kategori_adini_klasorden_bul(
        kaynak_klasor,
        klasor_haritasi,
        secili_kategori,
    )
    if tum_postalar_klasoru_mu(kaynak_klasor, klasor_haritasi):
        return False
    if cop_klasoru_mu(kaynak_klasor, klasor_haritasi):
        return False
    if spam_klasoru_mu(kaynak_klasor, klasor_haritasi, secili_kategori):
        # Spam görünümünde \Deleted/EXPUNGE davranışı hesap ayarlarına göre daha riskli olabilir.
        # Spam'den taşıma ayrı bir güvenlik adımında ele alınacaktır.
        return False
    taslaklar = klasor_haritasi.get("Taslaklar", VARSAYILAN_KLASOR_HARITASI["Taslaklar"])
    if str(kaynak_klasor) == str(taslaklar):
        return False
    if kaynak_kategori == "Gelen Kutusu":
        return True
    if kaynak_kategori in ozel_klasorler:
        return True
    return False


def gmail_etiket_ekle_ve_kaynak_kaldir(
    imap,
    uidler,
    hedef_etiket,
    kaynak_klasor,
    hedef_hata,
    kaynak_hata,
    klasor_haritasi,
    ozel_klasorler,
    secili_kategori="",
):
    """Hedef Gmail etiketini ekler; güvenliyse seçili kaynak klasörden çıkarır."""
    imap_gmail_etiket_store(imap, uidler, "+", hedef_etiket, hedef_hata)
    kaynak_kategori = kategori_adini_klasorden_bul(kaynak_klasor, klasor_haritasi, secili_kategori)
    if kaynak_etiketi_kaldirilabilir_mi(kaynak_klasor, klasor_haritasi, ozel_klasorler, kaynak_kategori, secili_kategori):
        kaynak_etiket = gmail_etiket_ifadesi(kaynak_kategori, kaynak_klasor, klasor_haritasi, secili_kategori)
        if kaynak_etiket and kaynak_etiket != hedef_etiket:
            imap_uidleri_kaynak_klasorden_cikar(imap, uidler, kaynak_hata)
    return True


def okunmadi_etiketini_kaldir(metin):
    metin = metin or ""
    # Yeni görünüm etiketi kullanıcının dilinde olabilir; eski Türkçe önbellekler
    # de sürüm yükseltmelerinde sorunsuz temizlenmeye devam etmelidir.
    etiketler = dict.fromkeys((
        _("[Okunmadı] "),
        _("Okunmadı - "),
        "[Okunmadı] ",
        "Okunmadı - ",
    ))
    for etiket in etiketler:
        if metin.startswith(etiket):
            return metin[len(etiket):]
    return metin
