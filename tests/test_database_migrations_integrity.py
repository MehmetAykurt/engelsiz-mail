# -*- coding: utf-8 -*-
"""SQLite göçleri, işlem atomikliği, kurtarma ve bütünlük testleri."""

from __future__ import annotations

import contextlib
import os
import pathlib
import sqlite3
import unittest

from support import load_mail_module, module, temporary_workspace


LOGGER = module(
    "mail.logger",
    hata_kaydet=lambda *args, **kwargs: None,
    uyari_kaydet=lambda *args, **kwargs: None,
)


@contextlib.contextmanager
def database_environment():
    with temporary_workspace(prefix="engelsiz-mail-db-") as workspace:
        paths = module(
            "mail.paths",
            VERITABANI_DOSYASI=str(workspace.database_path),
            AYARLAR_KLASORU=str(workspace.config_dir),
            AYARLAR_DOSYASI=str(workspace.settings_path),
            EKLER_KLASORU=str(workspace.attachment_dir),
        )
        stubs = {
            "mail.logger": LOGGER,
            "mail.paths": paths,
            "mail.sqlite_compat": module("mail.sqlite_compat", sqlite3=sqlite3),
        }
        with load_mail_module("database", stubs=stubs) as database:
            yield database, workspace


def create_schema_to(database, path: pathlib.Path, version: int):
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        for target in range(1, int(version) + 1):
            connection.execute("BEGIN IMMEDIATE")
            for statement in database.MIGRATIONS[target]:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (target, 1_700_000_000 + target),
            )
            connection.execute(f"PRAGMA user_version = {target}")
            connection.commit()
    finally:
        connection.close()


class VeritabaniGocTestleri(unittest.TestCase):
    def test_her_eski_surumu_guncel_semaya_tasir(self):
        for start_version in range(0, 10):
            with self.subTest(start_version=start_version), database_environment() as (database, workspace):
                if start_version:
                    create_schema_to(database, workspace.database_path, start_version)
                database.veritabani_hazirla(str(workspace.database_path))
                with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                    version = db.execute("PRAGMA user_version").fetchone()[0]
                    applied = [row[0] for row in db.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    ).fetchall()]
                    pending_columns = {row[1] for row in db.execute(
                        "PRAGMA table_info(pending_deletions)"
                    ).fetchall()}
                    bulk_columns = {row[1] for row in db.execute(
                        "PRAGMA table_info(pending_bulk_operations)"
                    ).fetchall()}
                self.assertEqual(10, version)
                self.assertEqual(list(range(1, 11)), applied)
                self.assertTrue({"remote_completed", "remote_completed_at", "remote_verified"}.issubset(pending_columns))
                self.assertIn("settlement_verified_at", bulk_columns)

    def test_goc_mevcut_hesap_ve_mesaj_verisini_korur(self):
        with database_environment() as (database, workspace):
            create_schema_to(database, workspace.database_path, 8)
            raw = sqlite3.connect(workspace.database_path)
            try:
                raw.execute(
                    "INSERT INTO accounts(id,email,provider,created_at,updated_at) VALUES(1,'kullanici@example.com','gmail',1,1)"
                )
                raw.execute(
                    """INSERT INTO messages(
                           id,account_id,gmail_message_id,subject,sender,created_at,updated_at
                       ) VALUES(1,1,'9001','Türkçe konu','Gönderen',1,1)"""
                )
                raw.commit()
            finally:
                raw.close()
            database.veritabani_hazirla(str(workspace.database_path))
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                row = db.execute(
                    "SELECT subject,sender FROM messages WHERE gmail_message_id='9001'"
                ).fetchone()
        self.assertEqual("Türkçe konu", row[0])
        self.assertEqual("Gönderen", row[1])

    def test_gelecek_sema_surumu_sessizce_sifirlanmaz(self):
        with database_environment() as (database, workspace):
            connection = sqlite3.connect(workspace.database_path)
            connection.execute("PRAGMA user_version = 999")
            connection.commit()
            connection.close()
            with self.assertRaises(sqlite3.DatabaseError):
                database.veritabani_hazirla(str(workspace.database_path))
            connection = sqlite3.connect(workspace.database_path)
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            finally:
                connection.close()
        self.assertEqual(999, version)
        self.assertEqual([], tables)
        self.assertEqual([], list(workspace.cache_dir.glob("mail.db.bozuk-*")))

    def test_yapisal_uyumsuzluk_yedeklenip_temiz_sema_kurulur(self):
        with database_environment() as (database, workspace):
            connection = sqlite3.connect(workspace.database_path)
            connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)")
            for version in range(1, 11):
                connection.execute("INSERT INTO schema_migrations VALUES(?,?)", (version, version))
            connection.execute("PRAGMA user_version = 10")
            connection.commit()
            connection.close()
            database.veritabani_hazirla(str(workspace.database_path))
            backups = list(workspace.cache_dir.glob("mail.db.bozuk-*"))
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}
        self.assertEqual(1, len(backups))
        self.assertIn("messages", tables)
        self.assertIn("pending_deletions", tables)

    def test_bozuk_dosya_yedeklenip_yeni_sema_kurulur(self):
        with database_environment() as (database, workspace):
            workspace.database_path.write_bytes(b"bu bir sqlite veritabani degildir")
            database.veritabani_hazirla(str(workspace.database_path))
            backups = list(workspace.cache_dir.glob("mail.db.bozuk-*"))
            backup_contents = [path.read_bytes() for path in backups]
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(10, version)
        self.assertEqual(1, len(backup_contents))
        self.assertEqual(b"bu bir sqlite veritabani degildir", backup_contents[0])

    def test_dogrudan_bozuk_yedekleme_wal_ve_shm_dosyalarini_birlikte_tasir(self):
        with database_environment() as (database, workspace):
            workspace.database_path.write_bytes(b"ana")
            wal = pathlib.Path(str(workspace.database_path) + "-wal")
            shm = pathlib.Path(str(workspace.database_path) + "-shm")
            wal.write_bytes(b"wal")
            shm.write_bytes(b"shm")
            backup = pathlib.Path(database.bozuk_veritabanini_yedekle(str(workspace.database_path)))
            main_bytes = backup.read_bytes()
            wal_bytes = pathlib.Path(str(backup) + "-wal").read_bytes()
            shm_bytes = pathlib.Path(str(backup) + "-shm").read_bytes()
        self.assertEqual(b"ana", main_bytes)
        self.assertEqual(b"wal", wal_bytes)
        self.assertEqual(b"shm", shm_bytes)


class VeritabaniIslemVeButunlukTestleri(unittest.TestCase):
    def test_yazma_baglaminda_hata_tum_islemi_geri_alir(self):
        with database_environment() as (database, workspace):
            database.veritabani_hazirla(str(workspace.database_path))
            with self.assertRaises(RuntimeError):
                with database.veritabani_baglantisi(str(workspace.database_path), yazma=True) as db:
                    db.execute(
                        "INSERT INTO accounts(email,provider,created_at,updated_at) VALUES('a@example.com','gmail',1,1)"
                    )
                    raise RuntimeError("yarıda kesildi")
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                count = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        self.assertEqual(0, count)

    def test_yazma_baglaminda_basarili_islem_commit_edilir(self):
        with database_environment() as (database, workspace):
            with database.veritabani_baglantisi(str(workspace.database_path), yazma=True) as db:
                db.execute(
                    "INSERT INTO accounts(email,provider,created_at,updated_at) VALUES('a@example.com','gmail',1,1)"
                )
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                count = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        self.assertEqual(1, count)

    def test_yabanci_anahtar_silmesi_bagli_kayitlari_temizler(self):
        with database_environment() as (database, workspace):
            with database.veritabani_baglantisi(str(workspace.database_path), yazma=True) as db:
                db.execute("INSERT INTO accounts(id,email,provider,created_at,updated_at) VALUES(1,'a@example.com','gmail',1,1)")
                db.execute("INSERT INTO folders(id,account_id,imap_name,display_name,created_at,updated_at) VALUES(1,1,'INBOX','Gelen',1,1)")
                db.execute("INSERT INTO messages(id,account_id,subject,sender,created_at,updated_at) VALUES(1,1,'Konu','G',1,1)")
                db.execute("INSERT INTO folder_messages(folder_id,message_id,uidvalidity,uid,last_seen_at,created_at,updated_at) VALUES(1,1,10,5,1,1,1)")
                db.execute("DELETE FROM accounts WHERE id=1")
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                counts = [db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("accounts", "folders", "messages", "folder_messages")]
        self.assertEqual([0, 0, 0, 0], counts)

    def test_foreign_key_check_yetim_kaydi_raporlar(self):
        with database_environment() as (database, workspace):
            database.veritabani_hazirla(str(workspace.database_path))
            raw = sqlite3.connect(workspace.database_path)
            raw.execute("PRAGMA foreign_keys=OFF")
            raw.execute(
                "INSERT INTO folders(id,account_id,imap_name,display_name,created_at,updated_at) VALUES(99,999,'X','X',1,1)"
            )
            raw.commit()
            raw.close()
            ok, details = database.veritabani_butunluk_denetle(str(workspace.database_path))
        self.assertFalse(ok)
        self.assertTrue(any(item.startswith("foreign_key:table=folders") for item in details))


    def test_basarili_baglanti_sonrasi_hazirlik_imzasi_guncel_kalir(self):
        with database_environment() as (database, workspace):
            with database.veritabani_baglantisi(str(workspace.database_path), yazma=True) as db:
                db.execute(
                    "INSERT INTO accounts(email,provider,created_at,updated_at) VALUES('imza@example.com','gmail',1,1)"
                )
            key = os.path.normcase(os.path.abspath(str(workspace.database_path)))
            cached = database._HAZIR_VERITABANLARI.get(key)
            current = database._veritabani_dosya_kimligi(str(workspace.database_path))
        self.assertEqual(current, cached)

    def test_veritabani_dosyasi_degistirilirse_hazirlik_onbellegi_yeniden_dogrular(self):
        with database_environment() as (database, workspace):
            database.veritabani_hazirla(str(workspace.database_path))
            first_inode = os.stat(workspace.database_path).st_ino
            os.remove(workspace.database_path)
            connection = sqlite3.connect(workspace.database_path)
            connection.close()
            second_inode = os.stat(workspace.database_path).st_ino
            database.veritabani_hazirla(str(workspace.database_path))
            with database.veritabani_baglantisi(str(workspace.database_path)) as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                table_count = db.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()[0]
        # Bazı dosya sistemleri silinen inode'u hemen yeniden kullanır; güvenlik
        # denetimi inode eşit olsa bile boş yeni dosyayı yeniden hazırlamalıdır.
        self.assertEqual(10, version)
        self.assertGreater(table_count, 0)


if __name__ == "__main__":
    unittest.main()
