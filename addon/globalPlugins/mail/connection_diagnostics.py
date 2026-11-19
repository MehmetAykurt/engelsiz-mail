# -*- coding: utf-8 -*-
"""Engelsiz Mail hesap, ağ, IMAP ve SMTP bağlantı tanısı."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import socket
from typing import NamedTuple

from .config import ayarlari_denetim_icin_yukle
from .errors import MailHatasi
from .folders import SISTEM_KLASORLERI, VARSAYILAN_KLASOR_HARITASI, imap_klasor_haritasi_olustur, klasor_gorunen_adi
from .imap_client import GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT, ImapBaglantisi
from .logger import hata_kaydet
from .smtp_client import (
    BAGLANTI_DENETIM_ZAMAN_ASIMI,
    GMAIL_SMTP_PORT,
    GMAIL_SMTP_STARTTLS_PORT,
    GMAIL_SMTP_SUNUCU,
    baglanti_hatasi_kullanici_mesaji,
    smtp_baglanti_denetle,
)
from .validators import eposta_adresi_gecerli_mi


class BaglantiDenetimSonucu(NamedTuple):
    basarili: bool
    durum_kodu: str
    rapor: str


def sifre_notu_durumunu_al(hesap, sifre):
    """Şifre notunun görünür durumunu çevrilmiş metinden bağımsız belirler."""
    if not sifre:
        return _("Başarısız"), _("Şifre çözme")
    if hesap.get("sifre_saklama_turu") == "duz_metin":
        return _("Uyarı"), _("Şifre saklama biçimi")
    return _("Başarılı"), _("Şifre çözme")


def _raporu_olustur(durum_kodu, satirlar, sorun_yardimi=False):
    durum_metni = {
        "hata": _("Sorun bulundu."),
        "uyari": _("Başarılı, ancak uyarı var."),
        "basarili": _("Başarılı."),
        "belirsiz": _("Sonuç kesin olarak doğrulanamadı."),
    }.get(durum_kodu, _("Sonuç kesin olarak doğrulanamadı."))
    bolumler = [_('Bağlantı denetimi tamamlandı. Sonuç: {0}').format(durum_metni)]
    if sorun_yardimi:
        bolumler.append(_("Sorun varsa önce e-posta adresinizi, uygulama şifrenizi, internet bağlantınızı, güvenlik duvarınızı ve kurum ağı kısıtlamalarını denetleyin."))
    bolumler.extend(["", _("Ayrıntılar:")])
    bolumler.extend(satirlar)
    return "\n\n".join(bolumler)


def baglanti_denetimini_yap(eposta=None, sifre=None):
    """Bağlantı sorunlarını adım adım denetler ve kullanıcıya okunabilir rapor döndürür."""
    satirlar = []
    hata_sayisi = 0
    uyari_sayisi = 0

    def ekle(durum, baslik, aciklama):
        nonlocal hata_sayisi, uyari_sayisi
        if durum == _("Başarısız"):
            hata_sayisi += 1
        elif durum == _("Uyarı"):
            uyari_sayisi += 1
        satirlar.append(f"{durum}: {baslik}\n{aciklama}")

    try:
        hesap = ayarlari_denetim_icin_yukle(eposta, sifre)
        if hesap["kaynak"] == "kayitli":
            if hesap["ayar_dosyasi_var"]:
                ekle(_("Başarılı"), _("Ayar dosyası"), _("Engelsiz Mail ayar dosyası NVDA yapılandırma klasöründe bulundu."))
            else:
                ekle(_("Başarısız"), _("Ayar dosyası"), _("Kayıtlı hesap bilgisi bulunamadı. Hesap menüsünden Bağlan seçeneğiyle hesap bilgilerinizi kaydedin."))
        else:
            ekle(_("Başarılı"), _("Geçici hesap bilgisi"), _("Bağlan penceresine yazılan e-posta adresi ve uygulama şifresi denetleniyor."))
    except Exception as e:
        hata_kaydet("Kayıtlı hesap bilgileri denetim için okunamadı.", e)
        satirlar.append(f"{_('Başarısız')}: {_('Kayıtlı hesap bilgisi')}\n{baglanti_hatasi_kullanici_mesaji(e)}")
        return BaglantiDenetimSonucu(False, "hata", _raporu_olustur("hata", satirlar))

    eposta = hesap.get("eposta", "")
    sifre = hesap.get("sifre", "")

    if eposta_adresi_gecerli_mi(eposta):
        ekle(_("Başarılı"), _("E-posta adresi"), _("Kayıtlı e-posta adresinin biçimi geçerli görünüyor."))
    else:
        ekle(_("Başarısız"), _("E-posta adresi"), _("E-posta adresi eksik veya geçersiz görünüyor. Örnek biçim: adiniz@gmail.com"))

    if sifre:
        if len(sifre) < 12:
            ekle(_("Uyarı"), _("Uygulama şifresi"), _("Uygulama şifresi kısa görünüyor. Google uygulama şifreleri 16 karakterden oluşur."))
        else:
            ekle(_("Başarılı"), _("Uygulama şifresi"), _("Uygulama şifresi okunabildi ve denetim için hazırlandı."))
    else:
        ekle(_("Başarısız"), _("Uygulama şifresi"), _("Kayıtlı uygulama şifresi okunamadı veya boş. Hesap bilgilerini yeniden kaydetmeniz gerekebilir."))

    for not_satiri in hesap.get("notlar", []):
        durum, baslik = sifre_notu_durumunu_al(hesap, sifre)
        ekle(durum, baslik, not_satiri)

    # E-posta veya şifre yoksa ağ denetimine geçmek yanıltıcı sonuç üretebilir.
    if not eposta or not sifre:
        return BaglantiDenetimSonucu(False, "hata", _raporu_olustur("hata", satirlar))

    try:
        with socket.create_connection((GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle(_("Başarılı"), _("Gmail IMAP 993 TCP erişimi"), _('{0}:{1} adresine TCP bağlantısı başlatılabildi.').format(GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT))
    except Exception as e:
        ekle(_("Başarısız"), _("Gmail IMAP 993 TCP erişimi"), baglanti_hatasi_kullanici_mesaji(e))

    try:
        with socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle(_("Başarılı"), _("Gmail SMTP 465 TCP erişimi"), _('{0}:{1} adresine TCP bağlantısı başlatılabildi.').format(GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT))
    except Exception as e:
        ekle(_("Uyarı"), _("Gmail SMTP 465 TCP erişimi"), baglanti_hatasi_kullanici_mesaji(e))

    try:
        with socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle(_("Başarılı"), _("Gmail SMTP 587 TCP erişimi"), _('{0}:{1} adresine TCP bağlantısı başlatılabildi.').format(GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT))
    except Exception as e:
        ekle(_("Uyarı"), _("Gmail SMTP 587 TCP erişimi"), baglanti_hatasi_kullanici_mesaji(e))

    klasor_haritasi = {}
    try:
        with ImapBaglantisi(
            {"eposta": eposta, "sifre": sifre},
            timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI,
        ) as imap:
            ekle(_("Başarılı"), _("IMAP kullanıcı doğrulaması"), _("Gmail IMAP sunucusu e-posta adresini ve uygulama şifresini kabul etti."))

            tip, veri = imap.list()
            if tip != "OK":
                raise MailHatasi(_("Gmail klasör listesi alınamadı."))
            klasor_haritasi, ozel_klasorler = imap_klasor_haritasi_olustur(veri)
            ekle(_("Başarılı"), _("Gmail klasör listesi"), _('Klasör listesi okundu. Tanınan özel arşiv klasörü sayısı: {0}. Sistem klasörleri aşağıda tek tek seçilerek denetlenecek.').format(len(ozel_klasorler)))

            # Sistem klasörlerine erişim denetimi.
            for ad in SISTEM_KLASORLERI:
                klasor = klasor_haritasi.get(ad, VARSAYILAN_KLASOR_HARITASI.get(ad, "INBOX"))
                tip, _secim_verisi = imap.select(klasor, readonly=True)
                if tip != "OK":
                    ekle(_("Uyarı"), _('{0} klasörü').format(klasor_gorunen_adi(ad)), _("Klasör seçilemedi. Gmail hesabınızda bu klasör farklı adla görünüyor olabilir."))
                else:
                    ekle(_("Başarılı"), _('{0} klasörü').format(klasor_gorunen_adi(ad)), _("Klasör seçilebildi."))
    except Exception as e:
        ekle(_("Başarısız"), _("IMAP denetimi"), baglanti_hatasi_kullanici_mesaji(e))

    try:
        smtp_yontemi = smtp_baglanti_denetle(eposta, sifre)
        ekle(_("Başarılı"), _("SMTP kullanıcı doğrulaması"), _('Gmail SMTP sunucusu e-posta adresini ve uygulama şifresini kabul etti. Kullanılan yöntem: {0}. Denetim sırasında e-posta gönderilmedi.').format(smtp_yontemi))
    except Exception as e:
        ekle(_("Başarısız"), _("SMTP denetimi"), baglanti_hatasi_kullanici_mesaji(e))

    if hata_sayisi:
        durum_kodu = "hata"
        basarili = False
    elif uyari_sayisi:
        durum_kodu = "uyari"
        basarili = True
    else:
        durum_kodu = "basarili"
        basarili = True

    rapor = _raporu_olustur(durum_kodu, satirlar, sorun_yardimi=bool(hata_sayisi))
    return BaglantiDenetimSonucu(basarili, durum_kodu, rapor)
