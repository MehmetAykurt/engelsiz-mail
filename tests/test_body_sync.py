# -*- coding: utf-8 -*-
"""Gövde eşitlemesinin depolama sınırında güvenli biçimde durduğunu sınar."""

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


class GovdeSenkronizasyonTestleri(unittest.TestCase):
    def test_depolama_sinirinda_tek_uyariyla_durur(self):
        class MailHatasi(Exception):
            pass

        class OnbellekSiniriHatasi(MailHatasi):
            pass

        uyari = Mock()
        paket = _modul("mail")
        paket.__path__ = [str(MAIL_KOKU)]
        sahteler = {
            "mail": paket,
            "mail.attachments": _modul("mail.attachments", mesaj_metni_ve_ekleri_cikar=Mock()),
            "mail.errors": _modul("mail.errors", MailHatasi=MailHatasi),
            "mail.imap_client": _modul(
                "mail.imap_client",
                imap_toplu_uid_fetch=Mock(),
                uid_listesini_parcala=lambda uidler, boyut: [uidler[i:i + boyut] for i in range(0, len(uidler), boyut)],
            ),
            "mail.logger": _modul("mail.logger", hata_kaydet=Mock(), uyari_kaydet=uyari),
            "mail.mail_store": _modul(
                "mail.mail_store",
                govdesi_eksik_uidleri_al=lambda _eposta, _klasor, uidler: list(uidler),
                mesaj_govdesini_kaydet=Mock(),
            ),
            "mail.message_parser": _modul("mail.message_parser", ham_mesaj_verisi_al=Mock()),
            "mail.cache_limits": _modul(
                "mail.cache_limits",
                OnbellekSiniriHatasi=OnbellekSiniriHatasi,
                onbellek_kotasi_denetle=Mock(),
            ),
        }
        eskiler = {ad: sys.modules.get(ad) for ad in sahteler}
        sys.modules.update(sahteler)
        try:
            sys.modules.pop("mail.body_sync", None)
            spec = importlib.util.spec_from_file_location(
                "mail.body_sync", MAIL_KOKU / "body_sync.py"
            )
            modul = importlib.util.module_from_spec(spec)
            sys.modules["mail.body_sync"] = modul
            spec.loader.exec_module(modul)
        finally:
            for ad, eski in eskiler.items():
                if eski is None:
                    sys.modules.pop(ad, None)
                else:
                    sys.modules[ad] = eski

        indir = Mock(side_effect=OnbellekSiniriHatasi("sinir"))
        modul._govdeyi_indir_ve_kaydet = indir
        sonuc = modul.klasor_govdelerini_senkronize_et(
            object(), "kullanici@example.com", "INBOX", ["3", "2", "1"]
        )

        self.assertTrue(sonuc["sinira_ulasti"])
        self.assertEqual(1, indir.call_count)
        self.assertEqual(1, uyari.call_count)


if __name__ == "__main__":
    unittest.main()
