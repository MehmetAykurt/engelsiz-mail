# -*- coding: utf-8 -*-
"""11. çalışma / 8. aşama: Engelsiz Mail 1.8.2 final yerelleştirme ve paket sözleşmeleri."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

from babel.messages import pofile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.8.2"


def _manifest_values(path: Path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Modül yüklenemedi: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Final182Tests(unittest.TestCase):
    def test_all_primary_version_sources_are_182(self):
        manifest = _manifest_values(PROJECT_ROOT / "manifest.ini")
        version = _load_module("stage11_final_version", PROJECT_ROOT / "globalPlugins" / "mail" / "version.py")
        self.assertEqual(VERSION, manifest["version"])
        self.assertEqual(VERSION, version.EKLENTI_SURUMU)

    def test_turkish_and_english_documents_publish_182(self):
        tr_readme = (PROJECT_ROOT / "doc" / "tr" / "readme.html").read_text(encoding="utf-8")
        en_readme = (PROJECT_ROOT / "doc" / "en" / "readme.html").read_text(encoding="utf-8")
        tr_new = (PROJECT_ROOT / "doc" / "tr" / "ne-yeni.html").read_text(encoding="utf-8")
        en_new = (PROJECT_ROOT / "doc" / "en" / "ne-yeni.html").read_text(encoding="utf-8")
        self.assertIn(f"<strong>Sürüm:</strong> {VERSION}", tr_readme)
        self.assertIn(f"<strong>Version:</strong> {VERSION}", en_readme)
        self.assertIn(f"Engelsiz Mail {VERSION} Sürümündeki Yenilikler", tr_new)
        self.assertIn(f"What's New in Engelsiz Mail {VERSION}", en_new)
        self.assertIn("İngilizce dil desteği eklendi.", tr_new)
        self.assertIn("English language support was added.", en_new)
        self.assertIn("çalışma hızı artırıldı", tr_new)
        self.assertIn("overall speed was improved", en_new)

    def test_pot_and_po_metadata_publish_180(self):
        for relative in ("locale/nvda.pot", "locale/en/LC_MESSAGES/nvda.po"):
            path = PROJECT_ROOT / relative
            with path.open("r", encoding="utf-8") as file:
                catalog = pofile.read_po(file)
            self.assertEqual(VERSION, catalog.version, relative)
            self.assertEqual("Engelsiz Mail", catalog.project, relative)

    def test_english_catalog_is_complete_for_final_source(self):
        pot = PROJECT_ROOT / "locale" / "nvda.pot"
        po = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.po"
        with pot.open("r", encoding="utf-8") as file:
            template = pofile.read_po(file)
        with po.open("r", encoding="utf-8") as file:
            english = pofile.read_po(file)
        source_ids = {message.id for message in template if message.id}
        translations = {message.id: message.string for message in english if message.id}
        self.assertEqual(861, len(source_ids))
        self.assertEqual(source_ids, set(translations))
        self.assertFalse([key for key, value in translations.items() if not value])

    def test_final_addon_contains_runtime_localization_only(self):
        builder = _load_module("stage11_final_builder", PROJECT_ROOT / "tools" / "build_addon_package.py")
        with tempfile.TemporaryDirectory() as temp:
            addon = Path(temp) / f"EngelsizMail-{VERSION}.nvda-addon"
            builder.eklenti_paketi_olustur(PROJECT_ROOT, addon)
            with zipfile.ZipFile(addon) as archive:
                names = set(archive.namelist())
                manifest = archive.read("manifest.ini").decode("utf-8")
            self.assertIn(f'version = "{VERSION}"', manifest)
            self.assertIn("doc/tr/readme.html", names)
            self.assertIn("doc/en/readme.html", names)
            self.assertIn("doc/tr/ne-yeni.html", names)
            self.assertIn("doc/en/ne-yeni.html", names)
            self.assertIn("locale/en/manifest.ini", names)
            self.assertIn("locale/en/LC_MESSAGES/nvda.mo", names)
            self.assertNotIn("locale/en/LC_MESSAGES/nvda.po", names)
            self.assertNotIn("locale/nvda.pot", names)

    def test_source_and_addon_builders_remain_reproducible(self):
        source_builder = _load_module("stage11_final_source_builder", PROJECT_ROOT / "tools" / "build_source_archive.py")
        addon_builder = _load_module("stage11_final_addon_builder2", PROJECT_ROOT / "tools" / "build_addon_package.py")
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            z1, z2 = temp / "a.zip", temp / "b.zip"
            a1, a2 = temp / "a.nvda-addon", temp / "b.nvda-addon"
            source_builder.kaynak_arsivi_olustur(PROJECT_ROOT, z1, "engelsiz_mail")
            source_builder.kaynak_arsivi_olustur(PROJECT_ROOT, z2, "engelsiz_mail")
            addon_builder.eklenti_paketi_olustur(PROJECT_ROOT, a1)
            addon_builder.eklenti_paketi_olustur(PROJECT_ROOT, a2)
            self.assertEqual(z1.read_bytes(), z2.read_bytes())
            self.assertEqual(a1.read_bytes(), a2.read_bytes())


if __name__ == "__main__":
    unittest.main()
