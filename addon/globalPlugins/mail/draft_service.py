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
    onceki_taslak_kimligi=None,
    onceki_taslak_klasoru=None,
    kimlik_dondur=False,
    html_icerik=None,
    ekli_resimler=None,
):
    """Taslağı Gmail Taslaklar klasörüne ekler; istenirse eski kaydı güvenle yeniler."""
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
        html_icerik=html_icerik,
        ekli_resimler=ekli_resimler,
    )
    ham_mesaj = mesaj.as_bytes(policy=SMTP)
    mesaj_kimligi = str(mesaj.get("Message-ID", "") or "").strip()
    adaylar = taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari)
    if onceki_taslak_kimligi:
        eski_klasor = str(onceki_taslak_klasoru or "").strip()
        if not eski_klasor or eski_klasor not in adaylar:
            raise MailHatasi(_("Eski taslağın klasörü doğrulanamadı; eski taslak korundu."))
        adaylar = [eski_klasor]

    with ImapBaglantisi(ayarlar) as imap:
        for aday_klasor in adaylar:
            try:
                tip, _veri = imap.append(aday_klasor, "(\\Draft)", None, ham_mesaj)
                if tip == "OK":
                    if not kimlik_dondur and not onceki_taslak_kimligi:
                        return True
                    try:
                        return _yeni_taslak_kimligini_al(
                            imap, mesaj_kimligi, aday_klasor, onceki_taslak_kimligi
                        )
                    except Exception as e:
                        # APPEND başarılı oldu; doğrulama sonrasında yeni klasöre
                        # tekrar eklemek aynı iletiyi çoğaltabilir. Otomatik
                        # kayıt bu sonucu belirsiz olarak ele alıp durmalıdır.
                        hata_kaydet("Gmail taslağı eklendi ancak sonucu doğrulanamadı.", e)
                        try:
                            hata = MailHatasi(
                                _("Taslak kaydının sonucu doğrulanamadı. Yeniden kaydetmeden önce Taslaklar klasörünü denetleyin."),
                                belirsiz_kayit=True,
                            )
                        except TypeError:
                            hata = MailHatasi(
                                _("Taslak kaydının sonucu doğrulanamadı. Yeniden kaydetmeden önce Taslaklar klasörünü denetleyin.")
                            )
                            hata.belirsiz_kayit = True
                        raise hata from e
                hata_kaydet(f"Taslak klasörü kabul etmedi: {aday_klasor}")
            except (OSError, ValueError, imaplib.IMAP4.error) as e:
                hata_kaydet(f"Taslak kaydetme denemesi başarısız: {aday_klasor}", e)
                # Yanıt alınamadıysa APPEND gerçekleşmiş olabilir. Başka klasöre
                # ikinci kez yazmak aynı taslağı çoğaltabilir.
                try:
                    hata = MailHatasi(
                        _("Taslak kaydının sonucu doğrulanamadı. Yeniden kaydetmeden önce Taslaklar klasörünü denetleyin."),
                        belirsiz_kayit=True,
                    )
                except TypeError:
                    hata = MailHatasi(
                        _("Taslak kaydının sonucu doğrulanamadı. Yeniden kaydetmeden önce Taslaklar klasörünü denetleyin.")
                    )
                    hata.belirsiz_kayit = True
                raise hata from e

    raise MailHatasi(_("Taslak, Gmail'in Taslaklar klasörüne kaydedilemedi."))


def _yeni_taslak_kimligini_al(imap, mesaj_kimligi, klasor, onceki_taslak_kimligi=None):
    """APPEND edilen iletinin Gmail UID ve ileti kimliğini doğrular; sonra eskisini kaldırır."""
    from .imap_client import (
        imap_ok_mu,
        imap_uid_search_sonucu_uidleri_al,
        imap_uidleri_kalici_sil,
        imap_uidvalidity_al,
        imap_x_gm_msgid_haritasi_al,
    )

    if not mesaj_kimligi:
        raise MailHatasi(_("Taslak Gmail'e eklendi ancak ileti kimliği doğrulanamadı; önceki taslak korundu."))
    tip, _secim = imap.select(klasor, readonly=False)
    imap_ok_mu(tip, _("Taslak eklendi ancak Taslaklar klasörü doğrulanamadı."))
    uidvalidity = imap_uidvalidity_al(imap)
    if not uidvalidity:
        raise MailHatasi(_("Taslak eklendi ancak klasör kimliği doğrulanamadı; önceki taslak korundu."))
    tip, arama = imap.uid("SEARCH", None, "HEADER", "Message-ID", mesaj_kimligi)
    imap_ok_mu(tip, _("Taslak eklendi ancak Gmail taslak kimliği doğrulanamadı; önceki taslak korundu."))
    uidler = imap_uid_search_sonucu_uidleri_al(arama)
    if len(uidler) != 1:
        raise MailHatasi(_("Taslak Gmail'e eklendi ancak benzersiz kimliği doğrulanamadı; önceki taslak korundu."))
    yeni_uid = str(uidler[0])
    yeni_gmail_id = imap_x_gm_msgid_haritasi_al(imap, [yeni_uid]).get(yeni_uid)
    if not yeni_gmail_id:
        raise MailHatasi(_("Taslak Gmail'e eklendi ancak Gmail ileti kimliği alınamadı; önceki taslak korundu."))

    eski_taslak_silindi = True
    if onceki_taslak_kimligi:
        eski_uid = str(onceki_taslak_kimligi.get("uid", "") or "")
        eski_uidvalidity = int(onceki_taslak_kimligi.get("uidvalidity") or 0)
        eski_gmail_id = str(onceki_taslak_kimligi.get("gmail_message_id", "") or "")
        try:
            if (not eski_uid.isdigit() or not eski_gmail_id or eski_uidvalidity != uidvalidity
                    or eski_uid == yeni_uid):
                raise MailHatasi(_("Önceki taslak kimliği değişti; silinmedi."))
            tip, onceki_var_mi = imap.uid("SEARCH", "UID", eski_uid)
            imap_ok_mu(tip, _("Önceki taslak aranamadı; silinmedi."))
            bulunan_uidler = imap_uid_search_sonucu_uidleri_al(onceki_var_mi)
            if eski_uid in bulunan_uidler:
                eski_gmail_idler = imap_x_gm_msgid_haritasi_al(imap, [eski_uid])
                if str(eski_gmail_idler.get(eski_uid)) != eski_gmail_id:
                    raise MailHatasi(_("Önceki taslağın Gmail kimliği değişti; silinmedi."))
                imap_uidleri_kalici_sil(imap, eski_uid, _("Önceki taslak silinemedi."))
                tip, kalan = imap.uid("SEARCH", "UID", eski_uid)
                imap_ok_mu(tip, _("Önceki taslağın silinme sonucu doğrulanamadı."))
                if eski_uid in imap_uid_search_sonucu_uidleri_al(kalan):
                    raise MailHatasi(_("Önceki taslak hâlâ görünüyor."))
        except Exception as e:
            hata_kaydet("Yeni Gmail taslağı kaydedildi ancak önceki taslak kaldı.", e)
            eski_taslak_silindi = False

    return {
        "kimlik": {"uid": yeni_uid, "uidvalidity": uidvalidity, "gmail_message_id": str(yeni_gmail_id)},
        "klasor": klasor,
        "eski_taslak_silindi": eski_taslak_silindi,
    }
