# -*- coding: utf-8 -*-
"""Derin inceleme raporundaki bulgular için geriye dönük testler.

Orta ve düşük düzey bulguların tamamı normal geriye dönük test olarak
çalışır. Bir bulgunun yeniden ortaya çıkması test takımını başarısız kılar.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
import re
import tempfile
import unittest
import zipfile

from support import MAIL_ROOT, FakeIMAP, load_mail_module, module


class ReportedRegressionTests(unittest.TestCase):
    def test_mixed_valid_and_invalid_recipient_is_rejected(self):
        """2.1: Tek bir hatalı adres bile varsa ileti oluşturma durmalıdır."""
        fake_log = module(
            "logHandler",
            log=type(
                "FakeLog",
                (),
                {
                    "exception": staticmethod(lambda *a, **k: None),
                    "error": staticmethod(lambda *a, **k: None),
                    "debug": staticmethod(lambda *a, **k: None),
                    "warning": staticmethod(lambda *a, **k: None),
                },
            )(),
        )
        with load_mail_module("smtp_client", stubs={"logHandler": fake_log}) as smtp_client:
            with self.assertRaises(smtp_client.MailHatasi):
                smtp_client.eposta_mesaji_olustur(
                    "gonderen@example.com",
                    "dogru@example.com, hatali-adres",
                    "Deneme",
                    "İçerik",
                    [],
                )

    def test_sync_skip_does_not_return_stale_grouped_cache(self):
        """2.2: Kilit nedeniyle eşitleme atlanırsa canlı UID listesi kullanılmalıdır."""
        class MailHatasi(Exception):
            pass

        imap = FakeIMAP("imap.example.com")
        imap.script("status", ("OK", [b"INBOX (MESSAGES 2 UNSEEN 2)"]))
        imap.script("select", ("OK", [b"2"]))
        imap.uid_responses["SEARCH"] = ("OK", [b"1 2"])

        def imap_toplu_uid_fetch(_imap, uidler, _komut):
            return {
                str(uid): (
                    f"From: Yeni {uid} <yeni{uid}@example.com>\r\n"
                    "To: kullanici@example.com\r\n"
                    f"Subject: Yeni ileti {uid}\r\n\r\n"
                ).encode("utf-8")
                for uid in uidler
            }

        stale_rows = [
            {
                "uid": "1",
                "sender": "Eski <eski@example.com>",
                "recipients_to": "kullanici@example.com",
                "subject": "Eski önbellek",
                "preview": "",
                "has_attachments": False,
                "gmail_thread_id": "t1",
                "gmail_message_id": "m1",
                "is_seen": True,
                "internal_date": 1,
            }
        ]

        stubs = {
            "mail.errors": module("mail.errors", MailHatasi=MailHatasi),
            "mail.imap_client": module(
                "mail.imap_client",
                ImapBaglantisi=lambda _ayarlar: imap,
                imap_status_sayilarini_ayristir=lambda _veri: {"messages": 2, "unseen": 2},
                imap_toplu_uid_fetch=imap_toplu_uid_fetch,
                uidleri_ayristir=lambda _veri: ["1", "2"],
            ),
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.header_sync": module(
                "mail.header_sync",
                klasor_basliklarini_senkronize_et=lambda *a, **k: {
                    "atlandi": True,
                    "iptal_edildi": False,
                    "kaydedilen": 0,
                },
            ),
            "mail.mail_store": module(
                "mail.mail_store",
                klasor_basliklarini_listele=lambda *a, **k: stale_rows,
                klasor_konusma_basliklarini_listele=lambda *a, **k: stale_rows,
                klasor_onizleme_haritasi_al=lambda *a, **k: {},
                klasor_yerel_onbellegi_var_mi=lambda *a, **k: True,
            ),
            "mail.message_parser": module(
                "mail.message_parser",
                adres_basligini_gosterime_hazirla=lambda deger, *a, **k: str(deger or "Alıcı yok"),
                fetch_sonucunda_ek_var_mi=lambda _veri: False,
                gonderen_gosterimini_al=lambda deger, varsayilan="Bilinmiyor": str(deger or varsayilan),
                ham_mesaj_verisi_al=lambda veri: bytes(veri),
                seen_bayragi_var_mi=lambda _veri: False,
            ),
            "mail.text_utils": module("mail.text_utils", guvenli_coz=lambda deger: str(deger or "")),
            "mail.config": module("mail.config", konusmalari_grupla_ayari_yukle=lambda: True),
            "mail.conversation": module(
                "mail.conversation",
                epostalari_konusmalara_grupla=lambda mailler, _sinir: list(mailler),
            ),
        }

        with load_mail_module("mailbox_loader", stubs=stubs) as mailbox_loader:
            sonuc = mailbox_loader.eposta_listesi_hazirla(
                {"eposta": "kullanici@example.com", "sifre": "x"},
                "Gelen Kutusu",
                "INBOX",
                lambda _imap: ({"Gelen Kutusu": "INBOX"}, []),
                50,
                False,
            )

        self.assertIn("2", [kayit["id"] for kayit in sonuc["mailler"]])

    def test_startup_sync_stop_closes_active_imap_connection(self):
        """2.3: Başlangıç eşitlemesi durdurulurken etkin IMAP bağlantısı kapanmalıdır."""
        source = (MAIL_ROOT / "startup_sync.py").read_text(encoding="utf-8")
        method = self._class_method_node(source, "BaslangicSenkronizasyonYoneticisi", "durdur")
        self.assertTrue(self._method_calls_shutdown(method))

    def test_pending_deletion_stop_closes_active_imap_connection(self):
        """2.3: Bekleyen silme yöneticisi durdurulurken etkin IMAP bağlantısı kapanmalıdır."""
        source = (MAIL_ROOT / "pending_deletions.py").read_text(encoding="utf-8")
        method = self._class_method_node(source, "BekleyenSilmeYoneticisi", "durdur")
        self.assertTrue(self._method_calls_shutdown(method))

    def test_plaintext_password_backup_is_an_explicit_supported_contract(self):
        """2.4: Kullanıcının bilinçli tercihi olan taşınabilir şifre yedeği korunur."""
        class MailHatasi(Exception):
            pass

        stubs = {
            "mail.errors": module("mail.errors", MailHatasi=MailHatasi),
            "mail.paths": module("mail.paths", AYARLAR_DOSYASI="ayarlar.json"),
            "mail.security": module(
                "mail.security",
                uygulama_sifresini_coz=lambda _deger: "abcd efgh ijkl mnop",
                uygulama_sifresini_sifrele=lambda deger: f"DPAPI:{deger}",
            ),
            "mail.storage": module(
                "mail.storage",
                guvenli_json_oku=lambda *a, **k: {},
                guvenli_json_yedekleyerek_yaz=lambda *a, **k: None,
            ),
            "mail.version": module("mail.version", EKLENTI_SURUMU="1.7.0"),
        }
        with load_mail_module("settings_backup", stubs=stubs) as settings_backup:
            sonuc = settings_backup._hassas_ayar_kopyasi(
                {"eposta": "kullanici@example.com", "sifre_dpapi": "sifreli"}
            )
        self.assertEqual("abcdefghijklmnop", sonuc["sifre"].replace(" ", ""))
        self.assertNotIn("sifre_dpapi", sonuc)

    def test_vendor_source_hash_matches_packaged_imaplib(self):
        """2.5: SOURCE.txt içindeki imaplib SHA-256 değeri gerçek dosyayla eşleşmelidir."""
        source_text = (MAIL_ROOT / "vendor" / "SOURCE.txt").read_text(encoding="utf-8")
        match = re.search(r"imaplib\.py\s+SHA-256:\s*([0-9a-fA-F]{64})", source_text)
        self.assertIsNotNone(match, "SOURCE.txt içinde imaplib.py SHA-256 kaydı bulunamadı.")
        actual = hashlib.sha256((MAIL_ROOT / "vendor" / "imaplib.py").read_bytes()).hexdigest()
        self.assertEqual(actual, match.group(1).lower())

    def test_contacts_are_not_saved_before_send_success(self):
        """3.1: Rehber kaydı gönder düğmesinde değil, başarılı sonuçtan sonra yapılmalıdır."""
        source = (MAIL_ROOT / "ui" / "compose_window.py").read_text(encoding="utf-8")
        send_method = self._class_method_node(source, "YeniPostaPenceresi", "gonder_tiklandi")
        success_method = self._class_method_node(source, "YeniPostaPenceresi", "gonderim_basarili")
        self.assertFalse(self._method_calls_name(send_method, "rehbere_ekle"))
        self.assertTrue(self._method_calls_name(success_method, "rehbere_ekle"))

    def test_invalid_attachment_record_raises_mail_error(self):
        """3.2: Geçersiz ek kaydı AttributeError yerine anlaşılır MailHatasi üretmelidir."""
        fake_log = module(
            "logHandler",
            log=type(
                "FakeLog",
                (),
                {
                    "error": staticmethod(lambda *a, **k: None),
                    "debug": staticmethod(lambda *a, **k: None),
                    "warning": staticmethod(lambda *a, **k: None),
                },
            )(),
        )
        with load_mail_module("smtp_client", stubs={"logHandler": fake_log}) as smtp_client:
            with self.assertRaises(smtp_client.MailHatasi):
                smtp_client.eposta_mesaji_olustur(
                    "gonderen@example.com",
                    "alici@example.com",
                    "Deneme",
                    "İçerik",
                    [123],
                )

    def test_logger_records_passed_exception_outside_except_block(self):
        """3.3: Verilen hata nesnesinin türü ve metni etkin except bloğu olmadan da kaydedilmelidir."""
        class FakeLog:
            def __init__(self):
                self.records = []

            def exception(self, *args, **kwargs):
                self.records.append(("exception", args, kwargs))

            def error(self, *args, **kwargs):
                self.records.append(("error", args, kwargs))

            def debug(self, *args, **kwargs):
                self.records.append(("debug", args, kwargs))

            def warning(self, *args, **kwargs):
                self.records.append(("warning", args, kwargs))

        fake_log = FakeLog()
        with load_mail_module(
            "logger",
            stubs={"logHandler": module("logHandler", log=fake_log)},
        ) as logger:
            error = ValueError("örnek hata")
            logger.hata_kaydet("Kayıt denemesi", error)

        rendered = repr(fake_log.records)
        has_explicit_error = "ValueError" in rendered and "örnek hata" in rendered
        has_exc_info_object = any(
            kwargs.get("exc_info") not in (None, True, False)
            for _level, _args, kwargs in fake_log.records
        )
        self.assertTrue(has_explicit_error or has_exc_info_object)

    def test_distribution_tree_has_no_python_cache_artifacts(self):
        """3.4: Temiz kaynak arşivi önbellek ve derlenmiş Python dosyası taşımamalıdır."""
        from tools.build_source_archive import kaynak_arsivi_olustur

        with tempfile.TemporaryDirectory() as gecici:
            kok = pathlib.Path(gecici) / "kaynak"
            (kok / "tests" / "__pycache__").mkdir(parents=True)
            (kok / ".pytest_cache").mkdir(parents=True)
            (kok / "globalPlugins" / "mail").mkdir(parents=True)
            (kok / "globalPlugins" / "mail" / "modul.py").write_text("x = 1\n", encoding="utf-8")
            (kok / "tests" / "__pycache__" / "test.cpython-313.pyc").write_bytes(b"pyc")
            (kok / ".pytest_cache" / "README.md").write_text("cache", encoding="utf-8")
            hedef = pathlib.Path(gecici) / "paket.zip"
            kaynak_arsivi_olustur(kok, hedef, "engelsiz_mail")

            with zipfile.ZipFile(hedef, "r") as arsiv:
                adlar = arsiv.namelist()

        self.assertIn("engelsiz_mail/globalPlugins/mail/modul.py", adlar)
        self.assertFalse(any("__pycache__" in ad or ".pytest_cache" in ad for ad in adlar))
        self.assertFalse(any(ad.endswith((".pyc", ".pyo")) for ad in adlar))

    def test_internationalized_email_address_is_supported(self):
        """3.5: EAI kapsamındaki Unicode yerel bölüm ve alan adı kabul edilmelidir."""
        with load_mail_module("validators") as validators:
            self.assertTrue(validators.eposta_adresi_gecerli_mi("çağrı@örnek.istanbul"))

    @staticmethod
    def _class_method_node(source: str, class_name: str, method_name: str) -> ast.AST:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                        return child
        raise AssertionError(f"Yöntem bulunamadı: {class_name}.{method_name}")

    @staticmethod
    def _method_calls_name(method: ast.AST, target_name: str) -> bool:
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == target_name:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr == target_name:
                return True
        return False

    @staticmethod
    def _method_calls_shutdown(method: ast.AST) -> bool:
        return ReportedRegressionTests._method_calls_name(method, "shutdown")


if __name__ == "__main__":
    unittest.main()
