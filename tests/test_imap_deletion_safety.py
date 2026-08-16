# -*- coding: utf-8 -*-
"""IMAP taşıma ve kalıcı silme yardımcılarının güvenlik testleri."""

from __future__ import annotations

import unittest
from unittest import mock

from support import FakeIMAP, load_mail_module, module


class MailHatasi(Exception):
    pass


LOGGER = module(
    "mail.logger",
    hata_kaydet=lambda *args, **kwargs: None,
    uyari_kaydet=lambda *args, **kwargs: None,
)
ERRORS = module("mail.errors", MailHatasi=MailHatasi)


class ImapSilmeGuvenligiTestleri(unittest.TestCase):
    def load(self):
        return load_mail_module(
            "imap_client",
            stubs={"mail.logger": LOGGER, "mail.errors": ERRORS},
        )

    def test_uid_kumesi_sirayi_korur_tekrarlari_atar(self):
        with self.load() as imap_client:
            self.assertEqual("4,2,9", imap_client.uid_kumesi_hazirla([4, "2", 4, 9]))

    def test_uid_kumesi_gecersiz_degerde_islemi_durdurur(self):
        with self.load() as imap_client:
            for value in ([1, "x"], ["1:4"], ["-1"], []):
                with self.subTest(value=value):
                    with self.assertRaises(MailHatasi):
                        imap_client.uid_kumesi_hazirla(value)

    def test_gmail_etiket_store_yalniz_izinli_islemleri_kullanir(self):
        imap = FakeIMAP()
        with self.load() as imap_client:
            self.assertTrue(
                imap_client.imap_gmail_etiket_store(
                    imap, "1,2", "+", "\\Trash", "taşınamadı"
                )
            )
            with self.assertRaises(MailHatasi):
                imap_client.imap_gmail_etiket_store(
                    imap, "1", "DELETE", "\\Trash", "hata"
                )
        self.assertIn(("uid", ("STORE", "1,2", "+X-GM-LABELS", "(\\Trash)")), imap.calls)

    def test_kalici_silme_genel_expunge_yerine_uid_expunge_kullanir(self):
        imap = FakeIMAP()
        imap.uid_responses["STORE"] = ("OK", [b""])
        imap.uid_responses["EXPUNGE"] = ("OK", [b"1 2"])
        with self.load() as imap_client:
            self.assertTrue(imap_client.imap_uidleri_kalici_sil(imap, "1,2"))
        self.assertEqual(
            [
                ("uid", ("STORE", "1,2", "+FLAGS.SILENT", "(\\Deleted)")),
                ("uid", ("EXPUNGE", "1,2")),
            ],
            imap.calls,
        )

    def test_kalici_silme_expunge_hatasinda_deleted_bayragini_geri_alir(self):
        imap = FakeIMAP()
        store_calls = {"count": 0}

        def store(*args):
            store_calls["count"] += 1
            return ("OK", [b""])

        imap.uid_responses["STORE"] = store
        imap.uid_responses["EXPUNGE"] = ("NO", [b"failed"])
        with self.load() as imap_client:
            with self.assertRaisesRegex(MailHatasi, "kalıcı"):
                imap_client.imap_uidleri_kalici_sil(imap, "7")
        self.assertEqual(2, store_calls["count"])
        self.assertIn(
            ("uid", ("STORE", "7", "-FLAGS.SILENT", "(\\Deleted)")),
            imap.calls,
        )

    def test_kaynak_klasorden_cikarma_da_uid_expunge_ile_sinirlanir(self):
        imap = FakeIMAP()
        imap.uid_responses["STORE"] = ("OK", [b""])
        imap.uid_responses["EXPUNGE"] = ("OK", [b""])
        with self.load() as imap_client:
            self.assertTrue(imap_client.imap_uidleri_kaynak_klasorden_cikar(imap, "8,9"))
        self.assertEqual(("uid", ("EXPUNGE", "8,9")), imap.calls[-1])

    def test_x_gm_msgid_haritasi_tum_uidler_dogrulanmadan_donmez(self):
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = (
            "OK",
            [(b"1 (UID 10 X-GM-MSGID 1010)", b"")],
        )
        with self.load() as imap_client:
            with self.assertRaisesRegex(MailHatasi, "doğrulanamadı"):
                imap_client.imap_x_gm_msgid_haritasi_al(imap, [10, 11])

    def test_x_gm_msgid_haritasi_parcali_fetch_sonuclarini_birlestirir(self):
        imap = FakeIMAP()

        def fetch(uid_set, _query):
            rows = []
            for uid in str(uid_set).split(","):
                rows.append((f"1 (UID {uid} X-GM-MSGID 9{uid})".encode(), b""))
            return ("OK", rows)

        imap.uid_responses["FETCH"] = fetch
        with self.load() as imap_client:
            mapping = imap_client.imap_x_gm_msgid_haritasi_al(imap, range(1, 56))
        self.assertEqual("91", mapping["1"])
        self.assertEqual("955", mapping["55"])
        fetch_calls = [call for call in imap.calls if call[0] == "uid" and call[1][0] == "FETCH"]
        self.assertEqual(2, len(fetch_calls))

    def test_copte_uid_cozumu_butun_gmail_idlerini_zorunlu_tutar(self):
        imap = FakeIMAP()

        def search(_criterion, msgid):
            return ("OK", [b"77"] if str(msgid) == "100" else [b""])

        imap.uid_responses["SEARCH"] = search
        with self.load() as imap_client:
            with self.assertRaisesRegex(MailHatasi, "doğrulanamadı"):
                imap_client.imap_gmail_msgidleri_copte_uidlere_cevir(
                    imap, ["100", "200"], '"[Gmail]/Trash"'
                )

    def test_kalici_silme_cop_gorunumu_gecikirse_bir_kez_yeniden_dener(self):
        imap = FakeIMAP()
        attempts = {"count": 0}

        def search(_criterion, _msgid):
            attempts["count"] += 1
            return ("OK", [b""] if attempts["count"] == 1 else [b"77"])

        imap.uid_responses["SEARCH"] = search
        imap.uid_responses["STORE"] = ("OK", [b""])
        imap.uid_responses["EXPUNGE"] = ("OK", [b""])
        with self.load() as imap_client, mock.patch.object(imap_client.time, "sleep") as sleep:
            self.assertTrue(
                imap_client.imap_gmail_msgidleri_kalici_sil(
                    imap, ["100"], '"[Gmail]/Trash"'
                )
            )
        sleep.assert_called_once_with(0.5)
        self.assertEqual(2, attempts["count"])

    def test_uidvalidity_farkli_yanit_bicimlerinden_ayristirilir(self):
        with self.load() as imap_client:
            samples = (
                ([b"UIDVALIDITY 123"], 123),
                ([b"[UIDVALIDITY 456] UIDs valid"], 456),
                ([b"789"], 789),
                ([(b"* OK", b"UIDVALIDITY 321")], 321),
            )
            for data, expected in samples:
                with self.subTest(data=data):
                    self.assertEqual(expected, imap_client.imap_uidvalidity_ayristir(data))

    def test_eposta_boyutu_sinir_asiminda_indirmeyi_durdurur(self):
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = ("OK", [b"1 (UID 5 RFC822.SIZE 5242881)"])
        with self.load() as imap_client:
            with self.assertRaisesRegex(MailHatasi, "çok büyük"):
                imap_client.imap_eposta_boyutunu_denetle(
                    imap, 5, 5 * 1024 * 1024, "E-posta"
                )

    def test_gmail_uzantisi_yoksa_etiketli_silme_durdurulur(self):
        imap = FakeIMAP()
        imap.capability = mock.Mock(return_value=("OK", [b"IMAP4rev1 UIDPLUS"]))
        with self.load() as imap_client:
            with self.assertRaisesRegex(MailHatasi, "Gmail etiket desteği"):
                imap_client.imap_gmail_etiket_destegini_dogrula(imap)


if __name__ == "__main__":
    unittest.main()
