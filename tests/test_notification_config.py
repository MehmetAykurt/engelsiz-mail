# -*- coding: utf-8 -*-
"""Bildirim kanalı ayarlarının okunma ve kaydedilme testleri."""

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


def config_yukle(ham_ayarlar):
    paket = _modul("mail")
    paket.__path__ = [str(MAIL_KOKU)]
    wx = _modul(
        "wx",
        FONTSTYLE_NORMAL=0,
        FONTSTYLE_ITALIC=1,
        FONTWEIGHT_NORMAL=0,
        FONTWEIGHT_BOLD=1,
    )
    sahteler = {
        "wx": wx,
        "mail": paket,
        "mail.errors": _modul("mail.errors", MailHatasi=RuntimeError),
        "mail.logger": _modul("mail.logger", hata_kaydet=Mock()),
        "mail.paths": _modul("mail.paths", AYARLAR_DOSYASI="ayarlar.json"),
        "mail.security": _modul(
            "mail.security",
            uygulama_sifresini_sifrele=Mock(return_value="sifreli"),
            uygulama_sifresini_coz=Mock(return_value="cozulmus"),
        ),
        "mail.storage": _modul(
            "mail.storage",
            guvenli_json_oku=Mock(return_value=dict(ham_ayarlar)),
            guvenli_json_guncelle=Mock(),
        ),
        "mail.validators": _modul(
            "mail.validators", bildirim_ses_dosyasi_duzenle=lambda yol: str(yol or "").strip()
        ),
    }
    eskiler = {ad: sys.modules.get(ad) for ad in sahteler}
    sys.modules.update(sahteler)
    try:
        sys.modules.pop("mail.config", None)
        spec = importlib.util.spec_from_file_location("mail.config", MAIL_KOKU / "config.py")
        modul = importlib.util.module_from_spec(spec)
        sys.modules["mail.config"] = modul
        spec.loader.exec_module(modul)
    finally:
        for ad, eski in eskiler.items():
            if eski is None:
                sys.modules.pop(ad, None)
            else:
                sys.modules[ad] = eski
    return modul


class BildirimConfigTestleri(unittest.TestCase):
    def test_etkin_bildirim_iki_kanal_da_kapaliysa_mesaj_guvenli_varsayilandir(self):
        config = config_yukle(
            {"bildirim_etkin": True, "bildirim_ses": False, "bildirim_mesaj": False}
        )
        sonuc = config.bildirim_ayarlari_yukle()
        self.assertFalse(sonuc[config.BILDIRIM_SES_ALANI])
        self.assertTrue(sonuc[config.BILDIRIM_MESAJ_ALANI])

    def test_mesajla_bildir_ayri_alan_olarak_kaydedilir(self):
        config = config_yukle({})
        kaydedilen = {}

        def guncelle(guncelleyici):
            guncelleyici(kaydedilen, {})
            return True

        config._ayarlari_guncelle = guncelle
        sonuc = config.bildirim_ayarlari_kaydet(
            True, True, "sistem", "", False, True, False
        )
        self.assertTrue(sonuc)
        self.assertFalse(kaydedilen[config.BILDIRIM_MESAJ_ALANI])
        self.assertTrue(kaydedilen[config.BILDIRIM_GONDEREN_ALANI])


if __name__ == "__main__":
    unittest.main()
