# -*- coding: utf-8 -*-
"""Arayüzden bağımsız Gmail taslak kaydetme hizmeti."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


from email.policy import SMTP

from .errors import MailHatasi
from .folders import taslak_klasor_adaylarini_temizle
from .imap_client import ImapBaglantisi
from .logger import hata_kaydet
from .smtp_client import eposta_mesaji_olustur
from .vendor import imaplib


def taslagi_sunucuya_kaydet(
    kime,
    bilgi,
    gizli,
    konu,
    icerik,
    ek_kayitlari,
    yanit_basliklari=None,
    taslak_klasor_adaylari=None,
    ayarlar=None,
):
    """Taslağı ilk kullanılabilir Gmail Taslaklar klasörüne APPEND eder."""
    if ayarlar is None:
        from .config import ayarlari_yukle
        ayarlar = ayarlari_yukle()
    ayarlar = dict(ayarlar)
    if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
        raise MailHatasi(_("Hesap bilgileri eksik."))

    mesaj = eposta_mesaji_olustur(
        ayarlar["eposta"],
        kime,
        konu,
        icerik,
        ek_kayitlari,
        ek_basliklar=yanit_basliklari,
        taslak=True,
        gorunen_ad=ayarlar.get("gorunen_ad", ""),
        bilgi_basligi=bilgi,
        gizli_basligi=gizli,
    )
    ham_mesaj = mesaj.as_bytes(policy=SMTP)

    with ImapBaglantisi(ayarlar) as imap:
        for aday_klasor in taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari):
            try:
                tip, _veri = imap.append(aday_klasor, "(\\Draft)", None, ham_mesaj)
                if tip == "OK":
                    return True
                hata_kaydet(f"Taslak klasörü kabul etmedi: {aday_klasor}")
            except (OSError, ValueError, imaplib.IMAP4.error) as e:
                hata_kaydet(f"Taslak kaydetme denemesi başarısız: {aday_klasor}", e)

    raise MailHatasi(_("Taslak, Gmail'in Taslaklar klasörüne kaydedilemedi."))
