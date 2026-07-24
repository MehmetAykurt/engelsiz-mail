# -*- coding: utf-8 -*-
"""Engelsiz Mail hesap, ağ, IMAP ve SMTP bağlantı tanısı."""

import socket

from .config import ayarlari_denetim_icin_yukle
from .errors import MailHatasi
from .folders import SISTEM_KLASORLERI, VARSAYILAN_KLASOR_HARITASI, imap_klasor_haritasi_olustur
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


def baglanti_denetimini_yap(eposta=None, sifre=None):
    """Bağlantı sorunlarını adım adım denetler ve kullanıcıya okunabilir rapor döndürür."""
    satirlar = []
    hata_sayisi = 0
    uyari_sayisi = 0

    def ekle(durum, baslik, aciklama):
        nonlocal hata_sayisi, uyari_sayisi
        if durum == "Başarısız":
            hata_sayisi += 1
        elif durum == "Uyarı":
            uyari_sayisi += 1
        satirlar.append(f"{durum}: {baslik}\n{aciklama}")

    try:
        hesap = ayarlari_denetim_icin_yukle(eposta, sifre)
        if hesap["kaynak"] == "kayitli":
            if hesap["ayar_dosyasi_var"]:
                ekle("Başarılı", "Ayar dosyası", "Engelsiz Mail ayar dosyası NVDA yapılandırma klasöründe bulundu.")
            else:
                ekle("Başarısız", "Ayar dosyası", "Kayıtlı hesap bilgisi bulunamadı. Hesap menüsünden Bağlan seçeneğiyle hesap bilgilerinizi kaydedin.")
        else:
            ekle("Başarılı", "Geçici hesap bilgisi", "Bağlan penceresine yazılan e-posta adresi ve uygulama şifresi denetleniyor.")
    except Exception as e:
        hata_kaydet("Kayıtlı hesap bilgileri denetim için okunamadı.", e)
        return False, "Bağlantı denetimi tamamlandı. Sonuç: Sorun bulundu.\n\nAyrıntılar:\nBaşarısız: Kayıtlı hesap bilgisi\n" + baglanti_hatasi_kullanici_mesaji(e)

    eposta = hesap.get("eposta", "")
    sifre = hesap.get("sifre", "")

    if eposta_adresi_gecerli_mi(eposta):
        ekle("Başarılı", "E-posta adresi", "Kayıtlı e-posta adresinin biçimi geçerli görünüyor.")
    else:
        ekle("Başarısız", "E-posta adresi", "E-posta adresi eksik veya geçersiz görünüyor. Örnek biçim: adiniz@gmail.com")

    if sifre:
        if len(sifre) < 12:
            ekle("Uyarı", "Uygulama şifresi", "Uygulama şifresi kısa görünüyor. Gmail uygulama şifreleri genellikle 16 hanelidir.")
        else:
            ekle("Başarılı", "Uygulama şifresi", "Uygulama şifresi okunabildi ve denetim için hazırlandı.")
    else:
        ekle("Başarısız", "Uygulama şifresi", "Kayıtlı uygulama şifresi okunamadı veya boş. Hesap bilgilerini yeniden kaydetmeniz gerekebilir.")

    for not_satiri in hesap.get("notlar", []):
        if "düz metin" in not_satiri.lower():
            ekle("Uyarı", "Şifre saklama biçimi", not_satiri)
        else:
            ekle("Başarılı", "Şifre çözme", not_satiri)

    # E-posta veya şifre yoksa ağ denetimine geçmek yanıltıcı sonuç üretebilir.
    if not eposta or not sifre:
        sonuc = "Sorun bulundu."
        rapor = [f"Bağlantı denetimi tamamlandı. Sonuç: {sonuc}", "", "Ayrıntılar:"] + satirlar
        return False, "\n\n".join(rapor)

    try:
        with socket.create_connection((GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle("Başarılı", "Gmail IMAP 993 TCP erişimi", f"{GMAIL_IMAP_SUNUCU}:{GMAIL_IMAP_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Başarısız", "Gmail IMAP 993 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    try:
        with socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle("Başarılı", "Gmail SMTP 465 TCP erişimi", f"{GMAIL_SMTP_SUNUCU}:{GMAIL_SMTP_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Uyarı", "Gmail SMTP 465 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    try:
        with socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI):
            pass
        ekle("Başarılı", "Gmail SMTP 587 TCP erişimi", f"{GMAIL_SMTP_SUNUCU}:{GMAIL_SMTP_STARTTLS_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Uyarı", "Gmail SMTP 587 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    klasor_haritasi = {}
    try:
        with ImapBaglantisi(
            {"eposta": eposta, "sifre": sifre},
            timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI,
        ) as imap:
            ekle("Başarılı", "IMAP kullanıcı doğrulaması", "Gmail IMAP sunucusu e-posta adresini ve uygulama şifresini kabul etti.")

            tip, veri = imap.list()
            if tip != "OK":
                raise MailHatasi("Gmail klasör listesi alınamadı.")
            klasor_haritasi, ozel_klasorler = imap_klasor_haritasi_olustur(veri)
            ekle("Başarılı", "Gmail klasör listesi", f"Klasör listesi okundu. Tanınan özel arşiv klasörü sayısı: {len(ozel_klasorler)}. Sistem klasörleri aşağıda tek tek seçilerek denetlenecek.")

            # Sistem klasörlerine erişim denetimi.
            for ad in SISTEM_KLASORLERI:
                klasor = klasor_haritasi.get(ad, VARSAYILAN_KLASOR_HARITASI.get(ad, "INBOX"))
                tip, _ = imap.select(klasor, readonly=True)
                if tip != "OK":
                    ekle("Uyarı", f"{ad} klasörü", "Klasör seçilemedi. Gmail hesabınızda bu klasör farklı adla görünüyor olabilir.")
                else:
                    ekle("Başarılı", f"{ad} klasörü", "Klasör seçilebildi.")
    except Exception as e:
        ekle("Başarısız", "IMAP denetimi", baglanti_hatasi_kullanici_mesaji(e))

    try:
        smtp_yontemi = smtp_baglanti_denetle(eposta, sifre)
        ekle("Başarılı", "SMTP kullanıcı doğrulaması", f"Gmail SMTP sunucusu e-posta adresini ve uygulama şifresini kabul etti. Kullanılan yöntem: {smtp_yontemi}. Denetim sırasında e-posta gönderilmedi.")
    except Exception as e:
        ekle("Başarısız", "SMTP denetimi", baglanti_hatasi_kullanici_mesaji(e))

    if hata_sayisi:
        sonuc = "Sorun bulundu."
        basarili = False
    elif uyari_sayisi:
        sonuc = "Başarılı, ancak uyarı var."
        basarili = True
    else:
        sonuc = "Başarılı."
        basarili = True

    rapor = [f"Bağlantı denetimi tamamlandı. Sonuç: {sonuc}"]
    if hata_sayisi:
        rapor.append("Sorun varsa önce e-posta adresinizi, uygulama şifrenizi, internet bağlantınızı, güvenlik duvarınızı ve kurum ağı kısıtlamalarını kontrol edin.")
    rapor.extend(["", "Ayrıntılar:"])
    rapor.extend(satirlar)
    return basarili, "\n\n".join(rapor)
