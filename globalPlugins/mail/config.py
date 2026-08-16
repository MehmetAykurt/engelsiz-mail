# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import os

import wx

from .errors import MailHatasi
from .logger import hata_kaydet
from .paths import AYARLAR_DOSYASI
from .security import uygulama_sifresini_sifrele, uygulama_sifresini_coz
from .storage import guvenli_json_oku, guvenli_json_guncelle
from .validators import bildirim_ses_dosyasi_duzenle

VARSAYILAN_MESAJ_SAYISI = 25
AYAR_SEMA_SURUMU_ALANI = "sema_surumu"
GUNCEL_AYAR_SEMA_SURUMU = 1
EN_AZ_MESAJ_SAYISI = 1
EN_COK_MESAJ_SAYISI = 100
SIFRE_DPAPI_ALANI = "sifre_dpapi"
SIFRE_DUZ_METIN_ALANI = "sifre"
MESAJ_SAYISI_ALANI = "mesaj_sayisi"
GORUNEN_AD_ALANI = "gorunen_ad"
IMZA_ALANI = "imza"
IMZA_AZAMI_UZUNLUK = 10000
ONIZLEME_ALANI = "onizleme"
SILME_ONAY_ALANI = "silme_onayi"
KALICI_SILME_ONAY_ALANI = "kalici_silme_onayi"
ADRES_OTOMATIK_KAYDET_ALANI = "adres_otomatik_kaydet"
ESCAPE_KAPAT_ALANI = "escape_kapat"
KONUSMALARI_GRUPLA_ALANI = "konusmalari_grupla"
BILDIRIM_SON_UID_ALANI = "bildirim_son_uid"
BILDIRIM_SON_UID_HESAP_ALANI = "bildirim_son_uid_hesap"
BILDIRIM_UIDVALIDITY_ALANI = "bildirim_uidvalidity"
BILDIRIM_BASLATILDI_ALANI = "bildirim_baslatildi"
BILDIRIM_ETKIN_ALANI = "bildirim_etkin"
BILDIRIM_ARALIK_ALANI = "bildirim_aralik"
BILDIRIM_SES_ALANI = "bildirim_ses"
BILDIRIM_SES_TURU_ALANI = "bildirim_ses_turu"
BILDIRIM_SES_DOSYASI_ALANI = "bildirim_ses_dosyasi"
BILDIRIM_SES_TURU_SISTEM = "sistem"
BILDIRIM_SES_TURU_DOSYA = "dosya"
BILDIRIM_MESAJ_ALANI = "bildirim_mesaj"
BILDIRIM_GONDEREN_ALANI = "bildirim_gonderen"
BILDIRIM_KONU_ALANI = "bildirim_konu"
BILDIRIM_ARALIK_SECENEKLERI = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
VARSAYILAN_BILDIRIM_ARALIGI = 30
GORUNUM_YAZI_TIPI_ALANI = "gorunum_yazi_tipi"
GORUNUM_YAZI_BOYUTU_ALANI = "gorunum_yazi_boyutu"
GORUNUM_YAZI_STILI_ALANI = "gorunum_yazi_stili"
GORUNUM_METIN_RENGI_ALANI = "gorunum_metin_rengi"
GORUNUM_ARKA_PLAN_RENGI_ALANI = "gorunum_arka_plan_rengi"
GORUNUM_SISTEM_RENKLERI_ALANI = "gorunum_sistem_renkleri"
GORUNUM_YAZI_BOYUTU_EN_AZ = 8
GORUNUM_YAZI_BOYUTU_EN_COK = 36

GORUNUM_YAZI_STILI_SECENEKLERI = {
    "Normal": (wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL),
    "Kalın": (wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD),
    "İtalik": (wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL),
    "Kalın İtalik": (wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_BOLD),
}

GORUNUM_METIN_RENKLERI = {
    "Siyah": (0, 0, 0),
    "Beyaz": (255, 255, 255),
    "Koyu Gri": (64, 64, 64),
    "Mavi": (0, 0, 255),
    "Kırmızı": (192, 0, 0),
    "Yeşil": (0, 128, 0),
}

GORUNUM_ARKA_PLAN_RENKLERI = {
    "Beyaz": (255, 255, 255),
    "Siyah": (0, 0, 0),
    "Açık Gri": (240, 240, 240),
    "Koyu Gri": (64, 64, 64),
    "Açık Sarı": (255, 255, 224),
    "Açık Mavi": (224, 240, 255),
}


def gorunum_yazi_stili_gorunen_adi(ad):
    """Kalıcı ayar anahtarını değiştirmeden yazı stili adını yerelleştirir."""
    ad = str(ad or "").strip()
    return {
        "Normal": _("Normal"),
        "Kalın": _("Kalın"),
        "İtalik": _("İtalik"),
        "Kalın İtalik": _("Kalın İtalik"),
    }.get(ad, ad)


def gorunum_metin_rengi_gorunen_adi(ad):
    """Kalıcı ayar anahtarını değiştirmeden metin rengi adını yerelleştirir."""
    ad = str(ad or "").strip()
    return {
        "Siyah": _("Siyah"),
        "Beyaz": _("Beyaz"),
        "Koyu Gri": _("Koyu Gri"),
        "Mavi": _("Mavi"),
        "Kırmızı": _("Kırmızı"),
        "Yeşil": _("Yeşil"),
    }.get(ad, ad)


def gorunum_arka_plan_rengi_gorunen_adi(ad):
    """Kalıcı ayar anahtarını değiştirmeden arka plan rengi adını yerelleştirir."""
    ad = str(ad or "").strip()
    return {
        "Beyaz": _("Beyaz"),
        "Siyah": _("Siyah"),
        "Açık Gri": _("Açık Gri"),
        "Koyu Gri": _("Koyu Gri"),
        "Açık Sarı": _("Açık Sarı"),
        "Açık Mavi": _("Açık Mavi"),
    }.get(ad, ad)



def ayar_kopyasi_olustur(ayarlar):
    """Ayar yazmadan önce eski düz metin şifre alanını temizleyen güvenli kopya üretir."""
    yeni_ayarlar = dict(ayarlar) if isinstance(ayarlar, dict) else {}
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    yeni_ayarlar[AYAR_SEMA_SURUMU_ALANI] = GUNCEL_AYAR_SEMA_SURUMU
    return yeni_ayarlar


def _ayarlari_guncelle(guncelleyici):
    """Ayarları tek bir kilitli okuma-değiştirme-yazma işlemiyle günceller."""
    def ayarlari_duzenle(mevcut_ayarlar):
        if not isinstance(mevcut_ayarlar, dict):
            mevcut_ayarlar = {}
        yeni_ayarlar = ayar_kopyasi_olustur(mevcut_ayarlar)
        guncelleyici(yeni_ayarlar, mevcut_ayarlar)
        yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
        yeni_ayarlar[AYAR_SEMA_SURUMU_ALANI] = GUNCEL_AYAR_SEMA_SURUMU
        return yeni_ayarlar

    return guvenli_json_guncelle(AYARLAR_DOSYASI, {}, ayarlari_duzenle)


def mesaj_sayisini_duzenle(deger, varsayilan=VARSAYILAN_MESAJ_SAYISI):
    """Ayar dosyasından gelen mesaj sayısını güvenli aralığa çeker."""
    try:
        sayi = int(str(deger).strip())
    except Exception:
        sayi = int(varsayilan)
    if sayi < EN_AZ_MESAJ_SAYISI:
        return EN_AZ_MESAJ_SAYISI
    if sayi > EN_COK_MESAJ_SAYISI:
        return EN_COK_MESAJ_SAYISI
    return sayi


def _duz_metin_sifreyi_sifreliye_tasi(ayarlar, eposta, sifre):
    """Eski ayar dosyasındaki düz metin şifreyi DPAPI alanına taşır."""
    if not sifre:
        return
    try:
        sifreli_deger = uygulama_sifresini_sifrele(sifre)

        def guncelle(yeni_ayarlar, mevcut_ayarlar):
            yeni_ayarlar["eposta"] = eposta
            yeni_ayarlar[SIFRE_DPAPI_ALANI] = sifreli_deger

        _ayarlari_guncelle(guncelle)
    except Exception as e:
        hata_kaydet("Düz metin uygulama şifresi şifreli alana taşınamadı.", e)


def ayarlari_yukle():
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    eposta = str(ayarlar.get("eposta", "")).strip()
    gorunen_ad = str(ayarlar.get(GORUNEN_AD_ALANI, "")).strip()
    sifre = ""

    sifreli_deger = str(ayarlar.get(SIFRE_DPAPI_ALANI, "")).strip()
    if sifreli_deger:
        try:
            sifre = uygulama_sifresini_coz(sifreli_deger)
        except Exception as e:
            hata_kaydet("Kayıtlı uygulama şifresi çözülemedi.", e)
            sifre = ""
    else:
        sifre = str(ayarlar.get(SIFRE_DUZ_METIN_ALANI, "")).strip().replace(" ", "")
        if sifre:
            _duz_metin_sifreyi_sifreliye_tasi(ayarlar, eposta, sifre)

    mesaj_sayisi = mesaj_sayisini_duzenle(ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI))

    return {
        "eposta": eposta,
        "gorunen_ad": gorunen_ad,
        "sifre": sifre,
        MESAJ_SAYISI_ALANI: mesaj_sayisi,
    }


def ayarlari_denetim_icin_yukle(eposta=None, sifre=None):
    """Bağlantı denetimi için hesap bilgisini ayrıntılı ve raporlanabilir biçimde okur."""
    if eposta is not None or sifre is not None:
        return {
            "eposta": str(eposta or "").strip(),
            "gorunen_ad": "",
            "sifre": str(sifre or "").strip().replace(" ", ""),
            "kaynak": "gecici",
            "ayar_dosyasi_var": os.path.exists(AYARLAR_DOSYASI),
            "notlar": [],
        }

    ayar_dosyasi_var = os.path.exists(AYARLAR_DOSYASI)
    ham_ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ham_ayarlar, dict):
        ham_ayarlar = {}

    sonuc = {
        "eposta": str(ham_ayarlar.get("eposta", "")).strip(),
        "gorunen_ad": str(ham_ayarlar.get(GORUNEN_AD_ALANI, "")).strip(),
        "sifre": "",
        "kaynak": "kayitli",
        "ayar_dosyasi_var": ayar_dosyasi_var,
        "notlar": [],
    }

    sifreli_deger = str(ham_ayarlar.get(SIFRE_DPAPI_ALANI, "")).strip()
    duz_metin_sifre = str(ham_ayarlar.get(SIFRE_DUZ_METIN_ALANI, "")).strip().replace(" ", "")
    if sifreli_deger:
        sonuc["sifre"] = uygulama_sifresini_coz(sifreli_deger)
        sonuc["notlar"].append(_("Kayıtlı uygulama şifresi Windows DPAPI ile çözüldü."))
    elif duz_metin_sifre:
        sonuc["sifre"] = duz_metin_sifre
        sonuc["notlar"].append(_("Eski düz metin uygulama şifresi alanı bulundu. Hesap yeniden kaydedildiğinde şifreli alana taşınmalıdır."))
    else:
        sonuc["notlar"].append(_("Kayıtlı uygulama şifresi bulunamadı."))
    return sonuc


def ayarlari_kaydet(eposta, sifre, mesaj_sayisi=None, gorunen_ad=None):
    eposta = str(eposta or "").strip()
    if gorunen_ad is None:
        gorunen_ad = None
    else:
        gorunen_ad = str(gorunen_ad or "").strip()
    sifre = str(sifre or "").strip().replace(" ", "")
    try:
        sifreli_deger = uygulama_sifresini_sifrele(sifre)
    except Exception as e:
        hata_kaydet("Uygulama şifresi şifrelenemedi.", e)
        return False

    kaydedilecek_mesaj_sayisi = None if mesaj_sayisi is None else mesaj_sayisini_duzenle(mesaj_sayisi)

    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        if kaydedilecek_mesaj_sayisi is None:
            yeni_ayarlar[MESAJ_SAYISI_ALANI] = mesaj_sayisini_duzenle(
                mevcut_ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)
            )
        else:
            yeni_ayarlar[MESAJ_SAYISI_ALANI] = kaydedilecek_mesaj_sayisi
        eski_eposta = str(mevcut_ayarlar.get("eposta", "") or "").strip().lower()
        yeni_eposta = eposta.lower()
        if eski_eposta and eski_eposta != yeni_eposta:
            for alan in (BILDIRIM_SON_UID_ALANI, BILDIRIM_SON_UID_HESAP_ALANI, BILDIRIM_UIDVALIDITY_ALANI, BILDIRIM_BASLATILDI_ALANI):
                yeni_ayarlar.pop(alan, None)
        yeni_ayarlar["eposta"] = eposta
        if gorunen_ad is None:
            yeni_ayarlar[GORUNEN_AD_ALANI] = str(mevcut_ayarlar.get(GORUNEN_AD_ALANI, "") or "").strip()
        else:
            yeni_ayarlar[GORUNEN_AD_ALANI] = gorunen_ad
        yeni_ayarlar[SIFRE_DPAPI_ALANI] = sifreli_deger

    return _ayarlari_guncelle(guncelle)


def hesap_bilgilerini_sil():
    """Kayıtlı hesap alanlarını diğer kullanıcı tercihlerini koruyarak siler."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar.pop("eposta", None)
        yeni_ayarlar.pop(GORUNEN_AD_ALANI, None)
        yeni_ayarlar.pop(SIFRE_DPAPI_ALANI, None)
        yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
        yeni_ayarlar.pop(BILDIRIM_SON_UID_ALANI, None)
        yeni_ayarlar.pop(BILDIRIM_SON_UID_HESAP_ALANI, None)
        yeni_ayarlar.pop(BILDIRIM_UIDVALIDITY_ALANI, None)
        yeni_ayarlar.pop(BILDIRIM_BASLATILDI_ALANI, None)

    return _ayarlari_guncelle(guncelle)


def mesaj_sayisini_kaydet(mesaj_sayisi):
    """Listelenecek e-posta sayısını hesap bilgilerine dokunmadan kaydeder."""
    duzenlenmis_mesaj_sayisi = mesaj_sayisini_duzenle(mesaj_sayisi)

    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[MESAJ_SAYISI_ALANI] = duzenlenmis_mesaj_sayisi

    return _ayarlari_guncelle(guncelle)


def imza_metnini_duzenle(imza):
    """İmza metninin satır sonlarını düzenler ve dış boşluklarını temizler."""
    return str(imza or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def imza_yukle():
    """Kayıtlı düz metin imzayı döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return ""
    return imza_metnini_duzenle(ayarlar.get(IMZA_ALANI, ""))[:IMZA_AZAMI_UZUNLUK]


def imza_kaydet(imza):
    """İmza metnini hesap bilgilerine dokunmadan ayarlara kaydeder."""
    duzenlenmis_imza = imza_metnini_duzenle(imza)
    if not duzenlenmis_imza:
        raise MailHatasi(_("İmza metni boş bırakılamaz."))
    if len(duzenlenmis_imza) > IMZA_AZAMI_UZUNLUK:
        raise MailHatasi(_('İmza en fazla {0} karakter olabilir.').format(IMZA_AZAMI_UZUNLUK))

    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[IMZA_ALANI] = duzenlenmis_imza

    return _ayarlari_guncelle(guncelle)


def imza_kaldir():
    """Kayıtlı imzayı diğer ayarlara dokunmadan kaldırır."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar.pop(IMZA_ALANI, None)

    return _ayarlari_guncelle(guncelle)


def onizleme_ayari_yukle():
    """E-posta listesinde ön izleme okunup okunmayacağını döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False
    return bool(ayarlar.get(ONIZLEME_ALANI, False))


def onizleme_ayari_kaydet(etkin):
    """Ön izleme ayarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[ONIZLEME_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def silme_onayi_ayari_yukle():
    """E-posta silerken kullanıcıdan onay istenip istenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(SILME_ONAY_ALANI, True))


def silme_onayi_ayari_kaydet(etkin):
    """Silme onayı ayarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[SILME_ONAY_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def kalici_silme_onayi_ayari_yukle():
    """Shift+Delete ile kalıcı silerken onay istenip istenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(KALICI_SILME_ONAY_ALANI, True))


def kalici_silme_onayi_ayari_kaydet(etkin):
    """Kalıcı silme onayı ayarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[KALICI_SILME_ONAY_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def adres_otomatik_kaydet_ayari_yukle():
    """Gönderilen alıcı adreslerinin adres geçmişine otomatik eklenip eklenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(ADRES_OTOMATIK_KAYDET_ALANI, True))


def adres_otomatik_kaydet_ayari_kaydet(etkin):
    """Gönderilen alıcı adreslerini otomatik kaydetme ayarını saklar."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[ADRES_OTOMATIK_KAYDET_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def escape_kapat_ayari_yukle():
    """Escape tuşunun ana Engelsiz Mail penceresini kapatıp kapatmayacağını döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False
    return bool(ayarlar.get(ESCAPE_KAPAT_ALANI, False))


def escape_kapat_ayari_kaydet(etkin):
    """Escape ile kapatma ayarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[ESCAPE_KAPAT_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def konusmalari_grupla_ayari_yukle():
    """Gmail konuşmalarının ana listede tek satır gösterilip gösterilmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False
    return bool(ayarlar.get(KONUSMALARI_GRUPLA_ALANI, False))


def konusmalari_grupla_ayari_kaydet(etkin):
    """Konuşma gruplama ayarını diğer hesap bilgilerine dokunmadan saklar."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[KONUSMALARI_GRUPLA_ALANI] = bool(etkin)

    return _ayarlari_guncelle(guncelle)


def bildirim_ses_turu_duzenle(deger):
    """Bildirim ses türünü güvenli değerlerden birine çeker."""
    deger = str(deger or "").strip().lower()
    if deger == BILDIRIM_SES_TURU_DOSYA:
        return BILDIRIM_SES_TURU_DOSYA
    return BILDIRIM_SES_TURU_SISTEM


def bildirim_araligini_duzenle(deger, varsayilan=VARSAYILAN_BILDIRIM_ARALIGI):
    """Bildirim kontrol aralığını izin verilen dakika seçeneklerinden birine çeker."""
    try:
        dakika = int(str(deger).strip())
    except Exception:
        dakika = int(varsayilan)
    if dakika in BILDIRIM_ARALIK_SECENEKLERI:
        return dakika

    # Eski ya da elle değiştirilmiş ayar dosyalarında en yakın güvenli değeri seç.
    en_yakin = min(BILDIRIM_ARALIK_SECENEKLERI, key=lambda secenek: abs(secenek - dakika))
    return en_yakin


def bildirim_ayarlari_yukle():
    """Yeni e-posta bildirim ayarlarını okur."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    etkin = bool(ayarlar.get(BILDIRIM_ETKIN_ALANI, False))
    sesle_bildir = bool(ayarlar.get(BILDIRIM_SES_ALANI, True))
    mesajla_bildir = bool(ayarlar.get(BILDIRIM_MESAJ_ALANI, True))
    if etkin and not sesle_bildir and not mesajla_bildir:
        # Eski veya elle değiştirilmiş ayarlar bildirimi tamamen sessiz bırakmasın.
        mesajla_bildir = True

    return {
        BILDIRIM_ETKIN_ALANI: etkin,
        BILDIRIM_ARALIK_ALANI: bildirim_araligini_duzenle(
            ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI)
        ),
        BILDIRIM_SES_ALANI: sesle_bildir,
        BILDIRIM_SES_TURU_ALANI: bildirim_ses_turu_duzenle(
            ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        ),
        BILDIRIM_SES_DOSYASI_ALANI: bildirim_ses_dosyasi_duzenle(
            ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, "")
        ),
        BILDIRIM_MESAJ_ALANI: mesajla_bildir,
        BILDIRIM_GONDEREN_ALANI: bool(ayarlar.get(BILDIRIM_GONDEREN_ALANI, False)),
        BILDIRIM_KONU_ALANI: bool(ayarlar.get(BILDIRIM_KONU_ALANI, False)),
    }


def bildirim_ayarlari_kaydet(
    etkin, sesle_bildir, ses_turu, ses_dosyasi,
    mesajla_bildir, gonderen_bildir, konu_bildir
):
    """Bildirim ve ses ayarlarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[BILDIRIM_ETKIN_ALANI] = bool(etkin)
        yeni_ayarlar[BILDIRIM_SES_ALANI] = bool(sesle_bildir)
        yeni_ayarlar[BILDIRIM_SES_TURU_ALANI] = bildirim_ses_turu_duzenle(ses_turu)
        yeni_ayarlar[BILDIRIM_SES_DOSYASI_ALANI] = bildirim_ses_dosyasi_duzenle(ses_dosyasi)
        yeni_ayarlar[BILDIRIM_MESAJ_ALANI] = bool(mesajla_bildir)
        yeni_ayarlar[BILDIRIM_GONDEREN_ALANI] = bool(gonderen_bildir)
        yeni_ayarlar[BILDIRIM_KONU_ALANI] = bool(konu_bildir)
        yeni_ayarlar.pop("bildirim_onizleme", None)

    return _ayarlari_guncelle(guncelle)


def bildirim_son_uid_oku(eposta):
    """Aynı hesap için daha önce bildirime temel alınan son UID değerini okur."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return 0

    kayitli_hesap = str(ayarlar.get(BILDIRIM_SON_UID_HESAP_ALANI, "") or "").strip().lower()
    if kayitli_hesap != str(eposta or "").strip().lower():
        return 0

    try:
        return int(str(ayarlar.get(BILDIRIM_SON_UID_ALANI, "0")).strip() or "0")
    except Exception:
        return 0


def bildirim_baslatildi_mi(eposta):
    """Yeni e-posta bildirimi için ilk taramanın yapılıp yapılmadığını döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False

    kayitli_hesap = str(ayarlar.get(BILDIRIM_SON_UID_HESAP_ALANI, "") or "").strip().lower()
    if kayitli_hesap != str(eposta or "").strip().lower():
        return False

    if BILDIRIM_BASLATILDI_ALANI in ayarlar:
        return bool(ayarlar.get(BILDIRIM_BASLATILDI_ALANI, False))

    # Eski sürümlerden gelen ayarlarda ayrı başlatıldı alanı yoktu.
    # Hesap ve son UID alanı kayıtlıysa bildirim tabanı kurulmuş kabul edilir.
    return BILDIRIM_SON_UID_ALANI in ayarlar


def bildirim_uidvalidity_oku(eposta):
    """Aynı hesap için kaydedilmiş INBOX UIDVALIDITY değerini okur."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return 0

    kayitli_hesap = str(ayarlar.get(BILDIRIM_SON_UID_HESAP_ALANI, "") or "").strip().lower()
    if kayitli_hesap != str(eposta or "").strip().lower():
        return 0

    try:
        return int(str(ayarlar.get(BILDIRIM_UIDVALIDITY_ALANI, "0")).strip() or "0")
    except Exception:
        return 0


def bildirim_tabanini_sifirla(eposta, uidvalidity=0):
    """Hesap veya UIDVALIDITY değiştiğinde bildirim tabanını sessizce sıfırlar."""
    return bildirim_son_uid_kaydet(eposta, 0, baslatildi=False, uidvalidity=uidvalidity)


def bildirim_son_uid_kaydet(eposta, uid, baslatildi=True, uidvalidity=None):
    """Bildirim denetimi için son görülen UID ve UIDVALIDITY değerini hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar[BILDIRIM_SON_UID_HESAP_ALANI] = str(eposta or "").strip().lower()
        yeni_ayarlar[BILDIRIM_BASLATILDI_ALANI] = bool(baslatildi)
        try:
            yeni_ayarlar[BILDIRIM_SON_UID_ALANI] = int(uid)
        except Exception:
            yeni_ayarlar[BILDIRIM_SON_UID_ALANI] = 0
        if uidvalidity is not None:
            try:
                yeni_ayarlar[BILDIRIM_UIDVALIDITY_ALANI] = int(uidvalidity)
            except Exception:
                yeni_ayarlar.pop(BILDIRIM_UIDVALIDITY_ALANI, None)

    return _ayarlari_guncelle(guncelle)


def gorunum_ayarlari_yukle():
    """Kullanıcının ekrandaki görünüm tercihlerini okur."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    yazi_tipi = str(ayarlar.get(GORUNUM_YAZI_TIPI_ALANI, "") or "").strip()

    try:
        yazi_boyutu = int(str(ayarlar.get(GORUNUM_YAZI_BOYUTU_ALANI, "0")).strip() or "0")
    except Exception:
        yazi_boyutu = 0

    if yazi_boyutu and (yazi_boyutu < GORUNUM_YAZI_BOYUTU_EN_AZ or yazi_boyutu > GORUNUM_YAZI_BOYUTU_EN_COK):
        yazi_boyutu = 0

    yazi_stili = str(ayarlar.get(GORUNUM_YAZI_STILI_ALANI, "") or "").strip()
    if yazi_stili not in GORUNUM_YAZI_STILI_SECENEKLERI:
        yazi_stili = ""

    metin_rengi = str(ayarlar.get(GORUNUM_METIN_RENGI_ALANI, "") or "").strip()
    if metin_rengi not in GORUNUM_METIN_RENKLERI:
        metin_rengi = ""

    arka_plan_rengi = str(ayarlar.get(GORUNUM_ARKA_PLAN_RENGI_ALANI, "") or "").strip()
    if arka_plan_rengi not in GORUNUM_ARKA_PLAN_RENKLERI:
        arka_plan_rengi = ""

    return {
        GORUNUM_YAZI_TIPI_ALANI: yazi_tipi,
        GORUNUM_YAZI_BOYUTU_ALANI: yazi_boyutu,
        GORUNUM_YAZI_STILI_ALANI: yazi_stili,
        GORUNUM_METIN_RENGI_ALANI: metin_rengi,
        GORUNUM_ARKA_PLAN_RENGI_ALANI: arka_plan_rengi,
        GORUNUM_SISTEM_RENKLERI_ALANI: bool(ayarlar.get(GORUNUM_SISTEM_RENKLERI_ALANI, False)),
    }


def gorunum_ayarlari_kaydet(yazi_tipi=None, yazi_boyutu=None, yazi_stili=None, metin_rengi=None, arka_plan_rengi=None, sistem_renkleri=None):
    """Görünüm ayarlarını hesap bilgilerine dokunmadan kaydeder."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        if yazi_tipi is not None:
            duzenlenmis_yazi_tipi = str(yazi_tipi or "").strip()
            if duzenlenmis_yazi_tipi:
                yeni_ayarlar[GORUNUM_YAZI_TIPI_ALANI] = duzenlenmis_yazi_tipi
            else:
                yeni_ayarlar.pop(GORUNUM_YAZI_TIPI_ALANI, None)

        if yazi_boyutu is not None:
            try:
                duzenlenmis_yazi_boyutu = int(str(yazi_boyutu).strip())
            except Exception:
                raise MailHatasi(_("Yazı tipi boyutu yalnızca rakamlardan oluşmalıdır."))
            if duzenlenmis_yazi_boyutu < GORUNUM_YAZI_BOYUTU_EN_AZ or duzenlenmis_yazi_boyutu > GORUNUM_YAZI_BOYUTU_EN_COK:
                raise MailHatasi(_('Yazı tipi boyutu {0} ile {1} arasında olmalıdır.').format(GORUNUM_YAZI_BOYUTU_EN_AZ, GORUNUM_YAZI_BOYUTU_EN_COK))
            yeni_ayarlar[GORUNUM_YAZI_BOYUTU_ALANI] = duzenlenmis_yazi_boyutu

        if yazi_stili is not None:
            duzenlenmis_yazi_stili = str(yazi_stili or "").strip()
            if duzenlenmis_yazi_stili not in GORUNUM_YAZI_STILI_SECENEKLERI:
                raise MailHatasi(_("Geçersiz yazı stili seçildi."))
            yeni_ayarlar[GORUNUM_YAZI_STILI_ALANI] = duzenlenmis_yazi_stili

        if metin_rengi is not None:
            duzenlenmis_metin_rengi = str(metin_rengi or "").strip()
            if duzenlenmis_metin_rengi not in GORUNUM_METIN_RENKLERI:
                raise MailHatasi(_("Geçersiz metin rengi seçildi."))
            yeni_ayarlar[GORUNUM_METIN_RENGI_ALANI] = duzenlenmis_metin_rengi

        if arka_plan_rengi is not None:
            duzenlenmis_arka_plan_rengi = str(arka_plan_rengi or "").strip()
            if duzenlenmis_arka_plan_rengi not in GORUNUM_ARKA_PLAN_RENKLERI:
                raise MailHatasi(_("Geçersiz arka plan rengi seçildi."))
            yeni_ayarlar[GORUNUM_ARKA_PLAN_RENGI_ALANI] = duzenlenmis_arka_plan_rengi

        if sistem_renkleri is not None:
            yeni_ayarlar[GORUNUM_SISTEM_RENKLERI_ALANI] = bool(sistem_renkleri)

    return _ayarlari_guncelle(guncelle)


def gorunum_ayarlari_sifirla():
    """Tüm görünüm ayarlarını varsayılana döndürür."""
    def guncelle(yeni_ayarlar, mevcut_ayarlar):
        yeni_ayarlar.pop(GORUNUM_YAZI_TIPI_ALANI, None)
        yeni_ayarlar.pop(GORUNUM_YAZI_BOYUTU_ALANI, None)
        yeni_ayarlar.pop(GORUNUM_YAZI_STILI_ALANI, None)
        yeni_ayarlar.pop(GORUNUM_METIN_RENGI_ALANI, None)
        yeni_ayarlar.pop(GORUNUM_ARKA_PLAN_RENGI_ALANI, None)
        yeni_ayarlar.pop(GORUNUM_SISTEM_RENKLERI_ALANI, None)

    return _ayarlari_guncelle(guncelle)
