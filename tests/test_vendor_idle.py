# -*- coding: utf-8 -*-
"""Paketlenmiş IMAP IDLE bağlamının yenileme ve olay davranışları."""

import importlib.util
import pathlib
import unittest
from unittest.mock import Mock, patch


IMAPLIB_YOLU = (
    pathlib.Path(__file__).resolve().parents[1]
    / "globalPlugins"
    / "mail"
    / "vendor"
    / "imaplib.py"
)


def imaplib_yukle():
    spec = importlib.util.spec_from_file_location("engelsiz_mail_test_imaplib", IMAPLIB_YOLU)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class SahteImap:
    class error(Exception):
        pass

    class abort(Exception):
        pass

    def __init__(self, cevaplar):
        self.capabilities = ("IMAP4REV1", "IDLE")
        self.sock = object()
        self.tagged_commands = {}
        self._cevaplar = iter(cevaplar)
        self._command = Mock(return_value="A001")
        self.send = Mock()
        self._command_complete = Mock(return_value=("OK", [b"IDLE completed"]))

    def _get_response(self):
        return next(self._cevaplar)


class VendorIdleTestleri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.imaplib = imaplib_yukle()

    def test_sure_29_dakikayla_sinirlanir_ve_done_gonderilir(self):
        imap = SahteImap([None])
        with patch.object(self.imaplib.select, "select", return_value=([], [], [])):
            with self.imaplib.Idler(imap, duration=999999) as idler:
                self.assertEqual(29 * 60, idler.duration)
                self.assertEqual("RENEW", idler.wait())

        imap.send.assert_called_once_with(b"DONE" + self.imaplib.CRLF)
        imap._command_complete.assert_called_once_with("IDLE", "A001")

    def test_exists_yaniti_yeni_ileti_olayi_uretir(self):
        imap = SahteImap([None, b"* 2 EXISTS"])
        with patch.object(self.imaplib.select, "select", return_value=([imap.sock], [], [])):
            with self.imaplib.Idler(imap) as idler:
                self.assertEqual("EXISTS", idler.wait())

    def test_soket_kapanmasi_none_dondurur(self):
        imap = SahteImap([None])
        with patch.object(self.imaplib.select, "select", side_effect=OSError("kapandı")):
            with self.imaplib.Idler(imap) as idler:
                self.assertIsNone(idler.wait())

    def test_idle_destegi_olmayan_sunucu_reddedilir(self):
        imap = SahteImap([None])
        imap.capabilities = ("IMAP4REV1",)
        with self.assertRaises(SahteImap.error):
            self.imaplib.Idler(imap)


if __name__ == "__main__":
    unittest.main()
