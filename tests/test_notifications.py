# -*- coding: utf-8 -*-
"""IDLE bildirim yöneticisinin yaşam döngüsü ve bildirim kanalı testleri."""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock


MAIL_KOKU = pathlib.Path(__file__).resolve().parents[1] / "globalPlugins" / "mail"


def _modul(ad, **uyeler):
    sonuc = types.ModuleType(ad)
    for uye_adi, deger in uyeler.items():
        setattr(sonuc, uye_adi, deger)
    return sonuc


class SahteZamanlayici:
    def __init__(self, gecikme, callback, args):
        self.gecikme = gecikme
        self.callback = callback
        self.args = args
        self.durduruldu = False

    def Stop(self):
        self.durduruldu = True


class SahteWx(types.ModuleType):
    def __init__(self):
        super().__init__("wx")
        self.zamanlayicilar = []

    def CallLater(self, gecikme, callback, *args):
        sonuc = SahteZamanlayici(gecikme, callback, args)
        self.zamanlayicilar.append(sonuc)
        return sonuc

    @staticmethod
    def CallAfter(callback, *args):
        return callback(*args)

    @staticmethod
    def Bell():
        return None


def notifications_yukle(bildirim_ayarlari=None):
    wx = SahteWx()
    paket = _modul("mail")
    paket.__path__ = [str(MAIL_KOKU)]
    ayarlar = {
        "bildirim_etkin": True,
        "bildirim_ses": True,
        "bildirim_mesaj": True,
        "bildirim_ses_turu": "sistem",
        "bildirim_ses_dosyasi": "",
        "bildirim_gonderen": False,
        "bildirim_konu": False,
    }
    if bildirim_ayarlari:
        ayarlar.update(bildirim_ayarlari)
    ayar_yukle = Mock(side_effect=lambda: dict(ayarlar))
    arka_plan = Mock()

    sabitler = {
        "BILDIRIM_ETKIN_ALANI": "bildirim_etkin",
        "BILDIRIM_GONDEREN_ALANI": "bildirim_gonderen",
        "BILDIRIM_KONU_ALANI": "bildirim_konu",
        "BILDIRIM_MESAJ_ALANI": "bildirim_mesaj",
        "BILDIRIM_SES_ALANI": "bildirim_ses",
        "BILDIRIM_SES_DOSYASI_ALANI": "bildirim_ses_dosyasi",
        "BILDIRIM_SES_TURU_ALANI": "bildirim_ses_turu",
        "BILDIRIM_SES_TURU_DOSYA": "dosya",
        "BILDIRIM_SES_TURU_SISTEM": "sistem",
    }
    config = _modul(
        "mail.config",
        **sabitler,
        ayarlari_yukle=Mock(return_value={"eposta": "a@example.com", "sifre": "sifre"}),
        bildirim_ayarlari_yukle=ayar_yukle,
        bildirim_baslatildi_mi=Mock(return_value=True),
        bildirim_son_uid_kaydet=Mock(),
        bildirim_son_uid_oku=Mock(return_value=0),
        bildirim_tabanini_sifirla=Mock(),
        bildirim_uidvalidity_oku=Mock(return_value=1),
    )
    sahteler = {
        "wx": wx,
        "mail": paket,
        "mail.config": config,
        "mail.imap_client": _modul(
            "mail.imap_client",
            ImapBaglantisi=Mock(),
            imap_uidvalidity_al=Mock(return_value=1),
            uidleri_ayristir=Mock(return_value=[]),
        ),
        "mail.logger": _modul("mail.logger", hata_kaydet=Mock()),
        "mail.header_sync": _modul("mail.header_sync", klasor_basliklarini_senkronize_et=Mock()),
        "mail.body_sync": _modul("mail.body_sync", yeni_ileti_govdesini_ek_indirmeden_kaydet=Mock()),
        "mail.message_center": _modul("mail.message_center", mesaj_soyle_ve_sonra_calistir=Mock()),
        "mail.message_parser": _modul(
            "mail.message_parser", ham_mesaj_verisi_al=Mock(), gonderen_gosterimini_al=Mock()
        ),
        "mail.text_utils": _modul(
            "mail.text_utils", guvenli_coz=lambda deger: str(deger), konu_gosterimini_duzenle=lambda deger: str(deger)
        ),
        "mail.ui_helpers": _modul("mail.ui_helpers", arka_planda_calistir=arka_plan),
    }
    eskiler = {ad: sys.modules.get(ad) for ad in sahteler}
    sys.modules.update(sahteler)
    try:
        sys.modules.pop("mail.notifications", None)
        spec = importlib.util.spec_from_file_location(
            "mail.notifications", MAIL_KOKU / "notifications.py"
        )
        modul = importlib.util.module_from_spec(spec)
        sys.modules["mail.notifications"] = modul
        spec.loader.exec_module(modul)
    finally:
        for ad, eski in eskiler.items():
            if eski is None:
                sys.modules.pop(ad, None)
            else:
                sys.modules[ad] = eski
    return modul, wx, ayarlar, arka_plan


class BildirimYoneticisiTestleri(unittest.TestCase):
    def test_ayar_yenileme_eski_dinleyiciyi_hemen_gecersiz_kilar(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        eski_baglanti = Mock()
        yonetici._aktif_dinleme_kimligi = 7
        yonetici._idle_imap = eski_baglanti

        yonetici.ayarlari_yenile()

        self.assertIsNone(yonetici._aktif_dinleme_kimligi)
        self.assertIsNone(yonetici._idle_imap)
        eski_baglanti.shutdown.assert_called_once_with()
        self.assertEqual(2000, wx.zamanlayicilar[-1].gecikme)

    def test_eski_is_parcacigi_yeni_dinleyiciyi_silemez(self):
        modul, _wx, _ayarlar, arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()

        yonetici._dinleme_baslat()
        eski_kimlik = yonetici._aktif_dinleme_kimligi
        yonetici.ayarlari_yenile()
        yonetici._dinleme_baslat()
        yeni_kimlik = yonetici._aktif_dinleme_kimligi
        yeni_baglanti = Mock()
        yonetici._idle_imap = yeni_baglanti

        yonetici._idle_baglantisini_temizle(eski_kimlik, Mock())
        yonetici._dinleme_bitti(eski_kimlik, False)

        self.assertNotEqual(eski_kimlik, yeni_kimlik)
        self.assertEqual(yeni_kimlik, yonetici._aktif_dinleme_kimligi)
        self.assertIs(yeni_baglanti, yonetici._idle_imap)
        self.assertEqual(2, arka_plan.call_count)

    def test_basarisiz_aktif_dinleyici_bir_dakika_sonra_yeniden_baslar(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        yonetici._aktif_dinleme_kimligi = 3

        yonetici._dinleme_bitti(3, False)

        self.assertIsNone(yonetici._aktif_dinleme_kimligi)
        self.assertEqual(60000, wx.zamanlayicilar[-1].gecikme)

        yonetici._aktif_dinleme_kimligi = 4
        yonetici._dinleme_bitti(4, False)
        self.assertEqual(120000, wx.zamanlayicilar[-1].gecikme)

        yonetici._aktif_dinleme_kimligi = 5
        yonetici._dinleme_bitti(5, False)
        yonetici._aktif_dinleme_kimligi = 6
        yonetici._dinleme_bitti(6, False)
        self.assertEqual(modul.IDLE_AZAMI_YENIDEN_BAGLANMA_MS, wx.zamanlayicilar[-1].gecikme)

        yonetici._aktif_dinleme_kimligi = 7
        yonetici._dinleme_bitti(7, True)
        self.assertEqual(2000, wx.zamanlayicilar[-1].gecikme)
        self.assertEqual(0, yonetici._ardisik_idle_hatasi)

    def test_yalniz_ses_seciliyken_nvda_mesaji_verilmez(self):
        modul, _wx, _ayarlar, arka_plan = notifications_yukle(
            {"bildirim_ses": True, "bildirim_mesaj": False}
        )
        modul.bildirim_soyle = Mock()
        yonetici = modul.BildirimYoneticisi()

        yonetici._bildirim_ver({"sayi": 1, "son_eposta": {}})

        arka_plan.assert_called_with(modul.bildirim_sesi_cal)
        modul.bildirim_soyle.assert_not_called()

    def test_yalniz_mesaj_seciliyken_ses_calmaz(self):
        modul, _wx, _ayarlar, arka_plan = notifications_yukle(
            {"bildirim_ses": False, "bildirim_mesaj": True}
        )
        modul.bildirim_soyle = Mock()
        yonetici = modul.BildirimYoneticisi()

        yonetici._bildirim_ver({"sayi": 2, "son_eposta": {}})

        arka_plan.assert_not_called()
        modul.bildirim_soyle.assert_called_once()

    def test_durdur_aktif_baglantiyi_kapatir_ve_yeniden_baslatmaz(self):
        modul, _wx, _ayarlar, _arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        baglanti = Mock()
        yonetici._aktif_dinleme_kimligi = 4
        yonetici._idle_imap = baglanti

        yonetici.durdur()
        yonetici._dinleme_bitti(4, False)

        self.assertTrue(yonetici._sonlandirildi)
        self.assertIsNone(yonetici._aktif_dinleme_kimligi)
        baglanti.shutdown.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
