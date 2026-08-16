# -*- coding: utf-8 -*-
"""Yerel veritabanı bakımı, önbellek temizliği ve sıfırlama testleri."""

from __future__ import annotations

import importlib
import os
import time
import unittest

from support import temporary_database


def seed_message(store, email, folder, uidvalidity, uid, gmail_id, *, present=True, updated_at=None):
    account_id, folder_id, _changed = store.hesap_ve_klasor_hazirla(
        email, folder, folder, uidvalidity
    )
    store.baslik_paketini_kaydet(
        account_id,
        folder_id,
        uidvalidity,
        [{
            "uid": uid,
            "gmail_message_id": gmail_id,
            "gmail_thread_id": f"thread-{gmail_id}",
            "subject": f"Konu {gmail_id}",
            "sender": "Gönderen <g@example.com>",
            "internal_date": 1000 + uid,
            "flags": [],
        }],
    )
    store.klasor_senkronizasyonunu_tamamla(
        folder_id, uidvalidity, [uid] if present else []
    )
    return account_id, folder_id


class VeritabaniBakimTestleri(unittest.TestCase):
    def test_istatistikler_veritabani_ve_ek_boyutlarini_dondurur(self):
        with temporary_database() as (_database, workspace):
            store = importlib.import_module("mail.mail_store")
            maintenance = importlib.import_module("mail.database_maintenance")
            seed_message(store, "a@example.com", "INBOX", 10, 1, "1001")
            store.mesaj_govdesini_kaydet("a@example.com", "INBOX", 1, "gövde", 5)
            identity = store.mesaj_onbellek_kimligini_al("a@example.com", "INBOX", 1)
            relative = "a/inbox/ek.bin"
            path = workspace.attachment_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"123456")
            store.ek_kayitlarini_kaydet(
                identity["message_id"],
                [{
                    "part_path": "1", "file_name": "ek.bin", "content_type": "application/octet-stream",
                    "size_bytes": 6, "sha256": "x", "local_path": relative,
                }],
                True,
            )
            stats = maintenance.veritabani_istatistikleri()
        self.assertEqual(1, stats["accounts"])
        self.assertEqual(1, stats["folders"])
        self.assertEqual(1, stats["messages"])
        self.assertEqual(1, stats["bodies"])
        self.assertEqual(1, stats["attachments"])
        self.assertGreater(stats["database_bytes"], 0)
        self.assertEqual(6, stats["attachment_bytes"])

    def test_gmail_idleri_yalniz_belirtilen_hesaptan_silinir(self):
        with temporary_database() as (database, workspace):
            store = importlib.import_module("mail.mail_store")
            maintenance = importlib.import_module("mail.database_maintenance")
            seed_message(store, "a@example.com", "INBOX", 10, 1, "ortak")
            seed_message(store, "b@example.com", "INBOX", 20, 2, "ortak")
            identity = store.mesaj_onbellek_kimligini_al("a@example.com", "INBOX", 1)
            relative = "a/ek.txt"
            file_path = workspace.attachment_dir / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("ek", encoding="utf-8")
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute(
                    """INSERT INTO attachments(message_id,part_path,file_name,local_path,created_at,updated_at)
                       VALUES(?, '1', 'ek.txt', ?, 1, 1)""",
                    (identity["message_id"], relative),
                )
            result = maintenance.gmail_mesajlarini_yerelden_sil("a@example.com", ["ortak"])
            with database.veritabani_baglantisi() as db:
                remaining = [row[0] for row in db.execute(
                    "SELECT a.email FROM messages m JOIN accounts a ON a.id=m.account_id"
                ).fetchall()]
        self.assertEqual({"deleted_messages": 1, "deleted_files": 1}, result)
        self.assertEqual(["b@example.com"], remaining)
        self.assertFalse(file_path.exists())

    def test_yetim_temizligi_eski_mesaji_ve_ekini_siler(self):
        with temporary_database() as (database, workspace):
            store = importlib.import_module("mail.mail_store")
            maintenance = importlib.import_module("mail.database_maintenance")
            seed_message(store, "a@example.com", "INBOX", 10, 1, "1001", present=False)
            with database.veritabani_baglantisi() as db:
                message_id = int(db.execute(
                    "SELECT id FROM messages WHERE gmail_message_id='1001'"
                ).fetchone()[0])
            relative = "old/ek.txt"
            file_path = workspace.attachment_dir / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("eski", encoding="utf-8")
            old = 1_600_000_000
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute("UPDATE messages SET updated_at=? WHERE id=?", (old, message_id))
                db.execute("UPDATE folder_messages SET updated_at=?,is_present=0 WHERE message_id=?", (old, message_id))
                db.execute(
                    """INSERT INTO attachments(message_id,part_path,file_name,local_path,created_at,updated_at)
                       VALUES(?, '1', 'ek.txt', ?, ?, ?)""",
                    (message_id, relative, old, old),
                )
            result = maintenance.yetim_onbellegi_temizle(simdi=1_700_000_000)
            with database.veritabani_baglantisi() as db:
                count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(1, result["deleted_messages"])
        self.assertEqual(1, result["deleted_files"])
        self.assertEqual(0, count)
        self.assertFalse(file_path.exists())

    def test_bekleyen_silme_eski_mesaji_yetim_temizliginden_korur(self):
        with temporary_database() as (database, _workspace):
            store = importlib.import_module("mail.mail_store")
            maintenance = importlib.import_module("mail.database_maintenance")
            account_id, _folder_id = seed_message(
                store, "a@example.com", "INBOX", 10, 1, "1001", present=False
            )
            with database.veritabani_baglantisi() as db:
                message_id = int(db.execute(
                    "SELECT id FROM messages WHERE gmail_message_id='1001'"
                ).fetchone()[0])
            old = 1_600_000_000
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute("UPDATE messages SET updated_at=? WHERE id=?", (old, message_id))
                db.execute("UPDATE folder_messages SET updated_at=?,is_present=0 WHERE message_id=?", (old, message_id))
                db.execute(
                    """INSERT INTO pending_deletions(
                           account_id,operation_type,source_folder,source_category,source_uid,
                           gmail_message_id,source_uidvalidity,trash_folder,request_token,created_at,updated_at
                       ) VALUES(?, 'trash', 'INBOX', 'gelen', 1, '1001', 10, 'Trash', 'token', ?, ?)""",
                    (account_id, old, old),
                )
            result = maintenance.yetim_onbellegi_temizle(simdi=1_700_000_000)
            with database.veritabani_baglantisi() as db:
                count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(0, result["deleted_messages"])
        self.assertEqual(1, count)

    def test_kayitsiz_eski_dosya_silinir_yeni_dosya_korunur(self):
        with temporary_database() as (_database, workspace):
            maintenance = importlib.import_module("mail.database_maintenance")
            old_file = workspace.attachment_dir / "old.bin"
            new_file = workspace.attachment_dir / "new.bin"
            old_file.write_bytes(b"old")
            new_file.write_bytes(b"new")
            now = 1_700_000_000
            os.utime(old_file, (now - maintenance.YETIM_DOSYA_BEKLEME_SANIYESI - 1,) * 2)
            os.utime(new_file, (now, now))
            result = maintenance.yetim_onbellegi_temizle(simdi=now)
            old_exists = old_file.exists()
            new_exists = new_file.exists()
        self.assertEqual(1, result["deleted_files"])
        self.assertFalse(old_exists)
        self.assertTrue(new_exists)

    def test_sifirlama_bekleyen_silme_varken_reddedilir(self):
        with temporary_database() as (database, workspace):
            maintenance = importlib.import_module("mail.database_maintenance")
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute("INSERT INTO accounts(id,email,provider,created_at,updated_at) VALUES(1,'a@example.com','gmail',1,1)")
                db.execute(
                    """INSERT INTO pending_deletions(
                           account_id,operation_type,source_folder,source_category,source_uid,
                           gmail_message_id,source_uidvalidity,trash_folder,request_token,created_at,updated_at
                       ) VALUES(1,'trash','INBOX','gelen',1,'1001',10,'Trash','token',1,1)"""
                )
            with self.assertRaisesRegex(RuntimeError, "bekleyen silme"):
                maintenance.yerel_veritabanini_sifirla()
            database_still_exists = workspace.database_path.exists()
        self.assertTrue(database_still_exists)

    def test_sifirlama_veritabani_ve_ekleri_temizleyip_semayi_yeniden_kurar(self):
        with temporary_database() as (database, workspace):
            maintenance = importlib.import_module("mail.database_maintenance")
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute("INSERT INTO accounts(email,provider,created_at,updated_at) VALUES('a@example.com','gmail',1,1)")
            extra = workspace.attachment_dir / "x.bin"
            extra.write_bytes(b"x")
            self.assertTrue(maintenance.yerel_veritabanini_sifirla())
            with database.veritabani_baglantisi() as db:
                accounts = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
                version = db.execute("PRAGMA user_version").fetchone()[0]
            extra_exists = extra.exists()
        self.assertEqual(0, accounts)
        self.assertEqual(10, version)
        self.assertFalse(extra_exists)

    def test_sifirlama_posta_kilidi_doluyken_baslamaz(self):
        with temporary_database():
            maintenance = importlib.import_module("mail.database_maintenance")
            self.assertTrue(maintenance.POSTA_DURUM_KILIDI.acquire(False))
            try:
                with self.assertRaisesRegex(RuntimeError, "Başka bir e-posta işlemi"):
                    maintenance.yerel_veritabanini_sifirla()
            finally:
                maintenance.POSTA_DURUM_KILIDI.release()

    def test_temel_bakim_butunluk_ve_wal_sonucunu_dondurur(self):
        with temporary_database():
            maintenance = importlib.import_module("mail.database_maintenance")
            result = maintenance.temel_bakim_yap(temizlik=True)
            self.assertTrue(maintenance.veritabanini_sikistir())
        self.assertTrue(result["integrity_ok"])
        self.assertEqual(["ok"], result["integrity_details"])
        self.assertEqual(3, len(result["wal_checkpoint"]))
        self.assertIn("deleted_messages", result)


if __name__ == "__main__":
    unittest.main()
