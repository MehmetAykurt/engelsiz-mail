# -*- coding: utf-8 -*-
"""İkinci aşamada eklenen ortak test altyapısının kendi doğrulama testleri."""

import pathlib
import sys
import types
import unittest
from email.message import EmailMessage

from support import (
    FakeIMAP,
    FakeSMTPFactory,
    FakeWx,
    load_mail_module,
    module,
    nvda_module_stubs,
    temporary_database,
    temporary_workspace,
)


class ModuleLoaderTests(unittest.TestCase):
    def test_production_module_is_loaded_and_sys_modules_is_restored(self):
        old_mail = sys.modules.get("mail")
        with load_mail_module("validators") as validators:
            self.assertTrue(validators.eposta_adresi_gecerli_mi("test@example.com"))
            self.assertIn("mail.validators", sys.modules)
        self.assertIs(old_mail, sys.modules.get("mail"))
        self.assertNotIn("mail.validators", sys.modules)

    def test_stub_dependency_is_visible_only_inside_context(self):
        fake_logger = module("mail.logger", hata_kaydet=lambda *args: None)
        with load_mail_module("validators", stubs={"mail.logger": fake_logger}) as validators:
            self.assertEqual("mail.validators", validators.__name__)
            self.assertIs(fake_logger, sys.modules["mail.logger"])
        self.assertNotIn("mail.logger", sys.modules)


class FakeProtocolTests(unittest.TestCase):
    def test_fake_smtp_records_login_send_and_close(self):
        factory = FakeSMTPFactory()
        session = factory.SMTP_SSL("smtp.example.com", 465, timeout=5)
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["To"] = "recipient@example.com"
        message.set_content("Merhaba")

        session.login("sender@example.com", "secret")
        session.send_message(
            message,
            from_addr="sender@example.com",
            to_addrs=["recipient@example.com"],
        )
        session.quit()

        self.assertEqual(("sender@example.com", "secret"), session.logged_in_as)
        self.assertEqual(["recipient@example.com"], session.sent_messages[0]["to_addrs"])
        self.assertTrue(session.quit_called)
        self.assertTrue(session.closed)

    def test_fake_imap_supports_scripted_uid_responses_and_shutdown(self):
        imap = FakeIMAP("imap.example.com")
        imap.uid_responses["SEARCH"] = ("OK", [b"1 2 3"])

        self.assertEqual(("OK", [b"1 2 3"]), imap.uid("SEARCH", None, "ALL"))
        imap.shutdown()

        self.assertTrue(imap.shutdown_called)
        self.assertIn(("uid", ("SEARCH", None, "ALL")), imap.calls)


class EnvironmentTests(unittest.TestCase):
    def test_temporary_workspace_creates_and_removes_files(self):
        with temporary_workspace() as workspace:
            root = workspace.root
            created = workspace.file("örnek/çağrı.txt", "Türkçe içerik")
            self.assertEqual("Türkçe içerik", created.read_text(encoding="utf-8"))
            self.assertTrue(workspace.database_path.parent.is_dir())
        self.assertFalse(root.exists())

    def test_temporary_database_applies_real_migrations(self):
        with temporary_database() as (database, workspace):
            ok, details = database.veritabani_butunluk_denetle(
                str(workspace.database_path)
            )
            with database.veritabani_baglantisi(str(workspace.database_path)) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }

            self.assertTrue(ok, details)
            self.assertEqual(10, version)
            self.assertIn("messages", tables)
            self.assertIn("pending_deletions", tables)


class NVDATests(unittest.TestCase):
    def test_fake_wx_and_nvda_modules_record_user_feedback(self):
        with temporary_workspace() as workspace:
            wx = FakeWx(immediate_call_after=False)
            stubs, sink, returned_wx = nvda_module_stubs(
                str(workspace.config_dir), wx_module=wx
            )

            stubs["ui"].message("Yeni e-posta geldi")
            called = []
            returned_wx.CallAfter(called.append, "tamam")
            returned_wx.run_call_after_queue()

            self.assertEqual(["Yeni e-posta geldi"], sink.spoken_messages)
            self.assertEqual(["tamam"], called)
            self.assertIsInstance(stubs["globalVars"], types.ModuleType)
            self.assertEqual(
                str(workspace.config_dir),
                stubs["globalVars"].appArgs.configPath,
            )


if __name__ == "__main__":
    unittest.main()
