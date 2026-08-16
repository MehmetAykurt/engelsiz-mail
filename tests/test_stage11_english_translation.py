# -*- coding: utf-8 -*-
"""11. çalışma / 5. aşama: İngilizce dil dosyası ve belge sözleşmeleri."""

from __future__ import annotations

from pathlib import Path
import gettext
import io
import re
import tempfile
import types
import unittest
import zipfile

from babel.messages import pofile

from support.module_loader import PROJECT_ROOT, load_mail_module, module


POT = PROJECT_ROOT / "locale" / "nvda.pot"
PO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.po"
MO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.mo"


class IngilizceCeviriTestleri(unittest.TestCase):
    def test_ingilizce_katalog_tam_ve_bos_ceviri_yok(self):
        with POT.open("r", encoding="utf-8") as f:
            pot = pofile.read_po(f)
        with PO.open("r", encoding="utf-8") as f:
            po = pofile.read_po(f)
        pot_ids = {m.id for m in pot if m.id}
        po_map = {m.id: m.string for m in po if m.id}
        self.assertEqual(861, len(pot_ids))
        self.assertEqual(pot_ids, set(po_map))
        self.assertEqual([], [mid for mid, text in po_map.items() if not text])

    def test_yer_tutucular_ingilizcede_korunur(self):
        brace = re.compile(r"\{[^{}]+\}")
        with PO.open("r", encoding="utf-8") as f:
            po = pofile.read_po(f)
        sorunlar = []
        for m in po:
            if not m.id:
                continue
            if sorted(brace.findall(m.id)) != sorted(brace.findall(m.string or "")):
                sorunlar.append(m.id)
        self.assertEqual([], sorunlar)

    def test_mo_dosyasi_gercek_gettext_cevirisi_yapar(self):
        with MO.open("rb") as f:
            tr = gettext.GNUTranslations(f)
        self.assertEqual("Email sent successfully.", tr.gettext("E-posta başarıyla gönderildi."))
        self.assertEqual("Inbox", tr.gettext("Gelen Kutusu"))
        self.assertEqual("&Notifications...", tr.gettext("&Bildirimler..."))
        self.assertEqual(
            "The What's New file could not be found. Check the add-on folder.",
            tr.gettext("Yenilikler dosyası bulunamadı. Lütfen eklenti klasörünü denetleyin."),
        )
        self.assertEqual(
            r"(?m)^\d+\. message\r?\nFrom:",
            tr.gettext(r"(?m)^\d+\. ileti\r?\nKimden:"),
        )

    def test_ingilizce_manifest_ve_belgeler_var(self):
        manifest = (PROJECT_ROOT / "locale" / "en" / "manifest.ini").read_text(encoding="utf-8")
        self.assertIn('summary = "Engelsiz Mail"', manifest)
        self.assertIn('description = "Engelsiz Mail is an accessible email add-on', manifest)
        readme = (PROJECT_ROOT / "doc" / "en" / "readme.html").read_text(encoding="utf-8")
        yeni = (PROJECT_ROOT / "doc" / "en" / "ne-yeni.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', readme)
        self.assertIn("Engelsiz Mail NVDA Add-on - User Guide", readme)
        self.assertIn('<html lang="en">', yeni)
        self.assertIn("What's New in Engelsiz Mail 1.8.2", yeni)

    def test_belge_yolu_nvda_diline_gore_ingilizce_ve_turkce_secilir(self):
        global_vars = module("globalVars", appArgs=types.SimpleNamespace(configPath="/tmp/nvda-test"))
        language = module("languageHandler", getLanguage=lambda: "en_US")
        with load_mail_module("paths", stubs={"globalVars": global_vars, "languageHandler": language}) as paths:
            self.assertEqual("en", paths.belge_dili_klasoru())
            self.assertTrue(paths.yerellestirilmis_belge_yolu("readme.html").replace("\\", "/").endswith("/doc/en/readme.html"))
        language_tr = module("languageHandler", getLanguage=lambda: "tr")
        with load_mail_module("paths", stubs={"globalVars": global_vars, "languageHandler": language_tr}) as paths:
            self.assertEqual("tr", paths.belge_dili_klasoru())
            self.assertTrue(paths.yerellestirilmis_belge_yolu("readme.html").replace("\\", "/").endswith("/doc/tr/readme.html"))

    def test_kurulabilir_paket_ingilizce_dosyalarini_alir_po_pot_almaz(self):
        import importlib.util
        tool_path = PROJECT_ROOT / "tools" / "build_addon_package.py"
        spec = importlib.util.spec_from_file_location("build_addon_package_stage11_en", tool_path)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "test.nvda-addon"
            tool.eklenti_paketi_olustur(PROJECT_ROOT, target)
            with zipfile.ZipFile(target) as zf:
                names = set(zf.namelist())
            self.assertIn("locale/en/manifest.ini", names)
            self.assertIn("locale/en/LC_MESSAGES/nvda.mo", names)
            self.assertIn("doc/en/readme.html", names)
            self.assertIn("doc/en/ne-yeni.html", names)
            self.assertNotIn("locale/en/LC_MESSAGES/nvda.po", names)
            self.assertNotIn("locale/nvda.pot", names)


if __name__ == "__main__":
    unittest.main()
