
# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import email.utils
import os
import socket
import ssl
from email.message import EmailMessage
from email.policy import SMTP

from .attachments import ek_icerik_turu_bul, ek_kayitlari_boyutunu_denetle
from .errors import MailHatasi
from .logger import uyari_kaydet
from .message_parser import adres_basligini_duzenle
from .text_utils import eposta_basligi_tek_satir_yap, guvenli_coz
from .validators import alici_basligini_cozumle
from .vendor import smtplib


GMAIL_SMTP_SUNUCU = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
GMAIL_SMTP_STARTTLS_PORT = 587
BAGLANTI_ZAMAN_ASIMI = 20
BAGLANTI_DENETIM_ZAMAN_ASIMI = 10


def baglanti_hatasi_kullanici_mesaji(hata, varsayilan=None):
    """Teknik bağlantı hatalarını kullanıcıya anlaşılır Türkçe metinle açıklar."""
    if isinstance(hata, MailHatasi):
        return str(hata)
    if isinstance(hata, smtplib.SMTPAuthenticationError):
        return _("SMTP kullanıcı doğrulaması başarısız oldu. E-posta adresi veya uygulama şifresi hatalı olabilir.")
    if isinstance(hata, smtplib.SMTPRecipientsRefused):
        return _("SMTP sunucusu alıcı adreslerini kabul etmedi. Alıcı adreslerini denetleyin.")
    if isinstance(hata, smtplib.SMTPSenderRefused):
        return _("SMTP sunucusu gönderen adresini kabul etmedi. Hesap bilgilerini denetleyin.")
    if isinstance(hata, smtplib.SMTPDataError):
        return _("SMTP sunucusu e-posta verisini kabul etmedi. Gönderim tamamlanamadı.")
    if isinstance(hata, smtplib.SMTPNotSupportedError):
        if "smtputf8" in str(hata or "").lower():
            return (
                _("SMTP sunucusu uluslararası e-posta adreslerini desteklemiyor. "
                "Alıcı adresini ASCII karakterlerle yazmayı deneyin.")
            )
        return _("SMTP sunucusu gerekli güvenli bağlantı veya kullanıcı doğrulama yöntemini desteklemiyor.")

    metin = str(hata or "").lower()
    if isinstance(hata, socket.gaierror) or "getaddrinfo" in metin or "name or service" in metin:
        return _("Sunucu adı çözümlenemedi. İnternet bağlantınızı, DNS ayarlarınızı veya kurum ağı kısıtlamalarını denetleyin.")
    if isinstance(hata, socket.timeout) or "timed out" in metin or "zaman" in metin and "aş" in metin:
        return _("Bağlantı zaman aşımına uğradı. İnternet bağlantınız yavaş olabilir veya kurum ağı Gmail sunucularına erişimi engelliyor olabilir.")
    if "zorla kapatıldı" in metin or "forcibly closed" in metin or "uzaktaki bir ana bilgisayar" in metin:
        return _("Bağlantı sunucu veya aradaki ağ cihazı tarafından oturum aşamasında kapatıldı. Kurum ağı IMAP/SMTP oturumunu kesiyor olabilir.")
    if isinstance(hata, ssl.SSLError) or "ssl" in metin or "certificate" in metin or "sertifika" in metin:
        return _("Güvenli bağlantı kurulamadı. Sertifika denetimi, güvenlik yazılımı veya kurum ağı bağlantıyı etkiliyor olabilir.")
    if isinstance(hata, ConnectionRefusedError) or "refused" in metin:
        return _("Sunucu bağlantıyı reddetti. Güvenlik duvarı, kurum ağı veya geçici sunucu kısıtlaması olabilir.")
    if isinstance(hata, OSError):
        return varsayilan or _("Bağlantı kurulamadı. İnternet bağlantınızı, güvenlik duvarınızı ve kurum ağı ayarlarınızı denetleyin.")
    return varsayilan or _("Beklenmeyen bir bağlantı hatası oluştu. Ayrıntılı denetim için Hesap menüsündeki Bağlantıyı denetle seçeneğini kullanın.")

def _smtp_oturumunu_kapat(smtp):
    """SMTP oturumunu gönderim sonucunu değiştirmeden kapatır."""
    if smtp is None:
        return
    try:
        smtp.quit()
        return
    except Exception as e:
        uyari_kaydet("SMTP çıkış komutu tamamlanamadı; bağlantı doğrudan kapatılacak.", e)
    try:
        smtp.close()
    except Exception as e:
        uyari_kaydet("SMTP bağlantısı kapatılamadı.", e)


def _smtp_465_oturumu_ac(eposta, sifre, timeout):
    smtp = None
    try:
        smtp = smtplib.SMTP_SSL(
            GMAIL_SMTP_SUNUCU,
            GMAIL_SMTP_PORT,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        smtp.login(eposta, sifre)
        return smtp
    except Exception:
        _smtp_oturumunu_kapat(smtp)
        raise


def _smtp_587_oturumu_ac(eposta, sifre, timeout):
    smtp = None
    try:
        smtp = smtplib.SMTP(
            GMAIL_SMTP_SUNUCU,
            GMAIL_SMTP_STARTTLS_PORT,
            timeout=timeout,
        )
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(eposta, sifre)
        return smtp
    except Exception:
        _smtp_oturumunu_kapat(smtp)
        raise


def _smtp_oturumu_ac(eposta, sifre, timeout):
    """İleti gönderilmeden önce 465, gerekirse 587 üzerinden oturum açar."""
    ilk_hata = None
    try:
        return _smtp_465_oturumu_ac(eposta, sifre, timeout), "465 SSL"
    except Exception as e:
        ilk_hata = e
        uyari_kaydet("SMTP 465 SSL oturumu açılamadı; 587 STARTTLS denenecek.", e)

    try:
        return _smtp_587_oturumu_ac(eposta, sifre, timeout), "587 STARTTLS"
    except Exception as ikinci_hata:
        mesaj_465 = baglanti_hatasi_kullanici_mesaji(ilk_hata, "465 SSL yöntemi başarısız oldu.")
        mesaj_587 = baglanti_hatasi_kullanici_mesaji(ikinci_hata, "587 STARTTLS yöntemi başarısız oldu.")
        raise MailHatasi(
            _('SMTP bağlantısı kurulamadı. 465 SSL sonucu: {0} 587 STARTTLS sonucu: {1}').format(mesaj_465, mesaj_587)
        ) from ikinci_hata


def smtp_ssl_ile_gonder(eposta, sifre, alicilar, mesaj):
    """CPython smtplib ile güvenli SMTP oturumu açar ve iletiyi yalnızca bir kez gönderir."""
    smtp = None
    try:
        smtp, _yontem = _smtp_oturumu_ac(eposta, sifre, BAGLANTI_ZAMAN_ASIMI)
        try:
            smtp.send_message(
                mesaj,
                from_addr=eposta,
                to_addrs=list(alicilar or []),
            )
        except smtplib.SMTPServerDisconnected as e:
            raise MailHatasi(
                _("Gönderim sonucu doğrulanamadı. E-posta gönderilmiş olabilir. "
                "Yeniden göndermeden önce Gönderilen E-postalar klasörünü denetleyin.")
            ) from e
        except smtplib.SMTPException as e:
            raise MailHatasi(baglanti_hatasi_kullanici_mesaji(e, "E-posta gönderilemedi.")) from e
        except (socket.timeout, ssl.SSLError, OSError) as e:
            raise MailHatasi(
                _("Gönderim sonucu doğrulanamadı. E-posta gönderilmiş olabilir. "
                "Yeniden göndermeden önce Gönderilen E-postalar klasörünü denetleyin.")
            ) from e
    finally:
        _smtp_oturumunu_kapat(smtp)


def smtp_baglanti_denetle(eposta, sifre):
    """CPython smtplib ile kullanıcı doğrulamasını sınar; e-posta göndermez."""
    smtp = None
    try:
        smtp, yontem = _smtp_oturumu_ac(eposta, sifre, BAGLANTI_DENETIM_ZAMAN_ASIMI)
        return yontem
    finally:
        _smtp_oturumunu_kapat(smtp)


def gonderen_basligini_duzenle(gonderen, gorunen_ad=None):
    """Gönderen başlığını görünen ad varsa Ad <eposta> biçiminde hazırlar."""
    gonderen = str(gonderen or "").strip()
    gorunen_ad = str(gorunen_ad or "").strip()
    if gorunen_ad and gonderen:
        return email.utils.formataddr((gorunen_ad, gonderen))
    return gonderen


def _alici_basligini_dogrula(baslik, alan_adi):
    """Bir alıcı alanındaki bütün girdilerin geçerli olduğunu doğrular."""
    adresler, gecersizler = alici_basligini_cozumle(baslik)
    if gecersizler:
        ozet = ", ".join(gecersizler[:3])
        if len(gecersizler) > 3:
            ozet += f" ve {len(gecersizler) - 3} adres daha"
        raise MailHatasi(_('{0} alanında geçersiz e-posta adresi bulundu: {1}').format(alan_adi, ozet))
    if not adresler:
        raise MailHatasi(_('{0} alanında geçerli e-posta adresi bulunamadı.').format(alan_adi))
    return adresler

def eposta_mesaji_olustur(
    gonderen,
    kime_basligi,
    konu,
    icerik,
    ek_kayitlari,
    ek_basliklar=None,
    taslak=False,
    gorunen_ad=None,
    bilgi_basligi="",
    gizli_basligi="",
):
    """Gönderim veya taslak kaydı için MIME ileti oluşturur."""
    ek_kayitlari_boyutunu_denetle(ek_kayitlari)
    mesaj = EmailMessage(policy=SMTP)
    mesaj["From"] = gonderen_basligini_duzenle(gonderen, gorunen_ad)
    kime_basligi = str(kime_basligi or "").strip()
    if kime_basligi:
        _alici_basligini_dogrula(kime_basligi, "Kime")
        duzenli_kime = adres_basligini_duzenle(kime_basligi)
        mesaj["To"] = duzenli_kime
    bilgi_basligi = str(bilgi_basligi or "").strip()
    if bilgi_basligi:
        _alici_basligini_dogrula(bilgi_basligi, "Bilgi")
        duzenli_bilgi = adres_basligini_duzenle(bilgi_basligi)
        mesaj["Cc"] = duzenli_bilgi
    gizli_basligi = str(gizli_basligi or "").strip()
    if gizli_basligi:
        _alici_basligini_dogrula(gizli_basligi, "Gizli")
        duzenli_gizli = adres_basligini_duzenle(gizli_basligi)
        # Bcc yalnızca taslağın yeniden düzenlenebilmesi için sunucudaki taslakta tutulur.
        # Gerçek gönderimde gizli adresler sadece SMTP teslim listesine verilir.
        if taslak:
            mesaj["Bcc"] = duzenli_gizli
    mesaj["Subject"] = eposta_basligi_tek_satir_yap(konu) or "Konusuz"

    if taslak:
        mesaj["Date"] = email.utils.formatdate(localtime=True)
        mesaj["Message-ID"] = email.utils.make_msgid()
        mesaj["X-Unsent"] = "1"

    for baslik_adi, baslik_degeri in (ek_basliklar or {}).items():
        baslik_degeri = eposta_basligi_tek_satir_yap(baslik_degeri)
        if baslik_adi and baslik_degeri and baslik_adi not in mesaj:
            mesaj[baslik_adi] = baslik_degeri

    mesaj.set_content(icerik or "")

    for kayit in ek_kayitlari or []:
        if isinstance(kayit, str):
            kayit = {"tur": "dosya", "yol": kayit}
        if not isinstance(kayit, dict):
            raise MailHatasi(
                _("Ek kaydı geçersiz. Lütfen eki kaldırıp yeniden ekleyin.")
            )
        tur = kayit.get("tur")
        if tur == "hazir":
            dosya_adi = guvenli_coz(kayit.get("ad") or "ek_dosya")
            veri = kayit.get("veri") or b""
            if not isinstance(veri, (bytes, bytearray)):
                raise MailHatasi(
                    _('Ek verisi geçersiz: {0}. Lütfen eki kaldırıp yeniden ekleyin.').format(dosya_adi)
                )
            if not veri:
                continue
            maintype, subtype = ek_icerik_turu_bul(dosya_adi)
            mesaj.add_attachment(bytes(veri), maintype=maintype, subtype=subtype, filename=dosya_adi)
            continue

        dosya_yolu = kayit.get("yol", "")
        if not os.path.isfile(dosya_yolu):
            raise MailHatasi(_('Ek dosya bulunamadı: {0}').format(os.path.basename(dosya_yolu)))
        maintype, subtype = ek_icerik_turu_bul(dosya_yolu)
        with open(dosya_yolu, "rb") as dosya:
            mesaj.add_attachment(
                dosya.read(),
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(dosya_yolu),
            )
    return mesaj
