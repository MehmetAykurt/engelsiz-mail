# -*- coding: utf-8 -*-
"""Beşinci aşamadaki düşük düzey düzeltmelerin ayrıntılı testleri."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from support import MAIL_ROOT, load_mail_module, module, temporary_workspace


LOG_HANDLER = module(
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


class Stage5LowFixTests(unittest.TestCase):
    def test_success_callback_receives_sent_recipients(self):
        source = (MAIL_ROOT / "ui" / "compose_window.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = self._method(tree, "YeniPostaPenceresi", "arka_planda_gonder")
        matching_calls = []
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "gorev_icin_guvenli_call_after":
                continue
            if len(node.args) < 3:
                continue
            callback = node.args[1]
            if isinstance(callback, ast.Attribute) and callback.attr == "gonderim_basarili":
                matching_calls.append(node)
        self.assertTrue(matching_calls, "Başarılı gönderim çağrısına alıcı listesi aktarılmıyor.")
        self.assertTrue(
            any(
                any(isinstance(alt, ast.Name) and alt.id == "alicilar" for alt in ast.walk(call.args[2]))
                for call in matching_calls
            )
        )

    def test_contacts_are_saved_only_by_success_handler(self):
        kaydedilen = []
        mesajlar = []
        kapanis_kodlari = []

        class Dialog:
            pass

        stubs = {
            "wx": module("wx", Dialog=Dialog, ID_OK=5100),
            "gui": module("gui"),
            "ui": module("ui", message=lambda metin: mesajlar.append(str(metin))),
            "mail.config": module(
                "mail.config",
                ayarlari_yukle=lambda: {},
                adres_otomatik_kaydet_ayari_yukle=lambda: True,
            ),
            "mail.contacts": module(
                "mail.contacts",
                adres_anahtari=lambda adres: str(adres or "").casefold(),
                kisileri_yukle=lambda: [],
                rehbere_ekle=lambda adres: kaydedilen.append(adres),
                rehberi_yukle=lambda: [],
            ),
            "mail.errors": module("mail.errors", MailHatasi=Exception),
            "mail.folders": module(
                "mail.folders",
                taslak_klasor_adaylarini_temizle=lambda _deger: [],
            ),
            "mail.draft_service": module(
                "mail.draft_service",
                taslagi_sunucuya_kaydet=lambda *a, **k: None,
            ),
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.message_center": module(
                "mail.message_center",
                mesaj_soyle_ve_sonra_calistir=lambda metin, callback, **_k: (
                    mesajlar.append(str(metin)),
                    callback(),
                ),
            ),
            "mail.message_parser": module(
                "mail.message_parser",
                adres_basligini_duzenle=lambda deger: str(deger or ""),
            ),
            "mail.smtp_client": module(
                "mail.smtp_client",
                eposta_mesaji_olustur=lambda *a, **k: None,
                smtp_ssl_ile_gonder=lambda *a, **k: None,
            ),
            "mail.text_utils": module(
                "mail.text_utils",
                guvenli_coz=lambda deger: str(deger or ""),
            ),
            "mail.ui_helpers": module(
                "mail.ui_helpers",
                arka_plan_gorev_jetonu_olustur=lambda *a, **k: None,
                arka_plan_gorevlerini_gecersiz_kil=lambda *a, **k: None,
                arka_planda_calistir=lambda *a, **k: None,
                gorev_icin_guvenli_call_after=lambda *a, **k: None,
                gorunum_denetimlerine_uygula=lambda *a, **k: None,
                pencere_kullanilabilir_mi=lambda *a, **k: True,
            ),
            "mail.validators": module(
                "mail.validators",
                alici_basligini_cozumle=lambda _deger: ([], []),
            ),
            "mail.ui.contacts_window": module(
                "mail.ui.contacts_window",
                KisiSecPenceresi=object,
            ),
        }

        with load_mail_module("ui.compose_window", stubs=stubs) as compose_window:
            pencere = compose_window.YeniPostaPenceresi.__new__(
                compose_window.YeniPostaPenceresi
            )
            pencere.gonderildi_callback = None
            pencere.EndModal = lambda kod: kapanis_kodlari.append(kod)
            pencere.gonderim_basarili(
                ("bir@example.com", "iki@example.com")
            )

        self.assertEqual(["iki@example.com", "bir@example.com"], kaydedilen)
        self.assertEqual(["E-posta başarıyla gönderildi."], mesajlar)
        self.assertEqual([5100], kapanis_kodlari)

    def test_invalid_ready_attachment_data_raises_mail_error(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            with self.assertRaisesRegex(smtp_client.MailHatasi, "Ek verisi geçersiz"):
                smtp_client.eposta_mesaji_olustur(
                    "gonderen@example.com",
                    "alici@example.com",
                    "Deneme",
                    "İçerik",
                    [{"tur": "hazir", "ad": "deneme.txt", "veri": "metin"}],
                )

    def test_bytearray_ready_attachment_is_supported(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            mesaj = smtp_client.eposta_mesaji_olustur(
                "gonderen@example.com",
                "alici@example.com",
                "Deneme",
                "İçerik",
                [{"tur": "hazir", "ad": "deneme.txt", "veri": bytearray(b"icerik")}],
            )
        ekler = list(mesaj.iter_attachments())
        self.assertEqual(1, len(ekler))
        self.assertEqual(b"icerik", ekler[0].get_payload(decode=True))

    def test_logger_preserves_exception_type_message_and_traceback_tuple(self):
        class FakeLog:
            def __init__(self):
                self.records = []

            def error(self, *args, **kwargs):
                self.records.append(("error", args, kwargs))

            def debug(self, *args, **kwargs):
                self.records.append(("debug", args, kwargs))

            def warning(self, *args, **kwargs):
                self.records.append(("warning", args, kwargs))

        fake_log = FakeLog()
        with load_mail_module("logger", stubs={"logHandler": module("logHandler", log=fake_log)}) as logger:
            hata = ValueError("Türkçe hata açıklaması")
            logger.hata_kaydet("Kayıt sınaması", hata)

        self.assertEqual("error", fake_log.records[0][0])
        metin = " ".join(str(value) for value in fake_log.records[0][1])
        self.assertIn("ValueError", metin)
        self.assertIn("Türkçe hata açıklaması", metin)
        exc_info = fake_log.records[0][2].get("exc_info")
        self.assertIsInstance(exc_info, tuple)
        self.assertIs(exc_info[0], ValueError)
        self.assertIs(exc_info[1], hata)

    def test_source_archive_is_deterministic_and_clean(self):
        from tools.build_source_archive import kaynak_arsivi_olustur

        with tempfile.TemporaryDirectory() as gecici:
            kok = Path(gecici) / "kaynak"
            (kok / "globalPlugins" / "mail").mkdir(parents=True)
            (kok / "tests" / "__pycache__").mkdir(parents=True)
            (kok / ".pytest_cache").mkdir(parents=True)
            (kok / "globalPlugins" / "mail" / "modul.py").write_text("deger = 1\n", encoding="utf-8")
            (kok / "tests" / "test_ornek.py").write_text("def test_ornek(): pass\n", encoding="utf-8")
            (kok / "tests" / "__pycache__" / "test.pyc").write_bytes(b"cache")
            (kok / ".pytest_cache" / "CACHEDIR.TAG").write_text("cache", encoding="utf-8")
            ilk = Path(gecici) / "ilk.zip"
            ikinci = Path(gecici) / "ikinci.zip"
            kaynak_arsivi_olustur(kok, ilk, "engelsiz_mail")
            kaynak_arsivi_olustur(kok, ikinci, "engelsiz_mail")

            self.assertEqual(hashlib.sha256(ilk.read_bytes()).hexdigest(), hashlib.sha256(ikinci.read_bytes()).hexdigest())
            with zipfile.ZipFile(ilk) as arsiv:
                adlar = arsiv.namelist()

        self.assertEqual(sorted(adlar, key=str.casefold), adlar)
        self.assertFalse(any("__pycache__" in ad or ".pytest_cache" in ad for ad in adlar))
        self.assertFalse(any(ad.endswith((".pyc", ".pyo")) for ad in adlar))

    def test_internationalized_addresses_and_invalid_boundaries(self):
        with load_mail_module("validators") as validators:
            for adres in (
                "çağrı@örnek.istanbul",
                "δοκιμή@παράδειγμα.ελ",
                "kullanıcı@example.com",
                "ascii@örnek.com",
            ):
                with self.subTest(adres=adres):
                    self.assertTrue(validators.eposta_adresi_gecerli_mi(adres))

            for adres in (
                "çağrı..test@örnek.istanbul",
                ".çağrı@örnek.istanbul",
                "çağrı.@örnek.istanbul",
                "çağrı test@örnek.istanbul",
                "çağrı🙂@örnek.istanbul",
                "çağrı@-örnek.istanbul",
                "çağrı@örnek",
            ):
                with self.subTest(adres=adres):
                    self.assertFalse(validators.eposta_adresi_gecerli_mi(adres))

    def test_message_builder_preserves_internationalized_recipient(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            mesaj = smtp_client.eposta_mesaji_olustur(
                "gonderen@example.com",
                "Çağrı Şahin <çağrı@örnek.istanbul>",
                "Türkçe konu",
                "Türkçe içerik",
                [],
            )
        self.assertIn("çağrı@örnek.istanbul", str(mesaj["To"]))

    def test_contact_header_keeps_name_for_internationalized_address(self):
        with temporary_workspace() as workspace:
            global_vars = module(
                "globalVars",
                appArgs=type("AppArgs", (), {"configPath": str(workspace.config_dir)})(),
            )
            storage = module(
                "mail.storage",
                guvenli_json_oku=lambda *a, **k: [],
                guvenli_json_yaz=lambda *a, **k: True,
            )
            with load_mail_module(
                "contacts",
                stubs={"globalVars": global_vars, "mail.storage": storage},
            ) as contacts:
                baslik = contacts.kisi_eposta_basligi(
                    {"ad": "Çağrı", "soyad": "Şahin", "eposta": "çağrı@örnek.istanbul"}
                )
        self.assertEqual("Çağrı Şahin <çağrı@örnek.istanbul>", baslik)

    def test_vendored_smtplib_requests_smtputf8_for_unicode_recipient(self):
        with load_mail_module("vendor.smtplib") as vendored_smtplib:
            smtp = vendored_smtplib.SMTP.__new__(vendored_smtplib.SMTP)
            smtp.ehlo_or_helo_if_needed = lambda: None
            smtp.has_extn = lambda ad: str(ad).lower() == "smtputf8"
            yakalanan = {}

            def sendmail(from_addr, to_addrs, msg, mail_options, rcpt_options):
                yakalanan.update(
                    from_addr=from_addr,
                    to_addrs=list(to_addrs),
                    msg=msg,
                    mail_options=tuple(mail_options),
                    rcpt_options=tuple(rcpt_options),
                )
                return {}

            smtp.sendmail = sendmail
            with load_mail_module(
                "smtp_client",
                stubs={"logHandler": LOG_HANDLER},
            ) as smtp_client:
                mesaj = smtp_client.eposta_mesaji_olustur(
                    "gonderen@example.com",
                    "çağrı@örnek.istanbul",
                    "Türkçe konu",
                    "Türkçe içerik",
                    [],
                )
            sonuc = smtp.send_message(
                mesaj,
                from_addr="gonderen@example.com",
                to_addrs=["çağrı@örnek.istanbul"],
            )

        self.assertEqual({}, sonuc)
        self.assertIn("SMTPUTF8", yakalanan["mail_options"])
        self.assertIn("BODY=8BITMIME", yakalanan["mail_options"])
        self.assertIn("çağrı@örnek.istanbul", yakalanan["to_addrs"])
        self.assertIn("çağrı@örnek.istanbul".encode("utf-8"), yakalanan["msg"])

    def test_smtputf8_unsupported_error_is_explained(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            hata = smtp_client.smtplib.SMTPNotSupportedError(
                "SMTPUTF8 not supported by server"
            )
            mesaj = smtp_client.baglanti_hatasi_kullanici_mesaji(hata)
        self.assertIn("uluslararası e-posta adreslerini desteklemiyor", mesaj)

    @staticmethod
    def _method(tree: ast.Module, class_name: str, method_name: str):
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == method_name:
                        return child
        raise AssertionError(f"Yöntem bulunamadı: {class_name}.{method_name}")


if __name__ == "__main__":
    unittest.main()
