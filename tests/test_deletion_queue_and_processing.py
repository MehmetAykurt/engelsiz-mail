# -*- coding: utf-8 -*-
"""Silme kuyruğu, toplu silme ve IMAP işleme bütünleşme testleri."""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
import time
import unittest
from unittest import mock

from support import FakeIMAP, FakeWx, module, temporary_database


class _Connection:
    def __init__(self, imap):
        self.imap = imap
        self.shutdown_called = False

    def __enter__(self):
        return self.imap

    def __exit__(self, exc_type, exc, tb):
        return False

    def shutdown(self):
        self.shutdown_called = True
        self.imap.shutdown()
        return True


@contextlib.contextmanager
def deletion_environment():
    """Gerçek SQLite şemasıyla, ağsız silme modüllerini yükler."""
    with temporary_database() as (database, workspace):
        wx = FakeWx()
        stubs = {
            "wx": wx,
            "mail.config": module(
                "mail.config",
                ayarlari_yukle=lambda: {
                    "eposta": "kullanici@example.com",
                    "sifre": "uygulama-sifresi",
                },
            ),
            "mail.ui_helpers": module(
                "mail.ui_helpers",
                arka_planda_calistir=lambda islev, *a, **k: islev(*a, **k),
            ),
        }
        with mock.patch.dict(sys.modules, stubs):
            store = importlib.import_module("mail.mail_store")
            pending = importlib.import_module("mail.pending_deletions")
            yield database, workspace, store, pending, wx


def seed_folder(store, email, folder, display, uidvalidity, records):
    account_id, folder_id, _changed = store.hesap_ve_klasor_hazirla(
        email, folder, display, uidvalidity
    )
    store.baslik_paketini_kaydet(account_id, folder_id, uidvalidity, records)
    store.klasor_senkronizasyonunu_tamamla(
        folder_id, uidvalidity, [int(record["uid"]) for record in records]
    )
    return account_id, folder_id


def message_record(uid, gmail_id, subject="Deneme", seen=False):
    return {
        "uid": int(uid),
        "gmail_message_id": str(gmail_id),
        "gmail_thread_id": f"thread-{gmail_id}",
        "rfc_message_id": f"<{gmail_id}@example.com>",
        "subject": subject,
        "sender": "Gönderen <gonderen@example.com>",
        "recipients_to": "kullanici@example.com",
        "internal_date": 1_700_000_000 + int(uid),
        "preview": "Ön izleme",
        "flags": ["\\Seen"] if seen else [],
    }


class SilmeKuyruguTestleri(unittest.TestCase):
    def test_tekli_cop_kuyrugu_atomik_kaydedilir_ve_kaynakta_gizlenir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            _account, inbox_id = seed_folder(
                store,
                "kullanici@example.com",
                "INBOX",
                "Gelen Kutusu",
                111,
                [message_record(10, "90010")],
            )
            count = pending.silme_isteklerini_kuyruga_al(
                "KULLANICI@example.com",
                "INBOX",
                "gelen",
                [10, 10],
                "trash",
                '"[Gmail]/Trash"',
            )
            with database.veritabani_baglantisi() as db:
                queue = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
                membership = dict(
                    db.execute(
                        "SELECT is_present FROM folder_messages WHERE folder_id=? AND uid=10",
                        (inbox_id,),
                    ).fetchone()
                )
                folder = dict(db.execute("SELECT * FROM folders WHERE id=?", (inbox_id,)).fetchone())
        self.assertEqual(1, count)
        self.assertEqual("trash", queue["operation_type"])
        self.assertEqual("90010", queue["gmail_message_id"])
        self.assertEqual(111, queue["source_uidvalidity"])
        self.assertEqual(0, membership["is_present"])
        self.assertEqual(0, folder["message_count"])
        self.assertEqual(0, folder["unseen_count"])

    def test_kalici_silme_mesajin_butun_klasor_uyeliklerini_gizler(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            seed_folder(store, "kullanici@example.com", '"Arşiv"', "Arşiv", 222, [message_record(88, "90010")])
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "permanent", '"[Gmail]/Trash"'
            )
            with database.veritabani_baglantisi() as db:
                present = [int(row[0]) for row in db.execute(
                    "SELECT is_present FROM folder_messages fm JOIN messages m ON m.id=fm.message_id WHERE m.gmail_message_id='90010'"
                ).fetchall()]
        self.assertEqual([0, 0], sorted(present))

    def test_ayni_istek_yeniden_kuyruga_alininca_durum_sifirlanir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            with database.veritabani_baglantisi(yazma=True) as db:
                old = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
                db.execute(
                    "UPDATE pending_deletions SET attempt_count=7, remote_completed=1, remote_verified=1, last_error='x'"
                )
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            with database.veritabani_baglantisi() as db:
                new = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
        self.assertNotEqual(old["request_token"], new["request_token"])
        self.assertEqual(0, new["attempt_count"])
        self.assertEqual(0, new["remote_completed"])
        self.assertEqual(0, new["remote_verified"])
        self.assertIsNone(new["last_error"])

    def test_kalici_istek_ayni_gmail_idli_cop_isteginin_yerini_alir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "permanent", '"[Gmail]/Trash"'
            )
            with database.veritabani_baglantisi() as db:
                rows = [dict(row) for row in db.execute("SELECT * FROM pending_deletions").fetchall()]
        self.assertEqual(1, len(rows))
        self.assertEqual("permanent", rows[0]["operation_type"])

    def test_gecerli_ve_gecersiz_uid_karisimi_kismi_silme_yapmaz(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            _account, inbox_id = seed_folder(
                store, "kullanici@example.com", "INBOX", "Gelen", 111,
                [message_record(10, "90010")],
            )
            with self.assertRaisesRegex(ValueError, "geçersiz.*UID"):
                pending.silme_isteklerini_kuyruga_al(
                    "kullanici@example.com", "INBOX", "gelen", [10, "bozuk"],
                    "trash", '"[Gmail]/Trash"',
                )
            with database.veritabani_baglantisi() as db:
                queue_count = db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0]
                present = db.execute(
                    "SELECT is_present FROM folder_messages WHERE folder_id=? AND uid=10",
                    (inbox_id,),
                ).fetchone()[0]
        self.assertEqual(0, queue_count)
        self.assertEqual(1, present)

    def test_uidvalidity_ve_gmail_id_yoksa_kuyruk_reddedilir(self):
        with deletion_environment() as (database, _workspace, _store, pending, _wx):
            with self.assertRaisesRegex(ValueError, "UIDVALIDITY"):
                pending.silme_isteklerini_kuyruga_al(
                    "kullanici@example.com", "INBOX", "gelen", [5], "trash", '"[Gmail]/Trash"'
                )
            with database.veritabani_baglantisi() as db:
                self.assertEqual(0, db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0])

    def test_hatalı_toplu_islem_fk_hatasi_yerel_gizlemeyi_geri_alir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            _account, inbox_id = seed_folder(
                store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")]
            )
            with self.assertRaises(Exception):
                pending.silme_isteklerini_kuyruga_al(
                    "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"',
                    toplu_islem_id=999999,
                )
            with database.veritabani_baglantisi() as db:
                self.assertEqual(0, db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0])
                present = db.execute(
                    "SELECT is_present FROM folder_messages WHERE folder_id=? AND uid=10", (inbox_id,)
                ).fetchone()[0]
        self.assertEqual(1, present)

    def test_bekleyen_uidler_hesap_klasor_ve_kategoriye_gore_ayrilir(self):
        with deletion_environment() as (_database, _workspace, store, pending, _wx):
            seed_folder(store, "a@example.com", "INBOX", "Gelen", 111, [message_record(1, "101")])
            seed_folder(store, "a@example.com", '"Etiket"', "Etiket", 222, [message_record(2, "102")])
            pending.silme_isteklerini_kuyruga_al("a@example.com", "INBOX", "gelen", [1], "trash", '"Trash"')
            pending.silme_isteklerini_kuyruga_al("a@example.com", '"Etiket"', "etiket", [2], "trash", '"Trash"')
            self.assertEqual({"1"}, pending.bekleyen_kaynak_uidleri("a@example.com", kaynak_klasor="INBOX"))
            self.assertEqual({"2"}, pending.bekleyen_kaynak_uidleri("a@example.com", kaynak_kategori="etiket"))
            self.assertEqual(set(), pending.bekleyen_kaynak_uidleri("b@example.com", kaynak_klasor="INBOX"))


class TopluSilmeTestleri(unittest.TestCase):
    def test_toplu_islem_bilinen_yerel_uidleri_kuyruga_baglar(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(
                store, "kullanici@example.com", '"[Gmail]/Spam"', "Spam", 333,
                [message_record(1, "501"), message_record(2, "502", seen=True)],
            )
            result = pending.toplu_silme_istegini_kuyruga_al(
                "kullanici@example.com", "empty_spam", '"[Gmail]/Spam"', "spam",
                "permanent", '"[Gmail]/Trash"',
            )
            with database.veritabani_baglantisi() as db:
                bulk = dict(db.execute("SELECT * FROM pending_bulk_operations").fetchone())
                queues = [dict(row) for row in db.execute(
                    "SELECT * FROM pending_deletions ORDER BY source_uid"
                ).fetchall()]
        self.assertEqual(2, result["yerel_adet"])
        self.assertFalse(result["zaten_devam_ediyor"])
        self.assertEqual(0, bulk["snapshot_complete"])
        self.assertEqual([1, 2], [row["source_uid"] for row in queues])
        self.assertTrue(all(row["bulk_operation_id"] == bulk["id"] for row in queues))

    def test_ayni_toplu_islem_ikinci_kez_olusturulmaz(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", '"[Gmail]/Trash"', "Çöp", 333, [message_record(1, "501")])
            first = pending.toplu_silme_istegini_kuyruga_al(
                "kullanici@example.com", "empty_trash", '"[Gmail]/Trash"', "cop",
                "permanent", '"[Gmail]/Trash"',
            )
            second = pending.toplu_silme_istegini_kuyruga_al(
                "kullanici@example.com", "empty_trash", '"[Gmail]/Trash"', "cop",
                "permanent", '"[Gmail]/Trash"',
            )
            with database.veritabani_baglantisi() as db:
                count = db.execute("SELECT COUNT(*) FROM pending_bulk_operations").fetchone()[0]
        self.assertEqual(first["toplu_islem_id"], second["toplu_islem_id"])
        self.assertTrue(second["zaten_devam_ediyor"])
        self.assertEqual(1, count)

    def test_sunucu_anlik_goruntusu_eski_yerel_uidleri_guncel_uidlerle_degistirir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", '"[Gmail]/Spam"', "Spam", 111, [message_record(1, "501")])
            result = pending.toplu_silme_istegini_kuyruga_al(
                "kullanici@example.com", "empty_spam", '"[Gmail]/Spam"', "spam",
                "permanent", '"[Gmail]/Trash"',
            )
            with database.veritabani_baglantisi() as db:
                bulk = dict(db.execute(
                    "SELECT pbo.*, a.email FROM pending_bulk_operations pbo JOIN accounts a ON a.id=pbo.account_id"
                ).fetchone())
            imap = FakeIMAP()
            imap.script("response:UIDVALIDITY", ("OK", [b"999"]))
            imap.uid_responses["SEARCH"] = ("OK", [b"7 8"])
            imap.uid_responses["FETCH"] = (
                "OK",
                [
                    (b"1 (UID 7 X-GM-MSGID 7007)", b""),
                    (b"2 (UID 8 X-GM-MSGID 8008)", b""),
                ],
            )
            pending._toplu_islem_anlik_goruntusunu_hazirla(imap, bulk)
            with database.veritabani_baglantisi() as db:
                bulk_after = dict(db.execute("SELECT * FROM pending_bulk_operations").fetchone())
                rows = [dict(row) for row in db.execute(
                    "SELECT * FROM pending_deletions ORDER BY source_uid"
                ).fetchall()]
        self.assertEqual(1, bulk_after["snapshot_complete"])
        self.assertEqual(999, bulk_after["source_uidvalidity"])
        self.assertEqual([7, 8], [row["source_uid"] for row in rows])
        self.assertEqual(["7007", "8008"], [row["gmail_message_id"] for row in rows])
        self.assertTrue(all(row["bulk_operation_id"] == result["toplu_islem_id"] for row in rows))

    def test_toplu_klasor_bilgileri_bekleyen_ve_okunmamis_sayisini_dondurur(self):
        with deletion_environment() as (_database, _workspace, store, pending, _wx):
            seed_folder(
                store, "kullanici@example.com", '"[Gmail]/Spam"', "Spam", 333,
                [message_record(1, "501"), message_record(2, "502", seen=True)],
            )
            pending.toplu_silme_istegini_kuyruga_al(
                "kullanici@example.com", "empty_spam", '"[Gmail]/Spam"', "spam",
                "permanent", '"[Gmail]/Trash"',
            )
            info = pending.bekleyen_toplu_klasor_bilgileri("kullanici@example.com")
        self.assertEqual(2, info["spam"]["pending_count"])
        self.assertEqual(1, info["spam"]["known_unseen_count"])
        self.assertFalse(info["spam"]["snapshot_complete"])


class SilmeIslemeTestleri(unittest.TestCase):
    def test_cop_islemi_sunucuda_dogrulaninca_kuyruk_temizlenir(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            seed_folder(store, "kullanici@example.com", '"[Gmail]/Trash"', "Çöp", 222, [message_record(90, "90010")])
            # Çöp üyeliğini sunucu işlemi öncesi görünmez kabul et.
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute(
                    "UPDATE folder_messages SET is_present=0 WHERE folder_id=(SELECT id FROM folders WHERE imap_name='\"[Gmail]/Trash\"')"
                )
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            imap = FakeIMAP()
            state = {"moved": False}

            def search(*args):
                if imap.selected_mailbox == "INBOX":
                    return ("OK", [b"" if state["moved"] else b"10"])
                if imap.selected_mailbox == '"[Gmail]/Trash"':
                    return ("OK", [b"90" if state["moved"] else b""])
                return ("OK", [b""])

            def store(*args):
                state["moved"] = True
                return ("OK", [b""])

            imap.uid_responses["SEARCH"] = search
            imap.uid_responses["STORE"] = store
            connection = _Connection(imap)
            with mock.patch.object(pending, "ImapBaglantisi", return_value=connection), \
                    mock.patch.object(pending, "imap_gmail_etiket_destegini_dogrula", return_value=True):
                result = pending.bekleyen_silmeleri_isle(
                    {"eposta": "kullanici@example.com", "sifre": "x"}
                )
            with database.veritabani_baglantisi() as db:
                queue_count = db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0]
                source_present = db.execute(
                    "SELECT is_present FROM folder_messages fm JOIN folders f ON f.id=fm.folder_id WHERE f.imap_name='INBOX'"
                ).fetchone()[0]
        self.assertEqual(1, result["islenen"])
        self.assertEqual(0, result["bekleyen"])
        self.assertEqual(0, queue_count)
        self.assertEqual(0, source_present)
        self.assertTrue(state["moved"])

    def test_kalici_silme_dogrulaninca_mesaj_ve_ek_dosyasi_silinir(self):
        with deletion_environment() as (database, workspace, store, pending, _wx):
            seed_folder(
                store, "kullanici@example.com", '"[Gmail]/Trash"', "Çöp", 222,
                [message_record(90, "90010")],
            )
            store.mesaj_govdesini_kaydet(
                "kullanici@example.com", '"[Gmail]/Trash"', 90, "gövde", 5
            )
            identity = store.mesaj_onbellek_kimligini_al(
                "kullanici@example.com", '"[Gmail]/Trash"', 90
            )
            relative = "hesap/cop/ek.txt"
            attachment = workspace.attachment_dir / relative
            attachment.parent.mkdir(parents=True, exist_ok=True)
            attachment.write_bytes(b"ek")
            store.ek_kayitlarini_kaydet(
                identity["message_id"],
                [{
                    "part_path": "1.2", "file_name": "ek.txt", "content_type": "text/plain",
                    "size_bytes": 2, "sha256": "x", "local_path": relative,
                }],
                True,
            )
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", '"[Gmail]/Trash"', "cop", [90],
                "permanent", '"[Gmail]/Trash"',
            )
            imap = FakeIMAP()
            state = {"deleted": False}

            def search(*args):
                return ("OK", [b"" if state["deleted"] else b"90"])

            def expunge(*args):
                state["deleted"] = True
                return ("OK", [b"90"])

            imap.uid_responses["SEARCH"] = search
            imap.uid_responses["STORE"] = ("OK", [b""])
            imap.uid_responses["EXPUNGE"] = expunge
            connection = _Connection(imap)
            with mock.patch.object(pending, "ImapBaglantisi", return_value=connection):
                result = pending.bekleyen_silmeleri_isle(
                    {"eposta": "kullanici@example.com", "sifre": "x"}
                )
            with database.veritabani_baglantisi() as db:
                message_count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                queue_count = db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0]
        self.assertEqual(1, result["islenen"])
        self.assertEqual(0, message_count)
        self.assertEqual(0, queue_count)
        self.assertFalse(attachment.exists())
        self.assertTrue(state["deleted"])

    def test_kayit_hatasi_deneme_sayisini_artirir_ve_kuyrugu_korur(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            imap = FakeIMAP()
            imap.uid_responses["SEARCH"] = ("NO", [b"failure"])
            connection = _Connection(imap)
            with mock.patch.object(pending, "ImapBaglantisi", return_value=connection):
                result = pending.bekleyen_silmeleri_isle(
                    {"eposta": "kullanici@example.com", "sifre": "x"}
                )
            with database.veritabani_baglantisi() as db:
                row = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
        self.assertEqual(0, result["islenen"])
        self.assertEqual(1, result["bekleyen"])
        self.assertEqual(1, row["attempt_count"])
        self.assertIn("sunucuda aranamadı", row["last_error"])

    def test_islem_baslamadan_iptal_edilirse_baglanti_acilmaz(self):
        with deletion_environment() as (_database, _workspace, _store, pending, _wx):
            constructor = mock.Mock(side_effect=AssertionError("bağlantı açılmamalı"))
            with mock.patch.object(pending, "ImapBaglantisi", constructor):
                result = pending.bekleyen_silmeleri_isle(
                    {"eposta": "kullanici@example.com", "sifre": "x"},
                    iptal_edildi_mi=lambda: True,
                )
        self.assertTrue(result["iptal_edildi"])
        constructor.assert_not_called()

    def test_isleme_kilidi_doluysa_ikinci_islem_sunucuya_cikmaz(self):
        with deletion_environment() as (_database, _workspace, _store, pending, _wx):
            self.assertTrue(pending._ISLEME_KILIDI.acquire(False))
            try:
                result = pending.bekleyen_silmeleri_isle(
                    {"eposta": "kullanici@example.com", "sifre": "x"}
                )
            finally:
                pending._ISLEME_KILIDI.release()
        self.assertTrue(result["kilitli"])
        self.assertEqual(0, result["islenen"])

    def test_request_token_eski_is_parcasinin_yeni_kaydi_degistirmesini_engeller(self):
        with deletion_environment() as (database, _workspace, store, pending, _wx):
            seed_folder(store, "kullanici@example.com", "INBOX", "Gelen", 111, [message_record(10, "90010")])
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            with database.veritabani_baglantisi() as db:
                row = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
            pending.silme_isteklerini_kuyruga_al(
                "kullanici@example.com", "INBOX", "gelen", [10], "trash", '"[Gmail]/Trash"'
            )
            attempts = pending._hata_kaydet(row["id"], row["request_token"], RuntimeError("eski"))
            with database.veritabani_baglantisi() as db:
                current = dict(db.execute("SELECT * FROM pending_deletions").fetchone())
        self.assertEqual(0, attempts)
        self.assertEqual(0, current["attempt_count"])
        self.assertIsNone(current["last_error"])


if __name__ == "__main__":
    unittest.main()
