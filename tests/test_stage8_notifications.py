# -*- coding: utf-8 -*-
"""Sekizinci aşama: bildirim, UID tabanı ve IMAP IDLE davranışları."""

from __future__ import annotations

import types
import unittest
from unittest.mock import ANY, Mock

from test_notifications import notifications_yukle


class _ImapBaglam:
    def __init__(self, imap):
        self.imap = imap

    def __enter__(self):
        return self.imap

    def __exit__(self, *_args):
        return False


class _BildirimImap:
    def __init__(self, uid_yanitlari):
        self.uid_yanitlari = list(uid_yanitlari)
        self.cagrilar = []

    def select(self, mailbox, readonly=True):
        self.cagrilar.append(("select", mailbox, readonly))
        return "OK", [b"3"]

    def uid(self, command, *args):
        self.cagrilar.append(("uid", command, *args))
        if not self.uid_yanitlari:
            raise AssertionError(f"Beklenmeyen UID çağrısı: {command} {args}")
        return self.uid_yanitlari.pop(0)


class BildirimMetniVeZamanlayiciTestleri(unittest.TestCase):
    def test_ilk_acilista_on_bes_saniyelik_gecikme_kullanilir(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        modul.BildirimYoneticisi()
        self.assertEqual(15000, wx.zamanlayicilar[-1].gecikme)

    def test_bildirim_kapaliysa_idle_zamanlayicisi_yine_kurulur(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle({"bildirim_etkin": False})
        modul.BildirimYoneticisi()
        self.assertEqual(15000, wx.zamanlayicilar[-1].gecikme)

    def test_bekleyen_konusma_durdurulunca_zamanlayici_iptal_edilir(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        modul.bildirim_soyle("Yeni e-postanız var.", 500)
        zamanlayici = wx.zamanlayicilar[-1]
        self.assertIs(zamanlayici, modul.BILDIRIM_SOYLE_TIMER)
        self.assertTrue(modul.bekleyen_bildirim_konusmasini_durdur())
        self.assertTrue(zamanlayici.durduruldu)
        self.assertIsNone(modul.BILDIRIM_SOYLE_TIMER)

    def test_yonetici_durdurulunca_bekleyen_konusma_da_iptal_edilir(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        modul.bildirim_soyle("Yeni e-postanız var.", 500)
        zamanlayici = wx.zamanlayicilar[-1]
        yonetici.durdur()
        self.assertTrue(zamanlayici.durduruldu)
        self.assertIsNone(modul.BILDIRIM_SOYLE_TIMER)

    def test_ayar_yenileme_bekleyen_eski_konusmayi_iptal_eder(self):
        modul, wx, _ayarlar, _arka_plan = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        modul.bildirim_soyle("Eski bildirim", 500)
        zamanlayici = wx.zamanlayicilar[-1]
        yonetici.ayarlari_yenile()
        self.assertTrue(zamanlayici.durduruldu)

    def test_turkce_gonderen_ve_konu_bildirim_metninde_korunur(self):
        modul, *_ = notifications_yukle()
        metin = modul.bildirim_mesaji_olustur(
            2,
            {"kimden": "Gülşüm@example.com", "konu": "İçimdeki Fısıltı"},
            {"bildirim_gonderen": True, "bildirim_konu": True},
        )
        self.assertEqual(
            "2 yeni e-postanız var. Gönderen: Gülşüm@example.com. Konu: İçimdeki Fısıltı.",
            metin,
        )

    def test_eski_dinleyiciden_gelen_sonuc_yok_sayilir(self):
        modul, *_ = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        yonetici._aktif_dinleme_kimligi = 4
        yonetici._bildirim_ver = Mock()
        callback = Mock()
        yonetici.yeni_eposta_callback_ayarla(callback)
        yonetici._yeni_ileti_alindi(3, {"sayi": 1})
        yonetici._bildirim_ver.assert_not_called()
        callback.assert_not_called()

    def test_aktif_dinleyici_bildirimi_ve_pencere_callbackini_cagirir(self):
        modul, *_ = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        yonetici._aktif_dinleme_kimligi = 4
        yonetici._bildirim_ver = Mock()
        callback = Mock()
        sonuc = {"sayi": 1}
        yonetici.yeni_eposta_callback_ayarla(callback)
        yonetici._yeni_ileti_alindi(4, sonuc)
        yonetici._bildirim_ver.assert_called_once_with(sonuc)
        callback.assert_called_once_with(sonuc)

    def test_gecersiz_callback_temizlenir(self):
        modul, *_ = notifications_yukle()
        yonetici = modul.BildirimYoneticisi()
        yonetici.yeni_eposta_callback_ayarla("callback değil")
        self.assertIsNone(yonetici._yeni_eposta_callback)


class BildirimUidTabaniTestleri(unittest.TestCase):
    @staticmethod
    def _hazirla(uid_yanitlari, *, onceki_uid=10, baslatildi=True, kayitli_uv=1, gecerli_uv=1):
        modul, _wx, _ayarlar, _arka_plan = notifications_yukle(
            {"bildirim_ses": False, "bildirim_mesaj": True}
        )
        imap = _BildirimImap(uid_yanitlari)
        modul.ImapBaglantisi = lambda _ayar: _ImapBaglam(imap)
        modul.imap_uidvalidity_al = Mock(return_value=gecerli_uv)
        modul.uidleri_ayristir = lambda veri: [
            parca.decode() if isinstance(parca, bytes) else str(parca)
            for blok in (veri or [])
            for parca in (blok.split() if isinstance(blok, (bytes, str)) else [])
        ]
        modul.bildirim_son_uid_oku = Mock(return_value=onceki_uid)
        modul.bildirim_baslatildi_mi = Mock(return_value=baslatildi)
        modul.bildirim_uidvalidity_oku = Mock(return_value=kayitli_uv)
        modul.bildirim_son_uid_kaydet = Mock()
        modul.bildirim_tabanini_sifirla = Mock()
        modul.klasor_basliklarini_senkronize_et = Mock(return_value={})
        modul.yeni_ileti_govdesini_ek_indirmeden_kaydet = Mock(return_value=True)
        return modul, imap

    def test_ilk_kurulum_mevcut_iletileri_yeni_saymadan_taban_kurar(self):
        modul, _imap = self._hazirla(
            [("OK", [b"2 5 9"])], onceki_uid=0, baslatildi=False
        )
        self.assertIsNone(modul.bildirim_gelen_kutusu_kontrol_et())
        modul.bildirim_son_uid_kaydet.assert_called_once_with(
            "a@example.com", 9, baslatildi=True, uidvalidity=1
        )

    def test_yeni_okunmamis_iletiler_sayilir_esitlenir_ve_govdeleri_onbellege_alinir(self):
        modul, _imap = self._hazirla([
            ("OK", [b"11 12 13"]),
            ("OK", [b"11 13"]),
            ("OK", [b"1 2 11 12 13"]),
        ])
        sonuc = modul.bildirim_gelen_kutusu_kontrol_et()
        self.assertEqual(2, sonuc["sayi"])
        modul.bildirim_son_uid_kaydet.assert_called_once_with(
            "a@example.com", 13, uidvalidity=1
        )
        self.assertEqual(3, modul.yeni_ileti_govdesini_ek_indirmeden_kaydet.call_count)
        modul.klasor_basliklarini_senkronize_et.assert_called_once()
        self.assertEqual(
            ["1", "2", "11", "12", "13"],
            modul.klasor_basliklarini_senkronize_et.call_args.kwargs["sunucu_uidleri"],
        )

    def test_bildirim_kapali_olsa_da_yeni_ileti_verisi_esitlenir(self):
        modul, _imap = self._hazirla([
            ("OK", [b"11"]),
            ("OK", [b"11"]),
            ("OK", [b"1 11"]),
        ])
        modul.bildirim_ayarlari_yukle = Mock(return_value={
            "bildirim_etkin": False,
            "bildirim_ses": False,
            "bildirim_mesaj": False,
        })

        modul.bildirim_gelen_kutusu_kontrol_et()

        modul.klasor_basliklarini_senkronize_et.assert_called_once()
        modul.yeni_ileti_govdesini_ek_indirmeden_kaydet.assert_called_once_with(
            ANY, "a@example.com", 11
        )

    def test_govde_kaydi_basarisiz_uid_tamamlanmis_sayilmaz(self):
        modul, _imap = self._hazirla([
            ("OK", [b"11"]),
            ("OK", [b"11"]),
            ("OK", [b"1 11"]),
        ])
        modul.yeni_ileti_govdesini_ek_indirmeden_kaydet.side_effect = RuntimeError(
            "Geçici veritabanı hatası"
        )

        modul.bildirim_gelen_kutusu_kontrol_et()

        modul.bildirim_son_uid_kaydet.assert_not_called()

    def test_yeni_ama_okunmus_ileti_tabanı_ilerletir_bildirim_vermez(self):
        modul, _imap = self._hazirla([
            ("OK", [b"11"]),
            ("OK", [b""]),
            ("OK", [b"1 11"]),
        ])
        self.assertIsNone(modul.bildirim_gelen_kutusu_kontrol_et())
        modul.bildirim_son_uid_kaydet.assert_called_once_with(
            "a@example.com", 11, uidvalidity=1
        )

    def test_uidvalidity_degisiminde_taban_sifirlanir_ve_mevcutlar_yeni_sayilmaz(self):
        modul, _imap = self._hazirla(
            [("OK", [b"20 21"])],
            onceki_uid=10,
            baslatildi=True,
            kayitli_uv=1,
            gecerli_uv=2,
        )
        self.assertIsNone(modul.bildirim_gelen_kutusu_kontrol_et())
        modul.bildirim_tabanini_sifirla.assert_called_once_with("a@example.com", 2)
        modul.bildirim_son_uid_kaydet.assert_called_once_with(
            "a@example.com", 21, baslatildi=True, uidvalidity=2
        )

    def test_bildirim_kapaliysa_veri_kontrolu_yine_baslar(self):
        modul, _wx, _ayarlar, _arka_plan = notifications_yukle({"bildirim_etkin": False})
        modul.ImapBaglantisi = Mock()
        self.assertIsNone(modul.bildirim_gelen_kutusu_kontrol_et())
        modul.ImapBaglantisi.assert_called_once()


if __name__ == "__main__":
    unittest.main()
