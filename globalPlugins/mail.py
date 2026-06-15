# -*- coding: utf-8 -*-
# Engelsiz Mail
# Telif Hakkı (C) 2026 Mehmet Aykurt

import base64
import ctypes
from ctypes import wintypes
import email
import email.utils
from email import policy as email_policy
from email.header import decode_header
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parsedate_to_datetime
import globalPluginHandler
import hashlib
import globalVars
import gui
import html
import json
from logHandler import log
import mimetypes
import os
import quopri
import re
import socket
import ssl
import tempfile
import threading
import time
import webbrowser
import wx
import ui

try:
    import winsound
except Exception:
    winsound = None

try:
    import versionInfo
except Exception:
    versionInfo = None


EKLENTI_ADI = "Engelsiz Mail"
EKLENTI_SURUMU = "1.5.5"  # TODO: Modüler yapıya geçerken manifest.ini ile tek kaynaktan yönetilecek.
AYARLAR_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "ayarlar.json")
REHBER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "adres.json")
KISILER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "kisiler.json")
KLASOR_SAYISI_ONBELLEK_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "klasor_sayilari.json")

GMAIL_IMAP_SUNUCU = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_SUNUCU = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
GMAIL_SMTP_STARTTLS_PORT = 587
BAGLANTI_ZAMAN_ASIMI = 20
VARSAYILAN_MESAJ_SAYISI = 25
EN_AZ_MESAJ_SAYISI = 1
EN_COK_MESAJ_SAYISI = 100
AZAMI_TEK_EK_BOYUTU = 10 * 1024 * 1024
AZAMI_TOPLAM_EK_BOYUTU = 10 * 1024 * 1024
AZAMI_EML_DOSYA_BOYUTU = 50 * 1024 * 1024
AZAMI_EPOSTA_ISLEME_BOYUTU = 30 * 1024 * 1024
AZAMI_EK_ONBELLEK_TEK_BOYUTU = 12 * 1024 * 1024
AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU = 20 * 1024 * 1024
AZAMI_IMAP_YANIT_SATIRI = 5000
AZAMI_IMAP_LITERAL_BOYUTU = 50 * 1024 * 1024
YENILEME_GECIKMESI_MS = 800
BAGLANTI_DENETIM_ZAMAN_ASIMI = 10
SIFRE_DPAPI_ALANI = "sifre_dpapi"
SIFRE_DUZ_METIN_ALANI = "sifre"
SIFRE_DPAPI_ON_EK = "dpapi-v1:"
MESAJ_SAYISI_ALANI = "mesaj_sayisi"
ONIZLEME_ALANI = "onizleme"
SILME_ONAY_ALANI = "silme_onayi"
KALICI_SILME_ONAY_ALANI = "kalici_silme_onayi"
ADRES_OTOMATIK_KAYDET_ALANI = "adres_otomatik_kaydet"
ESCAPE_KAPAT_ALANI = "escape_kapat"
ONIZLEME_KARAKTER_SINIRI = 280
# Liste ön izlemesinde bazı HTML iletilerin ilk bölümü yalnızca head/style içerebilir.
# Daha fazla gövde kırpığı almak, gerçek metne ulaşma şansını artırır; gösterilen metin yine 280 karakterle sınırlıdır.
ONIZLEME_FETCH_BOYUTU = 12000
HTML_TEMIZLE_KARAKTER_SINIRI = 120000
RE_HTML_STYLE_SCRIPT_HEAD = re.compile(r"<(style|script|head)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_HTML_BLOK_ETIKETLERI = re.compile(r"</?(br|p|div|tr|li|h[1-6])[^>]*>", re.IGNORECASE)
RE_HTML_ETIKETLERI = re.compile(r"<[^>]+>")
RE_COKLU_BOSLUK = re.compile(r"[ \t]+")
RE_GRUP_ARACI_GONDEREN = re.compile(
    r"\s+via\s+(groups\.io|google\s+groups|groups\.google\.com)\s*$",
    re.IGNORECASE,
)
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
BILDIRIM_SON_UID_ALANI = "bildirim_son_uid"
BILDIRIM_SON_UID_HESAP_ALANI = "bildirim_son_uid_hesap"
BILDIRIM_UIDVALIDITY_ALANI = "bildirim_uidvalidity"
BILDIRIM_BASLATILDI_ALANI = "bildirim_baslatildi"
BILDIRIM_ARALIK_SECENEKLERI = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
VARSAYILAN_BILDIRIM_ARALIGI = 30
ONERI_GORUS_ALICI = "m.aykurt38@gmail.com"
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

BILDIRIM_YONETICISI = None
BILDIRIM_SOYLE_TIMER = None


class MailHatasi(Exception):
    """Kullanıcıya sade biçimde bildirilebilecek posta işlemi hatası."""


class YerelImapIstemcisi:
    """NVDA ortamında imaplib bulunmadığında kullanılan sınırlı IMAP istemcisi."""

    def __init__(self, sunucu, port, timeout=BAGLANTI_ZAMAN_ASIMI):
        self.sunucu = sunucu
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.dosya = None
        self._etiket_sayaci = 0
        self._baglan()

    def _baglan(self):
        try:
            ctx = ssl.create_default_context()
            ham_soket = socket.create_connection((self.sunucu, self.port), timeout=self.timeout)
            self.sock = ctx.wrap_socket(ham_soket, server_hostname=self.sunucu)
            self.sock.settimeout(self.timeout)
            self.dosya = self.sock.makefile("rb")
            karsilama = self._satir_oku("IMAP sunucusundan karşılama yanıtı alınamadı.")
            if not karsilama:
                raise MailHatasi("IMAP sunucusundan yanıt alınamadı.")
        except MailHatasi:
            raise
        except socket.timeout as e:
            raise MailHatasi("IMAP sunucusu zamanında yanıt vermedi. İnternet bağlantınızı veya kurum ağı kısıtlamalarını kontrol edin.") from e
        except ssl.SSLError as e:
            raise MailHatasi("IMAP sunucusuyla güvenli bağlantı kurulamadı. Kurum ağı, güvenlik yazılımı veya sertifika denetimi bağlantıyı kesiyor olabilir.") from e
        except OSError as e:
            raise MailHatasi("IMAP sunucusuna bağlantı kurulamadı. İnternet bağlantınızı, güvenlik duvarınızı veya kurum ağı ayarlarınızı kontrol edin.") from e

    def _satir_oku(self, hata_mesaji):
        try:
            satir = self.dosya.readline()
        except socket.timeout as e:
            raise MailHatasi("IMAP sunucusu zamanında yanıt vermedi. Bağlantı zaman aşımına uğradı.") from e
        except OSError as e:
            raise MailHatasi(hata_mesaji) from e
        if not satir:
            raise MailHatasi(hata_mesaji)
        return satir

    def _veri_oku(self, uzunluk):
        try:
            uzunluk = int(uzunluk)
        except Exception as e:
            raise MailHatasi("IMAP sunucusundan okunacak veri uzunluğu geçersiz.") from e

        if uzunluk < 0:
            raise MailHatasi("IMAP sunucusundan okunacak veri uzunluğu geçersiz.")
        if uzunluk == 0:
            return b""

        parcalar = []
        okunan = 0
        try:
            while okunan < uzunluk:
                veri = self.dosya.read(uzunluk - okunan)
                if not veri:
                    raise MailHatasi("IMAP sunucusundan beklenen veri eksik alındı. Bağlantı kesilmiş olabilir.")
                parcalar.append(veri)
                okunan += len(veri)
        except socket.timeout as e:
            raise MailHatasi("IMAP sunucusundan veri okunurken zaman aşımı oluştu.") from e
        except OSError as e:
            raise MailHatasi("IMAP sunucusundan veri okunamadı. Bağlantı kesilmiş olabilir.") from e

        return b"".join(parcalar)

    def _yeni_etiket(self):
        self._etiket_sayaci += 1
        return f"A{self._etiket_sayaci:04d}"

    def _tirnakla(self, metin):
        metin = str(metin)
        if any(ord(karakter) < 32 for karakter in metin):
            raise MailHatasi("IMAP komut değeri geçersiz denetim karakteri içeriyor.")
        metin = metin.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{metin}"'

    def _yanit_oku(self, etiket):
        etiket_bytes = etiket.encode("ascii", errors="ignore")
        veriler = []
        son_satir = b""

        for _sayac in range(AZAMI_IMAP_YANIT_SATIRI):
            satir = self._satir_oku("IMAP bağlantısı beklenmedik biçimde kapandı.")

            eslesme = re.search(br"\{(\d+)\}\r?\n$", satir)
            if eslesme:
                uzunluk = int(eslesme.group(1))
                if uzunluk > AZAMI_IMAP_LITERAL_BOYUTU:
                    raise MailHatasi("IMAP sunucusundan beklenenden büyük veri yanıtı alındı.")
                ham = self._veri_oku(uzunluk)
                veriler.append((satir.rstrip(b"\r\n"), ham))
                continue

            temiz_satir = satir.rstrip(b"\r\n")
            veriler.append(temiz_satir)
            if temiz_satir.startswith(etiket_bytes + b" ") or temiz_satir == etiket_bytes:
                son_satir = temiz_satir
                break
        else:
            raise MailHatasi("IMAP sunucusundan çok uzun veya hatalı yanıt alındı.")

        parcalar = son_satir.decode("utf-8", errors="replace").split()
        durum = parcalar[1].upper() if len(parcalar) > 1 else "NO"
        return durum, veriler

    def _komut(self, komut):
        etiket = self._yeni_etiket()
        try:
            self.sock.sendall(f"{etiket} {komut}\r\n".encode("utf-8"))
        except socket.timeout as e:
            raise MailHatasi("IMAP komutu gönderilirken zaman aşımı oluştu.") from e
        except OSError as e:
            raise MailHatasi("IMAP komutu gönderilemedi. Bağlantı kesilmiş olabilir.") from e
        return self._yanit_oku(etiket)

    def login(self, eposta, sifre):
        return self._komut(f"LOGIN {self._tirnakla(eposta)} {self._tirnakla(sifre)}")

    def capability(self):
        return self._komut("CAPABILITY")

    def logout(self):
        try:
            return self._komut("LOGOUT")
        finally:
            try:
                if self.dosya:
                    self.dosya.close()
            except Exception as e:
                hata_kaydet("IMAP dosya nesnesi kapatılamadı.", e)
            try:
                if self.sock:
                    self.sock.close()
            except Exception as e:
                hata_kaydet("IMAP soketi kapatılamadı.", e)

    def list(self):
        return self._komut('LIST "" "*"')

    def select(self, klasor, readonly=False):
        komut = "EXAMINE" if readonly else "SELECT"
        return self._komut(f"{komut} {klasor}")

    def status(self, klasor, ogeler="(MESSAGES UNSEEN)"):
        """Seçilen klasörün toplam ve okunmamış ileti bilgisini alır."""
        ogeler = str(ogeler or "(MESSAGES UNSEEN)").strip()
        if not ogeler.startswith("("):
            ogeler = "(" + ogeler + ")"
        return self._komut(f"STATUS {klasor} {ogeler}")

    def uid(self, *args):
        temiz_argumanlar = [str(arg) for arg in args if arg is not None]
        return self._komut("UID " + " ".join(temiz_argumanlar))

    def delete(self, klasor):
        return self._komut(f"DELETE {klasor}")

    def create(self, klasor):
        return self._komut(f"CREATE {klasor}")

    def rename(self, eski_klasor, yeni_klasor):
        return self._komut(f"RENAME {eski_klasor} {yeni_klasor}")

    def expunge(self):
        return self._komut("EXPUNGE")

    def close(self):
        return self._komut("CLOSE")

    def append(self, klasor, bayraklar, tarih, mesaj_verisi):
        """IMAP APPEND komutuyla klasöre ham ileti ekler."""
        if isinstance(mesaj_verisi, str):
            mesaj_verisi = mesaj_verisi.encode("utf-8")
        mesaj_verisi = mesaj_verisi or b""

        etiket = self._yeni_etiket()
        bayrak_parcasi = f" {bayraklar}" if bayraklar else ""
        tarih_parcasi = f" {self._tirnakla(tarih)}" if tarih else ""
        komut = f"{etiket} APPEND {klasor}{bayrak_parcasi}{tarih_parcasi} {{{len(mesaj_verisi)}}}\r\n"
        self.sock.sendall(komut.encode("utf-8"))

        satir = self._satir_oku("IMAP sunucusundan taslak kaydetme yanıtı alınamadı.")

        temiz_satir = satir.rstrip(b"\r\n")
        if temiz_satir.startswith(b"+"):
            self.sock.sendall(mesaj_verisi + b"\r\n")
            return self._yanit_oku(etiket)

        # Bazı hata durumlarında sunucu devam yanıtı yerine doğrudan son yanıt döndürebilir.
        etiket_bytes = etiket.encode("ascii", errors="ignore")
        veriler = [temiz_satir]
        if temiz_satir.startswith(etiket_bytes + b" ") or temiz_satir == etiket_bytes:
            parcalar = temiz_satir.decode("utf-8", errors="replace").split()
            durum = parcalar[1].upper() if len(parcalar) > 1 else "NO"
            return durum, veriler

        durum, devam = self._yanit_oku(etiket)
        return durum, veriler + devam


class ImapBaglantisi:
    """IMAP bağlantısını güvenli biçimde açıp kapatan yardımcı sınıf."""

    def __init__(self, ayarlar):
        self.ayarlar = ayarlar
        self.imap = None

    def __enter__(self):
        eposta = self.ayarlar.get("eposta", "")
        sifre = self.ayarlar.get("sifre", "")
        if not eposta or not sifre:
            raise MailHatasi("Hesap bilgileri eksik.")
        self.imap = YerelImapIstemcisi(GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT, BAGLANTI_ZAMAN_ASIMI)
        tip, _veri = self.imap.login(eposta, sifre)
        if tip != "OK":
            raise MailHatasi("Gmail hesabına giriş yapılamadı. E-posta adresi veya uygulama şifresi hatalı olabilir.")
        return self.imap

    def __exit__(self, exc_type, exc, tb):
        if not self.imap:
            return
        try:
            self.imap.logout()
        except Exception as e:
            hata_kaydet("IMAP oturumu kapatılırken hata oluştu.", e)


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
    imap_ok_mu(tip, "IMAP sunucu yetenekleri alınamadı.")
    return imap_yeteneklerini_ayristir(veri)


def imap_gmail_etiket_destegini_dogrula(imap):
    """Gmail X-GM-LABELS desteği yoksa güvenli taşıma/silme işlemlerini durdurur."""
    yetenekler = imap_yeteneklerini_al(imap)
    if "X-GM-EXT-1" not in yetenekler:
        raise MailHatasi(
            "Gmail etiket desteği algılanamadı. Güvenli taşıma, arşivleme veya Çöp Kutusu'na taşıma işlemi yapılamadı. "
            "Lütfen bağlantıyı denetleyin ve hesabın Gmail IMAP desteğini kontrol edin."
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
            raise MailHatasi("Geçersiz e-posta kimliği algılandı. İşlem güvenlik nedeniyle durduruldu.")
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
        raise MailHatasi("İşlem yapılacak e-posta bulunamadı.")
    if not etiket:
        return False
    if islem not in ("+", "-"):
        raise MailHatasi("Geçersiz Gmail etiket işlemi.")
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
        raise MailHatasi("Kaynak klasörden kaldırılacak e-posta bulunamadı.")
    tip, _veri = imap.uid("STORE", uidler, "+FLAGS.SILENT", "(\\Deleted)")
    imap_ok_mu(tip, "E-postalar kaynak klasörden kaldırılmak üzere işaretlenemedi.")
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
        raise MailHatasi("Silinecek e-posta bulunamadı.")
    tip, _veri = imap.uid("STORE", uidler, "+FLAGS.SILENT", "(\\Deleted)")
    imap_ok_mu(tip, "E-posta kalıcı silme için işaretlenemedi.")
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
        raise MailHatasi("Kalıcı silinecek e-posta bulunamadı.")

    sonuc = {}
    for uid_parcasi in uid_listesini_parcala(uid_listesi, 50):
        uid_kumesi = uid_kumesi_hazirla(uid_parcasi, "Kalıcı silinecek e-posta bulunamadı.")
        tip, veri = imap.uid("FETCH", uid_kumesi, "(X-GM-MSGID)")
        imap_ok_mu(tip, "E-postaların Gmail ileti kimlikleri alınamadı.")
        for satir in imap_fetch_metin_satirlari(veri):
            uid_eslesme = re.search(r"\bUID\s+(\d+)\b", satir, flags=re.IGNORECASE)
            mesaj_eslesme = re.search(r"\bX-GM-MSGID\s+(\d+)\b", satir, flags=re.IGNORECASE)
            if uid_eslesme and mesaj_eslesme:
                sonuc[uid_eslesme.group(1)] = mesaj_eslesme.group(1)

    eksikler = [uid for uid in uid_listesi if uid not in sonuc]
    if eksikler:
        raise MailHatasi("E-postaların Gmail ileti kimliği doğrulanamadı. Kalıcı silme güvenlik nedeniyle durduruldu.")
    return sonuc


def imap_uid_search_sonucu_uidleri_al(search_sonucu):
    """UID SEARCH yanıtındaki UID değerlerini döndürür."""
    uidler = []
    gorulen = set()
    for satir in imap_fetch_metin_satirlari(search_sonucu):
        eslesme = re.search(r"\bSEARCH\b(.*)$", satir, flags=re.IGNORECASE)
        if not eslesme:
            continue
        for uid in re.findall(r"\b\d+\b", eslesme.group(1)):
            if uid not in gorulen:
                uidler.append(uid)
                gorulen.add(uid)
    return uidler


def imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru):
    """X-GM-MSGID değerlerini Çöp Kutusu'ndaki UID değerlerine çevirir."""
    tip, _veri = imap.select(cop_klasoru, readonly=False)
    imap_ok_mu(tip, "Çöp Kutusu kalıcı silme için açılamadı.")

    uidler = []
    bulunan_msgidler = set()
    for msgid in msgidleri or []:
        msgid = str(msgid or "").strip()
        if not msgid.isdigit():
            continue
        tip, veri = imap.uid("SEARCH", "X-GM-MSGID", msgid)
        imap_ok_mu(tip, "E-posta Çöp Kutusu'nda kalıcı silme için bulunamadı.")
        bulunan_uidler = imap_uid_search_sonucu_uidleri_al(veri)
        if bulunan_uidler:
            bulunan_msgidler.add(msgid)
            uidler.extend(bulunan_uidler)

    beklenen_msgidler = {str(msgid).strip() for msgid in msgidleri or [] if str(msgid).strip().isdigit()}
    if not uidler or bulunan_msgidler != beklenen_msgidler:
        raise MailHatasi("E-posta Çöp Kutusu'nda doğrulanamadı. Kalıcı silme güvenlik nedeniyle tamamlanmadı.")
    return uidler


def imap_gmail_msgidleri_kalici_sil(imap, msgidleri, cop_klasoru, hata_mesaji="E-posta kalıcı olarak silinemedi."):
    """Gmail ileti kimliklerini Çöp Kutusu üzerinden kalıcı olarak siler."""
    try:
        cop_uidleri = imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru)
    except MailHatasi:
        # Gmail etiketi yeni eklendiyse Çöp Kutusu görünümünün aynı oturumda güncellenmesi kısa gecikebilir.
        time.sleep(0.5)
        cop_uidleri = imap_gmail_msgidleri_copte_uidlere_cevir(imap, msgidleri, cop_klasoru)

    uid_kumesi = uid_kumesi_hazirla(cop_uidleri, "Kalıcı silinecek e-posta Çöp Kutusu'nda bulunamadı.")
    return imap_uidleri_kalici_sil(imap, uid_kumesi, hata_mesaji)


def hata_kaydet(baslik, hata=None):
    """Teknik ayrıntıları NVDA günlüğüne yazar; kullanıcıya ham hata göstermez."""
    try:
        if hata:
            log.exception(f"{EKLENTI_ADI}: {baslik}")
        else:
            log.debug(f"{EKLENTI_ADI}: {baslik}")
    except Exception:
        pass


def pencere_kullanilabilir_mi(pencere):
    """Kapanmış veya yok edilmekte olan wx pencerelerine geri dönüşü engeller."""
    try:
        if pencere is None:
            return False
        if getattr(pencere, "_kapatildi", False):
            return False
        if hasattr(pencere, "IsBeingDeleted") and pencere.IsBeingDeleted():
            return False
        return True
    except Exception:
        return False


def guvenli_call_after(pencere, islev, *args, **kwargs):
    """Arka plan işlemlerinden arayüze güvenli dönüş yapar."""
    def calistir():
        if not pencere_kullanilabilir_mi(pencere):
            return
        try:
            islev(*args, **kwargs)
        except Exception as e:
            hata_kaydet("Arayüz güncellemesi yapılamadı.", e)

    wx.CallAfter(calistir)


def guvenli_modal_goster(pencere, odak_denetcimi=None, ebeveyn=None):
    """Modal pencereyi gösterir; kapatılırken odağı pencere yok edilmeden hedef denetime döndürür."""
    sonuc = wx.ID_CANCEL
    try:
        sonuc = pencere.ShowModal()
        if odak_denetcimi is not None:
            try:
                hedef_pencere = ebeveyn if ebeveyn is not None else odak_denetcimi
                if pencere_kullanilabilir_mi(hedef_pencere):
                    try:
                        hedef_pencere.Raise()
                    except Exception:
                        pass
                    try:
                        odak_denetcimi.SetFocus()
                    except Exception as e:
                        hata_kaydet("Modal pencere sonrası odak denetime verilemedi.", e)
            except Exception as e:
                hata_kaydet("Modal pencere sonrası odak dönüşü yapılamadı.", e)
        return sonuc
    finally:
        try:
            pencere.Destroy()
        except Exception as e:
            hata_kaydet("Modal pencere yok edilemedi.", e)


def odagi_listeye_guvenli_dondur(pencere, denetim):
    """Dialog kapanışlarından sonra odağı ana listeye güvenli biçimde döndürür."""
    def odaklan():
        try:
            if pencere_kullanilabilir_mi(pencere):
                try:
                    pencere.Raise()
                except Exception:
                    pass
            if pencere_kullanilabilir_mi(denetim):
                denetim.SetFocus()
        except Exception as e:
            hata_kaydet("Odağın listeye dönmesi sağlanamadı.", e)

    try:
        wx.CallAfter(odaklan)
    except Exception as e:
        hata_kaydet("Odak dönüşü planlanamadı.", e)


def bildirim_soyle(mesaj, gecikme_ms=350):
    """Menü kapanışı veya hızlı arayüz yenilemesi sırasında NVDA konuşması kesilmesin diye bildirimi geciktirir."""
    global BILDIRIM_SOYLE_TIMER

    def soyle_ve_temizle():
        global BILDIRIM_SOYLE_TIMER
        BILDIRIM_SOYLE_TIMER = None
        ui.message(mesaj)

    try:
        try:
            if BILDIRIM_SOYLE_TIMER:
                BILDIRIM_SOYLE_TIMER.Stop()
        except Exception as e:
            hata_kaydet("Bekleyen konuşma zamanlayıcısı durdurulamadı.", e)
        BILDIRIM_SOYLE_TIMER = None

        if gecikme_ms and gecikme_ms > 0:
            BILDIRIM_SOYLE_TIMER = wx.CallLater(int(gecikme_ms), soyle_ve_temizle)
        else:
            ui.message(mesaj)
    except Exception as e:
        hata_kaydet("Bildirim verilemedi.", e)



def arka_planda_calistir(hedef, *args):
    thread = threading.Thread(target=hedef, args=args, daemon=True)
    thread.start()
    return thread


def bozuk_json_dosyasini_yedekle(dosya_yolu):
    """Okunamayan JSON dosyasını silmek yerine .bozuk uzantılı yedeğe taşır."""
    try:
        if not dosya_yolu or not os.path.exists(dosya_yolu):
            return
        temel_yedek_yolu = dosya_yolu + ".bozuk"
        yedek_yolu = temel_yedek_yolu
        sayac = 1
        while os.path.exists(yedek_yolu):
            sayac += 1
            yedek_yolu = f"{temel_yedek_yolu}.{sayac}"
        os.replace(dosya_yolu, yedek_yolu)
        hata_kaydet(f"Bozuk JSON dosyası yedeklendi: {yedek_yolu}")
    except Exception as e:
        hata_kaydet("Bozuk JSON dosyası yedeklenemedi.", e)


def guvenli_json_oku(dosya_yolu, varsayilan):
    try:
        if not os.path.exists(dosya_yolu):
            return varsayilan
        with open(dosya_yolu, "r", encoding="utf-8") as dosya:
            veri = json.load(dosya)
        return veri if isinstance(veri, type(varsayilan)) else varsayilan
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
        hata_kaydet(f"JSON dosyası okunamadı: {dosya_yolu}", e)
        bozuk_json_dosyasini_yedekle(dosya_yolu)
        return varsayilan


def ayar_kopyasi_olustur(ayarlar):
    """Ayar yazmadan önce eski düz metin şifre alanını temizleyen güvenli kopya üretir."""
    yeni_ayarlar = dict(ayarlar) if isinstance(ayarlar, dict) else {}
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return yeni_ayarlar


def guvenli_json_yaz(dosya_yolu, veri):
    klasor = os.path.dirname(dosya_yolu)
    gecici_yol = None
    try:
        os.makedirs(klasor, exist_ok=True)
        fd, gecici_yol = tempfile.mkstemp(prefix="engelsizmail_", suffix=".tmp", dir=klasor)
        with os.fdopen(fd, "w", encoding="utf-8") as dosya:
            json.dump(veri, dosya, ensure_ascii=False, indent=2)
            dosya.flush()
            try:
                os.fsync(dosya.fileno())
            except OSError:
                pass
        os.replace(gecici_yol, dosya_yolu)
        return True
    except (OSError, TypeError, ValueError) as e:
        hata_kaydet(f"JSON dosyası yazılamadı: {dosya_yolu}", e)
        if gecici_yol:
            try:
                os.remove(gecici_yol)
            except OSError:
                pass
        return False


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


def mesaj_sayisi_metnini_dogrula(metin):
    """Ayar penceresindeki mesaj sayısı alanını doğrular."""
    metin = str(metin or "").strip()
    if not metin:
        raise MailHatasi("Listelenecek e-posta sayısı boş bırakılamaz.")
    try:
        sayi = int(metin)
    except Exception as e:
        raise MailHatasi("Listelenecek e-posta sayısı yalnızca rakamlardan oluşmalıdır.") from e
    if sayi < EN_AZ_MESAJ_SAYISI or sayi > EN_COK_MESAJ_SAYISI:
        raise MailHatasi(f"Listelenecek e-posta sayısı {EN_AZ_MESAJ_SAYISI} ile {EN_COK_MESAJ_SAYISI} arasında olmalıdır.")
    return sayi


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.c_void_p),
    ]


def _dpapi_modullerini_al():
    """Windows DPAPI işlevlerini döndürür."""
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        raise MailHatasi("Windows DPAPI bu ortamda kullanılamıyor.")

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def _blob_olustur(veri):
    tampon = ctypes.create_string_buffer(veri)
    blob = _DATA_BLOB(len(veri), ctypes.cast(tampon, ctypes.c_void_p))
    return blob, tampon


def _windows_hatasi(mesaj):
    hata_kodu = ctypes.get_last_error()
    if hata_kodu:
        return f"{mesaj} Windows hata kodu: {hata_kodu}."
    return mesaj


def uygulama_sifresini_sifrele(sifre):
    """Google uygulama şifresini Windows kullanıcı hesabına bağlı biçimde şifreler."""
    sifre = str(sifre or "").strip().replace(" ", "")
    if not sifre:
        return ""

    crypt32, kernel32 = _dpapi_modullerini_al()
    veri = sifre.encode("utf-8")
    giris_blob, _tampon = _blob_olustur(veri)
    cikis_blob = _DATA_BLOB()

    sonuc = crypt32.CryptProtectData(
        ctypes.byref(giris_blob),
        EKLENTI_ADI,
        None,
        None,
        None,
        0,
        ctypes.byref(cikis_blob),
    )
    if not sonuc:
        raise MailHatasi(_windows_hatasi("Uygulama şifresi şifrelenemedi."))

    try:
        sifreli_veri = ctypes.string_at(cikis_blob.pbData, cikis_blob.cbData)
    finally:
        if cikis_blob.pbData:
            kernel32.LocalFree(cikis_blob.pbData)

    return SIFRE_DPAPI_ON_EK + base64.b64encode(sifreli_veri).decode("ascii")


def uygulama_sifresini_coz(sifreli_deger):
    """Windows DPAPI ile saklanan Google uygulama şifresini çözer."""
    sifreli_deger = str(sifreli_deger or "").strip()
    if not sifreli_deger:
        return ""
    if not sifreli_deger.startswith(SIFRE_DPAPI_ON_EK):
        raise MailHatasi("Uygulama şifresi desteklenmeyen bir biçimde saklanmış.")

    try:
        sifreli_veri = base64.b64decode(sifreli_deger[len(SIFRE_DPAPI_ON_EK):].encode("ascii"), validate=True)
    except Exception as e:
        raise MailHatasi("Kayıtlı uygulama şifresi okunamadı.") from e

    crypt32, kernel32 = _dpapi_modullerini_al()
    giris_blob, _tampon = _blob_olustur(sifreli_veri)
    cikis_blob = _DATA_BLOB()

    sonuc = crypt32.CryptUnprotectData(
        ctypes.byref(giris_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(cikis_blob),
    )
    if not sonuc:
        raise MailHatasi(_windows_hatasi("Kayıtlı uygulama şifresi çözülemedi."))

    try:
        duz_veri = ctypes.string_at(cikis_blob.pbData, cikis_blob.cbData)
    finally:
        if cikis_blob.pbData:
            kernel32.LocalFree(cikis_blob.pbData)

    return duz_veri.decode("utf-8", errors="replace").strip().replace(" ", "")


def _duz_metin_sifreyi_sifreliye_tasi(ayarlar, eposta, sifre):
    """Eski ayar dosyasındaki düz metin şifreyi DPAPI alanına taşır."""
    if not sifre:
        return
    try:
        yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
        yeni_ayarlar["eposta"] = eposta
        yeni_ayarlar[SIFRE_DPAPI_ALANI] = uygulama_sifresini_sifrele(sifre)
        yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
        guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)
    except Exception as e:
        hata_kaydet("Düz metin uygulama şifresi şifreli alana taşınamadı.", e)


def ayarlari_yukle():
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    eposta = str(ayarlar.get("eposta", "")).strip()
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
        "sifre": sifre,
        MESAJ_SAYISI_ALANI: mesaj_sayisi,
    }


def ayarlari_kaydet(eposta, sifre, mesaj_sayisi=None):
    eposta = str(eposta or "").strip()
    sifre = str(sifre or "").strip().replace(" ", "")
    try:
        sifreli_deger = uygulama_sifresini_sifrele(sifre)
    except Exception as e:
        hata_kaydet("Uygulama şifresi şifrelenemedi.", e)
        return False

    mevcut_ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(mevcut_ayarlar, dict):
        mevcut_ayarlar = {}

    if mesaj_sayisi is None:
        mesaj_sayisi = mesaj_sayisini_duzenle(mevcut_ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI))
    else:
        mesaj_sayisi = mesaj_sayisini_duzenle(mesaj_sayisi)

    yeni_ayarlar = ayar_kopyasi_olustur(mevcut_ayarlar)
    eski_eposta = str(mevcut_ayarlar.get("eposta", "") or "").strip().lower()
    yeni_eposta = eposta.lower()
    if eski_eposta and eski_eposta != yeni_eposta:
        for alan in (BILDIRIM_SON_UID_ALANI, BILDIRIM_SON_UID_HESAP_ALANI, BILDIRIM_UIDVALIDITY_ALANI, BILDIRIM_BASLATILDI_ALANI):
            yeni_ayarlar.pop(alan, None)
    yeni_ayarlar["eposta"] = eposta
    yeni_ayarlar[SIFRE_DPAPI_ALANI] = sifreli_deger
    yeni_ayarlar[MESAJ_SAYISI_ALANI] = mesaj_sayisi
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def mesaj_sayisini_kaydet(mesaj_sayisi):
    """Listelenecek e-posta sayısını hesap bilgilerine dokunmadan kaydeder."""
    mevcut_ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(mevcut_ayarlar, dict):
        mevcut_ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(mevcut_ayarlar)
    yeni_ayarlar[MESAJ_SAYISI_ALANI] = mesaj_sayisini_duzenle(mesaj_sayisi)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def onizleme_ayari_yukle():
    """E-posta listesinde ön izleme okunup okunmayacağını döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False
    return bool(ayarlar.get(ONIZLEME_ALANI, False))


def onizleme_ayari_kaydet(etkin):
    """Ön izleme ayarını hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[ONIZLEME_ALANI] = bool(etkin)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def silme_onayi_ayari_yukle():
    """E-posta silerken kullanıcıdan onay istenip istenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(SILME_ONAY_ALANI, True))


def silme_onayi_ayari_kaydet(etkin):
    """Silme onayı ayarını hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[SILME_ONAY_ALANI] = bool(etkin)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def kalici_silme_onayi_ayari_yukle():
    """Shift+Delete ile kalıcı silerken onay istenip istenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(KALICI_SILME_ONAY_ALANI, True))


def kalici_silme_onayi_ayari_kaydet(etkin):
    """Kalıcı silme onayı ayarını hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[KALICI_SILME_ONAY_ALANI] = bool(etkin)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def adres_otomatik_kaydet_ayari_yukle():
    """Gönderilen alıcı adreslerinin adres geçmişine otomatik eklenip eklenmeyeceğini döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return True
    return bool(ayarlar.get(ADRES_OTOMATIK_KAYDET_ALANI, True))


def adres_otomatik_kaydet_ayari_kaydet(etkin):
    """Gönderilen alıcı adreslerini otomatik kaydetme ayarını saklar."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[ADRES_OTOMATIK_KAYDET_ALANI] = bool(etkin)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def escape_kapat_ayari_yukle():
    """Escape tuşunun ana Engelsiz Mail penceresini kapatıp kapatmayacağını döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        return False
    return bool(ayarlar.get(ESCAPE_KAPAT_ALANI, False))


def escape_kapat_ayari_kaydet(etkin):
    """Escape ile kapatma ayarını hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[ESCAPE_KAPAT_ALANI] = bool(etkin)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def bildirim_ses_turu_duzenle(deger):
    """Bildirim ses türünü güvenli değerlerden birine çeker."""
    deger = str(deger or "").strip().lower()
    if deger == BILDIRIM_SES_TURU_DOSYA:
        return BILDIRIM_SES_TURU_DOSYA
    return BILDIRIM_SES_TURU_SISTEM


def bildirim_ses_dosyasi_duzenle(dosya_yolu):
    """Kullanıcı tanımlı bildirim sesi dosya yolunu temizler."""
    dosya_yolu = str(dosya_yolu or "").strip()
    if not dosya_yolu:
        return ""
    return dosya_yolu


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

    return {
        BILDIRIM_ETKIN_ALANI: bool(ayarlar.get(BILDIRIM_ETKIN_ALANI, False)),
        BILDIRIM_ARALIK_ALANI: bildirim_araligini_duzenle(
            ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI)
        ),
        BILDIRIM_SES_ALANI: bool(ayarlar.get(BILDIRIM_SES_ALANI, True)),
        BILDIRIM_SES_TURU_ALANI: bildirim_ses_turu_duzenle(
            ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        ),
        BILDIRIM_SES_DOSYASI_ALANI: bildirim_ses_dosyasi_duzenle(
            ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, "")
        ),
        BILDIRIM_MESAJ_ALANI: bool(ayarlar.get(BILDIRIM_MESAJ_ALANI, True)),
        BILDIRIM_GONDEREN_ALANI: bool(ayarlar.get(BILDIRIM_GONDEREN_ALANI, False)),
        BILDIRIM_KONU_ALANI: bool(ayarlar.get(BILDIRIM_KONU_ALANI, False)),
    }


def bildirim_ayarlari_kaydet(
    etkin,
    aralik,
    sesle_bildir,
    ses_turu,
    ses_dosyasi,
    mesajla_bildir,
    gonderen_bildir,
    konu_bildir,
):
    """Bildirim ayarlarını hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar[BILDIRIM_ETKIN_ALANI] = bool(etkin)
    yeni_ayarlar[BILDIRIM_ARALIK_ALANI] = bildirim_araligini_duzenle(aralik)
    yeni_ayarlar[BILDIRIM_SES_ALANI] = bool(sesle_bildir)
    yeni_ayarlar[BILDIRIM_SES_TURU_ALANI] = bildirim_ses_turu_duzenle(ses_turu)
    yeni_ayarlar[BILDIRIM_SES_DOSYASI_ALANI] = bildirim_ses_dosyasi_duzenle(ses_dosyasi)
    yeni_ayarlar[BILDIRIM_MESAJ_ALANI] = bool(mesajla_bildir)
    yeni_ayarlar[BILDIRIM_GONDEREN_ALANI] = bool(gonderen_bildir)
    yeni_ayarlar[BILDIRIM_KONU_ALANI] = bool(konu_bildir)
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)




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
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    if yazi_tipi is not None:
        yazi_tipi = str(yazi_tipi or "").strip()
        if yazi_tipi:
            yeni_ayarlar[GORUNUM_YAZI_TIPI_ALANI] = yazi_tipi
        else:
            yeni_ayarlar.pop(GORUNUM_YAZI_TIPI_ALANI, None)

    if yazi_boyutu is not None:
        try:
            yazi_boyutu = int(str(yazi_boyutu).strip())
        except Exception:
            raise MailHatasi("Yazı tipi boyutu yalnızca rakamlardan oluşmalıdır.")
        if yazi_boyutu < GORUNUM_YAZI_BOYUTU_EN_AZ or yazi_boyutu > GORUNUM_YAZI_BOYUTU_EN_COK:
            raise MailHatasi(f"Yazı tipi boyutu {GORUNUM_YAZI_BOYUTU_EN_AZ} ile {GORUNUM_YAZI_BOYUTU_EN_COK} arasında olmalıdır.")
        yeni_ayarlar[GORUNUM_YAZI_BOYUTU_ALANI] = yazi_boyutu

    if yazi_stili is not None:
        yazi_stili = str(yazi_stili or "").strip()
        if yazi_stili not in GORUNUM_YAZI_STILI_SECENEKLERI:
            raise MailHatasi("Geçersiz yazı stili seçildi.")
        yeni_ayarlar[GORUNUM_YAZI_STILI_ALANI] = yazi_stili

    if metin_rengi is not None:
        metin_rengi = str(metin_rengi or "").strip()
        if metin_rengi not in GORUNUM_METIN_RENKLERI:
            raise MailHatasi("Geçersiz metin rengi seçildi.")
        yeni_ayarlar[GORUNUM_METIN_RENGI_ALANI] = metin_rengi

    if arka_plan_rengi is not None:
        arka_plan_rengi = str(arka_plan_rengi or "").strip()
        if arka_plan_rengi not in GORUNUM_ARKA_PLAN_RENKLERI:
            raise MailHatasi("Geçersiz arka plan rengi seçildi.")
        yeni_ayarlar[GORUNUM_ARKA_PLAN_RENGI_ALANI] = arka_plan_rengi

    if sistem_renkleri is not None:
        yeni_ayarlar[GORUNUM_SISTEM_RENKLERI_ALANI] = bool(sistem_renkleri)

    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def gorunum_ayarlari_sifirla():
    """Tüm görünüm ayarlarını varsayılana döndürür."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}
    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
    yeni_ayarlar.pop(GORUNUM_YAZI_TIPI_ALANI, None)
    yeni_ayarlar.pop(GORUNUM_YAZI_BOYUTU_ALANI, None)
    yeni_ayarlar.pop(GORUNUM_YAZI_STILI_ALANI, None)
    yeni_ayarlar.pop(GORUNUM_METIN_RENGI_ALANI, None)
    yeni_ayarlar.pop(GORUNUM_ARKA_PLAN_RENGI_ALANI, None)
    yeni_ayarlar.pop(GORUNUM_SISTEM_RENKLERI_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def gorunum_fontu_olustur(mevcut_font=None):
    """Görünüm ayarlarına göre wx.Font üretir. Ayar yoksa mevcut font korunur."""
    try:
        ayarlar = gorunum_ayarlari_yukle()
        yazi_tipi = ayarlar.get(GORUNUM_YAZI_TIPI_ALANI, "")
        yazi_boyutu = ayarlar.get(GORUNUM_YAZI_BOYUTU_ALANI, 0)
        yazi_stili = ayarlar.get(GORUNUM_YAZI_STILI_ALANI, "")

        temel_font = mevcut_font
        if temel_font is None or not temel_font.IsOk():
            temel_font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

        nokta = yazi_boyutu or temel_font.GetPointSize()
        if not nokta or nokta <= 0:
            nokta = 10

        yuz = yazi_tipi or temel_font.GetFaceName()
        stil = temel_font.GetStyle()
        agirlik = temel_font.GetWeight()
        if yazi_stili in GORUNUM_YAZI_STILI_SECENEKLERI:
            stil, agirlik = GORUNUM_YAZI_STILI_SECENEKLERI[yazi_stili]

        font = wx.Font(
            int(nokta),
            wx.FONTFAMILY_DEFAULT,
            stil,
            agirlik,
            temel_font.GetUnderlined(),
            yuz,
        )
        if font.IsOk():
            return font
    except Exception as e:
        hata_kaydet("Görünüm fontu oluşturulamadı.", e)
    return mevcut_font


def gorunum_rengi_olustur(renk_adi, renkler, varsayilan_sistem_rengi):
    """Hazır renk adını wx.Colour nesnesine çevirir; boşsa sistem rengini döndürür."""
    try:
        if renk_adi in renkler:
            return wx.Colour(*renkler[renk_adi])
        return wx.SystemSettings.GetColour(varsayilan_sistem_rengi)
    except Exception as e:
        hata_kaydet("Görünüm rengi oluşturulamadı.", e)
        return wx.NullColour


def gorunum_renkleri_al():
    """Metin ve arka plan renklerini döndürür."""
    ayarlar = gorunum_ayarlari_yukle()
    if ayarlar.get(GORUNUM_SISTEM_RENKLERI_ALANI, False):
        return (
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT),
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW),
        )
    metin_rengi = gorunum_rengi_olustur(
        ayarlar.get(GORUNUM_METIN_RENGI_ALANI, ""),
        GORUNUM_METIN_RENKLERI,
        wx.SYS_COLOUR_WINDOWTEXT,
    )
    arka_plan_rengi = gorunum_rengi_olustur(
        ayarlar.get(GORUNUM_ARKA_PLAN_RENGI_ALANI, ""),
        GORUNUM_ARKA_PLAN_RENKLERI,
        wx.SYS_COLOUR_WINDOW,
    )
    return metin_rengi, arka_plan_rengi


def gorunum_denetime_uygula(denetim):
    """Tek bir wx denetimine kullanıcı görünüm ayarını uygular."""
    try:
        if denetim is None:
            return
        font = gorunum_fontu_olustur(denetim.GetFont())
        if font and font.IsOk():
            denetim.SetFont(font)

        metin_rengi, arka_plan_rengi = gorunum_renkleri_al()
        if metin_rengi and metin_rengi.IsOk():
            try:
                if hasattr(denetim, "SetTextColour"):
                    denetim.SetTextColour(metin_rengi)
                else:
                    denetim.SetForegroundColour(metin_rengi)
            except Exception:
                try:
                    denetim.SetForegroundColour(metin_rengi)
                except Exception:
                    pass
        if arka_plan_rengi and arka_plan_rengi.IsOk():
            try:
                denetim.SetBackgroundColour(arka_plan_rengi)
            except Exception:
                pass
        try:
            denetim.Refresh()
        except Exception:
            pass
    except Exception as e:
        hata_kaydet("Görünüm ayarı denetime uygulanamadı.", e)

def gorunum_denetimlerine_uygula(*denetimler):
    """Birden fazla denetime görünüm ayarını güvenli biçimde uygular."""
    for denetim in denetimler:
        gorunum_denetime_uygula(denetim)

def rehberi_yukle():
    adresler = guvenli_json_oku(REHBER_DOSYASI, [])
    if not isinstance(adresler, list):
        return []
    temiz = []
    for adres in adresler:
        adres = str(adres).strip()
        if adres and adres not in temiz:
            temiz.append(adres)
    return temiz[:200]


def rehbere_ekle(yeni_adres):
    yeni_adres = str(yeni_adres or "").strip()
    if not yeni_adres:
        return
    adresler = rehberi_yukle()
    if yeni_adres in adresler:
        adresler.remove(yeni_adres)
    adresler.insert(0, yeni_adres)
    guvenli_json_yaz(REHBER_DOSYASI, adresler[:200])


def kisi_anahtari(kisi):
    """Kişi kaydını karşılaştırmak için e-posta adresini küçük harfe çevirir."""
    return str((kisi or {}).get("eposta", "")).strip().lower()


def kisi_gorunen_ad(kisi):
    """Kişinin listelerde okunacak sade adını döndürür."""
    ad = str((kisi or {}).get("ad", "")).strip()
    soyad = str((kisi or {}).get("soyad", "")).strip()
    eposta = str((kisi or {}).get("eposta", "")).strip()
    tam_ad = " ".join(parca for parca in [ad, soyad] if parca).strip()
    parcalar = [parca for parca in (tam_ad, eposta) if parca]
    return " ".join(parcalar)


def kisi_eposta_basligi(kisi):
    """Kişiyi e-posta başlığına güvenli biçimde eklenebilir biçime getirir."""
    ad = str((kisi or {}).get("ad", "")).strip()
    soyad = str((kisi or {}).get("soyad", "")).strip()
    eposta = str((kisi or {}).get("eposta", "")).strip()
    tam_ad = " ".join(parca for parca in [ad, soyad] if parca).strip()
    if not eposta_adresi_gecerli_mi(eposta):
        return ""
    if tam_ad:
        try:
            return email.utils.formataddr((tam_ad, eposta))
        except Exception:
            return eposta
    return eposta


def kisileri_yukle():
    """Manuel oluşturulan kişileri ad, soyad ve e-posta alanlarıyla yükler."""
    veriler = guvenli_json_oku(KISILER_DOSYASI, [])
    if not isinstance(veriler, list):
        return []
    kisiler = []
    gorulen = set()
    for kayit in veriler:
        if not isinstance(kayit, dict):
            continue
        kisi = {
            "ad": str(kayit.get("ad", "")).strip(),
            "soyad": str(kayit.get("soyad", "")).strip(),
            "eposta": str(kayit.get("eposta", "")).strip(),
        }
        anahtar = kisi_anahtari(kisi)
        if not anahtar or anahtar in gorulen:
            continue
        if not eposta_adresi_gecerli_mi(kisi["eposta"]):
            continue
        gorulen.add(anahtar)
        kisiler.append(kisi)
    kisiler.sort(key=lambda k: (str(k.get("ad", "")).lower(), str(k.get("soyad", "")).lower(), str(k.get("eposta", "")).lower()))
    return kisiler[:1000]


def kisileri_kaydet(kisiler):
    """Kişileri temizleyip JSON dosyasına yazar."""
    temiz = []
    gorulen = set()
    for kayit in kisiler or []:
        if not isinstance(kayit, dict):
            continue
        kisi = {
            "ad": str(kayit.get("ad", "")).strip(),
            "soyad": str(kayit.get("soyad", "")).strip(),
            "eposta": str(kayit.get("eposta", "")).strip(),
        }
        anahtar = kisi_anahtari(kisi)
        if not anahtar or anahtar in gorulen:
            continue
        if not eposta_adresi_gecerli_mi(kisi["eposta"]):
            continue
        gorulen.add(anahtar)
        temiz.append(kisi)
    temiz.sort(key=lambda k: (str(k.get("ad", "")).lower(), str(k.get("soyad", "")).lower(), str(k.get("eposta", "")).lower()))
    guvenli_json_yaz(KISILER_DOSYASI, temiz[:1000])


def kisi_ekle_veya_guncelle(kisi, eski_eposta=None):
    """Yeni kişiyi ekler veya eski e-posta adresine sahip kaydı günceller."""
    kisi = {
        "ad": str((kisi or {}).get("ad", "")).strip(),
        "soyad": str((kisi or {}).get("soyad", "")).strip(),
        "eposta": str((kisi or {}).get("eposta", "")).strip(),
    }
    if not eposta_adresi_gecerli_mi(kisi["eposta"]):
        raise MailHatasi("Lütfen geçerli bir e-posta adresi yazın.")
    kisiler = kisileri_yukle()
    eski_anahtar = str(eski_eposta or "").strip().lower()
    yeni_anahtar = kisi_anahtari(kisi)
    sonuc = []
    eklendi = False
    for mevcut in kisiler:
        mevcut_anahtar = kisi_anahtari(mevcut)
        if eski_anahtar and mevcut_anahtar == eski_anahtar:
            if not eklendi:
                sonuc.append(kisi)
                eklendi = True
            continue
        if mevcut_anahtar == yeni_anahtar:
            if not eklendi:
                sonuc.append(kisi)
                eklendi = True
            continue
        sonuc.append(mevcut)
    if not eklendi:
        sonuc.append(kisi)
    kisileri_kaydet(sonuc)

def guvenli_coz(metin):
    if not metin:
        return ""
    try:
        sonuc = []
        for icerik, karakter_kumesi in decode_header(str(metin)):
            if isinstance(icerik, bytes):
                sonuc.append(icerik.decode(karakter_kumesi or "utf-8", errors="replace"))
            else:
                sonuc.append(str(icerik))
        return "".join(sonuc).strip()
    except Exception:
        return str(metin).strip()


def html_icerik_gibi_gorunuyor_mu(metin):
    """Metnin HTML etiketi veya HTML e-posta kırpığı içerip içermediğini denetler."""
    metin = str(metin or "")
    if not metin or "<" not in metin or ">" not in metin:
        return False
    return bool(re.search(r"(?is)<\s*/?\s*(html|head|body|style|script|table|tr|td|div|span|p|br|a|img|meta|title)\b", metin))


def turkce_tarih_yap(tarih_metni):
    if not tarih_metni:
        return "Tarih yok"
    aylar = {
        1: "Ocak",
        2: "Şubat",
        3: "Mart",
        4: "Nisan",
        5: "Mayıs",
        6: "Haziran",
        7: "Temmuz",
        8: "Ağustos",
        9: "Eylül",
        10: "Ekim",
        11: "Kasım",
        12: "Aralık",
    }
    try:
        tarih = parsedate_to_datetime(tarih_metni)
        return f"{tarih.day} {aylar[tarih.month]} {tarih.year} {tarih.hour:02d}:{tarih.minute:02d}"
    except Exception:
        return str(tarih_metni)


def html_kirpilmamis_bloklari_temizle(html_metni):
    """Kırpılmış HTML ön izlemelerinde kapanmamış head/style/script bloklarını atar."""
    metin = str(html_metni or "")
    for etiket in ("style", "script"):
        desen_acilis = re.compile(r"(?is)<\s*" + etiket + r"\b[^>]*>")
        desen_kapanis = re.compile(r"(?is)</\s*" + etiket + r"\s*>")
        while True:
            acilis = desen_acilis.search(metin)
            if not acilis:
                break
            kapanis = desen_kapanis.search(metin, acilis.end())
            if kapanis:
                metin = metin[:acilis.start()] + " " + metin[kapanis.end():]
            else:
                # IMAP BODY.PEEK kırpığı style/script bloğunun ortasında bittiyse
                # kalan CSS/JS kullanıcıya ön izleme olarak okutulmamalıdır.
                metin = metin[:acilis.start()]
                break

    head_acilis = re.search(r"(?is)<\s*head\b[^>]*>", metin)
    if head_acilis:
        head_kapanis = re.search(r"(?is)</\s*head\s*>", metin, head_acilis.end())
        if head_kapanis:
            metin = metin[:head_acilis.start()] + " " + metin[head_kapanis.end():]
        else:
            body_acilis = re.search(r"(?is)<\s*body\b[^>]*>", metin, head_acilis.end())
            if body_acilis:
                metin = metin[:head_acilis.start()] + " " + metin[body_acilis.start():]
            else:
                metin = metin[:head_acilis.start()]
    return metin


def html_temizle(html_metni):
    if not html_metni:
        return ""
    html_metni = str(html_metni)
    if len(html_metni) > HTML_TEMIZLE_KARAKTER_SINIRI:
        html_metni = html_metni[:HTML_TEMIZLE_KARAKTER_SINIRI]
    metin = RE_HTML_STYLE_SCRIPT_HEAD.sub("", html_metni)
    metin = html_kirpilmamis_bloklari_temizle(metin)
    metin = RE_HTML_BLOK_ETIKETLERI.sub("\n", metin)
    metin = RE_HTML_ETIKETLERI.sub(" ", metin)
    # Kırpılmış MIME/HTML parçalarında meta charset etiketi veya yarım HTML etiketi
    # parçalanmış biçimde metne sızabilir: t=iso-8859-9">, <table width=...
    metin = re.sub(r"(?is)<\s*/?\s*[a-z][^<>\r\n]{0,300}$", " ", metin)
    metin = re.sub(r"(?i)\b(?:charse)?t\s*=\s*[\"']?(?:utf-8|iso-8859-9|windows-1254|latin-1)[\"']?\s*[\"']?\s*>?", " ", metin)
    metin = html.unescape(metin)
    metin = RE_COKLU_BOSLUK.sub(" ", metin)
    satirlar = [satir.strip() for satir in metin.splitlines()]
    return "\n".join(satir for satir in satirlar if satir).strip()


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
        raise MailHatasi("Arşiv adı boş olamaz.")
    if len(ad) > 80:
        raise MailHatasi("Arşiv adı çok uzun. Lütfen en çok 80 karakterlik bir ad yazın.")
    if any(ord(karakter) < 32 for karakter in ad):
        raise MailHatasi("Arşiv adında satır sonu, sekme veya denetim karakteri bulunamaz.")
    if ad in (".", "..") or not ad.strip(" ."):
        raise MailHatasi("Lütfen harf veya rakam içeren geçerli bir arşiv adı yazın.")
    if "/" in ad or "\\" in ad:
        raise MailHatasi("Arşiv adında eğik çizgi veya ters eğik çizgi kullanılamaz.")
    if '"' in ad:
        raise MailHatasi("Arşiv adında çift tırnak kullanılamaz.")

    ad_kucuk = ad.lower()
    sistem_adlari = {str(oge).lower() for oge in SISTEM_KLASORLERI}
    sistem_adlari.update({"inbox", "[gmail]", "[google mail]"})
    if ad_kucuk in sistem_adlari or ad_kucuk.startswith("[gmail]") or ad_kucuk.startswith("[google mail]"):
        raise MailHatasi("Bu ad Gmail sistem klasörü için ayrılmıştır. Lütfen farklı bir arşiv adı yazın.")

    eski_kucuk = str(eski_ad or "").strip().lower()
    mevcut_kucuk = {str(oge or "").strip().lower() for oge in (mevcut_adlar or [])}
    mevcut_kucuk.discard(eski_kucuk)
    if ad_kucuk in mevcut_kucuk:
        raise MailHatasi("Bu adla bir arşiv klasörü zaten var.")
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
            if "STATUS" not in metin.upper():
                continue
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


def klasor_sayisi_mesaji(kategori_adi, klasor_bilgisi=None, listelenen_sayi=None):
    """Klasör toplamı ve okunmamış sayısı için kısa NVDA bildirimi üretir."""
    kategori_adi = str(kategori_adi or "Klasör").strip() or "Klasör"
    bilgi = klasor_bilgisi if isinstance(klasor_bilgisi, dict) else {}
    toplam = bilgi.get("messages")
    okunmamis = bilgi.get("unseen")

    parcalar = [f"{kategori_adi} klasörü hazır."]
    if isinstance(toplam, int) and toplam >= 0:
        if isinstance(okunmamis, int) and okunmamis > 0:
            parcalar.append(f"Toplam {toplam} ileti, {okunmamis} okunmamış.")
        elif isinstance(okunmamis, int):
            parcalar.append(f"Toplam {toplam} ileti. Okunmamış ileti yok.")
        else:
            parcalar.append(f"Toplam {toplam} ileti.")
    elif isinstance(okunmamis, int) and okunmamis > 0:
        parcalar.append(f"{okunmamis} okunmamış ileti var.")

    if isinstance(listelenen_sayi, int):
        if listelenen_sayi > 0:
            parcalar.append(f"{listelenen_sayi} e-posta listelendi.")
        else:
            parcalar.append("Gösterilecek e-posta yok.")
    return " ".join(parcalar)


def klasor_secimi_sayisi_mesaji(kategori_adi=None, klasor_bilgisi=None):
    """Klasör kutusunda dolaşırken okunacak kısa toplam/okunmamış bildirimi üretir.

    Klasör adını bu bildirime eklemeyiz; wx.Choice denetimi seçili klasör adını zaten NVDA'ya okutur.
    Sıfır iletili klasörlerde de gereksiz "Toplam 0" ifadesi yerine kısa bir mesaj döndürürüz.
    """
    bilgi = klasor_bilgisi if isinstance(klasor_bilgisi, dict) else {}
    toplam = bilgi.get("messages")
    okunmamis = bilgi.get("unseen")

    if isinstance(toplam, int) and toplam == 0:
        return "İleti yok."
    if isinstance(toplam, int) and toplam > 0:
        if isinstance(okunmamis, int) and okunmamis > 0:
            return f"Toplam {toplam} ileti, {okunmamis} okunmamış."
        return f"Toplam {toplam} ileti."
    if isinstance(okunmamis, int) and okunmamis > 0:
        return f"{okunmamis} okunmamış ileti var."
    return "İleti sayısı alınamadı."


def klasor_sayisi_onbellek_hesap_anahtari(eposta):
    """Klasör sayı önbelleğini hesaba bağlamak için açık e-posta yerine kısa hesap anahtarı üretir."""
    eposta = str(eposta or "").strip().lower()
    if not eposta:
        return ""
    try:
        return hashlib.sha256(eposta.encode("utf-8")).hexdigest()[:24]
    except Exception:
        return ""


def klasor_sayisi_bilgisini_duzenle(bilgi):
    """Klasör toplam/okunmamış bilgisini güvenli JSON biçimine çeker."""
    if not isinstance(bilgi, dict):
        return {}
    sonuc = {}
    for anahtar in ("messages", "unseen"):
        try:
            deger = bilgi.get(anahtar)
            if deger is None:
                continue
            sayi = int(str(deger).strip())
            if sayi < 0:
                continue
            sonuc[anahtar] = sayi
        except Exception:
            continue
    try:
        zaman = bilgi.get("zaman") or bilgi.get("time") or bilgi.get("timestamp")
        if zaman is not None:
            sonuc["zaman"] = int(float(str(zaman).strip()))
    except Exception:
        pass
    if sonuc and "zaman" not in sonuc:
        sonuc["zaman"] = int(time.time())
    return sonuc


def klasor_sayisi_onbellegi_yukle(eposta):
    """Son bilinen klasör toplam/okunmamış sayılarını JSON önbellekten yükler."""
    hesap_anahtari = klasor_sayisi_onbellek_hesap_anahtari(eposta)
    if not hesap_anahtari:
        return {}
    veri = guvenli_json_oku(KLASOR_SAYISI_ONBELLEK_DOSYASI, {})
    if not isinstance(veri, dict):
        return {}
    if str(veri.get("hesap_anahtari", "")) != hesap_anahtari:
        return {}
    klasorler = veri.get("klasorler", {})
    if not isinstance(klasorler, dict):
        return {}
    sonuc = {}
    for ad, bilgi in klasorler.items():
        ad = str(ad or "").strip()
        temiz = klasor_sayisi_bilgisini_duzenle(bilgi)
        if ad and temiz:
            sonuc[ad] = temiz
    return sonuc


def klasor_sayisi_onbellegi_kaydet(eposta, cache):
    """Klasör toplam/okunmamış sayılarını küçük JSON önbelleğine yazar."""
    hesap_anahtari = klasor_sayisi_onbellek_hesap_anahtari(eposta)
    if not hesap_anahtari or not isinstance(cache, dict):
        return False
    temiz_klasorler = {}
    for ad, bilgi in cache.items():
        ad = str(ad or "").strip()
        temiz = klasor_sayisi_bilgisini_duzenle(bilgi)
        if ad and temiz:
            temiz_klasorler[ad] = temiz
    veri = {
        "hesap_anahtari": hesap_anahtari,
        "guncelleme_zamani": int(time.time()),
        "klasorler": temiz_klasorler,
    }
    return guvenli_json_yaz(KLASOR_SAYISI_ONBELLEK_DOSYASI, veri)


def klasor_sayisi_onbellegi_temizle():
    """Hesap silindiğinde kalıcı klasör sayı önbelleğini kaldırır."""
    try:
        if os.path.exists(KLASOR_SAYISI_ONBELLEK_DOSYASI):
            os.remove(KLASOR_SAYISI_ONBELLEK_DOSYASI)
            return True
    except Exception as e:
        hata_kaydet("Klasör sayı önbelleği temizlenemedi.", e)
    return False


def guvenli_dosya_adi(metin, varsayilan="dosya", azami_uzunluk=90):
    metin = guvenli_coz(metin or varsayilan)
    metin = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", metin)
    metin = re.sub(r"\s+", " ", metin).strip(" ._")
    if not metin:
        metin = varsayilan
    return metin[:azami_uzunluk].strip(" ._") or varsayilan


def benzersiz_yol(klasor, dosya_adi):
    ad, uzanti = os.path.splitext(dosya_adi)
    aday = os.path.join(klasor, dosya_adi)
    sayac = 1
    while os.path.exists(aday):
        aday = os.path.join(klasor, f"{ad}_{sayac}{uzanti}")
        sayac += 1
    return aday


def alici_listesi_yap(kime):
    """Alıcı alanından geçerli ve tekrarsız e-posta adresleri çıkarır."""
    adresler = []
    gorulen = set()
    kaynak = str(kime or "").replace(";", ",")
    for _ad, adres in email.utils.getaddresses([kaynak]):
        adres = str(adres or "").strip()
        anahtar = adres.lower()
        if eposta_adresi_gecerli_mi(adres) and anahtar not in gorulen:
            adresler.append(adres)
            gorulen.add(anahtar)
    return adresler


def grup_araci_gonderen_bilgisini_temizle(metin):
    """Grup e-postalarında gönderen adındaki aracı servis bilgisini yalnızca görünüm için temizler."""
    metin = str(metin or "").strip()
    if not metin:
        return metin

    temiz = RE_GRUP_ARACI_GONDEREN.sub("", metin).strip()
    return temiz or metin


def adres_basligini_duzenle(deger):
    """Taslaklardaki alıcı başlıklarını tek satırlık düzenlenebilir metne çevirir."""
    adresler = []
    gorulen = set()
    kaynak = str(deger or "").replace(";", ",")
    kaynak = eposta_basligi_tek_satir_yap(kaynak)
    for ad, adres in email.utils.getaddresses([kaynak]):
        adres = str(adres or "").strip()
        ad = guvenli_coz(ad).strip()
        if not eposta_adresi_gecerli_mi(adres):
            continue
        anahtar = adres.lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        if ad:
            bicimli = email.utils.formataddr((ad, adres))
        else:
            bicimli = adres
        adresler.append(bicimli)
    return ", ".join(adresler)


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


def ek_icerik_turu_bul(dosya_adi):
    ctype, encoding = mimetypes.guess_type(dosya_adi or "")
    if ctype is None or encoding is not None or "/" not in ctype:
        ctype = "application/octet-stream"
    return ctype.split("/", 1)


def mesaj_metni_ve_ekleri_cikar(mesaj):
    duz_metinler = []
    html_metinler = []
    ekler = []
    atlanan_ekler = []
    toplam_ek_boyutu = 0

    parcalar = mesaj.walk() if mesaj.is_multipart() else [mesaj]
    for parca in parcalar:
        try:
            icerik_turu = parca.get_content_type()
            dosya_adi = parca.get_filename()
            icerik_duzeni = str(parca.get("Content-Disposition", "")).lower()

            if dosya_adi or "attachment" in icerik_duzeni:
                veri = parca.get_payload(decode=True)
                if veri:
                    temiz_ad = guvenli_coz(dosya_adi or "ek_dosya")
                    boyut = len(veri)
                    if boyut > AZAMI_EK_ONBELLEK_TEK_BOYUTU:
                        atlanan_ekler.append(
                            f"{temiz_ad} ({dosya_boyutu_metni(boyut)}): tek ek güvenlik sınırını aşıyor"
                        )
                        continue
                    if toplam_ek_boyutu + boyut > AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU:
                        atlanan_ekler.append(
                            f"{temiz_ad} ({dosya_boyutu_metni(boyut)}): toplam ek güvenlik sınırını aşıyor"
                        )
                        continue
                    ekler.append((temiz_ad, veri))
                    toplam_ek_boyutu += boyut
                continue

            if icerik_turu not in ("text/plain", "text/html"):
                continue

            veri = parca.get_payload(decode=True)
            if veri is None:
                icerik = str(parca.get_payload() or "")
            else:
                icerik = veri.decode(parca.get_content_charset() or "utf-8", errors="replace")

            if icerik_turu == "text/plain":
                duz_metinler.append(icerik)
            else:
                html_metinler.append(icerik)
        except Exception as e:
            hata_kaydet("E-posta parçası okunamadı.", e)

    duz_metin = "\n".join(metin.strip() for metin in duz_metinler if metin.strip())
    html_metin = "\n".join(metin.strip() for metin in html_metinler if metin.strip())

    if duz_metin and html_icerik_gibi_gorunuyor_mu(duz_metin):
        duz_metin = html_temizle(duz_metin)
    if not duz_metin.strip() and html_metin:
        duz_metin = html_temizle(html_metin)

    duz_metin = duz_metin.strip()
    if atlanan_ekler:
        ek_notu = [
            "",
            "Not: Bazı ekler çok büyük olduğu için belleğe yüklenmedi ve bu pencereden kaydedilemez ya da iletilemez.",
            f"Tek ek sınırı: {dosya_boyutu_metni(AZAMI_EK_ONBELLEK_TEK_BOYUTU)}.",
            f"Toplam ek sınırı: {dosya_boyutu_metni(AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU)}.",
            "Atlanan ekler:",
        ]
        ek_notu.extend(f"- {satir}" for satir in atlanan_ekler[:20])
        if len(atlanan_ekler) > 20:
            ek_notu.append(f"- Ayrıca {len(atlanan_ekler) - 20} ek daha atlandı.")
        duz_metin = (duz_metin + "\n" + "\n".join(ek_notu)).strip()

    return duz_metin, ekler


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
    metin = str(metin or "")

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


def onizleme_metni_olustur(ham_veri):
    """IMAP üzerinden alınan kısa içerikten kullanıcıya okunabilir ön izleme üretir."""
    if not ham_veri:
        return ""

    # Öncelik Python'un email paketindedir. Bu yol Content-Type, charset,
    # Content-Transfer-Encoding, multipart/alternative ve iç içe MIME parçalarını
    # standart kurallara göre çözer. BODY.PEEK[TEXT] dış başlık getirmediğinde
    # geçici Content-Type başlığı eklenerek yine email paketi denenir.
    try:
        onizleme = onizleme_email_paketiyle_coz(ham_veri)
        if onizleme:
            return onizleme
    except Exception:
        pass

    # Yedek yol: 1.6.11'de çalışan elle çözme sistemi korunur.
    try:
        onizleme = onizleme_multipart_govde_coz(ham_veri)
        if onizleme:
            return onizleme
    except Exception:
        pass

    karakter_kumesi = onizleme_karakter_kumesi_bul(ham_veri)

    try:
        ham_metin = onizleme_verisini_metin_yap(ham_veri, karakter_kumesi)
        ham_metin = onizleme_kodlamasini_coz(ham_metin, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(ham_metin)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
    except Exception:
        pass

    try:
        cozulmus_veri = quopri.decodestring(ham_veri)
        cozulmus_metin = onizleme_verisini_metin_yap(cozulmus_veri, karakter_kumesi)
        cozulmus_metin = onizleme_kodlamasini_coz(cozulmus_metin, karakter_kumesi)
        cozulmus_metin = onizleme_metnini_temizle(cozulmus_metin)
        if onizleme_metin_guvenli_mi(cozulmus_metin):
            return cozulmus_metin
    except Exception:
        pass

    try:
        mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
        icerik, _ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
        icerik = onizleme_kodlamasini_coz(icerik, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(icerik)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
    except Exception:
        pass

    try:
        ham_metin = onizleme_verisini_metin_yap(ham_veri, karakter_kumesi)
        ham_metin = onizleme_kodlamasini_coz(ham_metin, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(ham_metin)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
        return ""
    except Exception:
        return ""

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


def eposta_basligi_tek_satir_yap(deger):
    deger = str(deger or "").strip()
    deger = re.sub(r"[\r\n]+", " ", deger)
    deger = re.sub(r"\s+", " ", deger).strip()
    return deger


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


def smtp_yaniti_oku(dosya):
    satirlar = []
    while True:
        try:
            satir = dosya.readline()
        except socket.timeout as e:
            raise MailHatasi("SMTP sunucusu zamanında yanıt vermedi. Bağlantı zaman aşımına uğradı.") from e
        except OSError as e:
            raise MailHatasi("SMTP sunucusundan yanıt okunamadı. Bağlantı kesilmiş olabilir.") from e
        if not satir:
            raise MailHatasi("SMTP sunucusundan yanıt alınamadı.")
        satirlar.append(satir)
        if len(satir) >= 4 and satir[:3].isdigit() and satir[3:4] != b"-":
            break
    kod = int(satirlar[-1][:3])
    metin = b"".join(satirlar).decode("utf-8", errors="replace")
    return kod, metin


def smtp_komut_gonder(sock, dosya, komut, beklenen_kodlar):
    if isinstance(beklenen_kodlar, int):
        beklenen_kodlar = (beklenen_kodlar,)
    try:
        sock.sendall((komut + "\r\n").encode("utf-8"))
    except socket.timeout as e:
        raise MailHatasi("SMTP komutu gönderilirken zaman aşımı oluştu.") from e
    except OSError as e:
        raise MailHatasi("SMTP komutu gönderilemedi. Bağlantı kesilmiş olabilir.") from e
    kod, metin = smtp_yaniti_oku(dosya)
    if kod not in beklenen_kodlar:
        hata_kaydet(f"SMTP beklenmeyen yanıt. Kod: {kod}. Yanıt: {eposta_basligi_tek_satir_yap(metin)[:300]}")
        raise MailHatasi("SMTP sunucusu gönderimi kabul etmedi.")
    return kod, metin


def smtp_mesaj_verisini_hazirla(mesaj):
    ham = mesaj.as_bytes(policy=SMTP)
    satirlar = ham.splitlines(keepends=True)
    guvenli_satirlar = []
    for satir in satirlar:
        if satir.startswith(b"."):
            guvenli_satirlar.append(b"." + satir)
        else:
            guvenli_satirlar.append(satir)
    sonuc = b"".join(guvenli_satirlar)
    if not sonuc.endswith(b"\r\n"):
        sonuc += b"\r\n"
    return sonuc + b".\r\n"


def _smtp_mesaj_gonder_akisi(sock, dosya, eposta, sifre, alicilar, mesaj):
    kod, _metin = smtp_yaniti_oku(dosya)
    if kod != 220:
        raise MailHatasi("SMTP sunucusuna bağlanılamadı.")

    smtp_komut_gonder(sock, dosya, "EHLO engelsiz-mail", 250)
    smtp_komut_gonder(sock, dosya, "AUTH LOGIN", 334)
    smtp_komut_gonder(sock, dosya, base64.b64encode(eposta.encode("utf-8")).decode("ascii"), 334)
    smtp_komut_gonder(sock, dosya, base64.b64encode(sifre.encode("utf-8")).decode("ascii"), 235)
    smtp_komut_gonder(sock, dosya, f"MAIL FROM:<{eposta}>", 250)
    for alici in alicilar:
        smtp_komut_gonder(sock, dosya, f"RCPT TO:<{alici}>", (250, 251))
    smtp_komut_gonder(sock, dosya, "DATA", 354)
    try:
        sock.sendall(smtp_mesaj_verisini_hazirla(mesaj))
    except socket.timeout as e:
        raise MailHatasi("SMTP sunucusuna e-posta verisi gönderilirken zaman aşımı oluştu.") from e
    except OSError as e:
        raise MailHatasi("SMTP sunucusuna e-posta verisi gönderilemedi. Bağlantı kesilmiş olabilir.") from e
    kod, _metin = smtp_yaniti_oku(dosya)
    if kod != 250:
        raise MailHatasi("SMTP sunucusu e-postayı kabul etmedi.")
    try:
        smtp_komut_gonder(sock, dosya, "QUIT", 221)
    except Exception:
        pass


def smtp_465_ssl_ile_gonder(eposta, sifre, alicilar, mesaj):
    sock = None
    dosya = None
    try:
        ctx = ssl.create_default_context()
        ham_soket = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT), timeout=BAGLANTI_ZAMAN_ASIMI)
        sock = ctx.wrap_socket(ham_soket, server_hostname=GMAIL_SMTP_SUNUCU)
        sock.settimeout(BAGLANTI_ZAMAN_ASIMI)
        dosya = sock.makefile("rb")
        _smtp_mesaj_gonder_akisi(sock, dosya, eposta, sifre, alicilar, mesaj)
    finally:
        try:
            if dosya:
                dosya.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass


def smtp_587_starttls_ile_gonder(eposta, sifre, alicilar, mesaj):
    sock = None
    dosya = None
    try:
        sock = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT), timeout=BAGLANTI_ZAMAN_ASIMI)
        sock.settimeout(BAGLANTI_ZAMAN_ASIMI)
        dosya = sock.makefile("rb")

        kod, _metin = smtp_yaniti_oku(dosya)
        if kod != 220:
            raise MailHatasi("SMTP 587 sunucusundan beklenen karşılama yanıtı alınamadı.")
        smtp_komut_gonder(sock, dosya, "EHLO engelsiz-mail", 250)
        smtp_komut_gonder(sock, dosya, "STARTTLS", 220)

        try:
            if dosya:
                dosya.close()
        except Exception as e:
            hata_kaydet("SMTP 587 TLS öncesi dosya nesnesi kapatılamadı.", e)
        dosya = None

        ctx = ssl.create_default_context()
        guvenli_sock = ctx.wrap_socket(sock, server_hostname=GMAIL_SMTP_SUNUCU)
        guvenli_sock.settimeout(BAGLANTI_ZAMAN_ASIMI)
        sock = guvenli_sock
        dosya = sock.makefile("rb")

        smtp_komut_gonder(sock, dosya, "EHLO engelsiz-mail", 250)
        smtp_komut_gonder(sock, dosya, "AUTH LOGIN", 334)
        smtp_komut_gonder(sock, dosya, base64.b64encode(eposta.encode("utf-8")).decode("ascii"), 334)
        smtp_komut_gonder(sock, dosya, base64.b64encode(sifre.encode("utf-8")).decode("ascii"), 235)
        smtp_komut_gonder(sock, dosya, f"MAIL FROM:<{eposta}>", 250)
        for alici in alicilar:
            smtp_komut_gonder(sock, dosya, f"RCPT TO:<{alici}>", (250, 251))
        smtp_komut_gonder(sock, dosya, "DATA", 354)
        sock.sendall(smtp_mesaj_verisini_hazirla(mesaj))
        kod, _metin = smtp_yaniti_oku(dosya)
        if kod != 250:
            raise MailHatasi("SMTP sunucusu e-postayı kabul etmedi.")
        try:
            smtp_komut_gonder(sock, dosya, "QUIT", 221)
        except Exception:
            pass
    finally:
        try:
            if dosya:
                dosya.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass


def smtp_ssl_ile_gonder(eposta, sifre, alicilar, mesaj):
    """Önce Gmail SMTP 465 SSL ile gönderir; başarısız olursa 587 STARTTLS yedeğini dener."""
    ilk_hata = None
    try:
        return smtp_465_ssl_ile_gonder(eposta, sifre, alicilar, mesaj)
    except Exception as e:
        ilk_hata = e
        hata_kaydet("SMTP 465 SSL gönderimi başarısız oldu, 587 STARTTLS yedeği denenecek.", e)

    try:
        return smtp_587_starttls_ile_gonder(eposta, sifre, alicilar, mesaj)
    except Exception as ikinci_hata:
        mesaj_465 = baglanti_hatasi_kullanici_mesaji(ilk_hata, "465 SSL yöntemi başarısız oldu.")
        mesaj_587 = baglanti_hatasi_kullanici_mesaji(ikinci_hata, "587 STARTTLS yöntemi başarısız oldu.")
        raise MailHatasi(f"SMTP gönderimi yapılamadı. 465 SSL sonucu: {mesaj_465} 587 STARTTLS sonucu: {mesaj_587}") from ikinci_hata



def eposta_adresi_gecerli_mi(eposta):
    """E-posta adresini temel ve güvenli biçim kurallarına göre denetler."""
    eposta = str(eposta or "").strip()
    if not eposta or len(eposta) > 254:
        return False
    if any(karakter in eposta for karakter in (" ", "\t", "\r", "\n")):
        return False
    if eposta.count("@") != 1:
        return False

    yerel, alan = eposta.rsplit("@", 1)
    if not yerel or not alan or len(yerel) > 64 or len(alan) > 253:
        return False
    if yerel.startswith(".") or yerel.endswith(".") or ".." in yerel:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", yerel):
        return False
    if alan.startswith(".") or alan.endswith(".") or ".." in alan:
        return False

    etiketler = alan.split(".")
    if len(etiketler) < 2:
        return False
    for etiket in etiketler:
        if not etiket or len(etiket) > 63:
            return False
        if etiket.startswith("-") or etiket.endswith("-"):
            return False
        if not re.fullmatch(r"[A-Za-z0-9-]+", etiket):
            return False

    return True


def baglanti_hatasi_kullanici_mesaji(hata, varsayilan=None):
    """Teknik bağlantı hatalarını kullanıcıya anlaşılır Türkçe metinle açıklar."""
    if isinstance(hata, MailHatasi):
        return str(hata)

    metin = str(hata or "").lower()
    if isinstance(hata, socket.gaierror) or "getaddrinfo" in metin or "name or service" in metin:
        return "Sunucu adı çözümlenemedi. İnternet bağlantınızı, DNS ayarlarınızı veya kurum ağı kısıtlamalarını kontrol edin."
    if isinstance(hata, socket.timeout) or "timed out" in metin or "zaman" in metin and "aş" in metin:
        return "Bağlantı zaman aşımına uğradı. İnternet bağlantınız yavaş olabilir veya kurum ağı Gmail sunucularına erişimi engelliyor olabilir."
    if "zorla kapatıldı" in metin or "forcibly closed" in metin or "uzaktaki bir ana bilgisayar" in metin:
        return "Bağlantı sunucu veya aradaki ağ cihazı tarafından oturum aşamasında kapatıldı. Kurum ağı IMAP/SMTP oturumunu kesiyor olabilir."
    if isinstance(hata, ssl.SSLError) or "ssl" in metin or "certificate" in metin or "sertifika" in metin:
        return "Güvenli bağlantı kurulamadı. Sertifika denetimi, güvenlik yazılımı veya kurum ağı bağlantıyı etkiliyor olabilir."
    if isinstance(hata, ConnectionRefusedError) or "refused" in metin:
        return "Sunucu bağlantıyı reddetti. Güvenlik duvarı, kurum ağı veya geçici sunucu kısıtlaması olabilir."
    if isinstance(hata, OSError):
        return varsayilan or "Bağlantı kurulamadı. İnternet bağlantınızı, güvenlik duvarınızı ve kurum ağı ayarlarınızı kontrol edin."
    return varsayilan or "Beklenmeyen bir bağlantı hatası oluştu. Ayrıntılı denetim için Dosya menüsündeki Bağlantıyı Denetle seçeneğini kullanın."


def smtp_kod_bekle(sock, dosya, komut, beklenen_kodlar, hata_mesaji):
    if isinstance(beklenen_kodlar, int):
        beklenen_kodlar = (beklenen_kodlar,)
    if komut is not None:
        try:
            sock.sendall((komut + "\r\n").encode("utf-8"))
        except socket.timeout as e:
            raise MailHatasi("SMTP komutu gönderilirken zaman aşımı oluştu.") from e
        except OSError as e:
            raise MailHatasi("SMTP komutu gönderilemedi. Bağlantı kesilmiş olabilir.") from e
    kod, metin = smtp_yaniti_oku(dosya)
    if kod not in beklenen_kodlar:
        hata_kaydet(f"SMTP denetiminde beklenmeyen yanıt. Kod: {kod}. Yanıt: {eposta_basligi_tek_satir_yap(metin)[:300]}")
        raise MailHatasi(f"{hata_mesaji} Sunucu yanıt kodu: {kod}.")
    return kod, metin


def smtp_465_baglanti_denetle(eposta, sifre):
    """SMTP 465 SSL ile kullanıcı doğrulamasını sınar; e-posta göndermez."""
    sock = None
    dosya = None
    try:
        ctx = ssl.create_default_context()
        ham_soket = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI)
        sock = ctx.wrap_socket(ham_soket, server_hostname=GMAIL_SMTP_SUNUCU)
        sock.settimeout(BAGLANTI_DENETIM_ZAMAN_ASIMI)
        dosya = sock.makefile("rb")

        smtp_kod_bekle(sock, dosya, None, 220, "SMTP 465 sunucusundan beklenen karşılama yanıtı alınamadı.")
        smtp_kod_bekle(sock, dosya, "EHLO engelsiz-mail", 250, "SMTP 465 sunucusu EHLO komutunu kabul etmedi.")
        smtp_kod_bekle(sock, dosya, "AUTH LOGIN", 334, "SMTP 465 sunucusu kullanıcı doğrulamasını başlatmadı.")
        smtp_kod_bekle(sock, dosya, base64.b64encode(eposta.encode("utf-8")).decode("ascii"), 334, "SMTP 465 sunucusu e-posta adresini kabul etmedi.")
        smtp_kod_bekle(sock, dosya, base64.b64encode(sifre.encode("utf-8")).decode("ascii"), 235, "SMTP 465 kullanıcı doğrulaması başarısız oldu. E-posta adresi veya uygulama şifresi hatalı olabilir.")
        try:
            smtp_kod_bekle(sock, dosya, "QUIT", 221, "SMTP 465 çıkış komutu tamamlanamadı.")
        except Exception:
            pass
    finally:
        try:
            if dosya:
                dosya.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass


def smtp_587_starttls_baglanti_denetle(eposta, sifre):
    """SMTP 587 STARTTLS ile kullanıcı doğrulamasını sınar; e-posta göndermez."""
    sock = None
    dosya = None
    try:
        sock = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI)
        sock.settimeout(BAGLANTI_DENETIM_ZAMAN_ASIMI)
        dosya = sock.makefile("rb")

        smtp_kod_bekle(sock, dosya, None, 220, "SMTP 587 sunucusundan beklenen karşılama yanıtı alınamadı.")
        smtp_kod_bekle(sock, dosya, "EHLO engelsiz-mail", 250, "SMTP 587 sunucusu EHLO komutunu kabul etmedi.")
        smtp_kod_bekle(sock, dosya, "STARTTLS", 220, "SMTP 587 sunucusu STARTTLS başlatmayı kabul etmedi.")

        try:
            if dosya:
                dosya.close()
        except Exception as e:
            hata_kaydet("SMTP 587 denetimi TLS öncesi dosya nesnesi kapatılamadı.", e)
        dosya = None

        ctx = ssl.create_default_context()
        guvenli_sock = ctx.wrap_socket(sock, server_hostname=GMAIL_SMTP_SUNUCU)
        guvenli_sock.settimeout(BAGLANTI_DENETIM_ZAMAN_ASIMI)
        sock = guvenli_sock
        dosya = sock.makefile("rb")

        smtp_kod_bekle(sock, dosya, "EHLO engelsiz-mail", 250, "SMTP 587 TLS sonrası EHLO komutunu kabul etmedi.")
        smtp_kod_bekle(sock, dosya, "AUTH LOGIN", 334, "SMTP 587 sunucusu kullanıcı doğrulamasını başlatmadı.")
        smtp_kod_bekle(sock, dosya, base64.b64encode(eposta.encode("utf-8")).decode("ascii"), 334, "SMTP 587 sunucusu e-posta adresini kabul etmedi.")
        smtp_kod_bekle(sock, dosya, base64.b64encode(sifre.encode("utf-8")).decode("ascii"), 235, "SMTP 587 kullanıcı doğrulaması başarısız oldu. E-posta adresi veya uygulama şifresi hatalı olabilir.")
        try:
            smtp_kod_bekle(sock, dosya, "QUIT", 221, "SMTP 587 çıkış komutu tamamlanamadı.")
        except Exception:
            pass
    finally:
        try:
            if dosya:
                dosya.close()
        except Exception:
            pass
        try:
            if sock:
                sock.close()
        except Exception:
            pass


def smtp_baglanti_denetle(eposta, sifre):
    """Önce SMTP 465 SSL, başarısız olursa 587 STARTTLS ile kullanıcı doğrulamasını sınar."""
    ilk_hata = None
    try:
        smtp_465_baglanti_denetle(eposta, sifre)
        return "465 SSL"
    except Exception as e:
        ilk_hata = e
        hata_kaydet("SMTP 465 denetimi başarısız oldu, 587 STARTTLS denenecek.", e)

    try:
        smtp_587_starttls_baglanti_denetle(eposta, sifre)
        return "587 STARTTLS"
    except Exception as ikinci_hata:
        mesaj_465 = baglanti_hatasi_kullanici_mesaji(ilk_hata, "465 SSL yöntemi başarısız oldu.")
        mesaj_587 = baglanti_hatasi_kullanici_mesaji(ikinci_hata, "587 STARTTLS yöntemi başarısız oldu.")
        raise MailHatasi(f"SMTP kullanıcı doğrulaması iki yöntemle de başarısız oldu. 465 SSL sonucu: {mesaj_465} 587 STARTTLS sonucu: {mesaj_587}") from ikinci_hata


def ayarlari_denetim_icin_yukle(eposta=None, sifre=None):
    """Bağlantı denetimi için hesap bilgisini ayrıntılı ve raporlanabilir biçimde okur."""
    if eposta is not None or sifre is not None:
        return {
            "eposta": str(eposta or "").strip(),
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
        "sifre": "",
        "kaynak": "kayitli",
        "ayar_dosyasi_var": ayar_dosyasi_var,
        "notlar": [],
    }

    sifreli_deger = str(ham_ayarlar.get(SIFRE_DPAPI_ALANI, "")).strip()
    duz_metin_sifre = str(ham_ayarlar.get(SIFRE_DUZ_METIN_ALANI, "")).strip().replace(" ", "")
    if sifreli_deger:
        sonuc["sifre"] = uygulama_sifresini_coz(sifreli_deger)
        sonuc["notlar"].append("Kayıtlı uygulama şifresi Windows DPAPI ile çözüldü.")
    elif duz_metin_sifre:
        sonuc["sifre"] = duz_metin_sifre
        sonuc["notlar"].append("Eski düz metin uygulama şifresi alanı bulundu. Hesap yeniden kaydedildiğinde şifreli alana taşınmalıdır.")
    else:
        sonuc["notlar"].append("Kayıtlı uygulama şifresi bulunamadı.")
    return sonuc


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
                ekle("Başarısız", "Ayar dosyası", "Kayıtlı hesap bilgisi bulunamadı. Dosya menüsünden Bağlan seçeneğiyle hesap bilgilerinizi kaydedin.")
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
        test_soket = socket.create_connection((GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI)
        test_soket.close()
        ekle("Başarılı", "Gmail IMAP 993 TCP erişimi", f"{GMAIL_IMAP_SUNUCU}:{GMAIL_IMAP_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Başarısız", "Gmail IMAP 993 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    try:
        test_soket = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI)
        test_soket.close()
        ekle("Başarılı", "Gmail SMTP 465 TCP erişimi", f"{GMAIL_SMTP_SUNUCU}:{GMAIL_SMTP_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Uyarı", "Gmail SMTP 465 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    try:
        test_soket = socket.create_connection((GMAIL_SMTP_SUNUCU, GMAIL_SMTP_STARTTLS_PORT), timeout=BAGLANTI_DENETIM_ZAMAN_ASIMI)
        test_soket.close()
        ekle("Başarılı", "Gmail SMTP 587 TCP erişimi", f"{GMAIL_SMTP_SUNUCU}:{GMAIL_SMTP_STARTTLS_PORT} adresine TCP bağlantısı başlatılabildi.")
    except Exception as e:
        ekle("Uyarı", "Gmail SMTP 587 TCP erişimi", baglanti_hatasi_kullanici_mesaji(e))

    klasor_haritasi = {}
    try:
        imap = YerelImapIstemcisi(GMAIL_IMAP_SUNUCU, GMAIL_IMAP_PORT, BAGLANTI_DENETIM_ZAMAN_ASIMI)
        try:
            tip, veri = imap.login(eposta, sifre)
            if tip != "OK":
                raise MailHatasi("IMAP kullanıcı doğrulaması başarısız oldu. E-posta adresi veya uygulama şifresi hatalı olabilir.")
            ekle("Başarılı", "IMAP kullanıcı doğrulaması", "Gmail IMAP sunucusu e-posta adresini ve uygulama şifresini kabul etti.")

            tip, veri = imap.list()
            if tip != "OK":
                raise MailHatasi("Gmail klasör listesi alınamadı.")
            klasor_haritasi, ozel_klasorler = imap_klasor_haritasi_olustur(veri)
            ekle("Başarılı", "Gmail klasör listesi", f"Klasör listesi okundu. Tanınan özel arşiv klasörü sayısı: {len(ozel_klasorler)}. Sistem klasörleri aşağıda tek tek seçilerek denetlenecek.")

            # Temel klasör seçme denetimi.
            for ad in SISTEM_KLASORLERI:
                klasor = klasor_haritasi.get(ad, VARSAYILAN_KLASOR_HARITASI.get(ad, "INBOX"))
                tip, _ = imap.select(klasor, readonly=True)
                if tip != "OK":
                    ekle("Uyarı", f"{ad} klasörü", "Klasör seçilemedi. Gmail hesabınızda bu klasör farklı adla görünüyor olabilir.")
                else:
                    ekle("Başarılı", f"{ad} klasörü", "Klasör seçilebildi.")
        finally:
            try:
                imap.logout()
            except Exception:
                pass
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

def yardim_belgesini_ac():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    adaylar = [
        os.path.join(base_dir, "doc", "tr", "readme.html"),
    ]
    for yol in adaylar:
        if os.path.exists(yol):
            try:
                os.startfile(yol)
                return True
            except Exception as e:
                hata_kaydet("Yardım dosyası açılamadı.", e)
                break
    ui.message("Yardım dosyası bulunamadı. Lütfen eklenti klasörünü kontrol edin.")
    return False


def ne_yeni_belgesini_ac():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    adaylar = [
        os.path.join(base_dir, "doc", "tr", "ne-yeni.html"),
    ]
    for yol in adaylar:
        if os.path.exists(yol):
            try:
                os.startfile(yol)
                return True
            except Exception as e:
                hata_kaydet("Yenilikler dosyası açılamadı.", e)
                break
    ui.message("Yenilikler dosyası bulunamadı. Lütfen doc/tr/ne-yeni.html dosyasını kontrol edin.")
    return False


def nvda_surumunu_al():
    try:
        if versionInfo is not None:
            surum = getattr(versionInfo, "version", "")
            if surum:
                return str(surum)
            yil = getattr(versionInfo, "version_year", None)
            ana = getattr(versionInfo, "version_major", None)
            alt = getattr(versionInfo, "version_minor", None)
            yapi = getattr(versionInfo, "version_build", None)
            parcalar = [str(x) for x in (yil, ana, alt, yapi) if x is not None]
            if parcalar:
                return ".".join(parcalar)
    except Exception as e:
        hata_kaydet("NVDA sürümü alınamadı.", e)
    return "Bilinmiyor"


def hakkinda_penceresini_ac(parent=None):
    metin = (
        f"{EKLENTI_ADI}\n\n"
        f"Eklenti sürümü: {EKLENTI_SURUMU}\n"
        f"NVDA sürümü: {nvda_surumunu_al()}\n"
        "Geliştirici: Mehmet Aykurt\n"
        "E-posta: m.aykurt38@gmail.com\n"
        "Lisans: GNU Genel Kamu Lisansı, sürüm 2.0\n\n"
        "Engelsiz Mail, NVDA ekran okuyucusu kullanıcıları için geliştirilen erişilebilir e-posta eklentisidir."
    )
    try:
        gui.messageBox(
            metin,
            f"{EKLENTI_ADI} Hakkında",
            wx.OK | wx.ICON_INFORMATION,
            parent,
        )
    except TypeError:
        gui.messageBox(metin, f"{EKLENTI_ADI} Hakkında", wx.OK | wx.ICON_INFORMATION)


def uygulama_sifresi_sayfasini_ac():
    url = "https://myaccount.google.com/apppasswords"
    try:
        os.startfile(url)
        return True
    except Exception as e:
        hata_kaydet("Uygulama şifresi sayfası os.startfile ile açılamadı.", e)
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        hata_kaydet("Uygulama şifresi sayfası webbrowser ile açılamadı.", e)
    ui.message("Uygulama şifresi sayfası açılamadı. Adresi tarayıcınızda açabilirsiniz: https://myaccount.google.com/apppasswords")
    return False


class BaglantiDenetimSonucPenceresi(wx.Dialog):
    def __init__(self, parent, basarili, rapor):
        super().__init__(parent, title="Engelsiz Mail - Bağlantı Denetimi")
        self.rapor = str(rapor or "")
        self.detay_gosteriliyor = False

        ozet = self.ozet_metni_olustur(bool(basarili), self.rapor)

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="Bağlantı denetimi özeti:"), 0, wx.ALL, 5)
        self.txt_ozet = wx.TextCtrl(self, value=ozet, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_ozet.SetName("Bağlantı denetimi özeti")
        duzen.Add(self.txt_ozet, 0, wx.ALL | wx.EXPAND, 5)

        self.txt_ayrinti = wx.TextCtrl(self, value=self.rapor, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_ayrinti.SetName("Bağlantı denetimi ayrıntıları")
        duzen.Add(self.txt_ayrinti, 1, wx.ALL | wx.EXPAND, 5)
        self.txt_ayrinti.Hide()
        gorunum_denetimlerine_uygula(self.txt_ozet, self.txt_ayrinti)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ayrinti_btn = wx.Button(self, label="&Ayrıntıları Görüntüle")
        self.ayrinti_btn.Bind(wx.EVT_BUTTON, self.ayrintilari_goster)
        btn_duzen.Add(self.ayrinti_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, wx.ID_OK, label="&Kapat")
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 5)

        self.SetSizer(duzen)
        self.SetSize((760, 420))
        self.CenterOnParent()
        wx.CallAfter(self.txt_ozet.SetFocus)

    def ozet_metni_olustur(self, basarili, rapor):
        rapor = rapor or ""
        rapor_kucuk = rapor.lower()
        if "tamamlanamadı" in rapor_kucuk or "sonuç: sorun bulundu" in rapor_kucuk:
            return "Bağlantı denetimi tamamlandı. Sorun algılandı. Ayrıntıları görüntüleyerek sorunun hangi aşamada oluştuğunu inceleyebilirsiniz."
        if "uyarı var" in rapor_kucuk:
            return "Bağlantı denetimi tamamlandı. Bağlantınız çalışıyor; ancak uyarı var. Ayrıntıları görüntüleyerek uyarıları inceleyebilirsiniz."
        if basarili:
            return "Bağlantı denetimi tamamlandı. Bağlantınız başarılı. Herhangi bir sorun algılanmadı."
        return "Bağlantı denetimi tamamlandı. Sonuç kesin olarak doğrulanamadı. Ayrıntıları görüntüleyerek denetim adımlarını inceleyebilirsiniz."

    def ayrintilari_goster(self, event):
        if not self.detay_gosteriliyor:
            self.detay_gosteriliyor = True
            self.txt_ayrinti.Show()
            self.ayrinti_btn.SetLabel("Ayrıntıları &Gizle")
            self.Layout()
            self.SetSize((760, 600))
            wx.CallAfter(self.txt_ayrinti.SetFocus)
        else:
            self.detay_gosteriliyor = False
            self.txt_ayrinti.Hide()
            self.ayrinti_btn.SetLabel("&Ayrıntıları Görüntüle")
            self.Layout()
            self.SetSize((760, 420))
            wx.CallAfter(self.txt_ozet.SetFocus)


class AyarlarPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Hesaba Bağlan")
        ayarlar = ayarlari_yukle()
        self._kayitli_eposta = str(ayarlar.get("eposta", "") or "").strip()
        self._kayitli_sifre = str(ayarlar.get("sifre", "") or "").strip().replace(" ", "")
        self._baglanti_kontrol_ediliyor = False
        self._kapatildi = False
        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)

        duzen = wx.BoxSizer(wx.VERTICAL)

        duzen.Add(wx.StaticText(self, label="&E-posta adresiniz:"), 0, wx.ALL, 5)
        self.txt_eposta = wx.TextCtrl(self, value=self._kayitli_eposta)
        self.txt_eposta.SetName("E-posta adresi")
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Google uygulama şifreniz (16 hane):"), 0, wx.ALL, 5)
        self.txt_sifre = wx.TextCtrl(self, value="", style=wx.TE_PASSWORD)
        self.txt_sifre.SetName("Google uygulama şifresi")
        duzen.Add(self.txt_sifre, 0, wx.ALL | wx.EXPAND, 5)
        if self._kayitli_sifre:
            bilgi = wx.StaticText(
                self,
                label="Kayıtlı uygulama şifresi korunacaktır. Değiştirmek istemiyorsanız bu alanı boş bırakabilirsiniz.",
            )
            duzen.Add(bilgi, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.kaydet_btn = wx.Button(self, label="&Kaydet ve Bağlan")
        self.kaydet_btn.Bind(wx.EVT_BUTTON, self.kaydet_basildi)
        btn_duzen.Add(self.kaydet_btn, 0, wx.ALL, 5)

        sifre_olustur_btn = wx.Button(self, label="Şifre &Oluştur")
        sifre_olustur_btn.Bind(wx.EVT_BUTTON, self.sifre_olustur_basildi)
        btn_duzen.Add(sifre_olustur_btn, 0, wx.ALL, 5)

        yardim_btn = wx.Button(self, label="Uygulama Şifresi &Yardımı")
        yardim_btn.Bind(wx.EVT_BUTTON, self.yardim_basildi)
        btn_duzen.Add(yardim_btn, 0, wx.ALL, 5)

        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((650, 315 if self._kayitli_sifre else 275))
        self.CenterOnParent()
        wx.CallAfter(self.txt_eposta.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def pencere_kapatiliyor(self, event):
        if self._baglanti_kontrol_ediliyor:
            ui.message("Bağlantı denetleniyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        event.Skip()

    def sifre_olustur_basildi(self, event):
        uygulama_sifresi_sayfasini_ac()

    def yardim_basildi(self, event):
        yardim_belgesini_ac()

    def alanlari_etkinlestir(self, etkin=True):
        for denetim in (self.txt_eposta, self.txt_sifre, self.kaydet_btn, self.iptal_btn):
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def kaydet_basildi(self, event):
        if self._baglanti_kontrol_ediliyor:
            return

        eposta = self.txt_eposta.GetValue().strip()
        sifre = self.txt_sifre.GetValue().strip().replace(" ", "")

        eposta_degisti = eposta.lower() != self._kayitli_eposta.lower()
        etkin_sifre = sifre or ("" if eposta_degisti else self._kayitli_sifre)

        if not eposta:
            ui.message("Lütfen e-posta adresi alanını doldurun.")
            self.txt_eposta.SetFocus()
            return
        if not eposta_adresi_gecerli_mi(eposta):
            ui.message("Lütfen geçerli bir e-posta adresi yazın.")
            self.txt_eposta.SetFocus()
            return
        if not etkin_sifre:
            if eposta_degisti:
                ui.message("E-posta adresini değiştirdiğiniz için yeni Google uygulama şifresini yazmanız gerekir.")
            else:
                ui.message("Lütfen Google uygulama şifresi alanını doldurun.")
            self.txt_sifre.SetFocus()
            return
        if len(etkin_sifre) < 12:
            ui.message("Uygulama şifresi eksik görünüyor. Lütfen Google tarafından verilen şifreyi boşluksuz yazın.")
            self.txt_sifre.SetFocus()
            return

        self._baglanti_kontrol_ediliyor = True
        self.alanlari_etkinlestir(False)
        ui.message("Bağlantı denetleniyor. Lütfen bekleyin.")
        arka_planda_calistir(self._baglantiyi_denetle, eposta, etkin_sifre)

    def _baglantiyi_denetle(self, eposta, sifre):
        try:
            with ImapBaglantisi({"eposta": eposta, "sifre": sifre}):
                pass
            guvenli_call_after(self, self._baglanti_basarili, eposta, sifre)
        except Exception as e:
            hata_kaydet("Hesap bağlantısı doğrulanamadı.", e)
            guvenli_call_after(self, self._baglanti_hatali)

    def _baglanti_basarili(self, eposta, sifre):
        if not pencere_kullanilabilir_mi(self):
            return
        self._baglanti_kontrol_ediliyor = False
        if ayarlari_kaydet(eposta, sifre):
            gui.messageBox(
                "Gmail bağlantısı kuruldu. E-posta adresiniz NVDA yapılandırma klasörüne, uygulama şifreniz ise Windows kullanıcı hesabınıza bağlı şifreli biçimde kaydedildi.",
                "Bağlantı Başarılı",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.EndModal(wx.ID_OK)
        else:
            self.alanlari_etkinlestir(True)
            ui.message("Hesap bilgileri kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")

    def _baglanti_hatali(self):
        if not pencere_kullanilabilir_mi(self):
            return
        self._baglanti_kontrol_ediliyor = False
        self.alanlari_etkinlestir(True)
        gui.messageBox(
            "Gmail hesabına bağlanılamadı. Lütfen e-posta adresinizi, Google uygulama şifrenizi ve internet bağlantınızı kontrol edin. Ayrıntılı denetim için Dosya menüsündeki Bağlantıyı Denetle seçeneğini kullanabilirsiniz.",
            "Bağlantı Başarısız",
            wx.OK | wx.ICON_WARNING,
        )
        self.txt_sifre.SetFocus()


class MesajSayisiPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - E-posta Sayısı")
        ayarlar = ayarlari_yukle()

        duzen = wx.BoxSizer(wx.VERTICAL)
        bilgi = f"Listelenecek e-posta sayısı ({EN_AZ_MESAJ_SAYISI} ile {EN_COK_MESAJ_SAYISI} arasında):"
        duzen.Add(wx.StaticText(self, label="&" + bilgi), 0, wx.ALL, 5)
        self.txt_mesaj_sayisi = wx.TextCtrl(
            self,
            value=str(ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)),
        )
        self.txt_mesaj_sayisi.SetName("Listelenecek e-posta sayısı")
        duzen.Add(self.txt_mesaj_sayisi, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label="&Tamam")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((460, 170))
        self.CenterOnParent()
        wx.CallAfter(self.txt_mesaj_sayisi.SetFocus)

    def tamam_basildi(self, event):
        try:
            mesaj_sayisi = mesaj_sayisi_metnini_dogrula(self.txt_mesaj_sayisi.GetValue())
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_mesaj_sayisi.SetFocus()
            return

        if mesaj_sayisini_kaydet(mesaj_sayisi):
            ui.message(f"Listelenecek e-posta sayısı {mesaj_sayisi} olarak kaydedildi.")
            self.EndModal(wx.ID_OK)
        else:
            ui.message("E-posta sayısı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")



class BildirimAyarlariPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Bildirimler")
        ayarlar = bildirim_ayarlari_yukle()

        duzen = wx.BoxSizer(wx.VERTICAL)

        bilgi = (
            "Yeni e-posta bildirimleri, NVDA çalışırken arka planda belirli aralıklarla "
            "Gelen Kutusu denetlenerek kullanılacaktır. Bu pencerede yalnızca bildirim ayarları kaydedilir."
        )
        duzen.Add(wx.StaticText(self, label=bilgi), 0, wx.ALL | wx.EXPAND, 5)

        self.chk_bildirim = wx.CheckBox(self, label="&Yeni e-posta bildirimi")
        self.chk_bildirim.SetValue(ayarlar.get(BILDIRIM_ETKIN_ALANI, False))
        duzen.Add(self.chk_bildirim, 0, wx.ALL, 5)

        duzen.Add(wx.StaticText(self, label="Kaç dakikada bir &bakılsın:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.cmb_aralik = wx.Choice(
            self,
            choices=[f"{dakika} dakika" for dakika in BILDIRIM_ARALIK_SECENEKLERI],
        )
        self.cmb_aralik.SetName("Bildirim kontrol aralığı")
        mevcut_aralik = bildirim_araligini_duzenle(ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI))
        try:
            self.cmb_aralik.SetSelection(BILDIRIM_ARALIK_SECENEKLERI.index(mevcut_aralik))
        except Exception:
            self.cmb_aralik.SetSelection(BILDIRIM_ARALIK_SECENEKLERI.index(VARSAYILAN_BILDIRIM_ARALIGI))
        duzen.Add(self.cmb_aralik, 0, wx.ALL | wx.EXPAND, 5)

        self.chk_ses = wx.CheckBox(self, label="&Sesle bildir")
        self.chk_ses.SetValue(ayarlar.get(BILDIRIM_SES_ALANI, True))
        self.chk_ses.Bind(wx.EVT_CHECKBOX, self.ses_alanlarini_guncelle)
        duzen.Add(self.chk_ses, 0, wx.ALL, 5)

        ses_kutusu = wx.StaticBox(self, label="Bildirim sesi")
        ses_duzen = wx.StaticBoxSizer(ses_kutusu, wx.VERTICAL)

        self.rb_sistem_sesi = wx.RadioButton(self, label="&Varsayılan sistem sesini kullan", style=wx.RB_GROUP)
        self.rb_ozel_ses = wx.RadioButton(self, label="&Kullanıcı tanımlı WAV dosyası kullan")
        self.rb_sistem_sesi.Bind(wx.EVT_RADIOBUTTON, self.ses_alanlarini_guncelle)
        self.rb_ozel_ses.Bind(wx.EVT_RADIOBUTTON, self.ses_alanlarini_guncelle)

        ses_turu = ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        self.rb_ozel_ses.SetValue(ses_turu == BILDIRIM_SES_TURU_DOSYA)
        self.rb_sistem_sesi.SetValue(ses_turu != BILDIRIM_SES_TURU_DOSYA)

        ses_duzen.Add(self.rb_sistem_sesi, 0, wx.ALL, 5)
        ses_duzen.Add(self.rb_ozel_ses, 0, wx.ALL, 5)

        dosya_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_ses_dosyasi = wx.TextCtrl(self, value=ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, ""))
        self.txt_ses_dosyasi.SetName("Bildirim sesi dosyası")
        dosya_duzen.Add(self.txt_ses_dosyasi, 1, wx.ALL | wx.EXPAND, 5)

        self.btn_ses_sec = wx.Button(self, label="G&özat...")
        self.btn_ses_sec.Bind(wx.EVT_BUTTON, self.ses_dosyasi_sec)
        dosya_duzen.Add(self.btn_ses_sec, 0, wx.ALL, 5)

        self.btn_ses_dinle = wx.Button(self, label="&Dinle")
        self.btn_ses_dinle.Bind(wx.EVT_BUTTON, self.ses_dosyasi_dinle)
        dosya_duzen.Add(self.btn_ses_dinle, 0, wx.ALL, 5)

        ses_duzen.Add(dosya_duzen, 0, wx.EXPAND)
        duzen.Add(ses_duzen, 0, wx.ALL | wx.EXPAND, 5)

        self.chk_mesaj = wx.CheckBox(self, label="&Mesajla bildir")
        self.chk_mesaj.SetValue(ayarlar.get(BILDIRIM_MESAJ_ALANI, True))
        duzen.Add(self.chk_mesaj, 0, wx.ALL, 5)

        self.chk_gonderen = wx.CheckBox(self, label="Gönderen &adresini bildir")
        self.chk_gonderen.SetValue(ayarlar.get(BILDIRIM_GONDEREN_ALANI, False))
        duzen.Add(self.chk_gonderen, 0, wx.ALL, 5)

        self.chk_konu = wx.CheckBox(self, label="&Konuyu bildir")
        self.chk_konu.SetValue(ayarlar.get(BILDIRIM_KONU_ALANI, False))
        duzen.Add(self.chk_konu, 0, wx.ALL, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label="&Tamam")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((640, 560))
        self.CenterOnParent()
        self.ses_alanlarini_guncelle()
        wx.CallAfter(self.chk_bildirim.SetFocus)

    def secili_araligi_al(self):
        secim = self.cmb_aralik.GetSelection()
        if secim == wx.NOT_FOUND:
            return VARSAYILAN_BILDIRIM_ARALIGI
        try:
            return BILDIRIM_ARALIK_SECENEKLERI[secim]
        except Exception:
            return VARSAYILAN_BILDIRIM_ARALIGI

    def secili_ses_turunu_al(self):
        if self.rb_ozel_ses.GetValue():
            return BILDIRIM_SES_TURU_DOSYA
        return BILDIRIM_SES_TURU_SISTEM

    def ses_alanlarini_guncelle(self, event=None):
        sesle_bildir = self.chk_ses.GetValue()
        ozel_ses = self.rb_ozel_ses.GetValue()
        try:
            self.rb_sistem_sesi.Enable(sesle_bildir)
            self.rb_ozel_ses.Enable(sesle_bildir)
            self.txt_ses_dosyasi.Enable(sesle_bildir and ozel_ses)
            self.btn_ses_sec.Enable(sesle_bildir and ozel_ses)
            self.btn_ses_dinle.Enable(sesle_bildir and ozel_ses)
        except Exception:
            pass
        if event is not None:
            event.Skip()

    def ses_dosyasi_sec(self, event=None):
        mevcut_yol = self.txt_ses_dosyasi.GetValue().strip()
        mevcut_klasor = os.path.dirname(mevcut_yol) if mevcut_yol else os.path.expanduser("~")
        if not os.path.isdir(mevcut_klasor):
            mevcut_klasor = os.path.expanduser("~")

        dlg = wx.FileDialog(
            self,
            "Bildirim sesi olarak kullanılacak WAV dosyasını seçin",
            defaultDir=mevcut_klasor,
            wildcard="WAV dosyaları (*.wav)|*.wav",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.txt_ses_dosyasi.SetValue(dlg.GetPath())
                self.rb_ozel_ses.SetValue(True)
                self.rb_sistem_sesi.SetValue(False)
                self.ses_alanlarini_guncelle()
        finally:
            dlg.Destroy()

    def ses_dosyasi_dinle(self, event=None):
        ses_dosyasi = self.txt_ses_dosyasi.GetValue().strip()
        if not ses_dosyasi:
            ui.message("Dinlenecek WAV dosyası seçilmedi.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if not ses_dosyasi.lower().endswith(".wav"):
            ui.message("Yalnızca WAV uzantılı bildirim sesi dinlenebilir.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if not os.path.exists(ses_dosyasi):
            ui.message("Seçilen bildirim sesi dosyası bulunamadı.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if winsound is None:
            ui.message("Bu sistemde ses dinleme desteği kullanılamıyor.")
            return
        try:
            winsound.PlaySound(ses_dosyasi, winsound.SND_FILENAME | winsound.SND_ASYNC)
            ui.message("Bildirim sesi çalınıyor.")
        except Exception as e:
            hata_kaydet("Bildirim sesi dinletilemedi.", e)
            ui.message("Bildirim sesi çalınamadı.")

    def tamam_basildi(self, event):
        if not self.chk_ses.GetValue() and not self.chk_mesaj.GetValue():
            ui.message("Bildirim için sesle bildir veya mesajla bildir seçeneklerinden en az biri işaretli olmalıdır.")
            self.chk_ses.SetFocus()
            return

        ses_turu = self.secili_ses_turunu_al()
        ses_dosyasi = self.txt_ses_dosyasi.GetValue().strip()

        if self.chk_ses.GetValue() and ses_turu == BILDIRIM_SES_TURU_DOSYA:
            if not ses_dosyasi:
                ui.message("Kullanıcı tanımlı ses için bir WAV dosyası seçilmelidir.")
                self.txt_ses_dosyasi.SetFocus()
                return
            if not ses_dosyasi.lower().endswith(".wav"):
                ui.message("Bildirim sesi için WAV uzantılı bir dosya seçilmelidir.")
                self.txt_ses_dosyasi.SetFocus()
                return
            if not os.path.exists(ses_dosyasi):
                ui.message("Seçilen bildirim sesi dosyası bulunamadı.")
                self.txt_ses_dosyasi.SetFocus()
                return

        if bildirim_ayarlari_kaydet(
            self.chk_bildirim.GetValue(),
            self.secili_araligi_al(),
            self.chk_ses.GetValue(),
            ses_turu,
            ses_dosyasi,
            self.chk_mesaj.GetValue(),
            self.chk_gonderen.GetValue(),
            self.chk_konu.GetValue(),
        ):
            bildirim_yoneticisini_yenile()
            bildirim_soyle("Bildirim ayarları kaydedildi.", 350)
            self.EndModal(wx.ID_OK)
        else:
            ui.message("Bildirim ayarları kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")



class OneriGorusPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Öneri ve Görüş Bildir")
        self._gonderiliyor = False
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        duzen = wx.BoxSizer(wx.VERTICAL)
        bilgi = (
            "İletişim Formu\n"
            "Her türlü öneri, görüş ve düşünceniz için bize yazın.\n"
            "Bildiriminiz bağlı Gmail hesabınız üzerinden gönderilecektir.\n"
            "Bildiriminiz değerlendirilecek ve en kısa süre içinde size dönüş yapılacaktır."
        )
        duzen.Add(wx.StaticText(self, label=bilgi), 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Ad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_ad = wx.TextCtrl(self)
        self.txt_ad.SetName("Ad")
        duzen.Add(self.txt_ad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Soyad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_soyad = wx.TextCtrl(self)
        self.txt_soyad.SetName("Soyad")
        duzen.Add(self.txt_soyad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="Yanıt için &e-posta adresiniz:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label="Lütfen e-posta adresinizi doğru yazdığınızdan emin olun."
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_eposta = wx.TextCtrl(self)
        self.txt_eposta.SetName("Yanıt için e-posta adresi")
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Konu:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label="Bildiriminizin konusu"
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_konu = wx.TextCtrl(self)
        self.txt_konu.SetName("Konu")
        duzen.Add(self.txt_konu, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Bildirim metni:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label="Bildirim metniniz"
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_mesaj = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_RICH2)
        self.txt_mesaj.SetName("Bildirim metni")
        duzen.Add(self.txt_mesaj, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.gonder_btn = wx.Button(self, label="&Gönder")
        self.gonder_btn.Bind(wx.EVT_BUTTON, self.gonder_tiklandi)
        btn_duzen.Add(self.gonder_btn, 0, wx.ALL, 5)

        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((640, 560))
        self.CenterOnParent()
        wx.CallAfter(self.txt_ad.SetFocus)

    def tus_yakalandi(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            if not self._gonderiliyor:
                self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()

    def alanlari_etkinlestir(self, etkin=True):
        for denetim in (
            self.txt_ad,
            self.txt_soyad,
            self.txt_eposta,
            self.txt_konu,
            self.txt_mesaj,
            self.gonder_btn,
            self.iptal_btn,
        ):
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def form_verisini_al(self):
        return {
            "ad": self.txt_ad.GetValue().strip(),
            "soyad": self.txt_soyad.GetValue().strip(),
            "eposta": self.txt_eposta.GetValue().strip(),
            "konu": self.txt_konu.GetValue().strip(),
            "mesaj": self.txt_mesaj.GetValue().strip(),
        }

    def formu_dogrula(self, veri):
        if not veri["ad"]:
            self.txt_ad.SetFocus()
            raise MailHatasi("Lütfen ad alanını doldurun.")
        if not veri["soyad"]:
            self.txt_soyad.SetFocus()
            raise MailHatasi("Lütfen soyad alanını doldurun.")
        if not eposta_adresi_gecerli_mi(veri["eposta"]):
            self.txt_eposta.SetFocus()
            raise MailHatasi("Size yanıt verilebilmesi için lütfen geçerli bir e-posta adresi yazın.")
        if not veri["konu"]:
            self.txt_konu.SetFocus()
            raise MailHatasi("Lütfen konu alanını doldurun.")
        if not veri["mesaj"]:
            self.txt_mesaj.SetFocus()
            raise MailHatasi("Lütfen bildirim metni alanını doldurun.")

    def gonder_tiklandi(self, event=None):
        if self._gonderiliyor:
            return
        ayarlar = ayarlari_yukle()
        if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
            gui.messageBox(
                "Öneri ve görüş göndermek için önce Dosya menüsünden Bağlan seçeneğiyle Gmail hesabınızı bağlayın.",
                "Hesap Bilgisi Eksik",
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        veri = self.form_verisini_al()
        try:
            self.formu_dogrula(veri)
        except MailHatasi as e:
            ui.message(str(e))
            return

        self._gonderiliyor = True
        self.alanlari_etkinlestir(False)
        ui.message("Öneri ve görüş gönderiliyor.")
        arka_planda_calistir(self.arka_planda_gonder, ayarlar, veri)

    def arka_planda_gonder(self, ayarlar, veri):
        try:
            konu = eposta_basligi_tek_satir_yap(veri.get("konu", "")) or "Konu belirtilmedi"
            baslik = f"[Engelsiz Mail] Öneri ve Görüş: {konu}"
            icerik = (
                "Engelsiz Mail eklentisi üzerinden öneri ve görüş bildirimi gönderildi.\n\n"
                f"Ad: {veri.get('ad', '')}\n"
                f"Soyad: {veri.get('soyad', '')}\n"
                f"Yanıt için e-posta: {veri.get('eposta', '')}\n"
                "Eklenti: Engelsiz Mail\n"
                f"Gönderen Gmail hesabı: {ayarlar.get('eposta', '')}\n"
                f"Konu: {konu}\n\n"
                "Bildirim metni:\n"
                f"{veri.get('mesaj', '')}\n"
            )
            mesaj = eposta_mesaji_olustur(
                ayarlar["eposta"],
                ONERI_GORUS_ALICI,
                baslik,
                icerik,
                [],
                ek_basliklar={"Reply-To": veri.get("eposta", "")},
                taslak=False,
            )
            smtp_ssl_ile_gonder(ayarlar["eposta"], ayarlar["sifre"], [ONERI_GORUS_ALICI], mesaj)
            guvenli_call_after(self, self.gonderim_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, self.gonderim_hatali, str(e))
        except Exception as e:
            hata_kaydet("Öneri ve görüş gönderilemedi.", e)
            guvenli_call_after(self, self.gonderim_hatali, "Öneri ve görüş gönderilemedi. Lütfen bağlantınızı ve Google uygulama şifrenizi kontrol edin.")

    def gonderim_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        ui.message("Öneri ve görüşünüz gönderildi.")
        self.EndModal(wx.ID_OK)

    def gonderim_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._gonderiliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_mesaj.SetFocus()

def dosya_boyutu_metni(boyut):
    """Bayt cinsinden dosya boyutunu kısa okunabilir metne çevirir."""
    try:
        boyut = int(boyut)
    except Exception:
        boyut = 0
    if boyut >= 1024 * 1024:
        return f"{boyut / (1024 * 1024):.1f} MB"
    if boyut >= 1024:
        return f"{boyut / 1024:.1f} KB"
    return f"{boyut} bayt"




def ham_eposta_boyutunu_denetle(ham_veri, islem_adi="E-posta"):
    """Aşırı büyük ham e-postaların NVDA'yı veya belleği zorlamasını engeller."""
    boyut = len(ham_veri or b"")
    if boyut <= 0:
        raise MailHatasi("E-posta içeriği boş döndü.")
    if boyut > AZAMI_EPOSTA_ISLEME_BOYUTU:
        raise MailHatasi(
            f"{islem_adi} çok büyük. Bu işlem için en çok "
            f"{dosya_boyutu_metni(AZAMI_EPOSTA_ISLEME_BOYUTU)} boyutunda e-posta işlenebilir. "
            "E-postayı Gmail web arayüzünden veya başka bir posta istemcisinden açmayı deneyin."
        )
    return boyut


def eml_dosya_boyutunu_denetle(dosya_yolu):
    """EML içe aktarmada aşırı büyük veya boş dosyaları belleğe almadan önce denetler."""
    try:
        boyut = os.path.getsize(dosya_yolu)
    except OSError as e:
        raise MailHatasi("EML dosya boyutu okunamadı.") from e
    if boyut <= 0:
        raise MailHatasi("EML dosyası boş görünüyor.")
    if boyut > AZAMI_EML_DOSYA_BOYUTU:
        raise MailHatasi(
            f"EML dosyası çok büyük. En çok {dosya_boyutu_metni(AZAMI_EML_DOSYA_BOYUTU)} boyutunda EML dosyası açılabilir."
        )
    return boyut


def ek_kayitlari_boyutunu_denetle(ek_kayitlari):
    """Gönderilecek veya taslak kaydedilecek eklerin boyutunu Gmail sınırı için denetler."""
    toplam = 0
    for kayit in ek_kayitlari or []:
        if isinstance(kayit, str):
            kayit = {"tur": "dosya", "yol": kayit}
        if not isinstance(kayit, dict):
            continue

        tur = kayit.get("tur")
        if tur == "hazir":
            ad = guvenli_coz(kayit.get("ad") or "ek_dosya")
            boyut = len(kayit.get("veri") or b"")
        else:
            yol = str(kayit.get("yol", "") or "").strip()
            if not yol or not os.path.isfile(yol):
                continue
            ad = os.path.basename(yol)
            try:
                boyut = os.path.getsize(yol)
            except OSError as e:
                raise MailHatasi(f"Ek dosya boyutu okunamadı: {ad}") from e

        if boyut > AZAMI_TEK_EK_BOYUTU:
            raise MailHatasi(
                f"Ek dosya çok büyük: {ad}. Tek ek en çok {dosya_boyutu_metni(AZAMI_TEK_EK_BOYUTU)} olabilir."
            )
        toplam += boyut

    if toplam > AZAMI_TOPLAM_EK_BOYUTU:
        raise MailHatasi(
            f"Ek dosyaların toplam boyutu çok büyük. Toplam ek boyutu en çok {dosya_boyutu_metni(AZAMI_TOPLAM_EK_BOYUTU)} olabilir."
        )


def eposta_mesaji_olustur(gonderen, kime_basligi, konu, icerik, ek_kayitlari, ek_basliklar=None, taslak=False):
    """Gönderim veya taslak kaydı için MIME ileti oluşturur."""
    ek_kayitlari_boyutunu_denetle(ek_kayitlari)
    mesaj = EmailMessage(policy=SMTP)
    mesaj["From"] = gonderen
    kime_basligi = str(kime_basligi or "").strip()
    if kime_basligi:
        duzenli_kime = adres_basligini_duzenle(kime_basligi)
        if not duzenli_kime:
            raise MailHatasi("Alıcı alanında geçerli e-posta adresi bulunamadı.")
        mesaj["To"] = duzenli_kime
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
        tur = kayit.get("tur")
        if tur == "hazir":
            dosya_adi = guvenli_coz(kayit.get("ad") or "ek_dosya")
            veri = kayit.get("veri") or b""
            if not veri:
                continue
            maintype, subtype = ek_icerik_turu_bul(dosya_adi)
            mesaj.add_attachment(veri, maintype=maintype, subtype=subtype, filename=dosya_adi)
            continue

        dosya_yolu = kayit.get("yol", "")
        if not os.path.isfile(dosya_yolu):
            raise MailHatasi(f"Ek dosya bulunamadı: {os.path.basename(dosya_yolu)}")
        maintype, subtype = ek_icerik_turu_bul(dosya_yolu)
        with open(dosya_yolu, "rb") as dosya:
            mesaj.add_attachment(
                dosya.read(),
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(dosya_yolu),
            )
    return mesaj


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


def taslagi_sunucuya_kaydet(kime, konu, icerik, ek_kayitlari, yanit_basliklari=None, taslak_klasor_adaylari=None):
    """İletiyi Gmail Taslaklar klasörüne kaydeder."""
    ayarlar = ayarlari_yukle()
    if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
        raise MailHatasi("Hesap bilgileri eksik.")

    mesaj = eposta_mesaji_olustur(
        ayarlar["eposta"],
        kime,
        konu,
        icerik,
        ek_kayitlari,
        ek_basliklar=yanit_basliklari,
        taslak=True,
    )
    ham_mesaj = mesaj.as_bytes(policy=SMTP)

    son_hata = ""
    with ImapBaglantisi(ayarlar) as imap:
        for aday_klasor in taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari):
            try:
                tip, _veri = imap.append(aday_klasor, "(\\Draft)", None, ham_mesaj)
                if tip == "OK":
                    return True
                son_hata = f"Taslak klasörü kabul etmedi: {aday_klasor}"
            except Exception as e:
                son_hata = f"Taslak kaydetme denemesi başarısız: {aday_klasor}"
                hata_kaydet(son_hata, e)
                continue

    raise MailHatasi("Taslak, Gmail'in Taslaklar klasörüne kaydedilemedi.")


class KisiDuzenlemePenceresi(wx.Dialog):
    def __init__(self, parent, kisi=None, baslik="Kişi Oluştur"):
        super().__init__(parent, title=baslik)
        kisi = dict(kisi or {})
        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Ad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_ad = wx.TextCtrl(self, value=str(kisi.get("ad", "")))
        self.txt_ad.SetName("Kişi adı")
        duzen.Add(self.txt_ad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Soyad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_soyad = wx.TextCtrl(self, value=str(kisi.get("soyad", "")))
        self.txt_soyad.SetName("Kişi soyadı")
        duzen.Add(self.txt_soyad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&E-posta adresi:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_eposta = wx.TextCtrl(self, value=str(kisi.get("eposta", "")))
        self.txt_eposta.SetName("Kişi e-posta adresi")
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, wx.ID_OK, "&Kaydet")
        iptal_btn = wx.Button(self, wx.ID_CANCEL, "İ&ptal")
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((420, 260))
        self.CenterOnParent()
        tamam_btn.Bind(wx.EVT_BUTTON, self.kaydet)
        gorunum_denetimlerine_uygula(self.txt_ad, self.txt_soyad, self.txt_eposta)
        wx.CallAfter(self.txt_ad.SetFocus)

    def veri_al(self):
        return {
            "ad": self.txt_ad.GetValue().strip(),
            "soyad": self.txt_soyad.GetValue().strip(),
            "eposta": self.txt_eposta.GetValue().strip(),
        }

    def kaydet(self, event):
        veri = self.veri_al()
        if not veri["ad"] and not veri["soyad"]:
            ui.message("Lütfen ad veya soyad alanlarından en az birini yazın.")
            self.txt_ad.SetFocus()
            return
        if not eposta_adresi_gecerli_mi(veri["eposta"]):
            ui.message("Lütfen geçerli bir e-posta adresi yazın.")
            self.txt_eposta.SetFocus()
            return
        self.EndModal(wx.ID_OK)


class KisilerPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Kişiler")
        self.kisiler = kisileri_yukle()
        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Kişiler:"), 0, wx.ALL, 5)
        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("Kişiler listesi")
        self.liste.InsertColumn(0, " ", width=700)
        self.liste.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.duzenle)
        duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        gorunum_denetimlerine_uygula(self.liste)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ekle_btn = wx.Button(self, label="&Ekle")
        self.duzenle_btn = wx.Button(self, label="&Düzenle")
        self.sil_btn = wx.Button(self, label="&Sil")
        kapat_btn = wx.Button(self, wx.ID_CANCEL, "&Kapat")
        self.ekle_btn.Bind(wx.EVT_BUTTON, self.ekle)
        self.duzenle_btn.Bind(wx.EVT_BUTTON, self.duzenle)
        self.sil_btn.Bind(wx.EVT_BUTTON, self.sil)
        btn_duzen.Add(self.ekle_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.duzenle_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.sil_btn, 0, wx.ALL, 5)
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((760, 520))
        self.CenterOnParent()
        self._rehber_acilis_duyuru_timer = None
        self._rehber_acilis_odak_timer = None
        self.listeyi_doldur(secim_yap=False)
        wx.CallAfter(self.rehber_acilisini_planla)

    def rehber_acilisini_planla(self):
        try:
            for timer_adi in ("_rehber_acilis_duyuru_timer", "_rehber_acilis_odak_timer"):
                timer = getattr(self, timer_adi, None)
                if timer:
                    try:
                        timer.Stop()
                    except Exception:
                        pass
                    setattr(self, timer_adi, None)
            self._rehber_acilis_duyuru_timer = wx.CallLater(550, self.rehber_durumunu_soyle)
            self._rehber_acilis_odak_timer = wx.CallLater(1100, self.rehber_acilis_liste_odagi_ver)
        except Exception as e:
            hata_kaydet("Kişiler penceresi açılış duyurusu planlanamadı.", e)
            try:
                self.rehber_durumunu_soyle()
                self.rehber_acilis_liste_odagi_ver()
            except Exception as e2:
                hata_kaydet("Kişiler penceresi açılış odağı ayarlanamadı.", e2)

    def rehber_acilis_liste_odagi_ver(self):
        try:
            if self.kisiler and self.liste.GetItemCount() > 0:
                self.liste.Select(0)
                self.liste.Focus(0)
            self.liste.SetFocus()
        except Exception as e:
            hata_kaydet("Kişiler listesine odak verilemedi.", e)

    def rehber_durum_metni(self):
        sayi = len(self.kisiler)
        if sayi <= 0:
            return "Rehberinizde kayıtlı kişi bulunamadı."
        return f"Rehberde {sayi} kişi listelendi."

    def rehber_durumunu_soyle(self, on_mesaj=None):
        mesajlar = []
        if on_mesaj:
            mesajlar.append(str(on_mesaj).strip())
        mesajlar.append(self.rehber_durum_metni())
        ui.message(" ".join(m for m in mesajlar if m))

    def rehber_durumunu_gecikmeli_soyle(self, on_mesaj=None, gecikme_ms=450):
        try:
            wx.CallLater(int(gecikme_ms), self.rehber_durumunu_soyle, on_mesaj)
        except Exception as e:
            hata_kaydet("Rehber durumu gecikmeli duyurulamadı.", e)
            try:
                self.rehber_durumunu_soyle(on_mesaj)
            except Exception as e2:
                hata_kaydet("Rehber durumu duyurulamadı.", e2)

    def listeyi_doldur(self, secilecek_eposta=None, secim_yap=True):
        self.liste.DeleteAllItems()
        secilecek_indeks = 0
        for indeks, kisi in enumerate(self.kisiler):
            self.liste.InsertItem(indeks, kisi_gorunen_ad(kisi))
            if secilecek_eposta and str(kisi.get("eposta", "")).lower() == secilecek_eposta.lower():
                secilecek_indeks = indeks
        if self.kisiler and secim_yap:
            self.liste.Select(secilecek_indeks)
            self.liste.Focus(secilecek_indeks)

    def secili_indeks(self):
        indeks = self.liste.GetFocusedItem()
        if indeks == wx.NOT_FOUND or indeks < 0 or indeks >= len(self.kisiler):
            return None
        return indeks

    def ekle(self, event):
        pencere = KisiDuzenlemePenceresi(self, baslik="Kişi Oluştur")
        kisi = None
        try:
            if pencere.ShowModal() == wx.ID_OK:
                kisi = pencere.veri_al()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi ekleme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.liste.SetFocus()
        except Exception:
            pass
        if kisi is not None:
            try:
                kisi_ekle_veya_guncelle(kisi)
                self.kisiler = kisileri_yukle()
                self.listeyi_doldur(kisi.get("eposta", ""))
                self.rehber_durumunu_gecikmeli_soyle("Kişi kaydedildi.")
            except MailHatasi as e:
                ui.message(str(e))
            except Exception as e:
                hata_kaydet("Kişi kaydedilemedi.", e)
                ui.message("Kişi kaydedilemedi.")

    def duzenle(self, event=None):
        indeks = self.secili_indeks()
        if indeks is None:
            ui.message("Düzenlenecek kişi seçilmedi.")
            return
        eski = dict(self.kisiler[indeks])
        pencere = KisiDuzenlemePenceresi(self, eski, "Kişi Düzenle")
        kisi = None
        try:
            if pencere.ShowModal() == wx.ID_OK:
                kisi = pencere.veri_al()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi düzenleme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.liste.SetFocus()
        except Exception:
            pass
        if kisi is not None:
            try:
                kisi_ekle_veya_guncelle(kisi, eski_eposta=eski.get("eposta", ""))
                self.kisiler = kisileri_yukle()
                self.listeyi_doldur(kisi.get("eposta", ""))
                self.rehber_durumunu_gecikmeli_soyle("Kişi güncellendi.")
            except MailHatasi as e:
                ui.message(str(e))
            except Exception as e:
                hata_kaydet("Kişi güncellenemedi.", e)
                ui.message("Kişi güncellenemedi.")

    def sil(self, event):
        indeks = self.secili_indeks()
        if indeks is None:
            ui.message("Silinecek kişi seçilmedi.")
            return
        kisi = self.kisiler[indeks]
        isim = kisi_gorunen_ad(kisi) or "seçili kişi"
        sonuc = wx.MessageBox(f"{isim} silinsin mi?", "Kişi Sil", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if sonuc != wx.YES:
            self.liste.SetFocus()
            return
        try:
            del self.kisiler[indeks]
            kisileri_kaydet(self.kisiler)
            self.kisiler = kisileri_yukle()
            self.listeyi_doldur()
            self.rehber_durumunu_gecikmeli_soyle("Kişi silindi.")
        except Exception as e:
            hata_kaydet("Kişi silinemedi.", e)
            ui.message("Kişi silinemedi.")


class KisiSecPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Kişilerden Alıcı Seç")
        self.kisiler = kisileri_yukle()
        self.secili_kisiler = []
        self.isaretli_indeksler_kumesi = set()

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Kişiler:"), 0, wx.ALL, 5)

        # wx.CheckListBox bazı Windows/wx/NVDA birleşimlerinde boşluk tuşunu
        # denetimin varsayılan etkinleştirme davranışına bırakabiliyor. Bu da
        # işaretleme yerine beklenmeyen pencere/düzenleme davranışına yol açabiliyor.
        # Bu yüzden seçim penceresinde işaret durumunu biz yönetiyoruz.
        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("Seçilecek kişiler listesi")
        self.liste.InsertColumn(0, "Durum", width=110)
        self.liste.InsertColumn(1, " ", width=560)
        self.liste.Bind(wx.EVT_KEY_DOWN, self.liste_tusuna_basildi)
        duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        gorunum_denetimlerine_uygula(self.liste)

        bilgi = wx.StaticText(self, label="Boşluk tuşuyla kişileri işaretleyip kaldırabilirsiniz. Ekle düğmesi işaretli kişileri alıcı alanına ekler.")
        duzen.Add(bilgi, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, wx.ID_OK, "&Ekle")
        iptal_btn = wx.Button(self, wx.ID_CANCEL, "İ&ptal")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)

        self.SetSizer(duzen)
        self.SetSize((760, 480))
        self.CenterOnParent()
        self.listeyi_doldur()
        wx.CallAfter(self.liste.SetFocus)

    def listeyi_doldur(self):
        self.liste.DeleteAllItems()
        if not self.kisiler:
            return
        for indeks, kisi in enumerate(self.kisiler):
            durum = "İşaretli" if indeks in self.isaretli_indeksler_kumesi else "İşaretli değil"
            item = self.liste.InsertItem(indeks, durum)
            self.liste.SetItem(item, 1, kisi_gorunen_ad(kisi))
        self.liste.Select(0)
        self.liste.Focus(0)

    def secili_indeks(self):
        indeks = self.liste.GetFocusedItem()
        if indeks == wx.NOT_FOUND or indeks < 0 or indeks >= len(self.kisiler):
            return None
        return indeks

    def isaret_durumunu_soyle(self, indeks):
        if indeks is None or indeks < 0 or indeks >= len(self.kisiler):
            return
        durum = "işaretli" if indeks in self.isaretli_indeksler_kumesi else "işaretli değil"
        ad = kisi_gorunen_ad(self.kisiler[indeks])
        ui.message(f"{ad}, {durum}.")

    def isareti_degistir(self, indeks):
        if indeks is None or indeks < 0 or indeks >= len(self.kisiler):
            return
        if indeks in self.isaretli_indeksler_kumesi:
            self.isaretli_indeksler_kumesi.remove(indeks)
        else:
            self.isaretli_indeksler_kumesi.add(indeks)
        self.liste.SetItem(indeks, 0, "İşaretli" if indeks in self.isaretli_indeksler_kumesi else "İşaretli değil")
        self.liste.Select(indeks)
        self.liste.Focus(indeks)
        self.isaret_durumunu_soyle(indeks)

    def liste_tusuna_basildi(self, event):
        tus = event.GetKeyCode()
        if tus in (wx.WXK_SPACE, ord(" ")):
            self.isareti_degistir(self.secili_indeks())
            return
        if tus == wx.WXK_RETURN:
            self.tamam(event)
            return
        event.Skip()

    def tamam(self, event):
        if not self.kisiler:
            ui.message("Kayıtlı kişi yok.")
            return
        secimler = sorted(self.isaretli_indeksler_kumesi)
        if not secimler:
            ui.message("Lütfen boşluk tuşuyla en az bir kişi işaretleyin.")
            self.liste.SetFocus()
            return
        self.secili_kisiler = [self.kisiler[i] for i in secimler if 0 <= i < len(self.kisiler)]
        if not self.secili_kisiler:
            ui.message("Geçerli kişi seçilemedi.")
            return
        self.EndModal(wx.ID_OK)

    def secili_adresler(self):
        return [kisi_eposta_basligi(k) for k in self.secili_kisiler if kisi_eposta_basligi(k)]


class YeniPostaPenceresi(wx.Dialog):
    def __init__(
        self,
        parent,
        varsayilan_kime="",
        varsayilan_konu="",
        varsayilan_icerik="",
        yanit_basliklari=None,
        baslik="Engelsiz Mail - E-posta Yaz",
        gonderildi_callback=None,
        taslak_sil_callback=None,
        taslak_kaydet_callback=None,
        taslak_klasor_adaylari=None,
        hazir_ekler=None,
    ):
        super().__init__(parent, title=baslik)
        self.ek_kayitlari = []
        self.yanit_basliklari = dict(yanit_basliklari or {})
        self.gonderildi_callback = gonderildi_callback
        self.taslak_sil_callback = taslak_sil_callback
        self.taslak_kaydet_callback = taslak_kaydet_callback
        self.taslak_klasor_adaylari = taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari)
        self._kapatildi = False
        self._taslak_kaydediliyor = False
        self._gonderiliyor = False
        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)

        kime_duzen = wx.BoxSizer(wx.HORIZONTAL)
        kime_duzen.Add(wx.StaticText(self, label="&Kime (e-posta adresi):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        gecmis_adresler = rehberi_yukle()
        if varsayilan_kime and varsayilan_kime not in gecmis_adresler:
            gecmis_adresler.insert(0, varsayilan_kime)
        self.txt_kime = wx.ComboBox(self, value=varsayilan_kime, choices=gecmis_adresler, style=wx.CB_DROPDOWN)
        self.txt_kime.SetName("Alıcı e-posta adresleri")
        kime_duzen.Add(self.txt_kime, 1, wx.ALL | wx.EXPAND, 5)
        self.kisi_sec_btn = wx.Button(self, label="Kişilerden &Seç")
        self.kisi_sec_btn.Bind(wx.EVT_BUTTON, self.kisilerden_sec)
        kime_duzen.Add(self.kisi_sec_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.ana_duzen.Add(kime_duzen, 0, wx.EXPAND)

        konu_duzen = wx.BoxSizer(wx.HORIZONTAL)
        konu_duzen.Add(wx.StaticText(self, label="K&onu:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_konu = wx.TextCtrl(self, value=varsayilan_konu)
        self.txt_konu.SetName("E-posta konusu")
        konu_duzen.Add(self.txt_konu, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(konu_duzen, 0, wx.EXPAND)

        self.ana_duzen.Add(wx.StaticText(self, label="&E-posta metni:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_icerik = wx.TextCtrl(self, value=varsayilan_icerik, style=wx.TE_MULTILINE | wx.TE_RICH2)
        self.txt_icerik.SetName("E-posta metni")
        self.ana_duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 5)

        ek_duzen = wx.BoxSizer(wx.HORIZONTAL)
        ek_duzen.Add(wx.StaticText(self, label="Ekli &dosyalar:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.liste_ekler = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 60))
        self.liste_ekler.SetName("Ekli dosyalar listesi")
        ek_duzen.Add(self.liste_ekler, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(ek_duzen, 0, wx.EXPAND)
        gorunum_denetimlerine_uygula(
            self.txt_kime,
            self.kisi_sec_btn,
            self.txt_konu,
            self.txt_icerik,
            self.liste_ekler,
        )

        for dosya_adi, veri in hazir_ekler or []:
            if veri:
                self.ek_kayitlari.append({"tur": "hazir", "ad": guvenli_coz(dosya_adi or "ek_dosya"), "veri": veri})
                self.liste_ekler.Append(guvenli_coz(dosya_adi or "ek_dosya"))

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ek_ekle_btn = wx.Button(self, label="Dosya e&kle")
        self.ek_ekle_btn.Bind(wx.EVT_BUTTON, self.dosya_ekle)
        btn_duzen.Add(self.ek_ekle_btn, 0, wx.ALL, 5)

        self.ek_kaldir_btn = wx.Button(self, label="Eki k&aldır")
        self.ek_kaldir_btn.Bind(wx.EVT_BUTTON, self.ek_kaldir)
        btn_duzen.Add(self.ek_kaldir_btn, 0, wx.ALL, 5)

        self.gonder_btn = wx.Button(self, label="&Gönder")
        self.gonder_btn.Bind(wx.EVT_BUTTON, self.gonder_tiklandi)
        btn_duzen.Add(self.gonder_btn, 0, wx.ALL, 5)

        self.taslak_kaydet_btn = wx.Button(self, label="Taslaklara &Kaydet")
        self.taslak_kaydet_btn.Bind(wx.EVT_BUTTON, self.taslak_kaydet_tiklandi)
        btn_duzen.Add(self.taslak_kaydet_btn, 0, wx.ALL, 5)

        if self.taslak_sil_callback:
            self.taslak_sil_btn = wx.Button(self, label="Taslağı &Sil")
            self.taslak_sil_btn.Bind(wx.EVT_BUTTON, self.taslagi_sil)
            btn_duzen.Add(self.taslak_sil_btn, 0, wx.ALL, 5)
        else:
            self.taslak_sil_btn = None

        self.iptal_btn = wx.Button(self, label="İ&ptal")
        self.iptal_btn.Bind(wx.EVT_BUTTON, self.iptal_tiklandi)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        self.ana_duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(self.ana_duzen)
        self.SetSize((760, 650))
        self.CenterOnParent()

        self._baslangic_durumu = self.taslak_durumu_al()

        if varsayilan_kime:
            wx.CallAfter(self.txt_icerik.SetFocus)
            wx.CallAfter(self.txt_icerik.SetInsertionPoint, 0)
        else:
            wx.CallAfter(self.txt_kime.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def pencere_kapatiliyor(self, event):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        event.Skip()

    def kisilerden_sec(self, event=None):
        kisiler = kisileri_yukle()
        if not kisiler:
            ui.message("Kayıtlı kişi yok. Düzen menüsünden Kişiler seçeneğiyle kişi oluşturabilirsiniz.")
            self.txt_kime.SetFocus()
            return
        pencere = KisiSecPenceresi(self)
        secilenler = []
        try:
            if pencere.ShowModal() == wx.ID_OK:
                secilenler = pencere.secili_adresler()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi seçme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.txt_kime.SetFocus()
        except Exception:
            pass
        if not secilenler:
            ui.message("Seçilen kişilerde geçerli e-posta adresi bulunamadı.")
            self.txt_kime.SetFocus()
            return
        mevcut = self.txt_kime.GetValue().strip()
        parcalar = []
        if mevcut:
            duzenli = adres_basligini_duzenle(mevcut)
            parcalar.extend([p.strip() for p in duzenli.split(",") if p.strip()] if duzenli else [mevcut])
        parcalar.extend(secilenler)
        birlesik = adres_basligini_duzenle(", ".join(parcalar))
        self.txt_kime.SetValue(birlesik)
        try:
            self.txt_kime.SetInsertionPointEnd()
        except Exception:
            pass
        ui.message(f"{len(secilenler)} kişi alıcı alanına eklendi.")
        self.txt_kime.SetFocus()

    def dosya_ekle(self, event):
        dlg = wx.FileDialog(
            self,
            "Eklenecek dosyaları seçin",
            "",
            "",
            "*.*",
            wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        )
        try:
            if dlg.ShowModal() == wx.ID_OK:
                eklenen_sayi = 0
                mevcut_yollar = {kayit.get("yol") for kayit in self.ek_kayitlari if kayit.get("tur") == "dosya"}
                for yol in dlg.GetPaths():
                    if yol not in mevcut_yollar:
                        self.ek_kayitlari.append({"tur": "dosya", "yol": yol})
                        self.liste_ekler.Append(os.path.basename(yol))
                        mevcut_yollar.add(yol)
                        eklenen_sayi += 1
                if eklenen_sayi:
                    ui.message(f"{eklenen_sayi} dosya eklendi.")
                wx.CallAfter(self.liste_ekler.SetFocus)
            else:
                wx.CallAfter(self.txt_icerik.SetFocus)
        finally:
            dlg.Destroy()

    def ek_kaldir(self, event):
        secili_indeks = self.liste_ekler.GetSelection()
        if secili_indeks == wx.NOT_FOUND:
            ui.message("Lütfen kaldırmak istediğiniz eki listeden seçin.")
            self.liste_ekler.SetFocus()
            return
        silinen_isim = self.liste_ekler.GetString(secili_indeks)
        del self.ek_kayitlari[secili_indeks]
        self.liste_ekler.Delete(secili_indeks)
        ui.message(f"Ek kaldırıldı: {silinen_isim}")
        if self.liste_ekler.GetCount() > 0:
            self.liste_ekler.SetSelection(min(secili_indeks, self.liste_ekler.GetCount() - 1))
        self.liste_ekler.SetFocus()

    def taslagi_sil(self, event):
        if not self.taslak_sil_callback:
            return
        try:
            if self.taslak_sil_callback():
                self.EndModal(wx.ID_OK)
        except Exception as e:
            hata_kaydet("Taslak silme isteği başlatılamadı.", e)
            ui.message("Taslak silme işlemi başlatılamadı.")

    def alanlari_etkinlestir(self, etkin=True):
        denetimler = [
            self.txt_kime,
            self.kisi_sec_btn,
            self.txt_konu,
            self.txt_icerik,
            self.gonder_btn,
            self.taslak_kaydet_btn,
            self.ek_ekle_btn,
            self.ek_kaldir_btn,
            self.liste_ekler,
            self.iptal_btn,
        ]
        if self.taslak_sil_btn:
            denetimler.append(self.taslak_sil_btn)
        for denetim in denetimler:
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def tus_yakalandi(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.iptal_tiklandi(event)
            return
        event.Skip()

    def taslak_durumu_al(self):
        ekler = []
        for kayit in self.ek_kayitlari:
            if isinstance(kayit, str):
                ekler.append(("dosya", kayit))
            elif kayit.get("tur") == "hazir":
                ekler.append(("hazir", kayit.get("ad", ""), len(kayit.get("veri") or b"")))
            else:
                ekler.append((kayit.get("tur", ""), kayit.get("yol", "")))
        return (
            self.txt_kime.GetValue().strip(),
            self.txt_konu.GetValue().strip(),
            self.txt_icerik.GetValue(),
            tuple(ekler),
        )

    def taslak_icerigi_var_mi(self):
        kime, konu, icerik, ekler = self.taslak_durumu_al()
        return bool(kime or konu or str(icerik or "").strip() or ekler)

    def taslak_degisti_mi(self):
        return self.taslak_durumu_al() != getattr(self, "_baslangic_durumu", None)

    def taslak_verisini_al(self):
        return {
            "kime": self.txt_kime.GetValue().strip(),
            "konu": self.txt_konu.GetValue().strip(),
            "icerik": self.txt_icerik.GetValue(),
            "ek_kayitlari": list(self.ek_kayitlari),
            "yanit_basliklari": dict(self.yanit_basliklari),
        }

    def iptal_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if not self.taslak_icerigi_var_mi() or not self.taslak_degisti_mi():
            self.EndModal(wx.ID_CANCEL)
            return

        sonuc = gui.messageBox(
            "Bu e-posta gönderilmedi. Değişiklikler taslaklara kaydedilsin mi?",
            "Taslak Kaydet",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
            self,
        )
        if sonuc == wx.YES:
            self.taslak_kaydet_tiklandi(event)
        elif sonuc == wx.NO:
            self.EndModal(wx.ID_CANCEL)
        else:
            self.txt_icerik.SetFocus()

    def taslak_kaydet_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if self._taslak_kaydediliyor:
            return
        if not self.taslak_icerigi_var_mi():
            ui.message("Kaydedilecek taslak içeriği bulunamadı.")
            self.txt_icerik.SetFocus()
            return
        veri = self.taslak_verisini_al()
        ui.message("Taslaklara kaydediliyor.")
        self._taslak_kaydediliyor = True
        self.alanlari_etkinlestir(False)
        arka_planda_calistir(self.arka_planda_taslak_kaydet, veri)

    def arka_planda_taslak_kaydet(self, veri):
        try:
            taslagi_sunucuya_kaydet(
                veri.get("kime", ""),
                veri.get("konu", ""),
                veri.get("icerik", ""),
                veri.get("ek_kayitlari", []),
                veri.get("yanit_basliklari", {}),
                self.taslak_klasor_adaylari,
            )
            guvenli_call_after(self, self.taslak_kaydetme_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, self.taslak_kaydetme_hatali, str(e))
        except Exception as e:
            hata_kaydet("Taslak kaydedilemedi.", e)
            guvenli_call_after(self, self.taslak_kaydetme_hatali, "Taslak kaydedilemedi. Lütfen bağlantınızı ve Google uygulama şifrenizi kontrol edin.")

    def taslak_kaydetme_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        callback_sonucu = False
        if self.taslak_kaydet_callback:
            try:
                callback_sonucu = bool(self.taslak_kaydet_callback())
            except Exception as e:
                hata_kaydet("Taslak kaydetme sonrası işlem başlatılamadı.", e)
        if callback_sonucu:
            ui.message("Taslaklara kaydedildi. Eski taslak kaldırılıyor.")
        else:
            ui.message("Taslaklara kaydedildi.")
        self.EndModal(wx.ID_OK)

    def taslak_kaydetme_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._taslak_kaydediliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()

    def gonder_tiklandi(self, event):
        if self._gonderiliyor:
            return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        kime = self.txt_kime.GetValue().strip()
        konu = self.txt_konu.GetValue().strip()
        icerik = self.txt_icerik.GetValue()
        alicilar = alici_listesi_yap(kime)

        if not alicilar:
            ui.message("Lütfen geçerli en az bir alıcı adresi girin.")
            self.txt_kime.SetFocus()
            return

        self._gonderiliyor = True
        if adres_otomatik_kaydet_ayari_yukle():
            rehbere_ekle(adres_basligini_duzenle(", ".join(alicilar)) or kime)
        ui.message("E-postanız gönderiliyor.")
        self.alanlari_etkinlestir(False)
        arka_planda_calistir(self.arka_planda_gonder, kime, konu, icerik, alicilar, list(self.ek_kayitlari), dict(self.yanit_basliklari))

    def arka_planda_gonder(self, kime, konu, icerik, alicilar, ek_kayitlari, yanit_basliklari=None):
        ayarlar = ayarlari_yukle()
        try:
            if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
                raise MailHatasi("Hesap bilgileri eksik.")

            mesaj = eposta_mesaji_olustur(
                ayarlar["eposta"],
                ", ".join(alicilar),
                konu,
                icerik,
                ek_kayitlari,
                ek_basliklar=yanit_basliklari,
                taslak=False,
            )

            smtp_ssl_ile_gonder(ayarlar["eposta"], ayarlar["sifre"], alicilar, mesaj)
            guvenli_call_after(self, self.gonderim_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, self.gonderim_hatali, str(e))
        except Exception as e:
            hata_kaydet("E-posta gönderilemedi.", e)
            guvenli_call_after(self, self.gonderim_hatali, "Gönderim başarısız oldu. Lütfen bağlantınızı ve Google uygulama şifrenizi kontrol edin.")

    def gonderim_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        callback_sonucu = False
        if self.gonderildi_callback:
            try:
                callback_sonucu = bool(self.gonderildi_callback())
            except Exception as e:
                hata_kaydet("Gönderim sonrası işlem başlatılamadı.", e)
        if callback_sonucu:
            ui.message("E-posta başarıyla gönderildi. Taslak kaldırılıyor.")
        else:
            ui.message("E-posta başarıyla gönderildi.")
        self.EndModal(wx.ID_OK)

    def gonderim_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._gonderiliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()


class ArsivSecimPenceresi(wx.Dialog):
    def __init__(self, parent, ozel_klasorler, ebeveyn_pencere):
        super().__init__(parent, title="Engelsiz Mail - Arşive Gönderme")
        self.secilen_isim = None
        self.ebeveyn = ebeveyn_pencere

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Hedef arşivi seçin:"), 0, wx.ALL, 5)

        self.liste_kutu = wx.ListBox(self, choices=list(ozel_klasorler), style=wx.LB_SINGLE)
        self.liste_kutu.SetName("Hedef arşiv klasörleri")
        if self.liste_kutu.GetCount() > 0:
            self.liste_kutu.SetSelection(0)
        duzen.Add(self.liste_kutu, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.tasi_btn = wx.Button(self, label="&Taşı")
        self.tasi_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(self.tasi_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((560, 320))
        self.CenterOnParent()
        wx.CallAfter(self.liste_kutu.SetFocus)

    def tamam_basildi(self, event):
        secim = self.liste_kutu.GetSelection()
        if secim == wx.NOT_FOUND:
            ui.message("Lütfen hedef arşiv klasörünü seçin. Arşiv yoksa Düzen menüsünden Arşiv Klasörlerini Yönet seçeneğiyle yeni arşiv oluşturun.")
            self.liste_kutu.SetFocus()
            return
        self.secilen_isim = self.liste_kutu.GetString(secim)
        self.EndModal(wx.ID_OK)


class YeniKlasorPenceresi(wx.Dialog):
    def __init__(self, parent, mevcut_adlar=None):
        super().__init__(parent, title="Engelsiz Mail - Yeni Arşiv Klasörü")
        self.klasor_adi = None
        self.mevcut_adlar = list(mevcut_adlar or [])

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Yeni arşiv klasörünün adını yazın:"), 0, wx.ALL, 5)
        self.txt_isim = wx.TextCtrl(self)
        self.txt_isim.SetName("Yeni arşiv klasörü adı")
        duzen.Add(self.txt_isim, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        olustur_btn = wx.Button(self, label="&Oluştur")
        olustur_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(olustur_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((420, 180))
        self.CenterOnParent()
        wx.CallAfter(self.txt_isim.SetFocus)

    def tamam_basildi(self, event):
        try:
            isim = arsiv_klasor_adini_dogrula(self.txt_isim.GetValue(), self.mevcut_adlar)
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_isim.SetFocus()
            return
        self.klasor_adi = isim
        self.EndModal(wx.ID_OK)


class ArsivYenidenAdlandirPenceresi(wx.Dialog):
    def __init__(self, parent, eski_isim, mevcut_adlar=None):
        super().__init__(parent, title="Engelsiz Mail - Arşiv Klasörünü Yeniden Adlandır")
        self.eski_isim = str(eski_isim or "").strip()
        self.mevcut_adlar = list(mevcut_adlar or [])
        self.yeni_isim = None

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Yeni arşiv klasörü adını yazın:"), 0, wx.ALL, 5)
        self.txt_isim = wx.TextCtrl(self, value=self.eski_isim)
        self.txt_isim.SetName("Yeni arşiv klasörü adı")
        duzen.Add(self.txt_isim, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label="&Tamam")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((500, 190))
        self.CenterOnParent()
        wx.CallAfter(self.txt_isim.SetFocus)
        wx.CallAfter(self.txt_isim.SetSelection, 0, len(self.eski_isim))

    def tamam_basildi(self, event):
        try:
            yeni_isim = arsiv_klasor_adini_dogrula(
                self.txt_isim.GetValue(),
                self.mevcut_adlar,
                self.eski_isim,
            )
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_isim.SetFocus()
            try:
                self.txt_isim.SetSelection(0, self.txt_isim.GetLastPosition())
            except Exception:
                pass
            return

        if yeni_isim.strip().lower() == self.eski_isim.strip().lower():
            ui.message("Arşiv adı değişmedi. Lütfen farklı bir ad yazın veya iptal düğmesine basın.")
            self.txt_isim.SetFocus()
            try:
                self.txt_isim.SetSelection(0, self.txt_isim.GetLastPosition())
            except Exception:
                pass
            return

        self.yeni_isim = yeni_isim
        self.EndModal(wx.ID_OK)


class ArsivYonetimPenceresi(wx.Dialog):
    def __init__(self, parent, ozel_klasorler, ebeveyn_pencere):
        super().__init__(parent, title="Engelsiz Mail - Arşiv Klasörlerini Yönet")
        self.ebeveyn = ebeveyn_pencere

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Arşiv klasörleri:"), 0, wx.ALL, 5)

        self.liste_kutu = wx.ListBox(self, choices=list(ozel_klasorler), style=wx.LB_SINGLE)
        self.liste_kutu.SetName("Arşiv klasörleri listesi")
        if self.liste_kutu.GetCount() > 0:
            self.liste_kutu.SetSelection(0)
        duzen.Add(self.liste_kutu, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)

        yeni_btn = wx.Button(self, label="&Yeni Oluştur")
        yeni_btn.Bind(wx.EVT_BUTTON, self.yeni_olustur_basildi)
        btn_duzen.Add(yeni_btn, 0, wx.ALL, 5)

        yeniden_btn = wx.Button(self, label="Yeniden &Adlandır")
        yeniden_btn.Bind(wx.EVT_BUTTON, self.yeniden_adlandir_basildi)
        btn_duzen.Add(yeniden_btn, 0, wx.ALL, 5)

        sil_btn = wx.Button(self, label="&Sil")
        sil_btn.Bind(wx.EVT_BUTTON, self.sil_basildi)
        btn_duzen.Add(sil_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, wx.ID_CANCEL, label="&Kapat")
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((620, 340))
        self.CenterOnParent()
        wx.CallAfter(self.liste_kutu.SetFocus)

    def secili_arsiv_adi(self):
        secim = self.liste_kutu.GetSelection()
        if secim == wx.NOT_FOUND:
            return ""
        return self.liste_kutu.GetString(secim)

    def yeni_olustur_basildi(self, event):
        dlg = YeniKlasorPenceresi(self, self.ebeveyn.ozel_klasorler)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            isim = dlg.klasor_adi
        finally:
            dlg.Destroy()
        if isim:
            self.ebeveyn.arsiv_klasoru_olustur(isim)
            self.EndModal(wx.ID_OK)

    def yeniden_adlandir_basildi(self, event):
        eski_isim = self.secili_arsiv_adi()
        if not eski_isim:
            ui.message("Lütfen yeniden adlandırmak istediğiniz arşivi seçin.")
            self.liste_kutu.SetFocus()
            return

        dlg = ArsivYenidenAdlandirPenceresi(self, eski_isim, self.ebeveyn.ozel_klasorler)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            yeni_isim = dlg.yeni_isim
        finally:
            try:
                dlg.Destroy()
            except Exception as e:
                hata_kaydet("Arşiv yeniden adlandırma penceresi kapatılamadı.", e)

        if not yeni_isim:
            self.liste_kutu.SetFocus()
            return

        self.ebeveyn.arsiv_klasoru_yeniden_adlandir(eski_isim, yeni_isim)
        self.EndModal(wx.ID_OK)

    def sil_basildi(self, event):
        isim = self.secili_arsiv_adi()
        if not isim:
            ui.message("Lütfen silmek istediğiniz arşivi seçin.")
            self.liste_kutu.SetFocus()
            return
        cevap = gui.messageBox(
            f"'{isim}' adlı arşiv klasörünü silmek istiyor musunuz?",
            "Arşiv Silme Onayı",
            wx.YES_NO | wx.ICON_WARNING,
            self,
        )
        if cevap == wx.YES:
            self.ebeveyn.arsiv_klasoru_sil(isim)
            self.EndModal(wx.ID_OK)


class KaliciSilmeOnayiPenceresi(wx.Dialog):
    def __init__(self, parent, soru):
        super().__init__(parent, title="Kalıcı Silme Onayı")
        self._kapatildi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)

        ana_duzen = wx.BoxSizer(wx.VERTICAL)
        metin = wx.StaticText(self, label=str(soru or "") + "\n\nBu işlem geri alınamaz.")
        try:
            metin.Wrap(560)
        except Exception:
            pass
        ana_duzen.Add(metin, 0, wx.ALL | wx.EXPAND, 10)

        self.bir_daha_gosterme = wx.CheckBox(self, label="Bu uyarıyı bir daha gösterme")
        ana_duzen.Add(self.bir_daha_gosterme, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dugme_duzen = wx.BoxSizer(wx.HORIZONTAL)
        evet_btn = wx.Button(self, wx.ID_YES, label="&Evet")
        hayir_btn = wx.Button(self, wx.ID_NO, label="&Hayır")
        evet_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_YES))
        hayir_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_NO))
        dugme_duzen.Add(evet_btn, 0, wx.ALL, 5)
        dugme_duzen.Add(hayir_btn, 0, wx.ALL, 5)
        ana_duzen.Add(dugme_duzen, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.SetSizerAndFit(ana_duzen)
        self.SetEscapeId(wx.ID_NO)
        try:
            hayir_btn.SetDefault()
        except Exception:
            pass
        self.CenterOnParent()
        wx.CallAfter(hayir_btn.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def bir_daha_gosterme_secili_mi(self):
        try:
            return bool(self.bir_daha_gosterme.GetValue())
        except Exception:
            return False


class MesajOkumaPenceresi(wx.Dialog):
    def __init__(self, parent, mesaj_verisi, ebeveyn_pencere):
        super().__init__(parent, title="Engelsiz Mail - E-posta Görüntüleme")
        self.mesaj_verisi = mesaj_verisi
        self.ebeveyn = ebeveyn_pencere
        self._kapatildi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        duzen = wx.BoxSizer(wx.VERTICAL)
        ek_sayisi = len(mesaj_verisi.get("ekler", []))
        ek_notu = f"\nBu e-postada {ek_sayisi} ek dosya var.\n" if ek_sayisi else ""
        kime_satiri = f"Kime: {mesaj_verisi.get('kime', '')}\n" if mesaj_verisi.get("kime") else ""
        ust_bilgi = (
            f"Kimden: {mesaj_verisi.get('kimden_tam', '')}\n"
            f"{kime_satiri}"
            f"Tarih: {mesaj_verisi.get('tarih', '')}\n"
            f"Konu: {mesaj_verisi.get('konu', '')}\n"
            f"{ek_notu}{'-' * 50}\n\n"
        )
        mesaj_icerigi = str(mesaj_verisi.get('icerik', '') or "")
        icerik = ust_bilgi + mesaj_icerigi
        self.icerik_baslangic_indeksi = len(ust_bilgi)
        self.txt_icerik = wx.TextCtrl(self, value=icerik, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.txt_icerik.SetName("E-posta içeriği")
        duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 10)
        gorunum_denetime_uygula(self.txt_icerik)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        if ek_sayisi:
            ek_btn = wx.Button(self, label=f"&Ekleri Kaydet ({ek_sayisi})")
            ek_btn.Bind(wx.EVT_BUTTON, self.ekleri_kaydet)
            btn_duzen.Add(ek_btn, 0, wx.ALL, 5)

        yanitla_btn = wx.Button(self, label="&Yanıtla")
        yanitla_btn.Bind(wx.EVT_BUTTON, self.mesaji_yanitla)
        btn_duzen.Add(yanitla_btn, 0, wx.ALL, 5)

        ilet_btn = wx.Button(self, label="İ&let")
        ilet_btn.Bind(wx.EVT_BUTTON, self.mesaji_ilet)
        btn_duzen.Add(ilet_btn, 0, wx.ALL, 5)

        arsiv_btn = wx.Button(self, label="A&rşivle")
        arsiv_btn.Bind(wx.EVT_BUTTON, self.mesaji_arsivle_ve_kapat)
        btn_duzen.Add(arsiv_btn, 0, wx.ALL, 5)

        sil_btn = wx.Button(self, label="&Sil")
        sil_btn.Bind(wx.EVT_BUTTON, self.mesaji_sil_ve_kapat)
        btn_duzen.Add(sil_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, label="&Kapat")
        kapat_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_OK))
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((860, 660))
        self.CenterOnParent()
        wx.CallAfter(self.icerik_baslangicina_odaklan)

    def icerik_baslangicina_odaklan(self):
        try:
            self.txt_icerik.SetFocus()
            konum = max(0, int(getattr(self, "icerik_baslangic_indeksi", 0)))
            self.txt_icerik.SetInsertionPoint(konum)
            try:
                self.txt_icerik.SetSelection(konum, konum)
            except Exception:
                pass
            try:
                self.txt_icerik.ShowPosition(konum)
            except Exception:
                pass
        except Exception as e:
            hata_kaydet("E-posta içeriği başlangıcına odaklanılamadı.", e)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def tus_yakalandi(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
            return
        event.Skip()

    def ekleri_kaydet(self, event):
        konu = guvenli_dosya_adi(self.mesaj_verisi.get("konu", "Konusuz"), "Konusuz")
        hedef_klasor = os.path.join(os.path.expanduser("~"), "Downloads", f"E-posta_Ekleri_{konu}")
        try:
            os.makedirs(hedef_klasor, exist_ok=True)
            kaydedilen = 0
            for dosya_adi, veri in self.mesaj_verisi.get("ekler", []):
                if not veri:
                    continue
                temiz_ad = guvenli_dosya_adi(dosya_adi, "ek_dosya")
                hedef_yol = benzersiz_yol(hedef_klasor, temiz_ad)
                with open(hedef_yol, "wb") as dosya:
                    dosya.write(veri)
                kaydedilen += 1
            if kaydedilen:
                ui.message(f"{kaydedilen} ek dosya İndirilenler klasörüne kaydedildi.")
            else:
                ui.message("Kaydedilecek ek dosya bulunamadı.")
        except Exception as e:
            hata_kaydet("Ek dosyalar kaydedilemedi.", e)
            ui.message("Ekler kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")

    def mesaji_yanitla(self, event):
        kime = self.mesaj_verisi.get("yanit_adresi") or self.mesaj_verisi.get("kimden_adres", "")
        konu = self.mesaj_verisi.get("konu", "")
        if not konu.lower().startswith("re:"):
            konu = "Re: " + konu
        icerik = f"\n\n\n--- Orijinal E-posta ---\n{self.mesaj_verisi.get('icerik', '')}"
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime=kime,
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            yanit_basliklari=yanit_basliklari_hazirla(self.mesaj_verisi),
            taslak_kaydet_callback=lambda: self.ebeveyn.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.ebeveyn.taslak_klasor_adaylari(),
        )
        guvenli_modal_goster(pencere, self.txt_icerik, self)

    def mesaji_ilet(self, event):
        konu = self.mesaj_verisi.get("konu", "")
        if not konu.lower().startswith("fwd:"):
            konu = "Fwd: " + konu
        icerik = f"\n\n\n--- İletilen E-posta ---\n{self.mesaj_verisi.get('icerik', '')}"
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime="",
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            taslak_kaydet_callback=lambda: self.ebeveyn.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.ebeveyn.taslak_klasor_adaylari(),
            hazir_ekler=self.mesaj_verisi.get("ekler", []),
        )
        guvenli_modal_goster(pencere, self.txt_icerik, self)

    def mesaji_arsivle_ve_kapat(self, event):
        self.EndModal(wx.ID_OK)
        guvenli_call_after(
            self.ebeveyn,
            self.ebeveyn.arsiv_secim_goster,
            [self.mesaj_verisi["id"]],
            self.mesaj_verisi.get("klasor"),
        )

    def mesaji_sil_ve_kapat(self, event):
        if self.ebeveyn.tek_mesaj_sil(
            self.mesaj_verisi["id"],
            self.mesaj_verisi.get("klasor"),
            self.mesaj_verisi.get("konu"),
        ):
            self.EndModal(wx.ID_OK)


class GelenKutusuPenceresi(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail")
        self.mailler = []
        self.isaretliler = set()
        self.ozel_klasorler = []
        self.kategori_isimleri = list(SISTEM_KLASORLERI)
        self.klasor_haritasi = dict(VARSAYILAN_KLASOR_HARITASI)
        self.secili_kategori = "Gelen Kutusu"
        self.yuklu_kategori = self.secili_kategori
        self.bekleyen_kategori = self.secili_kategori
        self.klasor_secimi_programatik = False
        self.yukleniyor = False
        self.ilk_yukleme = True
        self._yenileme_hedef_mail_id = None
        self._yenileme_hedef_indeks = None
        self._yenileme_sessiz = False
        self._kapatildi = False
        self._baglanti_denetleniyor = False
        self._yukleme_islem_no = 0
        self._klasor_sayisi_islem_no = 0
        self._klasor_sayisi_cache = {}
        self._klasor_sayisi_onbellegi_yukle()
        self._klasor_sayisi_duyuru_timer = None
        self._klasor_sayisi_sorgu_timer = None
        self._sistem_klasor_sayisi_guncelleniyor = False
        self._sistem_klasor_sayisi_acilista_guncellendi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        # wx.Choice denetimi Windows tarafında Enter tuşunu her zaman EVT_KEY_DOWN ile iletmeyebilir.
        # Bu yüzden klasör seçimi üzerindeyken Enter davranışı pencere düzeyindeki char hook ile de yakalanır.
        self.Bind(wx.EVT_CHAR_HOOK, self.ana_pencere_tus_yakalandi)

        self.id_hesap_baglan = wx.NewId()
        self.id_hesap_sil = wx.NewId()
        self.id_baglanti_denetle = wx.NewId()
        self.id_yeni = wx.NewId()
        self.id_yanitla = wx.NewId()
        self.id_ilet = wx.NewId()
        self.id_eml_ac = wx.NewId()
        self.id_kaydet_secili_txt = wx.NewId()
        self.id_kaydet_secili_eml = wx.NewId()
        self.id_kaydet_isaretli_txt = wx.NewId()
        self.id_kaydet_isaretli_eml = wx.NewId()
        self.id_cikis = wx.NewId()
        self.id_tumunu = wx.NewId()
        self.id_kaldir = wx.NewId()
        self.id_arsiv = wx.NewId()
        self.id_arsiv_yonet = wx.NewId()
        self.id_kisiler = wx.NewId()
        self.id_sil = wx.NewId()
        self.id_kalici_sil = wx.NewId()
        self.id_yenile = wx.NewId()
        self.id_eposta_sayisi = wx.NewId()
        self.id_onizleme = wx.NewId()
        self.id_silme_onayi = wx.NewId()
        self.id_kalici_silme_onayi = wx.NewId()
        self.id_adres_otomatik_kaydet = wx.NewId()
        self.id_escape_kapat = wx.NewId()
        self.id_bildirimler = wx.NewId()
        self.id_yazi_tipi = wx.NewId()
        self.id_yazi_boyutu = wx.NewId()
        self.id_yazi_stili = wx.NewId()
        self.id_metin_rengi = wx.NewId()
        self.id_arka_plan_rengi = wx.NewId()
        self.id_sistem_renkleri = wx.NewId()
        self.id_gorunum_sifirla = wx.NewId()
        self.id_yardim_kilavuzu = wx.NewId()
        self.id_ne_yeni = wx.NewId()
        self.id_hakkinda = wx.NewId()
        self.id_oneri_gorus = wx.NewId()

        self.Bind(wx.EVT_MENU, self.hesap_baglan, id=self.id_hesap_baglan)
        self.Bind(wx.EVT_MENU, self.hesap_bilgilerini_sil, id=self.id_hesap_sil)
        self.Bind(wx.EVT_MENU, self.baglantiyi_denetle_menu, id=self.id_baglanti_denetle)
        self.Bind(wx.EVT_MENU, self.yeni_posta_yaz, id=self.id_yeni)
        self.Bind(wx.EVT_MENU, self.secili_mesaji_yanitla, id=self.id_yanitla)
        self.Bind(wx.EVT_MENU, self.secili_mesaji_ilet, id=self.id_ilet)
        self.Bind(wx.EVT_MENU, self.eml_dosyasini_ac, id=self.id_eml_ac)
        self.Bind(wx.EVT_MENU, self.secili_epostayi_txt_kaydet, id=self.id_kaydet_secili_txt)
        self.Bind(wx.EVT_MENU, self.secili_epostayi_eml_kaydet, id=self.id_kaydet_secili_eml)
        self.Bind(wx.EVT_MENU, self.isaretli_epostalari_txt_kaydet, id=self.id_kaydet_isaretli_txt)
        self.Bind(wx.EVT_MENU, self.isaretli_epostalari_eml_kaydet, id=self.id_kaydet_isaretli_eml)
        self.Bind(wx.EVT_MENU, self.pencereyi_kapat, id=self.id_cikis)
        self.Bind(wx.EVT_CLOSE, self.pencereyi_kapat)
        self.Bind(wx.EVT_MENU, self.tumunu_isaretle, id=self.id_tumunu)
        self.Bind(wx.EVT_MENU, self.isaretleri_kaldir, id=self.id_kaldir)
        self.Bind(wx.EVT_MENU, self.arsive_gonder_menu, id=self.id_arsiv)
        self.Bind(wx.EVT_MENU, self.arsiv_klasorlerini_yonet, id=self.id_arsiv_yonet)
        self.Bind(wx.EVT_MENU, self.kisiler_penceresi_ac, id=self.id_kisiler)
        self.Bind(wx.EVT_MENU, self.posta_sil, id=self.id_sil)
        self.Bind(wx.EVT_MENU, self.posta_kalici_sil, id=self.id_kalici_sil)
        self.Bind(wx.EVT_MENU, self.listeyi_yenile, id=self.id_yenile)
        self.Bind(wx.EVT_MENU, self.yazi_tipi_sec, id=self.id_yazi_tipi)
        self.Bind(wx.EVT_MENU, self.yazi_boyutu_sec, id=self.id_yazi_boyutu)
        self.Bind(wx.EVT_MENU, self.yazi_stili_sec, id=self.id_yazi_stili)
        self.Bind(wx.EVT_MENU, self.metin_rengi_sec, id=self.id_metin_rengi)
        self.Bind(wx.EVT_MENU, self.arka_plan_rengi_sec, id=self.id_arka_plan_rengi)
        self.Bind(wx.EVT_MENU, self.sistem_renkleri_ayari_degistir, id=self.id_sistem_renkleri)
        self.Bind(wx.EVT_MENU, self.gorunumu_varsayilana_dondur, id=self.id_gorunum_sifirla)
        self.Bind(wx.EVT_MENU, self.eposta_sayisi_ayari_ac, id=self.id_eposta_sayisi)
        self.Bind(wx.EVT_MENU, self.onizleme_ayari_degistir, id=self.id_onizleme)
        self.Bind(wx.EVT_MENU, self.silme_onayi_ayari_degistir, id=self.id_silme_onayi)
        self.Bind(wx.EVT_MENU, self.kalici_silme_onayi_ayari_degistir, id=self.id_kalici_silme_onayi)
        self.Bind(wx.EVT_MENU, self.adres_otomatik_kaydet_ayari_degistir, id=self.id_adres_otomatik_kaydet)
        self.Bind(wx.EVT_MENU, self.escape_kapat_ayari_degistir, id=self.id_escape_kapat)
        self.Bind(wx.EVT_MENU, self.bildirim_ayarlari_ac, id=self.id_bildirimler)
        self.Bind(wx.EVT_MENU, self.yardim_kilavuzunu_ac, id=self.id_yardim_kilavuzu)
        self.Bind(wx.EVT_MENU, self.ne_yeni_ac, id=self.id_ne_yeni)
        self.Bind(wx.EVT_MENU, self.hakkinda_ac, id=self.id_hakkinda)
        self.Bind(wx.EVT_MENU, self.oneri_gorus_ac, id=self.id_oneri_gorus)

        self.menuleri_olustur()

        self.SetAcceleratorTable(
            wx.AcceleratorTable(
                [
                    (wx.ACCEL_ALT, ord("N"), self.id_yeni),
                    (wx.ACCEL_ALT, wx.WXK_F4, self.id_cikis),
                    (wx.ACCEL_ALT, ord("A"), self.id_tumunu),
                    (wx.ACCEL_ALT, ord("D"), self.id_kaldir),
                    (wx.ACCEL_ALT, ord("R"), self.id_arsiv),
                    (wx.ACCEL_ALT, ord("S"), self.id_sil),
                    (wx.ACCEL_SHIFT, wx.WXK_DELETE, self.id_kalici_sil),
                    (wx.ACCEL_NORMAL, wx.WXK_F5, self.id_yenile),
                ]
            )
        )

        # wx.Frame üzerinde doğru Tab dolaşımı için denetimler doğrudan Frame'e değil,
        # ayrı bir panele yerleştirilir.
        self.ana_panel = wx.Panel(self)
        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)
        ust = wx.BoxSizer(wx.HORIZONTAL)
        ust.Add(wx.StaticText(self.ana_panel, label="E-posta klasörleri:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.k_kutu = wx.Choice(self.ana_panel, choices=self.kategori_isimleri)
        self.k_kutu.SetName("E-posta klasörleri")
        self.k_kutu.SetSelection(0)
        self.k_kutu.Bind(wx.EVT_CHOICE, self.kategori_degisti)
        self.k_kutu.Bind(wx.EVT_SET_FOCUS, self.klasor_secimine_odaklandi)
        self.k_kutu.Bind(wx.EVT_KEY_DOWN, self.klasor_tusuna_basildi)
        ust.Add(self.k_kutu, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(ust, 0, wx.EXPAND)

        self.liste = wx.ListCtrl(self.ana_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("E-posta listesi")
        self.liste.InsertColumn(0, "Kimden", width=260)
        self.liste.InsertColumn(1, " ", width=430)
        self.liste.InsertItem(0, "E-postalarınız yükleniyor...")
        self.liste.Bind(wx.EVT_SET_FOCUS, self.listeye_odaklandi)
        self.liste.Bind(wx.EVT_KEY_DOWN, self.tusa_basildi)
        self.liste.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.mesaj_oku)
        self.liste.Bind(wx.EVT_CONTEXT_MENU, self.sag_tik_menusu)
        self.liste.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.sag_tik_menusu)
        self.ana_duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        self.gorunum_uygula()


        self.ana_panel.SetSizer(self.ana_duzen)
        self.SetSize((1050, 590))
        self.CenterOnParent()
        if self.hesap_bilgisi_var_mi():
            self.verileri_yukle_tetikle("Gelen Kutusu yükleniyor...", kategori_adi=self.secili_kategori)
            wx.CallAfter(self.liste.SetFocus)
        else:
            self.hesap_bilgisi_eksik_goster()
            wx.CallAfter(self.liste.SetFocus)

    def listeye_odaklan(self):
        """Ana e-posta listesine güvenli biçimde odak verir."""
        try:
            if not pencere_kullanilabilir_mi(self):
                return False
            if hasattr(self, "liste") and pencere_kullanilabilir_mi(self.liste):
                try:
                    if self.liste.GetItemCount() > 0 and self.liste.GetFocusedItem() < 0:
                        self.liste.Focus(0)
                        self.liste.Select(0)
                        self.liste.EnsureVisible(0)
                except Exception:
                    pass
                self.liste.SetFocus()
                return True
            if hasattr(self, "k_kutu") and pencere_kullanilabilir_mi(self.k_kutu):
                self.k_kutu.SetFocus()
                return True
        except Exception as e:
            hata_kaydet("Ana pencere odağı e-posta listesine verilemedi.", e)
        return False

    def one_getir_ve_odaklan(self):
        """Açık Engelsiz Mail penceresini öne getirir ve e-posta listesine odak verir."""
        try:
            if self.IsIconized():
                self.Iconize(False)
            if not self.IsShown():
                self.Show(True)
            try:
                self.Raise()
            except Exception:
                pass
            try:
                self.SetFocus()
            except Exception:
                pass

            def odakla():
                if pencere_kullanilabilir_mi(self):
                    self.listeye_odaklan()

            try:
                wx.CallAfter(odakla)
            except Exception as e:
                hata_kaydet("Açık pencere için odak dönüşü planlanamadı.", e)
            try:
                wx.CallLater(150, odakla)
            except Exception as e:
                hata_kaydet("Açık pencere için gecikmeli odak dönüşü planlanamadı.", e)
            return True
        except Exception as e:
            hata_kaydet("Açık Engelsiz Mail penceresi öne getirilemedi.", e)
            return False

    def menuleri_olustur(self):
        menu_bar = wx.MenuBar()

        dosya_menu = wx.Menu()
        dosya_menu.Append(self.id_yeni, "&Yeni E-posta Yaz	CTRL+N")
        dosya_menu.Append(self.id_eml_ac, "Aç...")
        kaydet_menu = wx.Menu()
        kaydet_menu.Append(self.id_kaydet_secili_txt, "Seçili E-postayı TXT Olarak Kaydet...")
        kaydet_menu.Append(self.id_kaydet_secili_eml, "Seçili E-postayı EML Olarak Kaydet...")
        kaydet_menu.AppendSeparator()
        kaydet_menu.Append(self.id_kaydet_isaretli_txt, "İşaretli E-postaları TXT Olarak Kaydet...")
        kaydet_menu.Append(self.id_kaydet_isaretli_eml, "İşaretli E-postaları EML Olarak Kaydet...")
        dosya_menu.AppendSubMenu(kaydet_menu, "&Kaydet")
        dosya_menu.AppendSeparator()
        dosya_menu.Append(self.id_hesap_baglan, "&Bağlan...")
        dosya_menu.Append(self.id_baglanti_denetle, "Bağlantıyı &Denetle...")
        dosya_menu.Append(self.id_hesap_sil, "Hesap Bilgilerini &Sil")
        dosya_menu.AppendSeparator()
        dosya_menu.Append(self.id_cikis, "&Çıkış	Alt+F4")
        menu_bar.Append(dosya_menu, "D&osya")

        duzen_menu = wx.Menu()
        duzen_menu.Append(self.id_tumunu, "Tümünü &İşaretle\tCTRL+A")
        duzen_menu.Append(self.id_kaldir, "İşaretleri &Kaldır\tAlt+D")
        duzen_menu.AppendSeparator()
        duzen_menu.Append(self.id_arsiv, "A&rşive Gönder\tAlt+R")
        duzen_menu.Append(self.id_arsiv_yonet, "Arşiv Klasörlerini &Yönet...")
        duzen_menu.Append(self.id_kisiler, "&Kişiler...")
        duzen_menu.Append(self.id_sil, "&Sil\tAlt+S")
        duzen_menu.AppendSeparator()
        duzen_menu.Append(self.id_yenile, "&Yenile\tF5")
        menu_bar.Append(duzen_menu, "Dü&zen")

        gorunum_menu = wx.Menu()
        gorunum_menu.Append(self.id_yazi_tipi, "&Yazı Tipi...")
        gorunum_menu.Append(self.id_yazi_boyutu, "Yazı Tipi &Boyutu...")
        gorunum_menu.Append(self.id_yazi_stili, "Yazı &Stili...")
        gorunum_menu.AppendSeparator()
        gorunum_menu.Append(self.id_metin_rengi, "&Metin Rengi...")
        gorunum_menu.Append(self.id_arka_plan_rengi, "&Arka Plan Rengi...")
        sistem_renkleri_item = gorunum_menu.AppendCheckItem(self.id_sistem_renkleri, "&Sistem Renklerini Kullan")
        try:
            sistem_renkleri_item.Check(gorunum_ayarlari_yukle().get(GORUNUM_SISTEM_RENKLERI_ALANI, False))
        except Exception as e:
            hata_kaydet("Sistem renkleri menü durumu okunamadı.", e)
        gorunum_menu.AppendSeparator()
        gorunum_menu.Append(self.id_gorunum_sifirla, "&Varsayılan Görünüme Dön")
        menu_bar.Append(gorunum_menu, "&Görünüm")

        ayarlar_menu = wx.Menu()
        ayarlar_menu.Append(self.id_eposta_sayisi, "&E-posta Sayısı...")
        ayarlar_menu.Append(self.id_bildirimler, "&Bildirimler...")
        onizleme_item = ayarlar_menu.AppendCheckItem(self.id_onizleme, "Ön &İzleme")
        try:
            onizleme_item.Check(onizleme_ayari_yukle())
        except Exception:
            pass
        silme_onayi_item = ayarlar_menu.AppendCheckItem(self.id_silme_onayi, "Silmeden önce onay iste")
        try:
            silme_onayi_item.Check(silme_onayi_ayari_yukle())
        except Exception:
            pass
        kalici_silme_onayi_item = ayarlar_menu.AppendCheckItem(self.id_kalici_silme_onayi, "Kalıcı silmeden önce onay iste")
        try:
            kalici_silme_onayi_item.Check(kalici_silme_onayi_ayari_yukle())
        except Exception:
            pass
        adres_kaydet_item = ayarlar_menu.AppendCheckItem(self.id_adres_otomatik_kaydet, "Gönderilen e-posta adreslerini otomatik kaydet")
        try:
            adres_kaydet_item.Check(adres_otomatik_kaydet_ayari_yukle())
        except Exception:
            pass
        escape_kapat_item = ayarlar_menu.AppendCheckItem(self.id_escape_kapat, "Escape tuşu ile eklentiyi kapat")
        try:
            escape_kapat_item.Check(escape_kapat_ayari_yukle())
        except Exception:
            pass
        menu_bar.Append(ayarlar_menu, "Ayar&lar")

        yardim_menu = wx.Menu()
        yardim_menu.Append(self.id_yardim_kilavuzu, "&Yardım Kılavuzu")
        yardim_menu.Append(self.id_ne_yeni, "&Yenilikler")
        yardim_menu.Append(self.id_hakkinda, "&Hakkında")
        yardim_menu.AppendSeparator()
        yardim_menu.Append(self.id_oneri_gorus, "Ö&neri ve Görüş Bildir...")
        menu_bar.Append(yardim_menu, "&Yardım")

        self.SetMenuBar(menu_bar)

    def kisiler_penceresi_ac(self, event=None):
        pencere = KisilerPenceresi(self)
        guvenli_modal_goster(pencere, self.liste, self)

    def gorunum_uygula(self):
        """Ana pencere denetimlerine görünüm ayarlarını uygular."""
        gorunum_denetimlerine_uygula(self.k_kutu, self.liste)
        try:
            self.ana_panel.Layout()
            self.Layout()
        except Exception:
            pass

    def yazi_tipi_sec(self, event=None):
        mevcut_ayar = gorunum_ayarlari_yukle()
        mevcut_yazi_tipi = mevcut_ayar.get(GORUNUM_YAZI_TIPI_ALANI, "")
        if not mevcut_yazi_tipi:
            try:
                mevcut_yazi_tipi = self.liste.GetFont().GetFaceName()
            except Exception:
                mevcut_yazi_tipi = ""

        try:
            fontlar = sorted(set(wx.FontEnumerator.GetFacenames()), key=lambda x: x.lower())
        except Exception:
            fontlar = []
        if not fontlar:
            fontlar = ["Arial", "Calibri", "Courier New", "Tahoma", "Times New Roman", "Verdana"]
        if mevcut_yazi_tipi and mevcut_yazi_tipi not in fontlar:
            fontlar.insert(0, mevcut_yazi_tipi)

        dlg = wx.SingleChoiceDialog(
            self,
            "Yazı tipini seçin:",
            "Yazı Tipi",
            fontlar,
        )
        try:
            if mevcut_yazi_tipi in fontlar:
                dlg.SetSelection(fontlar.index(mevcut_yazi_tipi))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_tipi = dlg.GetStringSelection().strip()
            if not yazi_tipi:
                ui.message("Yazı tipi seçilemedi.")
                self.liste.SetFocus()
                return
            gorunum_ayarlari_kaydet(yazi_tipi=yazi_tipi)
            self.gorunum_uygula()
            ui.message(f"Yazı tipi {yazi_tipi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı tipi seçilemedi.", e)
            ui.message("Yazı tipi seçilemedi.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def yazi_boyutu_sec(self, event=None):
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_YAZI_BOYUTU_ALANI, 0)
        if not mevcut:
            try:
                mevcut = self.liste.GetFont().GetPointSize()
            except Exception:
                mevcut = 10
        dlg = wx.TextEntryDialog(
            self,
            f"Yazı tipi boyutunu {GORUNUM_YAZI_BOYUTU_EN_AZ} ile {GORUNUM_YAZI_BOYUTU_EN_COK} arasında yazın:",
            "Yazı Tipi Boyutu",
            str(mevcut or 10),
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_boyutu = int(str(dlg.GetValue()).strip())
            gorunum_ayarlari_kaydet(yazi_boyutu=yazi_boyutu)
            self.gorunum_uygula()
            ui.message(f"Yazı tipi boyutu {yazi_boyutu} olarak ayarlandı.")
        except ValueError:
            ui.message("Yazı tipi boyutu yalnızca rakamlardan oluşmalıdır.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı tipi boyutu ayarlanamadı.", e)
            ui.message("Yazı tipi boyutu ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def yazi_stili_sec(self, event=None):
        secenekler = list(GORUNUM_YAZI_STILI_SECENEKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_YAZI_STILI_ALANI, "") or "Normal"
        dlg = wx.SingleChoiceDialog(
            self,
            "Yazı stilini seçin:",
            "Yazı Stili",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_stili = dlg.GetStringSelection().strip()
            gorunum_ayarlari_kaydet(yazi_stili=yazi_stili)
            self.gorunum_uygula()
            ui.message(f"Yazı stili {yazi_stili} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı stili ayarlanamadı.", e)
            ui.message("Yazı stili ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def metin_rengi_sec(self, event=None):
        secenekler = list(GORUNUM_METIN_RENKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_METIN_RENGI_ALANI, "") or "Siyah"
        dlg = wx.SingleChoiceDialog(
            self,
            "Metin rengini seçin:",
            "Metin Rengi",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            metin_rengi = dlg.GetStringSelection().strip()
            gorunum_ayarlari_kaydet(metin_rengi=metin_rengi)
            self.gorunum_uygula()
            ui.message(f"Metin rengi {metin_rengi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Metin rengi ayarlanamadı.", e)
            ui.message("Metin rengi ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def arka_plan_rengi_sec(self, event=None):
        secenekler = list(GORUNUM_ARKA_PLAN_RENKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_ARKA_PLAN_RENGI_ALANI, "") or "Beyaz"
        dlg = wx.SingleChoiceDialog(
            self,
            "Arka plan rengini seçin:",
            "Arka Plan Rengi",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            arka_plan_rengi = dlg.GetStringSelection().strip()
            gorunum_ayarlari_kaydet(arka_plan_rengi=arka_plan_rengi)
            self.gorunum_uygula()
            ui.message(f"Arka plan rengi {arka_plan_rengi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Arka plan rengi ayarlanamadı.", e)
            ui.message("Arka plan rengi ayarlanamadı.")
        finally:
            dlg.Destroy()
            wx.CallAfter(self.liste.SetFocus)

    def sistem_renkleri_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not gorunum_ayarlari_yukle().get(GORUNUM_SISTEM_RENKLERI_ALANI, False)
            if gorunum_ayarlari_kaydet(sistem_renkleri=etkin):
                self.gorunum_uygula()
                ui.message("Sistem renkleri kullanılacak." if etkin else "Özel renk ayarları kullanılacak.")
            else:
                ui.message("Sistem renkleri ayarı kaydedilemedi.")
        except Exception as e:
            hata_kaydet("Sistem renkleri ayarı değiştirilemedi.", e)
            ui.message("Sistem renkleri ayarı değiştirilemedi.")
        wx.CallAfter(self.liste.SetFocus)

    def gorunumu_varsayilana_dondur(self, event=None):
        if gorunum_ayarlari_sifirla():
            self.gorunum_uygula()
            ui.message("Yazı tipi, yazı tipi boyutu, yazı stili, metin rengi ve arka plan rengi varsayılana döndürüldü.")
        else:
            ui.message("Görünüm ayarları sıfırlanamadı. Lütfen dosya izinlerini kontrol edin.")
        wx.CallAfter(self.liste.SetFocus)

    def hesap_bilgisi_var_mi(self):
        ayarlar = ayarlari_yukle()
        return bool(ayarlar.get("eposta") and ayarlar.get("sifre"))

    def liste_bilgi_satiri_goster(self, mesaj):
        """E-posta listesinde bilgi satırı gösterir ve odak/seçimi erişilebilir biçimde sabitler."""
        try:
            self.liste.DeleteAllItems()
            self.liste.InsertItem(0, str(mesaj or "Bilgi yok."))
            try:
                self.liste.Select(0)
                self.liste.Focus(0)
                self.liste.EnsureVisible(0)
            except Exception:
                pass
            wx.CallAfter(self.liste.SetFocus)
        except Exception as e:
            hata_kaydet("Liste bilgi satırı gösterilemedi.", e)

    def hesap_bilgisi_eksik_goster(self):
        self.liste_bilgi_satiri_goster("Hesap bilgisi bulunamadı. Alt tuşuyla Dosya menüsünden Bağlan seçeneğini kullanın.")
        try:
            self.k_kutu.Enable()
        except Exception:
            pass

    def hesap_bilgilerini_sil(self, event=None):
        sonuc = gui.messageBox(
            "Kayıtlı hesap bilgilerini silmek istiyor musunuz? Bu işlem yalnızca Engelsiz Mail üzerinde kayıtlı e-posta adresini ve uygulama şifresini siler.",
            "Hesap Bilgilerini Sil",
            wx.YES_NO | wx.ICON_QUESTION,
            self,
        )
        if sonuc != wx.YES:
            return
        try:
            ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
            if not isinstance(ayarlar, dict):
                ayarlar = {}
            ayarlar.pop("eposta", None)
            ayarlar.pop(SIFRE_DPAPI_ALANI, None)
            ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
            guvenli_json_yaz(AYARLAR_DOSYASI, ayarlar)
            klasor_sayisi_onbellegi_temizle()
            self._klasor_sayisi_cache = {}
            self._sistem_klasor_sayisi_acilista_guncellendi = False
            self.mailler = []
            self.isaretliler.clear()
            self.hesap_bilgisi_eksik_goster()
            ui.message("Kayıtlı hesap bilgileri silindi.")
        except Exception as e:
            hata_kaydet("Hesap bilgileri silinemedi.", e)
            ui.message("Hesap bilgileri silinirken bir hata oluştu.")

    def baglantiyi_denetle_menu(self, event=None):
        if getattr(self, "_baglanti_denetleniyor", False):
            ui.message("Bağlantı denetimi zaten devam ediyor. Lütfen bekleyin.")
            return
        self._baglanti_denetleniyor = True
        ui.message("Bağlantı denetimi başlatıldı. Lütfen bekleyin.")
        arka_planda_calistir(self._baglantiyi_denetle_thread)

    def _baglantiyi_denetle_thread(self):
        try:
            basarili, rapor = baglanti_denetimini_yap()
        except Exception as e:
            hata_kaydet("Bağlantı denetimi tamamlanamadı.", e)
            basarili = False
            rapor = "Bağlantı denetimi tamamlanamadı.\n\n" + baglanti_hatasi_kullanici_mesaji(e)
        guvenli_call_after(self, self._baglanti_denetimi_goster, basarili, rapor)

    def _baglanti_denetimi_goster(self, basarili, rapor):
        self._baglanti_denetleniyor = False
        pencere = BaglantiDenetimSonucPenceresi(self, basarili, rapor)
        guvenli_modal_goster(pencere, self.liste, self)

    def hesap_baglan(self, event=None):
        pencere = AyarlarPenceresi(self)
        sonuc = guvenli_modal_goster(pencere, self.liste, self)
        if sonuc == wx.ID_OK and pencere_kullanilabilir_mi(self):
            self._klasor_sayisi_cache = {}
            self._sistem_klasor_sayisi_acilista_guncellendi = False
            self._klasor_sayisi_onbellegi_yukle()
            self.verileri_yukle_tetikle("Gelen Kutusu yükleniyor...", kategori_adi=self.secili_kategori)

    def eposta_sayisi_ayari_ac(self, event=None):
        pencere = MesajSayisiPenceresi(self)
        sonuc = guvenli_modal_goster(pencere, self.liste, self)
        if sonuc == wx.ID_OK and pencere_kullanilabilir_mi(self) and self.hesap_bilgisi_var_mi():
            self.verileri_yukle_tetikle("E-postalar yeni sayıya göre yükleniyor...", kategori_adi=self.secili_kategori)

    def silme_onayi_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not silme_onayi_ayari_yukle()
        except Exception:
            etkin = not silme_onayi_ayari_yukle()

        if silme_onayi_ayari_kaydet(etkin):
            bildirim_soyle("Silerken onay sorulacak." if etkin else "Silerken onay sorulmayacak.", 350)
        else:
            bildirim_soyle("Silme onayı ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def kalici_silme_onayi_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not kalici_silme_onayi_ayari_yukle()
        except Exception:
            etkin = not kalici_silme_onayi_ayari_yukle()

        if kalici_silme_onayi_ayari_kaydet(etkin):
            bildirim_soyle("Kalıcı silerken onay sorulacak." if etkin else "Kalıcı silerken onay sorulmayacak.", 350)
        else:
            bildirim_soyle("Kalıcı silme onayı ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def adres_otomatik_kaydet_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not adres_otomatik_kaydet_ayari_yukle()
        except Exception:
            etkin = not adres_otomatik_kaydet_ayari_yukle()

        if adres_otomatik_kaydet_ayari_kaydet(etkin):
            bildirim_soyle("Gönderilen adresler otomatik kaydedilecek." if etkin else "Gönderilen adresler otomatik kaydedilmeyecek.", 350)
        else:
            bildirim_soyle("Adres otomatik kaydetme ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def escape_kapat_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not escape_kapat_ayari_yukle()
        except Exception:
            etkin = not escape_kapat_ayari_yukle()

        if escape_kapat_ayari_kaydet(etkin):
            bildirim_soyle("Escape tuşu eklentiyi kapatacak." if etkin else "Escape tuşu eklentiyi kapatmayacak.", 350)
        else:
            bildirim_soyle("Escape ile kapatma ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def bildirim_ayarlari_ac(self, event=None):
        pencere = BildirimAyarlariPenceresi(self)
        guvenli_modal_goster(pencere, self.liste, self)

    def onizleme_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not onizleme_ayari_yukle()
        except Exception:
            etkin = not onizleme_ayari_yukle()

        if onizleme_ayari_kaydet(etkin):
            if etkin:
                if self.hesap_bilgisi_var_mi():
                    # Liste yenileme mesajı NVDA tarafından kesilebildiği için
                    # önce ayar değişikliğini gecikmeli ve kısa biçimde duyuruyoruz,
                    # ardından listeyi ön izlemeli olarak yeniliyoruz.
                    bildirim_soyle("Ön izleme etkinleştirildi.", 500)
                    self.verileri_yukle_tetikle("Ön izleme hazırlanıyor...", self.secili_kategori, None, None, False)
                else:
                    bildirim_soyle("Ön izleme etkinleştirildi.")
            else:
                try:
                    # Ön izleme konu satırına eklendiği için kapatılınca mevcut liste
                    # yeniden çizilmelidir. Aksi hâlde eski ön izleme metni satırda kalır.
                    self.arayuzu_yenile(self.mailler)
                except Exception as e:
                    hata_kaydet("Ön izleme kapatıldıktan sonra liste yenilenemedi.", e)
                bildirim_soyle("Ön izleme kapatıldı.", 500)
        else:
            bildirim_soyle("Ön izleme ayarı kaydedilemedi.", 500)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def yardim_kilavuzunu_ac(self, event=None):
        yardim_belgesini_ac()

    def ne_yeni_ac(self, event=None):
        ne_yeni_belgesini_ac()

    def hakkinda_ac(self, event=None):
        hakkinda_penceresini_ac(self)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def oneri_gorus_ac(self, event=None):
        pencere = OneriGorusPenceresi(self)
        guvenli_modal_goster(pencere, self.liste, self)

    def pencereyi_kapat(self, event=None):
        if event is not None and hasattr(event, "CanVeto"):
            event.Skip()
            return
        self.Close()

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def aktif_klasor(self):
        return self.klasor_haritasi.get(self.secili_kategori, "INBOX")

    def kategori_adini_klasorden_bul(self, klasor):
        """IMAP klasör değerinden kullanıcıya görünen kategori adını bulur."""
        klasor = str(klasor or "").strip()
        for ad, deger in self.klasor_haritasi.items():
            if str(deger) == klasor:
                return ad
        try:
            if klasor == str(self.aktif_klasor()):
                return self.secili_kategori
        except Exception:
            pass
        return ""

    def gmail_etiket_ifadesi(self, kategori_adi=None, klasor=None):
        """Kullanıcıya görünen klasörü Gmail X-GM-LABELS etiket ifadesine çevirir."""
        kategori_adi = str(kategori_adi or "").strip() or self.kategori_adini_klasorden_bul(klasor)
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

    def kaynak_etiketi_kaldirilabilir_mi(self, kaynak_klasor, kaynak_kategori=None):
        """Kaynak klasörden güvenli biçimde etiket kaldırılıp kaldırılamayacağını belirler."""
        kaynak_kategori = str(kaynak_kategori or "").strip() or self.kategori_adini_klasorden_bul(kaynak_klasor)
        if self.tum_postalar_klasoru_mu(kaynak_klasor):
            return False
        if self.cop_klasoru_mu(kaynak_klasor):
            return False
        if self.spam_klasoru_mu(kaynak_klasor):
            # Spam görünümünde \Deleted/EXPUNGE davranışı hesap ayarlarına göre daha riskli olabilir.
            # Spam'den taşıma ayrı bir güvenlik adımında ele alınacaktır.
            return False
        taslaklar = self.klasor_haritasi.get("Taslaklar", VARSAYILAN_KLASOR_HARITASI["Taslaklar"])
        if str(kaynak_klasor) == str(taslaklar):
            return False
        if kaynak_kategori == "Gelen Kutusu":
            return True
        if kaynak_kategori in self.ozel_klasorler:
            return True
        return False

    def gmail_etiket_ekle_ve_kaynak_kaldir(self, imap, uidler, hedef_etiket, kaynak_klasor, hedef_hata, kaynak_hata):
        """Hedef Gmail etiketini ekler; güvenliyse seçili kaynak klasörden çıkarır."""
        imap_gmail_etiket_store(imap, uidler, "+", hedef_etiket, hedef_hata)
        kaynak_kategori = self.kategori_adini_klasorden_bul(kaynak_klasor)
        if self.kaynak_etiketi_kaldirilabilir_mi(kaynak_klasor, kaynak_kategori):
            kaynak_etiket = self.gmail_etiket_ifadesi(kaynak_kategori, kaynak_klasor)
            if kaynak_etiket and kaynak_etiket != hedef_etiket:
                imap_uidleri_kaynak_klasorden_cikar(imap, uidler, kaynak_hata)
        return True

    def okunmadi_etiketini_kaldir(self, metin):
        metin = metin or ""
        for etiket in ("[Okunmadı] ", "Okunmadı - "):
            if metin.startswith(etiket):
                return metin[len(etiket):]
        return metin

    def birinci_sutun_basligi(self):
        """Seçili klasöre göre birinci sütun başlığını döndürür."""
        if self.secili_kategori in ("Gönderilen E-postalar", "Taslaklar"):
            return "Kime"
        return "Kimden"

    def birinci_sutun_basligini_guncelle(self):
        """Gönderilenler ve Taslaklar için liste başlığını Kime olarak günceller."""
        try:
            item = wx.ListItem()
            item.SetText(self.birinci_sutun_basligi())
            self.liste.SetColumn(0, item)
            self.liste.SetColumnWidth(0, 260)
        except Exception as e:
            hata_kaydet("Liste birinci sütun başlığı güncellenemedi.", e)

    def mesaj_liste_gosterimi(self, mesaj):
        """E-posta listesinin birinci sütununda gösterilecek metni döndürür."""
        metin = str(mesaj.get("liste_gosterim") or mesaj.get("kimden") or "").strip()
        if mesaj.get("ek_var") and not metin.startswith("Ek var. "):
            metin = "Eki var. " + metin
        return metin

    def mesaji_listede_okundu_yap(self, mail_id):
        hedef = str(mail_id)
        for indeks, mesaj in enumerate(self.mailler):
            if str(mesaj.get("id")) != hedef:
                continue
            mesaj["kimden"] = self.okunmadi_etiketini_kaldir(mesaj.get("kimden", ""))
            if "liste_gosterim" in mesaj:
                mesaj["liste_gosterim"] = self.okunmadi_etiketini_kaldir(mesaj.get("liste_gosterim", ""))
            gosterim = self.mesaj_liste_gosterimi(mesaj)
            if str(mesaj.get("id")) in self.isaretliler:
                gosterim = "[İşaretli] " + gosterim
            try:
                self.liste.SetItem(indeks, 0, gosterim)
            except Exception:
                pass
            break

    def cop_klasoru_mu(self, klasor):
        cop_klasoru = self.klasor_haritasi.get("Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"])
        return str(klasor) == str(cop_klasoru)

    def tum_postalar_klasoru_mu(self, klasor):
        tum_postalar = self.klasor_haritasi.get("Tüm Postalar", VARSAYILAN_KLASOR_HARITASI["Tüm Postalar"])
        return str(klasor) == str(tum_postalar)

    def taslak_klasoru_mu(self, klasor):
        taslaklar = self.klasor_haritasi.get("Taslaklar", VARSAYILAN_KLASOR_HARITASI["Taslaklar"])
        return str(klasor) == str(taslaklar) or self.secili_kategori == "Taslaklar"

    def spam_klasoru_mu(self, klasor):
        spam = self.klasor_haritasi.get("Spam", VARSAYILAN_KLASOR_HARITASI["Spam"])
        return str(klasor) == str(spam) or self.secili_kategori == "Spam"

    def taslak_silme_onayi_al(self, adet=1):
        if not silme_onayi_ayari_yukle():
            return True
        soru = (
            "Bu taslağı kalıcı olarak silmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} taslağı kalıcı olarak silmek istiyor musunuz?"
        )
        return gui.messageBox(
            soru,
            "Taslak Silme Onayı",
            wx.YES_NO | wx.ICON_WARNING,
        ) == wx.YES

    def tum_postalar_arsiv_onayi_al(self, adet):
        soru = (
            "Seçili e-postaya özel arşiv etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-posta burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} e-postaya özel arşiv etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-postalar burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
        )
        return gui.messageBox(soru, "Tüm Postalar Arşivleme Uyarısı", wx.YES_NO | wx.ICON_WARNING) == wx.YES

    def tum_postalar_tasima_onayi_al(self, adet, hedef_adi):
        hedef_adi = str(hedef_adi or "").strip() or "hedef"
        soru = (
            f"Seçili e-postaya '{hedef_adi}' etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-posta burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} e-postaya '{hedef_adi}' etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-postalar burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
        )
        return gui.messageBox(soru, "Tüm Postalar Taşıma Uyarısı", wx.YES_NO | wx.ICON_WARNING) == wx.YES

    def mail_konusunu_bul(self, mail_id):
        hedef = str(mail_id or "")
        for mesaj in self.mailler:
            if str(mesaj.get("id", "")) == hedef:
                konu = str(mesaj.get("konu", "")).strip()
                return konu or "Konusuz"
        return "Konusuz"

    def konu_ifadesi(self, konu):
        konu = str(konu or "").strip() or "Konusuz"
        return f"'{konu}' konulu"

    def silme_onayi_al(self, adet, kaynak_klasor, konu=None):
        if not silme_onayi_ayari_yukle():
            return True
        if self.taslak_klasoru_mu(kaynak_klasor):
            return self.taslak_silme_onayi_al(adet)
        konu_etiketi = self.konu_ifadesi(konu) if adet == 1 and konu else "Seçili"
        if self.cop_klasoru_mu(kaynak_klasor):
            soru = (
                f"{konu_etiketi} e-posta Çöp Kutusu'ndan kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} e-posta Çöp Kutusu'ndan kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
            )
            baslik = "Kalıcı Silme Onayı"
        elif self.spam_klasoru_mu(kaynak_klasor):
            soru = (
                f"{konu_etiketi} spam e-postası Çöp Kutusu'na taşınacaktır. Devam etmek istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} spam e-postası Çöp Kutusu'na taşınacaktır. Devam etmek istiyor musunuz?"
            )
            baslik = "Spam Silme Uyarısı"
        elif self.tum_postalar_klasoru_mu(kaynak_klasor):
            soru = (
                f"{konu_etiketi} e-posta Tüm Postalar klasöründen Çöp Kutusu'na taşınacaktır. "
                "Bu işlem, Gmail hesabınızda e-postayı Çöp Kutusu'na taşıyabilir. Devam etmek istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} e-posta Tüm Postalar klasöründen Çöp Kutusu'na taşınacaktır. "
                "Bu işlem, Gmail hesabınızda e-postaları Çöp Kutusu'na taşıyabilir. Devam etmek istiyor musunuz?"
            )
            baslik = "Tüm Postalar Silme Uyarısı"
        else:
            soru = (
                f"{konu_etiketi} e-postayı Çöp Kutusu'na taşımak istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} e-postayı Çöp Kutusu'na taşımak istiyor musunuz?"
            )
            baslik = "Silme Onayı"
        return gui.messageBox(soru, baslik, wx.YES_NO | wx.ICON_WARNING) == wx.YES

    def kalici_silme_onayi_al(self, adet, kaynak_klasor, konu=None):
        if not kalici_silme_onayi_ayari_yukle():
            return True

        konu_etiketi = self.konu_ifadesi(konu) if adet == 1 and konu else "Seçili"
        if self.taslak_klasoru_mu(kaynak_klasor):
            soru = (
                f"{konu_etiketi} taslak kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} taslak kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
            )
        else:
            soru = (
                f"{konu_etiketi} e-posta kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
                if adet == 1
                else f"Seçili {adet} e-posta kalıcı olarak silinecektir. Devam etmek istiyor musunuz?"
            )

        pencere = KaliciSilmeOnayiPenceresi(self, soru)
        sonuc = wx.ID_CANCEL
        bir_daha_gosterme = False
        try:
            sonuc = pencere.ShowModal()
            bir_daha_gosterme = pencere.bir_daha_gosterme_secili_mi()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kalıcı silme onayı penceresi kapatılamadı.", e)
            try:
                self.liste.SetFocus()
            except Exception:
                pass

        if sonuc != wx.ID_YES:
            return False
        if bir_daha_gosterme:
            kalici_silme_onayi_ayari_kaydet(False)
        return True

    def liste_odak_bilgisi_al(self):
        indeks = -1
        mail_id = None
        try:
            indeks = self.liste.GetFocusedItem()
        except Exception:
            indeks = -1
        if indeks != -1 and indeks < len(self.mailler):
            mail_id = str(self.mailler[indeks].get("id", ""))
        return mail_id, indeks

    def liste_secim_ver(self, indeks):
        if not self.mailler:
            wx.CallAfter(self.liste.SetFocus)
            return
        indeks = max(0, min(int(indeks), len(self.mailler) - 1))
        try:
            self.liste.SelectAll(False)
        except Exception:
            pass
        try:
            self.liste.Focus(indeks)
            self.liste.Select(indeks)
            self.liste.EnsureVisible(indeks)
        except Exception:
            pass
        wx.CallAfter(self.liste.SetFocus)

    def verileri_yukle_tetikle(self, liste_mesaji=None, kategori_adi=None, korunan_mail_id=None, korunan_indeks=None, sessiz=False):
        if not pencere_kullanilabilir_mi(self):
            return
        if self.yukleniyor:
            if sessiz:
                wx.CallLater(
                    YENILEME_GECIKMESI_MS,
                    self.verileri_yukle_tetikle,
                    liste_mesaji,
                    kategori_adi,
                    korunan_mail_id,
                    korunan_indeks,
                    sessiz,
                )
            else:
                ui.message("Devam eden işlem tamamlanınca e-posta listesi otomatik yenilenecek.")
                wx.CallLater(
                    YENILEME_GECIKMESI_MS,
                    self.verileri_yukle_tetikle,
                    liste_mesaji,
                    kategori_adi,
                    korunan_mail_id,
                    korunan_indeks,
                    True,
                )
            return

        hedef_kategori = kategori_adi or self.bekleyen_kategori or self.secili_kategori

        if korunan_mail_id is None and korunan_indeks is None and hedef_kategori == self.secili_kategori:
            korunan_mail_id, korunan_indeks = self.liste_odak_bilgisi_al()

        self._yenileme_hedef_mail_id = str(korunan_mail_id) if korunan_mail_id else None
        self._yenileme_hedef_indeks = korunan_indeks if korunan_indeks is not None and korunan_indeks != -1 else None
        self._yenileme_sessiz = bool(sessiz)

        self.secili_kategori = hedef_kategori

        if liste_mesaji and not sessiz:
            self.liste_bilgi_satiri_goster(liste_mesaji)

        self.yukleniyor = True
        try:
            self.k_kutu.Disable()
        except Exception:
            pass

        kaynak_klasor = self.klasor_haritasi.get(hedef_kategori, self.aktif_klasor())
        self._yukleme_islem_no += 1
        yukleme_islem_no = self._yukleme_islem_no
        arka_planda_calistir(self.verileri_yukle, hedef_kategori, kaynak_klasor, yukleme_islem_no)

    def yenilemeyi_gecikmeli_tetikle(self, liste_mesaji=None, kategori_adi=None, korunan_mail_id=None, korunan_indeks=None, sessiz=True, gecikme_ms=YENILEME_GECIKMESI_MS):
        """İşlem sonrası yenilemeyi kısa gecikmeyle başlatır; hızlı ardışık işlemlerde gereksiz uyarıyı engeller."""
        if not pencere_kullanilabilir_mi(self):
            return
        wx.CallLater(
            int(gecikme_ms),
            self.verileri_yukle_tetikle,
            liste_mesaji,
            kategori_adi,
            korunan_mail_id,
            korunan_indeks,
            sessiz,
        )

    def yeni_eposta_gonderildi(self):
        if self.hesap_bilgisi_var_mi():
            self.yenilemeyi_gecikmeli_tetikle(None, self.secili_kategori, None, None, True)
        return False

    def secili_eposta_idini_al(self):
        indeks = self.liste.GetFocusedItem()
        if indeks == -1 or indeks >= len(self.mailler):
            return None
        return self.mailler[indeks]["id"]

    def isaretli_eposta_idlerini_al(self):
        return list(self.isaretliler)

    def eml_dosyasi_sec(self):
        dlg = wx.FileDialog(
            self,
            "Lütfen daha önce kaydettiğiniz EML dosyasını seçiniz.",
            wildcard="EML dosyaları (*.eml)|*.eml|Tüm dosyalar (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.GetPath()
        finally:
            dlg.Destroy()

    def eml_dosyasini_ac(self, event=None):
        dosya_yolu = self.eml_dosyasi_sec()
        if not dosya_yolu:
            self.liste.SetFocus()
            return

        if not str(dosya_yolu).lower().endswith(".eml"):
            ui.message("Lütfen EML uzantılı bir dosya seçin.")
            self.liste.SetFocus()
            return

        try:
            eml_dosya_boyutunu_denetle(dosya_yolu)
        except MailHatasi as e:
            ui.message(str(e))
            self.liste.SetFocus()
            return

        cevap = gui.messageBox(
            "Seçtiğiniz EML dosyası Gelen Kutusuna eklenecektir. "
            "Bu işlem e-postayı yeniden göndermez; yalnızca Gmail hesabınıza bir kopya olarak ekler. "
            "Devam etmek istiyor musunuz?",
            "EML Dosyasını Aç",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if cevap != wx.YES:
            self.liste.SetFocus()
            return

        ui.message("EML dosyası açılıyor.")
        arka_planda_calistir(self.sunucudan_eml_dosyasini_ac, dosya_yolu)

    def sunucudan_eml_dosyasini_ac(self, dosya_yolu):
        ayarlar = ayarlari_yukle()
        try:
            dosya_yolu = str(dosya_yolu or "").strip()
            if not dosya_yolu or not os.path.exists(dosya_yolu):
                raise MailHatasi("EML dosyası bulunamadı.")
            if not dosya_yolu.lower().endswith(".eml"):
                raise MailHatasi("Lütfen EML uzantılı bir dosya seçin.")

            eml_dosya_boyutunu_denetle(dosya_yolu)
            with open(dosya_yolu, "rb") as dosya:
                ham_veri = dosya.read()

            if not ham_veri.strip():
                raise MailHatasi("EML dosyası boş görünüyor.")

            try:
                email.message_from_bytes(ham_veri, policy=email_policy.default)
            except Exception as e:
                raise MailHatasi("EML dosyası okunamadı veya geçerli bir e-posta dosyası değil.") from e

            with ImapBaglantisi(ayarlar) as imap:
                hedef_klasor = self.klasor_haritasi.get("Gelen Kutusu", "INBOX")
                tip, _veri = imap.append(hedef_klasor, None, None, ham_veri)
                if tip != "OK":
                    raise MailHatasi("EML dosyası Gelen Kutusuna eklenemedi.")

            guvenli_call_after(self, ui.message, "EML dosyası Gelen Kutusuna eklendi.")
            guvenli_call_after(
                self,
                self.yenilemeyi_gecikmeli_tetikle,
                "Gelen Kutusu yenileniyor...",
                "Gelen Kutusu",
                None,
                None,
                False,
            )
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("EML dosyası açılamadı.", e)
            guvenli_call_after(self, ui.message, "EML dosyası açılırken bir hata oluştu. Lütfen dosyayı, bağlantınızı ve hesap bilgilerinizi kontrol edin.")
        finally:
            guvenli_call_after(self, self.liste.SetFocus)

    def kaydetme_klasoru_sec(self):
        dlg = wx.DirDialog(
            self,
            "E-postaların kaydedileceği klasörü seçin:",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.GetPath()
        finally:
            dlg.Destroy()

    def secili_epostayi_txt_kaydet(self, event=None):
        mail_id = self.secili_eposta_idini_al()
        if not mail_id:
            ui.message("TXT olarak kaydetmek için e-posta seçin.")
            return
        self.epostalari_kaydet_menu([mail_id], "txt")

    def secili_epostayi_eml_kaydet(self, event=None):
        mail_id = self.secili_eposta_idini_al()
        if not mail_id:
            ui.message("EML olarak kaydetmek için e-posta seçin.")
            return
        self.epostalari_kaydet_menu([mail_id], "eml")

    def isaretli_epostalari_txt_kaydet(self, event=None):
        ids = self.isaretli_eposta_idlerini_al()
        if not ids:
            ui.message("TXT olarak kaydetmek için işaretli e-posta bulunamadı.")
            return
        self.epostalari_kaydet_menu(ids, "txt")

    def isaretli_epostalari_eml_kaydet(self, event=None):
        ids = self.isaretli_eposta_idlerini_al()
        if not ids:
            ui.message("EML olarak kaydetmek için işaretli e-posta bulunamadı.")
            return
        self.epostalari_kaydet_menu(ids, "eml")

    def epostalari_kaydet_menu(self, ids, bicim):
        hedef_klasor = self.kaydetme_klasoru_sec()
        if not hedef_klasor:
            self.liste.SetFocus()
            return
        kaynak_klasor = self.aktif_klasor()
        adet = len(ids)
        if bicim == "txt":
            ui.message("E-posta TXT olarak kaydediliyor." if adet == 1 else f"{adet} e-posta TXT olarak kaydediliyor.")
        else:
            ui.message("E-posta EML olarak kaydediliyor." if adet == 1 else f"{adet} e-posta EML olarak kaydediliyor.")
        arka_planda_calistir(self.sunucudan_epostalari_kaydet, ids, kaynak_klasor, hedef_klasor, bicim)

    def txt_kayit_metni_olustur(self, mesaj, icerik, ekler, kaynak_klasor):
        kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor")) or "Bilinmiyor"
        kime = adres_basligini_duzenle(mesaj.get("To", ""))
        cc = adres_basligini_duzenle(mesaj.get("Cc", ""))
        konu = guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
        tarih = turkce_tarih_yap(mesaj.get("Date", ""))
        ek_adlari = [guvenli_coz(ad or "ek_dosya") for ad, _veri in ekler]
        satirlar = [
            f"Kimden: {kimden}",
            f"Kime: {kime}",
        ]
        if cc:
            satirlar.append(f"Bilgi: {cc}")
        satirlar.extend(
            [
                f"Konu: {konu}",
                f"Tarih: {tarih}",
                f"Klasör: {self.secili_kategori}",
                f"IMAP klasörü: {kaynak_klasor}",
                f"Ek sayısı: {len(ek_adlari)}",
            ]
        )
        if ek_adlari:
            satirlar.append("Ekler:")
            for ek_adi in ek_adlari:
                satirlar.append(f"- {ek_adi}")
        satirlar.extend(["-" * 50, "", icerik or ""])
        return "\n".join(satirlar).strip() + "\n"

    def eposta_dosya_adi_olustur(self, mail_id, mesaj, uzanti):
        konu = guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
        konu = guvenli_dosya_adi(konu, "Konusuz", 60)
        mail_id = guvenli_dosya_adi(str(mail_id), "eposta", 20)
        return f"{mail_id}_{konu}.{uzanti}"

    def sunucudan_epostalari_kaydet(self, ids, kaynak_klasor, hedef_klasor, bicim):
        ayarlar = ayarlari_yukle()
        kaydedilen = 0
        hatali = 0
        son_hata_mesaji = ""
        try:
            if not ids:
                raise MailHatasi("Kaydedilecek e-posta bulunamadı.")
            if bicim not in ("txt", "eml"):
                raise MailHatasi("Desteklenmeyen kaydetme biçimi.")
            os.makedirs(hedef_klasor, exist_ok=True)

            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(kaynak_klasor, readonly=True)
                if tip != "OK":
                    raise MailHatasi("Seçili klasör açılamadı.")

                for mail_id in ids:
                    try:
                        tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
                        if tip != "OK":
                            hatali += 1
                            continue
                        ham_veri = ham_mesaj_verisi_al(veri)
                        if not ham_veri:
                            hatali += 1
                            continue
                        ham_eposta_boyutunu_denetle(ham_veri, "Kaydedilecek e-posta")

                        mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
                        dosya_adi = self.eposta_dosya_adi_olustur(mail_id, mesaj, bicim)
                        hedef_yol = benzersiz_yol(hedef_klasor, dosya_adi)

                        try:
                            if bicim == "eml":
                                with open(hedef_yol, "wb") as dosya:
                                    dosya.write(ham_veri)
                            else:
                                icerik, ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
                                kayit_metni = self.txt_kayit_metni_olustur(mesaj, icerik, ekler, kaynak_klasor)
                                with open(hedef_yol, "w", encoding="utf-8") as dosya:
                                    dosya.write(kayit_metni)
                        except OSError as e:
                            raise MailHatasi(
                                f"E-posta dosyaya yazılamadı: {os.path.basename(hedef_yol)}. "
                                "Seçilen klasör yazma korumalı olabilir, disk dolu olabilir "
                                "veya güvenlik yazılımı dosyayı kilitlemiş olabilir."
                            ) from e

                        kaydedilen += 1
                    except MailHatasi as e:
                        hatali += 1
                        son_hata_mesaji = str(e)
                        hata_kaydet(str(e), e)
                    except Exception as e:
                        hatali += 1
                        hata_kaydet("E-posta kaydedilemedi.", e)

            if kaydedilen and not hatali:
                mesaj = (
                    f"E-posta {bicim.upper()} olarak kaydedildi."
                    if kaydedilen == 1
                    else f"{kaydedilen} e-posta {bicim.upper()} olarak kaydedildi."
                )
            elif kaydedilen and hatali:
                mesaj = f"{kaydedilen} e-posta kaydedildi, {hatali} e-posta kaydedilemedi."
                if son_hata_mesaji:
                    mesaj += f" Son hata: {son_hata_mesaji}"
            else:
                mesaj = son_hata_mesaji or "E-postalar kaydedilemedi."
            guvenli_call_after(self, ui.message, mesaj)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("Kaydetme işlemi başarısız oldu.", e)
            guvenli_call_after(self, ui.message, "Kaydetme işlemi sırasında bir hata oluştu. Lütfen dosya izinlerini ve bağlantınızı kontrol edin.")
        finally:
            guvenli_call_after(self, self.liste.SetFocus)

    def yeni_posta_yaz(self, event=None):
        pencere = YeniPostaPenceresi(
            self,
            gonderildi_callback=lambda: self.yeni_eposta_gonderildi(),
            taslak_kaydet_callback=lambda: self.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.taslak_klasor_adaylari(),
        )
        guvenli_modal_goster(pencere, self.liste, self)

    def secili_mesaji_yanitla(self, event=None):
        self.secili_mesaji_yanitla_veya_ilet("yanitla")

    def secili_mesaji_ilet(self, event=None):
        self.secili_mesaji_yanitla_veya_ilet("ilet")

    def secili_mesaji_yanitla_veya_ilet(self, islem):
        if self.yukleniyor:
            ui.message("Devam eden işlem tamamlandıktan sonra yeniden deneyin.")
            return
        indeks = self.liste.GetFocusedItem()
        if indeks == -1 or indeks >= len(self.mailler):
            ui.message("Lütfen işlem yapmak istediğiniz e-postayı seçin.")
            return
        mail_id = self.mailler[indeks].get("id")
        kaynak_klasor = self.aktif_klasor()
        ui.message("Yanıt hazırlanıyor." if islem == "yanitla" else "İletilecek e-posta hazırlanıyor.")
        arka_planda_calistir(self.sunucudan_yanit_veya_ilet_hazirla, mail_id, kaynak_klasor, islem)

    def sunucudan_yanit_veya_ilet_hazirla(self, mail_id, kaynak_klasor, islem):
        ayarlar = ayarlari_yukle()
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(kaynak_klasor, readonly=False)
                imap_ok_mu(tip, "Seçili klasör açılamadı.")
                tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
                imap_ok_mu(tip, "E-posta içeriği alınamadı.")
                ham_veri = ham_mesaj_verisi_al(veri)
                if not ham_veri:
                    raise MailHatasi("E-posta içeriği boş döndü.")
                ham_eposta_boyutunu_denetle(ham_veri, "Yanıt veya iletme için e-posta")

            mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
            icerik, ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
            kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
            ad, adres = email.utils.parseaddr(kimden)
            veri = {
                "id": str(mail_id),
                "klasor": kaynak_klasor,
                "kimden_tam": f"{ad} ({adres})" if ad and adres else (adres or kimden),
                "kimden_adres": adres or kimden,
                "yanit_adresi": yanit_adresini_bul(mesaj),
                "kime": adres_basligini_duzenle(mesaj.get("To", "")),
                "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
                "tarih": turkce_tarih_yap(mesaj.get("Date", "")),
                "message_id": eposta_basligi_tek_satir_yap(mesaj.get("Message-ID", "")),
                "references": eposta_basligi_tek_satir_yap(mesaj.get("References", "")),
                "icerik": icerik or "",
                "ekler": ekler,
            }
            guvenli_call_after(self, self.yanit_veya_ilet_penceresini_ac, veri, islem)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("Yanıt/ilet hazırlığı başarısız oldu.", e)
            guvenli_call_after(self, ui.message, "E-posta hazırlanırken bir hata oluştu.")

    def yanit_veya_ilet_penceresini_ac(self, veri, islem):
        if not pencere_kullanilabilir_mi(self):
            return
        konu = veri.get("konu", "")
        if islem == "yanitla":
            if not konu.lower().startswith("re:"):
                konu = "Re: " + konu
            icerik = f"\n\n\n--- Orijinal E-posta ---\n{veri.get('icerik', '')}"
            kime = veri.get("yanit_adresi") or veri.get("kimden_adres", "")
            yanit_basliklari = yanit_basliklari_hazirla(veri)
        else:
            if not konu.lower().startswith("fwd:"):
                konu = "Fwd: " + konu
            icerik = f"\n\n\n--- İletilen E-posta ---\n{veri.get('icerik', '')}"
            kime = ""
            yanit_basliklari = {}

        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime=kime,
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            yanit_basliklari=yanit_basliklari,
            taslak_kaydet_callback=lambda: self.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.taslak_klasor_adaylari(),
            hazir_ekler=veri.get("ekler", []) if islem == "ilet" else None,
        )
        guvenli_modal_goster(pencere, self.liste, self)

    def listeyi_yenile(self, event=None):
        ui.message("Liste yenileniyor.")
        self.verileri_yukle_tetikle("E-postalar güncelleniyor...")

    def mesaj_oku(self, event):
        indeks = event.GetIndex()
        if indeks == -1 or indeks >= len(self.mailler):
            return
        mail_id = self.mailler[indeks]["id"]
        kaynak_klasor = self.aktif_klasor()
        if self.taslak_klasoru_mu(kaynak_klasor):
            ui.message("Taslak düzenleniyor.")
        else:
            ui.message("E-posta görüntüleniyor.")
        arka_planda_calistir(self.sunucudan_icerik_indir, mail_id, kaynak_klasor)

    def sunucudan_icerik_indir(self, mail_id, kaynak_klasor):
        ayarlar = ayarlari_yukle()
        try:
            klasor = kaynak_klasor or self.aktif_klasor()
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(klasor, readonly=False)
                if tip != "OK":
                    raise MailHatasi("Seçili klasör açılamadı.")
                tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
                if tip != "OK":
                    raise MailHatasi("E-posta içeriği alınamadı.")
                ham_veri = ham_mesaj_verisi_al(veri)
                if not ham_veri:
                    raise MailHatasi("E-posta içeriği boş döndü.")
                ham_eposta_boyutunu_denetle(ham_veri, "Görüntülenecek e-posta")

                mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
                icerik, ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
                kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
                ad, adres = email.utils.parseaddr(kimden)
                taslak_mi = self.taslak_klasoru_mu(klasor)
                veri = {
                    "id": str(mail_id),
                    "klasor": klasor,
                    "kimden_tam": f"{ad} ({adres})" if ad and adres else (adres or kimden),
                    "kimden_adres": adres or kimden,
                    "yanit_adresi": yanit_adresini_bul(mesaj),
                    "kime": adres_basligini_duzenle(mesaj.get("To", "")),
                    "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
                    "tarih": turkce_tarih_yap(mesaj.get("Date", "")),
                    "message_id": eposta_basligi_tek_satir_yap(mesaj.get("Message-ID", "")),
                    "references": eposta_basligi_tek_satir_yap(mesaj.get("References", "")),
                    "icerik": icerik or "",
                    "ekler": ekler,
                    "taslak_mi": taslak_mi,
                }
                if not taslak_mi:
                    imap.uid("STORE", str(mail_id), "+FLAGS.SILENT", "(\\Seen)")
            if veri.get("taslak_mi"):
                guvenli_call_after(self, self.taslak_penceresini_ac, veri)
            else:
                guvenli_call_after(self, self.mesaji_listede_okundu_yap, mail_id)
                guvenli_call_after(self, self.okuma_penceresini_ac, veri)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("E-posta içeriği indirilemedi.", e)
            guvenli_call_after(self, ui.message, "E-posta açılırken bir hata oluştu.")

    def taslak_penceresini_ac(self, veri):
        if not pencere_kullanilabilir_mi(self):
            return

        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime=veri.get("kime", ""),
            varsayilan_konu=veri.get("konu", ""),
            varsayilan_icerik=veri.get("icerik", ""),
            baslik="Engelsiz Mail - Taslak Düzenle",
            gonderildi_callback=lambda: self.taslak_gonderildi(veri.get("id"), veri.get("klasor")),
            taslak_sil_callback=lambda: self.taslak_sil_iste(veri.get("id"), veri.get("klasor")),
            taslak_kaydet_callback=lambda: self.taslak_kaydedildi(veri.get("id"), veri.get("klasor")),
            taslak_klasor_adaylari=self.taslak_klasor_adaylari(veri.get("klasor")),
            hazir_ekler=veri.get("ekler", []),
        )
        guvenli_modal_goster(pencere, self.liste, self)

    def taslak_gonderildi(self, mail_id, kaynak_klasor):
        if not mail_id:
            return False
        self.listeden_mesajlari_kaldir([mail_id])
        arka_planda_calistir(self.sunucudan_taslak_sil, [mail_id], kaynak_klasor, "Taslak kaldırıldı.")
        return True

    def taslak_kaydedildi(self, mail_id=None, kaynak_klasor=None):
        """Yeni taslak kaydedildikten sonra eski taslağı kaldırır veya Taslaklar listesini yeniler."""
        eski_taslak_var = bool(mail_id)
        if eski_taslak_var:
            self.listeden_mesajlari_kaldir([mail_id])
            arka_planda_calistir(self.sunucudan_taslak_sil, [mail_id], kaynak_klasor, "")
            return True

        if self.secili_kategori == "Taslaklar" and self.hesap_bilgisi_var_mi():
            self.yenilemeyi_gecikmeli_tetikle(None, self.secili_kategori, None, None, True)
        return False

    def taslak_sil_iste(self, mail_id, kaynak_klasor):
        if not mail_id:
            ui.message("Silinecek taslak bulunamadı.")
            return False
        if not self.taslak_silme_onayi_al():
            self.liste.SetFocus()
            return False
        self.listeden_mesajlari_kaldir([mail_id])
        ui.message("Taslak siliniyor.")
        arka_planda_calistir(self.sunucudan_taslak_sil, [mail_id], kaynak_klasor, "Taslak silindi.")
        return True

    def taslak_klasor_adaylari(self, kaynak_klasor=None):
        adaylar = []

        def ekle(deger):
            deger = str(deger or "").strip()
            if deger and deger not in adaylar:
                adaylar.append(deger)

        ekle(kaynak_klasor)
        ekle(self.klasor_haritasi.get("Taslaklar"))
        ekle(VARSAYILAN_KLASOR_HARITASI.get("Taslaklar"))
        ekle('"[Gmail]/Drafts"')
        ekle('"[Google Mail]/Drafts"')
        ekle(imap_klasor_adi_hazirla("Taslaklar"))
        ekle(imap_klasor_adi_hazirla("Drafts"))
        return adaylar

    def uidleri_klasorde_ara(self, imap, uidler):
        uid_kumesi = {str(uid) for uid in uidler if str(uid or "").strip()}
        if not uid_kumesi:
            return set()
        uid_araligi = ",".join(sorted(uid_kumesi, key=lambda x: int(x) if x.isdigit() else x))
        tip, veri = imap.uid("SEARCH", "UID", uid_araligi)
        if tip != "OK":
            return set()
        bulunanlar = {str(uid) for uid in uidleri_ayristir(veri)}
        return uid_kumesi.intersection(bulunanlar)

    def sunucudan_taslak_sil(self, ids, klasor, basari_mesaji="Taslak silindi."):
        ayarlar = ayarlari_yukle()
        try:
            uidler = [str(uid) for uid in ids if str(uid or "").strip()]
            if not uidler:
                raise MailHatasi("Silinecek taslak bulunamadı.")

            silindi = False
            son_hata = ""
            with ImapBaglantisi(ayarlar) as imap:
                for aday_klasor in self.taslak_klasor_adaylari(klasor):
                    try:
                        tip, _veri = imap.select(aday_klasor, readonly=False)
                        if tip != "OK":
                            son_hata = f"Taslaklar klasörü açılamadı: {aday_klasor}"
                            continue

                        mevcut_uidler = self.uidleri_klasorde_ara(imap, uidler)
                        if not mevcut_uidler:
                            son_hata = f"Taslak UID bu klasörde bulunamadı: {aday_klasor}"
                            continue

                        uid_seti = ",".join(sorted(mevcut_uidler, key=lambda x: int(x) if x.isdigit() else x))
                        try:
                            imap_uidleri_kalici_sil(imap, uid_seti, f"Taslak kalıcı olarak kaldırılamadı: {aday_klasor}")
                        except MailHatasi as e:
                            son_hata = str(e)
                            continue

                        try:
                            imap.select(aday_klasor, readonly=False)
                            kalan_uidler = self.uidleri_klasorde_ara(imap, mevcut_uidler)
                        except Exception:
                            kalan_uidler = set()

                        if not kalan_uidler:
                            silindi = True
                            break

                        son_hata = f"Taslak silme sonrasında hâlâ görünüyor: {aday_klasor}"
                    except Exception as e:
                        son_hata = f"Taslak silme denemesi başarısız: {aday_klasor}"
                        hata_kaydet(son_hata, e)
                        continue

            if not silindi:
                hata_kaydet(son_hata or "Taslak silinemedi.")
                raise MailHatasi("Taslak, Gmail tarafından kaldırılmadı. Liste yenileniyor.")

            if basari_mesaji:
                guvenli_call_after(self, ui.message, basari_mesaji)
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, None, self.secili_kategori, None, None, True)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, None, self.secili_kategori, None, None, True)
        except Exception as e:
            hata_kaydet("Taslak silinemedi.", e)
            guvenli_call_after(self, ui.message, "Taslak silinirken bir hata oluştu.")
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, None, self.secili_kategori, None, None, True)

    def okuma_penceresini_ac(self, veri):
        if not pencere_kullanilabilir_mi(self):
            return
        pencere = MesajOkumaPenceresi(self, veri, self)
        guvenli_modal_goster(pencere, self.liste, self)
        if pencere_kullanilabilir_mi(self):
            self.verileri_yukle_tetikle(
                kategori_adi=self.secili_kategori,
                korunan_mail_id=veri.get("id"),
                sessiz=True,
            )

    def arsiv_klasorlerini_yonet(self, event=None):
        if self.yukleniyor:
            ui.message("Devam eden işlem tamamlandıktan sonra yeniden deneyin.")
            return
        if not self.hesap_bilgisi_var_mi():
            ui.message("Arşiv klasörlerini yönetmek için önce Dosya menüsünden Bağlan seçeneğiyle Gmail hesabınızı bağlayın.")
            return
        pencere = ArsivYonetimPenceresi(self, self.ozel_klasorler, self)
        guvenli_modal_goster(pencere, self.liste, self)

    def arsiv_silindi_sonrasi_guncelle(self, silinen_klasor_adi):
        silinen_klasor_adi = str(silinen_klasor_adi or "").strip()
        if silinen_klasor_adi:
            self.klasor_haritasi.pop(silinen_klasor_adi, None)
            if silinen_klasor_adi in self.ozel_klasorler:
                self.ozel_klasorler = [ad for ad in self.ozel_klasorler if ad != silinen_klasor_adi]
        if self.secili_kategori == silinen_klasor_adi or self.bekleyen_kategori == silinen_klasor_adi or self.yuklu_kategori == silinen_klasor_adi:
            self.secili_kategori = "Gelen Kutusu"
            self.bekleyen_kategori = "Gelen Kutusu"
            self.yuklu_kategori = "Gelen Kutusu"
        self.klasor_secimi_programatik = True
        try:
            self.k_kutu.Clear()
            for kategori in self.kategori_isimleri + self.ozel_klasorler:
                self.k_kutu.Append(kategori)
            indeks = self.k_kutu.FindString(self.secili_kategori)
            if indeks == wx.NOT_FOUND:
                indeks = self.k_kutu.FindString("Gelen Kutusu")
                self.secili_kategori = "Gelen Kutusu"
                self.bekleyen_kategori = "Gelen Kutusu"
            if indeks != wx.NOT_FOUND:
                self.k_kutu.SetSelection(indeks)
        finally:
            self.klasor_secimi_programatik = False
        self.yenilemeyi_gecikmeli_tetikle("Klasörler güncelleniyor...", self.secili_kategori, None, None, False)
        wx.CallAfter(self.liste.SetFocus)

    def arsiv_secim_goster(self, sids, kaynak_klasor=None):
        if not sids:
            ui.message("Arşivlenecek e-posta bulunamadı.")
            return
        kaynak_klasor = kaynak_klasor or self.aktif_klasor()
        if self.tum_postalar_klasoru_mu(kaynak_klasor) and not self.tum_postalar_arsiv_onayi_al(len(sids)):
            self.liste.SetFocus()
            return
        dlg = ArsivSecimPenceresi(self, self.ozel_klasorler, self)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            hedef = dlg.secilen_isim
            if not hedef:
                ui.message("Lütfen hedef arşiv klasörünü seçin. Arşiv yoksa Düzen menüsünden Arşiv Klasörlerini Yönet seçeneğiyle yeni arşiv oluşturun.")
                return

            if not self.tum_postalar_klasoru_mu(kaynak_klasor):
                self.listeden_mesajlari_kaldir(sids)
            ui.message(f"E-postalar '{hedef}' klasörüne arşivleniyor.")
            arka_planda_calistir(self.sunucudan_ozel_arsivle, sids, hedef, kaynak_klasor)
        finally:
            dlg.Destroy()

    def arsiv_klasoru_olustur(self, klasor_adi):
        ui.message("Arşiv oluşturuluyor.")
        arka_planda_calistir(self.sunucudan_arsiv_olustur_thread, klasor_adi)

    def sunucudan_arsiv_olustur_thread(self, klasor_adi):
        ayarlar = ayarlari_yukle()
        try:
            klasor_adi = arsiv_klasor_adini_dogrula(klasor_adi, self.ozel_klasorler)
            with ImapBaglantisi(ayarlar) as imap:
                hedef = imap_klasor_adi_hazirla(klasor_adi)
                tip, _veri = imap.create(hedef)
                if tip != "OK":
                    raise MailHatasi("Arşiv klasörü oluşturulamadı.")
            guvenli_call_after(self, ui.message, f"'{klasor_adi}' arşiv klasörü oluşturuldu.")
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Klasörler güncelleniyor...", klasor_adi, None, None, False)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("Arşiv klasörü oluşturulamadı.", e)
            guvenli_call_after(self, ui.message, "Arşiv klasörü oluşturulurken bir hata oluştu.")

    def arsiv_klasoru_yeniden_adlandir(self, eski_ad, yeni_ad):
        ui.message("Arşiv yeniden adlandırılıyor.")
        arka_planda_calistir(self.sunucudan_arsiv_yeniden_adlandir_thread, eski_ad, yeni_ad)

    def sunucudan_arsiv_yeniden_adlandir_thread(self, eski_ad, yeni_ad):
        ayarlar = ayarlari_yukle()
        try:
            eski_ad = str(eski_ad or "").strip()
            if not eski_ad:
                raise MailHatasi("Arşiv adı boş olamaz.")
            yeni_ad = arsiv_klasor_adini_dogrula(yeni_ad, self.ozel_klasorler, eski_ad)
            with ImapBaglantisi(ayarlar) as imap:
                eski_hedef = self.klasor_haritasi.get(eski_ad, imap_klasor_adi_hazirla(eski_ad))
                yeni_hedef = imap_klasor_adi_hazirla(yeni_ad)
                tip, _veri = imap.rename(eski_hedef, yeni_hedef)
                if tip != "OK":
                    raise MailHatasi("Arşiv klasörü yeniden adlandırılamadı.")
            guvenli_call_after(self, ui.message, f"'{eski_ad}' arşivi '{yeni_ad}' olarak yeniden adlandırıldı.")
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Klasörler güncelleniyor...", yeni_ad, None, None, False)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("Arşiv klasörü yeniden adlandırılamadı.", e)
            guvenli_call_after(self, ui.message, "Arşiv klasörü yeniden adlandırılırken bir hata oluştu.")

    def arsiv_klasoru_sil(self, klasor_adi):
        ui.message("Arşiv siliniyor.")
        arka_planda_calistir(self.sunucudan_arsiv_sil_thread, klasor_adi)

    def sunucudan_arsiv_sil_thread(self, klasor_adi):
        ayarlar = ayarlari_yukle()
        try:
            with ImapBaglantisi(ayarlar) as imap:
                hedef = self.klasor_haritasi.get(klasor_adi, imap_klasor_adi_hazirla(klasor_adi))
                tip, _veri = imap.delete(hedef)
                if tip != "OK":
                    raise MailHatasi("Arşiv klasörü silinemedi.")
            guvenli_call_after(self, ui.message, "Arşiv klasörü silindi.")
            guvenli_call_after(self, self.arsiv_silindi_sonrasi_guncelle, klasor_adi)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
        except Exception as e:
            hata_kaydet("Arşiv klasörü silinemedi.", e)
            guvenli_call_after(self, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Silme işlemi sırasında bir hata oluştu."))

    def sunucudan_ozel_arsivle(self, ids, hedef_isim, mevcut_klasor):
        ayarlar = ayarlari_yukle()
        try:
            uidler = uid_kumesi_hazirla(ids, "Arşivlenecek e-posta bulunamadı.")
            with ImapBaglantisi(ayarlar) as imap:
                imap_gmail_etiket_destegini_dogrula(imap)
                tip, _veri = imap.select(mevcut_klasor, readonly=False)
                imap_ok_mu(tip, "Kaynak klasör açılamadı.")

                hedef_etiket = self.gmail_etiket_ifadesi(hedef_isim, self.klasor_haritasi.get(hedef_isim))
                if not hedef_etiket:
                    raise MailHatasi("Hedef arşiv etiketi hazırlanamadı.")
                self.gmail_etiket_ekle_ve_kaynak_kaldir(
                    imap,
                    uidler,
                    hedef_etiket,
                    mevcut_klasor,
                    "E-postalar hedef arşiv etiketine eklenemedi.",
                    "E-postalar kaynak etiketinden kaldırılamadı.",
                )
            if self.tum_postalar_klasoru_mu(mevcut_klasor):
                mesaj = f"E-postalara '{hedef_isim}' arşiv etiketi eklendi. Tüm Postalar'da görünmeye devam edebilirler."
            else:
                mesaj = f"E-postalar '{hedef_isim}' arşivine taşındı."
            guvenli_call_after(self, ui.message, mesaj)
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)
        except Exception as e:
            hata_kaydet("Arşivleme işlemi başarısız oldu.", e)
            guvenli_call_after(self, ui.message, "Arşivleme sırasında bir hata oluştu.")
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)

    def tek_mesaj_sil(self, mail_id, kaynak_klasor=None, konu=None):
        kaynak_klasor = kaynak_klasor or self.aktif_klasor()
        if not mail_id:
            ui.message("Silinecek e-posta bulunamadı.")
            return False
        if self.taslak_klasoru_mu(kaynak_klasor):
            if not self.taslak_silme_onayi_al(1):
                self.liste.SetFocus()
                return False
            self.listeden_mesajlari_kaldir([mail_id])
            ui.message("Taslak siliniyor.")
            arka_planda_calistir(self.sunucudan_taslak_sil, [mail_id], kaynak_klasor, "Taslak silindi.")
            return True
        silinecek_konu = konu or self.mail_konusunu_bul(mail_id)
        if not self.silme_onayi_al(1, kaynak_klasor, silinecek_konu):
            return False
        self.listeden_mesajlari_kaldir([mail_id])
        ui.message("E-posta siliniyor.")
        arka_planda_calistir(self.sunucudan_sil, [mail_id], kaynak_klasor)
        return True

    def secili_eposta_idlerini_al(self):
        secili_idler = list(self.isaretliler)
        if not secili_idler:
            indeks = self.liste.GetFocusedItem()
            if indeks != -1 and indeks < len(self.mailler):
                secili_idler.append(self.mailler[indeks]["id"])
        return secili_idler

    def posta_sil(self, event=None):
        secili_idler = self.secili_eposta_idlerini_al()
        if not secili_idler:
            ui.message("Lütfen silmek için e-posta seçin.")
            return

        adet = len(secili_idler)
        kaynak_klasor = self.aktif_klasor()
        if self.taslak_klasoru_mu(kaynak_klasor):
            if not self.taslak_silme_onayi_al(adet):
                self.liste.SetFocus()
                return
            self.listeden_mesajlari_kaldir(secili_idler)
            ui.message("Taslak siliniyor." if adet == 1 else "Taslaklar siliniyor.")
            basari_mesaji = "Taslak silindi." if adet == 1 else "Taslaklar silindi."
            arka_planda_calistir(self.sunucudan_taslak_sil, secili_idler, kaynak_klasor, basari_mesaji)
            return

        silinecek_konu = self.mail_konusunu_bul(secili_idler[0]) if adet == 1 else None
        if not self.silme_onayi_al(adet, kaynak_klasor, silinecek_konu):
            self.liste.SetFocus()
            return

        self.listeden_mesajlari_kaldir(secili_idler)
        ui.message("Siliniyor.")
        arka_planda_calistir(self.sunucudan_sil, secili_idler, kaynak_klasor)

    def posta_kalici_sil(self, event=None):
        secili_idler = self.secili_eposta_idlerini_al()
        if not secili_idler:
            ui.message("Lütfen kalıcı olarak silmek için e-posta seçin.")
            return

        adet = len(secili_idler)
        kaynak_klasor = self.aktif_klasor()
        silinecek_konu = self.mail_konusunu_bul(secili_idler[0]) if adet == 1 else None
        if not self.kalici_silme_onayi_al(adet, kaynak_klasor, silinecek_konu):
            self.liste.SetFocus()
            return

        self.listeden_mesajlari_kaldir(secili_idler)
        if self.taslak_klasoru_mu(kaynak_klasor):
            ui.message("Taslak kalıcı olarak siliniyor." if adet == 1 else "Taslaklar kalıcı olarak siliniyor.")
            basari_mesaji = "Taslak kalıcı olarak silindi." if adet == 1 else "Taslaklar kalıcı olarak silindi."
            arka_planda_calistir(self.sunucudan_taslak_sil, secili_idler, kaynak_klasor, basari_mesaji)
            return

        ui.message("E-posta kalıcı olarak siliniyor." if adet == 1 else "E-postalar kalıcı olarak siliniyor.")
        arka_planda_calistir(self.sunucudan_kalici_sil, secili_idler, kaynak_klasor)

    def listeden_mesajlari_kaldir(self, ids):
        id_kumesi = {str(uid) for uid in ids}
        silinecek_indeksler = [i for i, mesaj in enumerate(self.mailler) if str(mesaj["id"]) in id_kumesi]
        hedef_indeks = min(silinecek_indeksler) if silinecek_indeksler else self.liste.GetFocusedItem()
        for indeks in reversed(silinecek_indeksler):
            try:
                self.liste.DeleteItem(indeks)
            except Exception:
                pass
            del self.mailler[indeks]
        self.isaretliler.difference_update(id_kumesi)
        if not self.mailler:
            self.liste_bilgi_satiri_goster("Bu klasörde gösterilecek e-posta yok.")
        else:
            self.liste_secim_ver(hedef_indeks)

    def sunucudan_sil(self, ids, klasor):
        ayarlar = ayarlari_yukle()
        try:
            uidler = uid_kumesi_hazirla(ids, "Silinecek e-posta bulunamadı.")
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(klasor, readonly=False)
                imap_ok_mu(tip, "Seçili klasör açılamadı.")

                cop = self.klasor_haritasi.get("Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"])
                if str(klasor) == str(cop):
                    imap_uidleri_kalici_sil(imap, uidler, "E-posta Çöp Kutusu'ndan kalıcı olarak silinemedi.")
                    mesaj = "E-posta Çöp Kutusu'ndan kalıcı olarak silindi." if len(ids) == 1 else "E-postalar Çöp Kutusu'ndan kalıcı olarak silindi."
                else:
                    imap_gmail_etiket_destegini_dogrula(imap)
                    cop_etiketi = self.gmail_etiket_ifadesi("Çöp Kutusu", cop)
                    imap_gmail_etiket_store(imap, uidler, "+", cop_etiketi, "E-posta Çöp Kutusu'na taşınamadı.")
                    kaynak_kategori = self.kategori_adini_klasorden_bul(klasor)
                    if self.kaynak_etiketi_kaldirilabilir_mi(klasor, kaynak_kategori):
                        kaynak_etiket = self.gmail_etiket_ifadesi(kaynak_kategori, klasor)
                        if kaynak_etiket:
                            imap_gmail_etiket_store(imap, uidler, "-", kaynak_etiket, "E-posta kaynak etiketinden kaldırılamadı.")
                    if kaynak_kategori == "Spam":
                        mesaj = "Spam e-postası Çöp Kutusu'na taşındı." if len(ids) == 1 else "Spam e-postaları Çöp Kutusu'na taşındı."
                    else:
                        mesaj = "E-posta Çöp Kutusu'na taşındı." if len(ids) == 1 else "E-postalar Çöp Kutusu'na taşındı."
            guvenli_call_after(self, ui.message, mesaj)
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, None, self.secili_kategori, None, None, True)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)
        except Exception as e:
            hata_kaydet("Silme işlemi başarısız oldu.", e)
            guvenli_call_after(self, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Silme işlemi sırasında bir hata oluştu."))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)

    def sunucudan_kalici_sil(self, ids, klasor):
        ayarlar = ayarlari_yukle()
        try:
            uidler = uid_kumesi_hazirla(ids, "Kalıcı silinecek e-posta bulunamadı.")
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(klasor, readonly=False)
                imap_ok_mu(tip, "Seçili klasör açılamadı.")

                cop = self.klasor_haritasi.get("Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"])
                if str(klasor) == str(cop):
                    imap_uidleri_kalici_sil(imap, uidler, "E-posta kalıcı olarak silinemedi.")
                else:
                    imap_gmail_etiket_destegini_dogrula(imap)
                    msgid_haritasi = imap_x_gm_msgid_haritasi_al(imap, ids)
                    cop_etiketi = self.gmail_etiket_ifadesi("Çöp Kutusu", cop)
                    imap_gmail_etiket_store(imap, uidler, "+", cop_etiketi, "E-posta kalıcı silme için Çöp Kutusu'na taşınamadı.")
                    imap_gmail_msgidleri_kalici_sil(
                        imap,
                        [msgid_haritasi[str(uid)] for uid in ids],
                        cop,
                        "E-posta kalıcı olarak silinemedi.",
                    )

            mesaj = "E-posta kalıcı olarak silindi." if len(ids) == 1 else "E-postalar kalıcı olarak silindi."
            guvenli_call_after(self, ui.message, mesaj)
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, None, self.secili_kategori, None, None, True)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)
        except Exception as e:
            hata_kaydet("Kalıcı silme işlemi başarısız oldu.", e)
            guvenli_call_after(self, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Kalıcı silme işlemi sırasında bir hata oluştu."))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)

    def acilis_klasor_bildirimi_ver(self):
        if pencere_kullanilabilir_mi(self):
            ui.message("Gelen kutusu hazırlanırken lütfen bekleyiniz.")

    def kategori_degisti(self, event):
        if getattr(self, "klasor_secimi_programatik", False):
            event.Skip()
            return

        if self.yukleniyor:
            ui.message("Klasör yüklenirken seçim değiştirilemez.")
            event.Skip()
            return

        self.bekleyen_kategori = self.k_kutu.GetStringSelection()
        if self.bekleyen_kategori:
            self.klasor_sayisini_bildir_tetikle(self.bekleyen_kategori)
        event.Skip()

    def klasor_secimine_odaklandi(self, event):
        secim = ""
        try:
            secim = self.k_kutu.GetStringSelection()
        except Exception as e:
            hata_kaydet("Odaklanan klasör seçimi okunamadı.", e)
        if secim:
            self.klasor_sayisini_bildir_tetikle(secim, odak_mesaji=True)
        else:
            ui.message("E-posta klasörleri. Lütfen bir klasör seçiniz.")
        event.Skip()

    def _aktif_eposta_adresi(self):
        """Kayıtlı hesabın e-posta adresini güvenli biçimde döndürür."""
        try:
            ayarlar = ayarlari_yukle()
            return str(ayarlar.get("eposta", "") or "").strip()
        except Exception as e:
            hata_kaydet("Aktif hesap adresi alınamadı.", e)
            return ""

    def _klasor_sayisi_onbellegi_yukle(self):
        """Pencere açılışında son bilinen klasör sayılarını kalıcı JSON önbellekten belleğe alır."""
        try:
            eposta = self._aktif_eposta_adresi()
            if not eposta:
                return
            cache = klasor_sayisi_onbellegi_yukle(eposta)
            if isinstance(cache, dict) and cache:
                self._klasor_sayisi_cache.update(cache)
        except Exception as e:
            hata_kaydet("Klasör sayı önbelleği yüklenemedi.", e)

    def _klasor_sayisi_onbellegi_kaydet(self):
        """Bellekteki klasör sayılarını kalıcı JSON önbelleğine yazar."""
        try:
            eposta = self._aktif_eposta_adresi()
            if not eposta:
                return False
            return klasor_sayisi_onbellegi_kaydet(eposta, getattr(self, "_klasor_sayisi_cache", {}))
        except Exception as e:
            hata_kaydet("Klasör sayı önbelleği kaydedilemedi.", e)
            return False

    def _klasor_sayisi_cache_guncelle(self, kategori_adi, klasor_bilgisi, kaydet=True):
        """Tek klasörün sayı bilgisini bellek ve isteğe bağlı kalıcı önbellekte günceller."""
        kategori_adi = str(kategori_adi or "").strip()
        temiz = klasor_sayisi_bilgisini_duzenle(klasor_bilgisi)
        if not kategori_adi or not temiz:
            return False
        try:
            self._klasor_sayisi_cache[kategori_adi] = temiz
            if kaydet:
                self._klasor_sayisi_onbellegi_kaydet()
            return True
        except Exception as e:
            hata_kaydet("Klasör sayı önbelleği güncellenemedi.", e)
            return False

    def sistem_klasor_sayilarini_guncelle_tetikle(self):
        """Eklenti açılışında sistem klasörlerinin güncel toplam/okunmamış sayılarını arka planda alır."""
        try:
            if getattr(self, "_sistem_klasor_sayisi_guncelleniyor", False):
                return
            if not self.hesap_bilgisi_var_mi():
                return
            self._sistem_klasor_sayisi_guncelleniyor = True
            harita = dict(getattr(self, "klasor_haritasi", {}) or {})
            arka_planda_calistir(self.sistem_klasor_sayilarini_guncelle_thread, harita)
        except Exception as e:
            self._sistem_klasor_sayisi_guncelleniyor = False
            hata_kaydet("Sistem klasör sayı güncellemesi başlatılamadı.", e)

    def sistem_klasor_sayilarini_guncelle_thread(self, klasor_haritasi):
        """Sistem klasörlerinin STATUS bilgilerini tek IMAP bağlantısıyla günceller."""
        sonuc = {}
        try:
            ayarlar = ayarlari_yukle()
            if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
                return
            with ImapBaglantisi(ayarlar) as imap:
                for kategori_adi in SISTEM_KLASORLERI:
                    klasor = str((klasor_haritasi or {}).get(kategori_adi) or VARSAYILAN_KLASOR_HARITASI.get(kategori_adi, "")).strip()
                    if not klasor:
                        continue
                    try:
                        tip_status, status_verisi = imap.status(klasor, "(MESSAGES UNSEEN)")
                        if tip_status == "OK":
                            bilgi = imap_status_sayilarini_ayristir(status_verisi)
                            if bilgi:
                                sonuc[kategori_adi] = bilgi
                    except Exception as e:
                        hata_kaydet(f"Sistem klasör sayısı alınamadı: {kategori_adi}", e)
            if sonuc:
                guvenli_call_after(self, self.sistem_klasor_sayilarini_guncelle_sonuc, sonuc)
        except Exception as e:
            hata_kaydet("Sistem klasör sayıları güncellenemedi.", e)
        finally:
            guvenli_call_after(self, self.sistem_klasor_sayilarini_guncelle_bitti)

    def sistem_klasor_sayilarini_guncelle_sonuc(self, sonuc):
        """Arka planda alınan sistem klasör sayılarını bellek ve JSON önbelleğe aktarır."""
        if not isinstance(sonuc, dict):
            return
        degisti = False
        for kategori_adi, bilgi in sonuc.items():
            if self._klasor_sayisi_cache_guncelle(kategori_adi, bilgi, kaydet=False):
                degisti = True
        if degisti:
            self._klasor_sayisi_onbellegi_kaydet()

    def sistem_klasor_sayilarini_guncelle_bitti(self):
        self._sistem_klasor_sayisi_guncelleniyor = False

    def klasor_sayisi_duyurusunu_iptal_et(self):
        """Klasör üzerinde hızlı dolaşırken bekleyen eski sayı duyurusunu iptal eder."""
        for timer_adi, hata_mesaji in (
            ("_klasor_sayisi_duyuru_timer", "Bekleyen klasör sayı duyurusu iptal edilemedi."),
            ("_klasor_sayisi_sorgu_timer", "Bekleyen klasör sayı sorgusu iptal edilemedi."),
        ):
            timer = getattr(self, timer_adi, None)
            if timer:
                try:
                    timer.Stop()
                except Exception as e:
                    hata_kaydet(hata_mesaji, e)
            setattr(self, timer_adi, None)

    def klasor_sayisi_duyurusunu_planla(self, kategori_adi, klasor_bilgisi, gecikme_ms=400):
        """wx.Choice önce klasör adını okuduktan sonra sayı bilgisini gecikmeli duyurur."""
        kategori_adi = str(kategori_adi or "").strip()
        if not kategori_adi:
            return
        mesaj = klasor_secimi_sayisi_mesaji(kategori_adi, klasor_bilgisi)
        if not mesaj:
            return

        self.klasor_sayisi_duyurusunu_iptal_et()

        def duyur():
            self._klasor_sayisi_duyuru_timer = None
            if not pencere_kullanilabilir_mi(self):
                return
            try:
                if self.k_kutu.GetStringSelection() != kategori_adi:
                    return
            except Exception:
                return
            try:
                if wx.Window.FindFocus() is not self.k_kutu:
                    return
            except Exception:
                pass
            ui.message(mesaj)

        try:
            self._klasor_sayisi_duyuru_timer = wx.CallLater(int(gecikme_ms), duyur)
        except Exception as e:
            hata_kaydet("Klasör sayı duyurusu planlanamadı.", e)

    def klasor_sayisini_bildir_tetikle(self, kategori_adi, odak_mesaji=False):
        """Klasör kutusunda dolaşırken klasör toplam/okunmamış bilgisini arka planda bildirir."""
        kategori_adi = str(kategori_adi or "").strip()
        if not kategori_adi:
            self.klasor_sayisi_duyurusunu_iptal_et()
            return
        if not self.hesap_bilgisi_var_mi():
            self.klasor_sayisi_duyurusunu_iptal_et()
            if odak_mesaji:
                ui.message("E-posta klasörleri. Lütfen bir klasör seçiniz.")
            return

        self.klasor_sayisi_duyurusunu_iptal_et()
        self._klasor_sayisi_islem_no = getattr(self, "_klasor_sayisi_islem_no", 0) + 1
        islem_no = self._klasor_sayisi_islem_no

        cache = getattr(self, "_klasor_sayisi_cache", {})
        cache_var = kategori_adi in cache
        if cache_var:
            self.klasor_sayisi_duyurusunu_planla(kategori_adi, cache.get(kategori_adi), gecikme_ms=120)
            # Sistem klasörleri pencere açılışında topluca güncellenir.
            # Özel klasörlerde ise son bilinen sayı hızlı okunur, ardından arka planda güncel STATUS bilgisi alınır.
            if kategori_adi in SISTEM_KLASORLERI:
                return

        klasor = self.klasor_haritasi.get(kategori_adi, VARSAYILAN_KLASOR_HARITASI.get(kategori_adi, ""))
        if not klasor:
            return

        def sorguyu_baslat():
            self._klasor_sayisi_sorgu_timer = None
            if not pencere_kullanilabilir_mi(self):
                return
            try:
                if self.k_kutu.GetStringSelection() != kategori_adi:
                    return
            except Exception:
                return
            try:
                if wx.Window.FindFocus() is not self.k_kutu:
                    return
            except Exception:
                pass
            arka_planda_calistir(self.klasor_sayisini_bildir_thread, kategori_adi, klasor, islem_no)

        try:
            self._klasor_sayisi_sorgu_timer = wx.CallLater(300, sorguyu_baslat)
        except Exception as e:
            hata_kaydet("Klasör sayı sorgusu gecikmeli başlatılamadı.", e)
            sorguyu_baslat()

    def klasor_sayisini_bildir_thread(self, kategori_adi, klasor, islem_no):
        try:
            ayarlar = ayarlari_yukle()
            if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
                return
            klasor_bilgisi = {}
            with ImapBaglantisi(ayarlar) as imap:
                tip_status, status_verisi = imap.status(klasor, "(MESSAGES UNSEEN)")
                if tip_status == "OK":
                    klasor_bilgisi = imap_status_sayilarini_ayristir(status_verisi)
            if klasor_bilgisi:
                guvenli_call_after(self, self.klasor_sayisini_bildir_sonuc, kategori_adi, klasor_bilgisi, islem_no)
        except Exception as e:
            hata_kaydet("Klasör üzerinde dolaşırken toplam/okunmamış bilgisi alınamadı.", e)

    def klasor_sayisini_bildir_sonuc(self, kategori_adi, klasor_bilgisi, islem_no):
        if islem_no != getattr(self, "_klasor_sayisi_islem_no", 0):
            return
        try:
            if self.k_kutu.GetStringSelection() != kategori_adi:
                return
        except Exception:
            return
        try:
            if wx.Window.FindFocus() is not self.k_kutu:
                return
        except Exception:
            pass
        self._klasor_sayisi_cache_guncelle(kategori_adi, klasor_bilgisi)
        self.klasor_sayisi_duyurusunu_planla(kategori_adi, klasor_bilgisi, gecikme_ms=200)

    def klasor_seciminden_listeye_gec(self):
        """Klasör seçimi üzerindeyken Enter ile ilgili klasörü yükleyip e-posta listesine odaklanır."""
        secim = ""
        try:
            secim = self.k_kutu.GetStringSelection()
        except Exception as e:
            hata_kaydet("Klasör seçimi okunamadı.", e)
        if secim:
            self.bekleyen_kategori = secim

        if self.yukleniyor:
            ui.message("Klasör yüklenirken lütfen bekleyin.")
            return True

        if self.bekleyen_kategori and self.bekleyen_kategori != self.yuklu_kategori:
            self.verileri_yukle_tetikle(
                f"{self.bekleyen_kategori} yükleniyor...",
                kategori_adi=self.bekleyen_kategori,
            )

        try:
            self.liste.SetFocus()
        except Exception as e:
            hata_kaydet("Klasör seçiminden listeye odaklanılamadı.", e)
        return True

    def klasor_tusuna_basildi(self, event):
        tus = event.GetKeyCode()
        if tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.klasor_seciminden_listeye_gec()
            return
        event.Skip()

    def ana_pencere_tus_yakalandi(self, event):
        """Ana penceredeki Enter/Escape tuş davranışlarını güvenli biçimde yönetir."""
        tus = event.GetKeyCode()
        if tus == wx.WXK_ESCAPE and escape_kapat_ayari_yukle():
            self.pencereyi_kapat()
            return
        try:
            odak = wx.Window.FindFocus()
        except Exception:
            odak = None
        if odak is self.k_kutu and tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.klasor_seciminden_listeye_gec()
            return
        event.Skip()

    def listeye_odaklandi(self, event):
        if (
            not self.yukleniyor
            and self.bekleyen_kategori
            and self.bekleyen_kategori != self.yuklu_kategori
        ):
            self.verileri_yukle_tetikle(
                f"{self.bekleyen_kategori} yükleniyor...",
                kategori_adi=self.bekleyen_kategori,
            )
        event.Skip()

    def secili_eposta_idlerini_al(self):
        secili_idler = list(self.isaretliler)
        if not secili_idler:
            indeks = self.liste.GetFocusedItem()
            if indeks != -1 and indeks < len(self.mailler):
                secili_idler.append(self.mailler[indeks]["id"])
        return secili_idler

    def sag_tik_odagini_guncelle(self, event):
        try:
            indeks = -1
            if hasattr(event, "GetIndex"):
                try:
                    indeks = event.GetIndex()
                except Exception:
                    indeks = -1
            if indeks == -1 and hasattr(event, "GetPosition"):
                try:
                    konum = event.GetPosition()
                    if konum.x != -1 or konum.y != -1:
                        istemci_konum = self.liste.ScreenToClient(konum)
                        sonuc = self.liste.HitTest(istemci_konum)
                        indeks = sonuc[0] if isinstance(sonuc, tuple) else sonuc
                except Exception:
                    indeks = -1
            if indeks != -1 and indeks < len(self.mailler):
                self.liste.Focus(indeks)
                self.liste.Select(indeks)
                self.liste.EnsureVisible(indeks)
        except Exception:
            pass

    def tasima_hedefleri(self):
        hedefler = []

        def ekle(ad):
            ad = str(ad or "").strip()
            if not ad:
                return
            if ad == self.secili_kategori:
                return
            if ad not in self.klasor_haritasi:
                return
            if ad not in hedefler:
                hedefler.append(ad)

        ekle("Gelen Kutusu")
        for ad in self.ozel_klasorler:
            ekle(ad)
        return hedefler

    def tasima_onayi_al(self, adet, hedef_adi, konu=None):
        hedef_adi = str(hedef_adi or "").strip()
        konu_etiketi = self.konu_ifadesi(konu) if adet == 1 and konu else "Seçili"
        soru = (
            f"{konu_etiketi} e-posta '{hedef_adi}' klasörüne taşınacaktır. Devam etmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} e-posta '{hedef_adi}' klasörüne taşınacaktır. Devam etmek istiyor musunuz?"
        )
        return gui.messageBox(soru, "Taşıma Onayı", wx.YES_NO | wx.ICON_QUESTION) == wx.YES

    def tasi_menu(self, hedef_adi):
        secili_idler = self.secili_eposta_idlerini_al()
        if not secili_idler:
            ui.message("Lütfen taşımak için e-posta seçin.")
            return
        hedef_adi = str(hedef_adi or "").strip()
        if not hedef_adi or hedef_adi not in self.klasor_haritasi:
            ui.message("Hedef klasör bulunamadı.")
            return
        if hedef_adi == self.secili_kategori:
            ui.message("E-posta zaten seçili klasörde bulunuyor.")
            return
        kaynak_klasor = self.aktif_klasor()
        hedef_klasor = self.klasor_haritasi.get(hedef_adi)
        if str(kaynak_klasor) == str(hedef_klasor):
            ui.message("Kaynak ve hedef klasör aynı.")
            return
        adet = len(secili_idler)
        konu = self.mail_konusunu_bul(secili_idler[0]) if adet == 1 else None
        if self.tum_postalar_klasoru_mu(kaynak_klasor):
            if not self.tum_postalar_tasima_onayi_al(adet, hedef_adi):
                self.liste.SetFocus()
                return
        elif not self.tasima_onayi_al(adet, hedef_adi, konu):
            self.liste.SetFocus()
            return
        if not self.tum_postalar_klasoru_mu(kaynak_klasor):
            self.listeden_mesajlari_kaldir(secili_idler)
        ui.message(f"E-postalar '{hedef_adi}' klasörüne taşınıyor." if adet > 1 else f"E-posta '{hedef_adi}' klasörüne taşınıyor.")
        arka_planda_calistir(self.sunucudan_tasi, secili_idler, kaynak_klasor, hedef_adi)

    def sunucudan_tasi(self, ids, kaynak_klasor, hedef_adi):
        ayarlar = ayarlari_yukle()
        try:
            uidler = uid_kumesi_hazirla(ids, "Taşınacak e-posta bulunamadı.")
            hedef_adi = str(hedef_adi or "").strip()
            hedef_klasor = self.klasor_haritasi.get(hedef_adi)
            if not hedef_klasor:
                raise MailHatasi("Hedef klasör bulunamadı.")
            if str(kaynak_klasor) == str(hedef_klasor):
                raise MailHatasi("Kaynak ve hedef klasör aynı.")
            with ImapBaglantisi(ayarlar) as imap:
                imap_gmail_etiket_destegini_dogrula(imap)
                tip, _veri = imap.select(kaynak_klasor, readonly=False)
                imap_ok_mu(tip, "Kaynak klasör açılamadı.")

                hedef_etiket = self.gmail_etiket_ifadesi(hedef_adi, hedef_klasor)
                if not hedef_etiket:
                    raise MailHatasi("Hedef klasör etiketi hazırlanamadı.")
                self.gmail_etiket_ekle_ve_kaynak_kaldir(
                    imap,
                    uidler,
                    hedef_etiket,
                    kaynak_klasor,
                    "E-postalar hedef etikete eklenemedi.",
                    "E-postalar kaynak etiketinden kaldırılamadı.",
                )
            if self.tum_postalar_klasoru_mu(kaynak_klasor):
                mesaj = f"E-postaya '{hedef_adi}' etiketi eklendi. Tüm Postalar'da görünmeye devam edebilir." if len(ids) == 1 else f"E-postalara '{hedef_adi}' etiketi eklendi. Tüm Postalar'da görünmeye devam edebilirler."
            else:
                mesaj = f"E-posta '{hedef_adi}' klasörüne taşındı." if len(ids) == 1 else f"E-postalar '{hedef_adi}' klasörüne taşındı."
            guvenli_call_after(self, ui.message, mesaj)
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, True)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, ui.message, str(e))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)
        except Exception as e:
            hata_kaydet("Taşıma işlemi başarısız oldu.", e)
            guvenli_call_after(self, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Taşıma işlemi sırasında bir hata oluştu."))
            guvenli_call_after(self, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", self.secili_kategori, None, None, False)

    def sag_tik_menusu(self, event):
        self.sag_tik_odagini_guncelle(event)
        menu = wx.Menu()
        menu.Append(self.id_yanitla, "Yanıtla")
        menu.Append(self.id_ilet, "İlet")
        menu.AppendSeparator()
        menu.Append(self.id_arsiv, "Arşive Gönder	Alt+R")

        tasi_alt_menu = wx.Menu()
        hedefler = self.tasima_hedefleri()
        if hedefler:
            for hedef in hedefler:
                hedef_id = wx.NewId()
                tasi_alt_menu.Append(hedef_id, hedef)
                tasi_alt_menu.Bind(wx.EVT_MENU, lambda evt, hedef=hedef: self.tasi_menu(hedef), id=hedef_id)
        else:
            bos_item = tasi_alt_menu.Append(wx.ID_ANY, "Taşınabilecek klasör yok")
            bos_item.Enable(False)
        menu.AppendSubMenu(tasi_alt_menu, "Taşı")

        kaydet_alt_menu = wx.Menu()
        kaydet_alt_menu.Append(self.id_kaydet_secili_txt, "Seçili E-postayı TXT Olarak Kaydet...")
        kaydet_alt_menu.Append(self.id_kaydet_secili_eml, "Seçili E-postayı EML Olarak Kaydet...")
        kaydet_alt_menu.AppendSeparator()
        kaydet_alt_menu.Append(self.id_kaydet_isaretli_txt, "İşaretli E-postaları TXT Olarak Kaydet...")
        kaydet_alt_menu.Append(self.id_kaydet_isaretli_eml, "İşaretli E-postaları EML Olarak Kaydet...")
        menu.AppendSubMenu(kaydet_alt_menu, "Kaydet")

        menu.Append(self.id_sil, "Sil	Alt+S")
        menu.Append(self.id_kalici_sil, "Kalıcı Sil	Shift+Delete")
        menu.Append(self.id_yenile, "Yenile	F5")
        menu.AppendSeparator()
        menu.Append(self.id_tumunu, "Tümünü İşaretle	CTRL+A")
        menu.Append(self.id_kaldir, "İşaretleri Kaldır	Alt+D")
        self.liste.PopupMenu(menu)
        menu.Destroy()

    def arsive_gonder_menu(self, event=None):
        secili_idler = list(self.isaretliler)
        if not secili_idler:
            indeks = self.liste.GetFocusedItem()
            if indeks != -1 and indeks < len(self.mailler):
                secili_idler.append(self.mailler[indeks]["id"])
        if not secili_idler:
            ui.message("Lütfen arşive göndermek için e-posta seçin.")
            return
        self.arsiv_secim_goster(secili_idler)

    def tumunu_isaretle(self, event=None):
        if not self.mailler:
            ui.message("İşaretlenecek e-posta yok.")
            return
        for i, mesaj in enumerate(self.mailler):
            if mesaj["id"] not in self.isaretliler:
                self.isaretliler.add(mesaj["id"])
                self.liste.SetItem(i, 0, "[İşaretli] " + self.mesaj_liste_gosterimi(mesaj))
        ui.message(f"{len(self.isaretliler)} e-posta işaretlendi.")

    def isaretleri_kaldir(self, event=None):
        if not self.isaretliler:
            ui.message("Kaldırılacak işaret yok.")
            return
        self.isaretliler.clear()
        for i, mesaj in enumerate(self.mailler):
            self.liste.SetItem(i, 0, self.mesaj_liste_gosterimi(mesaj))
        ui.message("İşaretler kaldırıldı.")

    def tusa_basildi(self, event):
        tus = event.GetKeyCode()
        if tus == wx.WXK_DELETE:
            if event.ShiftDown():
                self.posta_kalici_sil()
            else:
                self.posta_sil()
            return
        if tus != wx.WXK_SPACE:
            event.Skip()
            return
        indeks = self.liste.GetFocusedItem()
        if indeks == -1 or indeks >= len(self.mailler):
            ui.message("İşaretlenecek e-posta yok.")
            return
        mail_id = self.mailler[indeks]["id"]
        if mail_id in self.isaretliler:
            self.isaretliler.remove(mail_id)
            self.liste.SetItem(indeks, 0, self.mesaj_liste_gosterimi(self.mailler[indeks]))
            ui.message("İşaret kaldırıldı.")
        else:
            self.isaretliler.add(mail_id)
            self.liste.SetItem(indeks, 0, "[İşaretli] " + self.mesaj_liste_gosterimi(self.mailler[indeks]))
            ui.message("E-posta işaretlendi.")

    def verileri_yukle(self, kategori_adi=None, kaynak_klasor=None, yukleme_islem_no=None):
        ayarlar = ayarlari_yukle()
        mesaj_sayisi = mesaj_sayisini_duzenle(ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI))
        onizleme_etkin = onizleme_ayari_yukle()
        try:
            with ImapBaglantisi(ayarlar) as imap:
                yeni_harita, yeni_ozeller = self.klasor_haritasini_hazirla(imap)
                hedef_kategori = kategori_adi or self.secili_kategori
                if hedef_kategori in yeni_harita:
                    aktif_klasor = yeni_harita.get(hedef_kategori, kaynak_klasor or "INBOX")
                elif kaynak_klasor:
                    aktif_klasor = kaynak_klasor
                else:
                    hedef_kategori = "Gelen Kutusu"
                    aktif_klasor = yeni_harita.get(hedef_kategori, "INBOX")

                klasor_bilgisi = {}
                try:
                    tip_status, status_verisi = imap.status(aktif_klasor, "(MESSAGES UNSEEN)")
                    if tip_status == "OK":
                        klasor_bilgisi = imap_status_sayilarini_ayristir(status_verisi)
                except Exception as e:
                    hata_kaydet("Klasör toplam/okunmamış bilgisi alınamadı.", e)

                tip, _veri = imap.select(aktif_klasor, readonly=False)
                if tip != "OK":
                    hata_kaydet(f"Klasör açılamadı: kategori={hedef_kategori}, imap={aktif_klasor}")
                    raise MailHatasi("Seçili klasör açılamadı.")
                tip, veri = imap.uid("SEARCH", "ALL")
                if tip != "OK":
                    raise MailHatasi("E-posta listesi alınamadı.")
                uidler = uidleri_ayristir(veri)
                if "messages" not in klasor_bilgisi:
                    klasor_bilgisi["messages"] = len(uidler)
                if "unseen" not in klasor_bilgisi:
                    try:
                        tip_unseen, unseen_veri = imap.uid("SEARCH", "UNSEEN")
                        if tip_unseen == "OK":
                            klasor_bilgisi["unseen"] = len(uidleri_ayristir(unseen_veri))
                    except Exception as e:
                        hata_kaydet("Okunmamış e-posta sayısı alınamadı.", e)

                yeni_mailler = []
                secili_uidler = [str(uid) for uid in reversed(uidler[-mesaj_sayisi:])]
                baslik_haritasi = imap_toplu_uid_fetch(
                    imap,
                    secili_uidler,
                    "(FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])",
                )
                onizleme_haritasi = {}
                if onizleme_etkin and secili_uidler:
                    onizleme_haritasi = imap_toplu_uid_fetch(
                        imap,
                        secili_uidler,
                        f"(BODY.PEEK[TEXT]<0.{ONIZLEME_FETCH_BOYUTU}>)",
                    )

                for uid_str in secili_uidler:
                    baslik_verisi = baslik_haritasi.get(uid_str, [])
                    if not baslik_verisi:
                        try:
                            tip, baslik_verisi = imap.uid(
                                "FETCH",
                                uid_str,
                                "(FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])",
                            )
                            if tip != "OK":
                                continue
                        except Exception as e:
                            hata_kaydet(f"E-posta başlığı alınamadı: UID {uid_str}", e)
                            continue

                    ham_baslik = ham_mesaj_verisi_al(baslik_verisi)
                    mesaj = email.message_from_bytes(ham_baslik, policy=email_policy.default)
                    kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
                    ad, adres = email.utils.parseaddr(kimden)
                    ad_gosterim = grup_araci_gonderen_bilgisini_temizle(ad)
                    kimden_goster = ad_gosterim or adres or kimden or "Bilinmiyor"
                    kime_goster = adres_basligini_duzenle(mesaj.get("To", "")) or "Alıcı yok"
                    liste_gosterim = kime_goster if hedef_kategori in ("Gönderilen E-postalar", "Taslaklar") else kimden_goster
                    if not seen_bayragi_var_mi(baslik_verisi):
                        kimden_goster = "[Okunmadı] " + kimden_goster
                        liste_gosterim = "[Okunmadı] " + liste_gosterim

                    onizleme = ""
                    if onizleme_etkin:
                        try:
                            onizleme_verisi = onizleme_haritasi.get(uid_str, [])
                            if not onizleme_verisi:
                                tip, onizleme_verisi = imap.uid(
                                    "FETCH",
                                    uid_str,
                                    f"(BODY.PEEK[TEXT]<0.{ONIZLEME_FETCH_BOYUTU}>)",
                                )
                                if tip != "OK":
                                    onizleme_verisi = []
                            if onizleme_verisi:
                                onizleme = onizleme_metni_olustur(ham_mesaj_verisi_al(onizleme_verisi))
                        except Exception as e:
                            hata_kaydet("E-posta ön izlemesi alınamadı.", e)

                    ek_var = fetch_sonucunda_ek_var_mi(baslik_verisi)

                    yeni_mailler.append(
                        {
                            "id": uid_str,
                            "kimden": kimden_goster,
                            "kime": kime_goster,
                            "liste_gosterim": liste_gosterim,
                            "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
                            "onizleme": onizleme,
                            "ek_var": ek_var,
                        }
                    )

            guvenli_call_after(
                self,
                self.arayuzu_yenile,
                yeni_mailler,
                yeni_harita,
                yeni_ozeller,
                hedef_kategori,
                yukleme_islem_no,
                klasor_bilgisi,
            )
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, self.yukleme_hatali, str(e), yukleme_islem_no)
        except Exception as e:
            hata_kaydet("E-posta listesi yüklenemedi.", e)
            guvenli_call_after(self, self.yukleme_hatali, baglanti_hatasi_kullanici_mesaji(e), yukleme_islem_no)

    def klasor_haritasini_hazirla(self, imap):
        """IMAP klasör listesini arka planda hazırlar; wx denetimlerine dokunmaz."""
        tip, veri = imap.list()
        if tip != "OK" or not veri:
            return dict(self.klasor_haritasi), list(self.ozel_klasorler)
        yeni_ozeller = []
        yeni_harita = dict(VARSAYILAN_KLASOR_HARITASI)

        for satir in veri:
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
                if gorunen_ad not in yeni_ozeller and gorunen_ad not in SISTEM_KLASORLERI:
                    yeni_ozeller.append(gorunen_ad)
                    yeni_harita[gorunen_ad] = imap_degeri

        return yeni_harita, yeni_ozeller

    def klasor_haritasini_uygula(self, yeni_harita=None, yeni_ozeller=None, hedef_kategori=None):
        """Arka planda hazırlanan klasör bilgisini ana arayüz iş parçacığında uygular."""
        if isinstance(yeni_harita, dict):
            self.klasor_haritasi = dict(yeni_harita)
        if isinstance(yeni_ozeller, list):
            self.ozel_klasorler = list(yeni_ozeller)

        tum_kategoriler = self.kategori_isimleri + self.ozel_klasorler
        yeni_secim = hedef_kategori or self.secili_kategori
        if yeni_secim not in tum_kategoriler:
            yeni_secim = "Gelen Kutusu"
        self.secili_kategori = yeni_secim
        self.yuklu_kategori = yeni_secim
        self.bekleyen_kategori = yeni_secim


    def yukleme_hatali(self, mesaj, yukleme_islem_no=None):
        if not pencere_kullanilabilir_mi(self):
            return
        if yukleme_islem_no is not None and yukleme_islem_no != getattr(self, "_yukleme_islem_no", None):
            return
        self.yukleniyor = False
        self._yenileme_sessiz = False
        try:
            self.k_kutu.Enable()
        except Exception:
            pass
        self.liste_bilgi_satiri_goster("E-postalar yüklenemedi.")
        ui.message(mesaj)

    def arayuzu_yenile(self, yeni_mailler, yeni_harita=None, yeni_ozeller=None, hedef_kategori=None, yukleme_islem_no=None, klasor_bilgisi=None):
        if not pencere_kullanilabilir_mi(self):
            return
        if yukleme_islem_no is not None and yukleme_islem_no != getattr(self, "_yukleme_islem_no", None):
            return
        self.klasor_haritasini_uygula(yeni_harita, yeni_ozeller, hedef_kategori)
        self.yukleniyor = False
        if isinstance(klasor_bilgisi, dict) and self.secili_kategori:
            self._klasor_sayisi_cache_guncelle(self.secili_kategori, klasor_bilgisi)
        try:
            self.k_kutu.Enable()
        except Exception:
            pass
        self.mailler = yeni_mailler
        self.isaretliler.clear()

        eski_secim = self.secili_kategori
        self.klasor_secimi_programatik = True
        try:
            self.k_kutu.Clear()
            tum_kategoriler = self.kategori_isimleri + self.ozel_klasorler
            for kategori in tum_kategoriler:
                self.k_kutu.Append(kategori)

            indeks = self.k_kutu.FindString(eski_secim)
            if indeks != wx.NOT_FOUND:
                self.k_kutu.SetSelection(indeks)
            else:
                self.k_kutu.SetSelection(0)
                self.secili_kategori = self.kategori_isimleri[0]
        finally:
            self.klasor_secimi_programatik = False

        self.yuklu_kategori = self.secili_kategori
        self.bekleyen_kategori = self.secili_kategori

        self.birinci_sutun_basligini_guncelle()
        self.liste.DeleteAllItems()
        hedef_indeks = 0
        hedef_mail_id = self._yenileme_hedef_mail_id
        hedef_indeks_yedek = self._yenileme_hedef_indeks
        sessiz_yenileme = bool(getattr(self, "_yenileme_sessiz", False))
        self._yenileme_hedef_mail_id = None
        self._yenileme_hedef_indeks = None
        self._yenileme_sessiz = False

        if not self.mailler:
            self.liste_bilgi_satiri_goster("Bu klasörde gösterilecek e-posta yok.")
        else:
            onizleme_etkin = onizleme_ayari_yukle()
            for i, mesaj in enumerate(self.mailler):
                self.liste.InsertItem(i, self.mesaj_liste_gosterimi(mesaj))
                konu_goster = str(mesaj.get("konu", "") or "")
                onizleme = str(mesaj.get("onizleme", "") or "").strip()
                if onizleme_etkin and onizleme:
                    konu_goster = f"{konu_goster}. {onizleme}"
                self.liste.SetItem(i, 1, konu_goster)
                if hedef_mail_id and str(mesaj.get("id")) == str(hedef_mail_id):
                    hedef_indeks = i

            if hedef_mail_id and not any(str(mesaj.get("id")) == str(hedef_mail_id) for mesaj in self.mailler):
                if hedef_indeks_yedek is not None:
                    hedef_indeks = hedef_indeks_yedek
            elif not hedef_mail_id and hedef_indeks_yedek is not None:
                hedef_indeks = hedef_indeks_yedek

            self.liste_secim_ver(hedef_indeks)

        if self.ilk_yukleme:
            self.ilk_yukleme = False

        if not getattr(self, "_sistem_klasor_sayisi_acilista_guncellendi", False):
            self._sistem_klasor_sayisi_acilista_guncellendi = True
            self.sistem_klasor_sayilarini_guncelle_tetikle()

        if not sessiz_yenileme:
            ui.message(klasor_sayisi_mesaji(self.secili_kategori, klasor_bilgisi, len(self.mailler)))


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
    except Exception as e:
        hata_kaydet("IMAP UIDVALIDITY değeri ayrıştırılamadı.", e)
    return 0


def bildirim_tabanini_sifirla(eposta, uidvalidity=0):
    """Hesap veya UIDVALIDITY değiştiğinde bildirim tabanını sessizce sıfırlar."""
    return bildirim_son_uid_kaydet(eposta, 0, baslatildi=False, uidvalidity=uidvalidity)


def bildirim_son_uid_kaydet(eposta, uid, baslatildi=True, uidvalidity=None):
    """Bildirim denetimi için son görülen UID ve UIDVALIDITY değerini hesap bilgilerine dokunmadan kaydeder."""
    ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not isinstance(ayarlar, dict):
        ayarlar = {}

    yeni_ayarlar = ayar_kopyasi_olustur(ayarlar)
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
    yeni_ayarlar.pop(SIFRE_DUZ_METIN_ALANI, None)
    return guvenli_json_yaz(AYARLAR_DOSYASI, yeni_ayarlar)


def bildirim_sesi_cal():
    """Yeni e-posta için ayara göre sistem sesi veya kullanıcı tanımlı WAV dosyası çalar."""
    try:
        ayarlar = bildirim_ayarlari_yukle()
        ses_turu = ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        ses_dosyasi = ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, "")

        if ses_turu == BILDIRIM_SES_TURU_DOSYA and ses_dosyasi and os.path.exists(ses_dosyasi) and ses_dosyasi.lower().endswith(".wav"):
            if winsound:
                winsound.PlaySound(ses_dosyasi, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                wx.Bell()
            return

        if winsound:
            winsound.Beep(880, 120)
            winsound.Beep(1175, 120)
        else:
            wx.Bell()
    except Exception as e:
        hata_kaydet("Bildirim sesi çalınamadı.", e)


def bildirim_mesaji_olustur(yeni_sayisi, son_eposta=None, ayarlar=None):
    """Ayar seçeneklerine göre kısa bildirim metni üretir."""
    ayarlar = ayarlar or {}
    son_eposta = son_eposta or {}

    if yeni_sayisi <= 1:
        parcalar = ["Yeni e-postanız var."]
    else:
        parcalar = [f"{yeni_sayisi} yeni e-postanız var."]

    if ayarlar.get(BILDIRIM_GONDEREN_ALANI):
        kimden = str(son_eposta.get("kimden", "") or "").strip()
        if kimden:
            parcalar.append(f"Gönderen: {kimden}.")

    if ayarlar.get(BILDIRIM_KONU_ALANI):
        konu = str(son_eposta.get("konu", "") or "").strip()
        if konu:
            parcalar.append(f"Konu: {konu}.")

    return " ".join(parcalar).strip()


def bildirim_eposta_basligi_al(imap, uid):
    """Yeni e-postanın gönderen ve konu bilgisini alır."""
    sonuc = {"uid": str(uid), "kimden": "", "konu": ""}
    try:
        tip, veri = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if tip != "OK":
            return sonuc
        ham = ham_mesaj_verisi_al(veri)
        if not ham:
            return sonuc
        mesaj = email.message_from_bytes(ham, policy=email_policy.default)
        kimden_ad, kimden_adres = email.utils.parseaddr(guvenli_coz(mesaj.get("From", "")))
        kimden_ad = guvenli_coz(kimden_ad).strip()
        kimden_adres = str(kimden_adres or "").strip()
        sonuc["kimden"] = kimden_ad or kimden_adres
        sonuc["konu"] = guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
    except Exception as e:
        hata_kaydet("Bildirim e-posta başlığı alınamadı.", e)
    return sonuc


def bildirim_gelen_kutusu_kontrol_et():
    """Gelen Kutusu'nda yeni UID var mı diye sessiz denetim yapar."""
    bildirim_ayar = bildirim_ayarlari_yukle()
    if not bildirim_ayar.get(BILDIRIM_ETKIN_ALANI):
        return None

    hesap_ayar = ayarlari_yukle()
    eposta = str(hesap_ayar.get("eposta", "") or "").strip()
    sifre = str(hesap_ayar.get("sifre", "") or "").strip()
    if not eposta or not sifre:
        return None

    try:
        with ImapBaglantisi(hesap_ayar) as imap:
            tip, secim_verisi = imap.select("INBOX", readonly=True)
            if tip != "OK":
                return None

            gecerli_uidvalidity = imap_uidvalidity_ayristir(secim_verisi)
            kayitli_uidvalidity = bildirim_uidvalidity_oku(eposta)

            onceki_uid = bildirim_son_uid_oku(eposta)
            bildirim_baslatildi = bildirim_baslatildi_mi(eposta)

            if (
                bildirim_baslatildi
                and kayitli_uidvalidity
                and gecerli_uidvalidity
                and kayitli_uidvalidity != gecerli_uidvalidity
            ):
                # UIDVALIDITY değiştiyse eski UID tabanı artık güvenilir değildir.
                # Mevcut gelen kutusunu yeni saymadan tabanı sessizce yeniden kur.
                bildirim_tabanini_sifirla(eposta, gecerli_uidvalidity)
                bildirim_baslatildi = False
                onceki_uid = 0

            if not bildirim_baslatildi:
                tip, arama_sonucu = imap.uid("SEARCH", "ALL")
                if tip != "OK":
                    return None

                uidler = []
                for uid in uidleri_ayristir(arama_sonucu):
                    try:
                        uidler.append(int(uid))
                    except Exception:
                        pass

                # İlk kurulumda, hesap değiştiğinde veya UIDVALIDITY değiştiğinde mevcut postalar yeni sayılmaz;
                # ancak gelen kutusu boşsa bu durum ayrıca kaydedilir. Böylece daha sonra
                # gelen ilk e-posta bildirimsiz geçmez.
                bildirim_son_uid_kaydet(eposta, max(uidler) if uidler else 0, baslatildi=True, uidvalidity=gecerli_uidvalidity)
                return None

            tip, arama_sonucu = imap.uid("SEARCH", "UID", f"{onceki_uid + 1}:*")
            if tip != "OK":
                return None

            yeni_uidler = []
            for uid in uidleri_ayristir(arama_sonucu):
                try:
                    uid_sayi = int(uid)
                except Exception:
                    continue
                if uid_sayi > onceki_uid:
                    yeni_uidler.append(uid_sayi)

            if not yeni_uidler:
                return None

            yeni_uidler = sorted(yeni_uidler)
            en_son_uid = max(yeni_uidler)

            son_eposta = {}
            if bildirim_ayar.get(BILDIRIM_GONDEREN_ALANI) or bildirim_ayar.get(BILDIRIM_KONU_ALANI):
                son_eposta = bildirim_eposta_basligi_al(imap, yeni_uidler[-1])

            bildirim_son_uid_kaydet(eposta, en_son_uid, uidvalidity=gecerli_uidvalidity)

            return {
                "sayi": len(yeni_uidler),
                "son_eposta": son_eposta,
                "ayarlar": bildirim_ayar,
            }
    except Exception as e:
        # İnternet yoksa veya Gmail bağlantısı kurulamazsa kullanıcı rahatsız edilmez.
        # Bir sonraki zamanlayıcı turunda yeniden denenir.
        hata_kaydet("Yeni e-posta bildirimi sessizce atlandı.", e)
        return None


def bildirim_yoneticisini_yenile():
    """Ayar değişikliğinden sonra arka plan bildirim yöneticisini günceller."""
    try:
        yonetici = globals().get("BILDIRIM_YONETICISI")
        if yonetici:
            yonetici.ayarlari_yenile()
    except Exception as e:
        hata_kaydet("Bildirim yöneticisi yenilenemedi.", e)


class BildirimYoneticisi:
    """NVDA açıkken Engelsiz Mail yeni e-posta bildirimlerini zamanlayan yönetici."""

    def __init__(self):
        self._sonlandirildi = False
        self._kontrol_suruyor = False
        self._zamanlayici = None
        self._kontrol_kimligi = 0
        self._aktif_kontrol_kimligi = None
        self.ayarlari_yenile(ilkcagri=True)

    def durdur(self):
        self._sonlandirildi = True
        self._aktif_kontrol_kimligi = None
        self._kontrol_suruyor = False
        self._zamanlayiciyi_durdur()

    def _zamanlayiciyi_durdur(self):
        try:
            if self._zamanlayici:
                self._zamanlayici.Stop()
        except Exception as e:
            hata_kaydet("Bildirim zamanlayıcısı durdurulamadı.", e)
        self._zamanlayici = None

    def ayarlari_yenile(self, ilkcagri=False):
        if self._sonlandirildi:
            return
        self._zamanlayiciyi_durdur()
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        # Eklenti/NVDA açılışında ilk kontrol kısa süre sonra yapılır.
        # Sonraki denetimler kullanıcının seçtiği dakika aralığına göre sürer.
        ilk_gecikme_ms = 15000 if ilkcagri else 2000
        self._sonraki_kontrolu_planla(ilk_gecikme_ms)

    def _sonraki_kontrolu_planla(self, gecikme_ms=None):
        if self._sonlandirildi:
            return
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            self._zamanlayiciyi_durdur()
            return

        if gecikme_ms is None:
            dakika = bildirim_araligini_duzenle(ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI))
            gecikme_ms = dakika * 60 * 1000

        self._zamanlayiciyi_durdur()
        self._zamanlayici = wx.CallLater(int(gecikme_ms), self._zamanlayici_tetiklendi)

    def _zamanlayici_tetiklendi(self):
        if self._sonlandirildi:
            return
        self._zamanlayici = None

        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        if self._kontrol_suruyor:
            self._sonraki_kontrolu_planla()
            return

        self._kontrol_kimligi += 1
        kontrol_kimligi = self._kontrol_kimligi
        self._aktif_kontrol_kimligi = kontrol_kimligi
        self._kontrol_suruyor = True
        arka_planda_calistir(self._arka_plan_kontrolu, kontrol_kimligi)

    def _arka_plan_kontrolu(self, kontrol_kimligi):
        sonuc = bildirim_gelen_kutusu_kontrol_et()
        wx.CallAfter(self._kontrol_bitti, kontrol_kimligi, sonuc)

    def _kontrol_bitti(self, kontrol_kimligi, sonuc):
        if self._sonlandirildi:
            return
        if kontrol_kimligi != self._aktif_kontrol_kimligi:
            return

        self._aktif_kontrol_kimligi = None
        self._kontrol_suruyor = False

        try:
            if sonuc:
                self._bildirim_ver(sonuc)
        except Exception as e:
            hata_kaydet("Yeni e-posta bildirimi verilemedi.", e)

        self._sonraki_kontrolu_planla()

    def _bildirim_ver(self, sonuc):
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        if ayarlar.get(BILDIRIM_SES_ALANI):
            arka_planda_calistir(bildirim_sesi_cal)

        if ayarlar.get(BILDIRIM_MESAJ_ALANI):
            mesaj = bildirim_mesaji_olustur(
                int(sonuc.get("sayi", 1) or 1),
                sonuc.get("son_eposta") or {},
                ayarlar,
            )
            bildirim_soyle(mesaj, 300)



class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "Engelsiz Mail"

    def __init__(self):
        super().__init__()
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        self.gelen_penceresi = None

        global BILDIRIM_YONETICISI
        BILDIRIM_YONETICISI = BildirimYoneticisi()

        self.main_item = self.tools_menu.Append(wx.ID_ANY, "&Engelsiz Mail")
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.ac_gelen, self.main_item)

    def terminate(self):
        try:
            global BILDIRIM_YONETICISI
            if BILDIRIM_YONETICISI:
                BILDIRIM_YONETICISI.durdur()
                BILDIRIM_YONETICISI = None

            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=self.main_item.GetId())
            try:
                self.tools_menu.Remove(self.main_item)
            except Exception:
                self.tools_menu.Remove(self.main_item.GetId())
            if pencere_kullanilabilir_mi(getattr(self, "gelen_penceresi", None)):
                self.gelen_penceresi.Close()
        except Exception as e:
            hata_kaydet("Menü öğesi kaldırılırken hata oluştu.", e)
        super().terminate()

    def ac_gelen(self, event):
        self.pencereyi_baslat(menuden_geldi=True)

    def script_gelen_ac(self, gesture):
        """Engelsiz Mail penceresini açar."""
        self.pencereyi_baslat(menuden_geldi=False)

    def _gelen_penceresi_kapandi(self, event):
        if event.GetEventObject() is self.gelen_penceresi:
            self.gelen_penceresi = None
        event.Skip()

    def pencereyi_one_getir(self, pencere):
        try:
            if hasattr(pencere, "one_getir_ve_odaklan"):
                return bool(pencere.one_getir_ve_odaklan())
            if pencere.IsIconized():
                pencere.Iconize(False)
            if not pencere.IsShown():
                pencere.Show(True)
            pencere.Raise()
            pencere.SetFocus()
            return True
        except Exception as e:
            hata_kaydet("Açık pencere öne getirilemedi.", e)
            return False

    def pencereyi_baslat(self, menuden_geldi=False):
        def ac():
            if pencere_kullanilabilir_mi(getattr(self, "gelen_penceresi", None)):
                getirildi = self.pencereyi_one_getir(self.gelen_penceresi)
                if getirildi:
                    bildirim_soyle("Engelsiz Mail penceresi öne getirildi.", 150)
                else:
                    ui.message("Engelsiz Mail penceresi zaten açık, ancak öne getirilemedi.")
                return

            pencere = GelenKutusuPenceresi(gui.mainFrame)
            self.gelen_penceresi = pencere
            pencere.Bind(wx.EVT_WINDOW_DESTROY, self._gelen_penceresi_kapandi)
            pencere.Show()
            pencere.Raise()

            wx.CallLater(
                900,
                pencere.acilis_klasor_bildirimi_ver
            )
        wx.CallAfter(ac)

    __gestures = {"kb:nvda+shift+m": "gelen_ac"}
