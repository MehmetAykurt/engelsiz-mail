# -*- coding: utf-8 -*-
"""Final dağıtım, belge, sürüm ve paket bütünlüğü testleri."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re
import struct
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
import zipfile


PROJE_KOKU = Path(__file__).resolve().parents[1]


class _BaglantiToplayici(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.baglantilar = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        degerler = dict(attrs)
        if degerler.get("href"):
            self.baglantilar.append(degerler["href"])


def _manifest_degerleri():
    sonuc = {}
    for satir in (PROJE_KOKU / "manifest.ini").read_text("utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        sonuc[anahtar.strip()] = deger.strip().strip('"')
    return sonuc


def _modul_yukle(ad, yol):
    spec = importlib.util.spec_from_file_location(ad, yol)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Modül yüklenemedi: {yol}")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class FinalPaketKalitesiTestleri(unittest.TestCase):
    def test_lisans_dosyasi_mevcut_ve_gpl_2(self):
        lisans = (PROJE_KOKU / "LICENSE").read_text("utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", lisans)
        self.assertIn("Version 2, June 1991", lisans)
        self.assertGreater(len(lisans), 17000)

    def test_manifest_python_ve_belge_surumu_uyumlu(self):
        manifest = _manifest_degerleri()
        version = _modul_yukle(
            "final_version",
            PROJE_KOKU / "globalPlugins" / "mail" / "version.py",
        )
        readme = (PROJE_KOKU / "doc" / "tr" / "readme.html").read_text("utf-8")
        yeni = (PROJE_KOKU / "doc" / "tr" / "ne-yeni.html").read_text("utf-8")
        surum = manifest["version"]
        self.assertEqual(surum, version.EKLENTI_SURUMU)
        self.assertIn(f"<strong>Sürüm:</strong> {surum}", readme)
        self.assertIn(f"Engelsiz Mail {surum}", yeni)
        self.assertEqual(manifest["name"], "engelsiz_mail")
        self.assertEqual(manifest["docFileName"], "readme.html")

    def test_html_belgelerindeki_yerel_baglantilar_gecerli(self):
        hatalar = []
        for belge in sorted((PROJE_KOKU / "doc").rglob("*.html")):
            toplayici = _BaglantiToplayici()
            toplayici.feed(belge.read_text("utf-8"))
            for href in toplayici.baglantilar:
                parcalar = urlsplit(href)
                if parcalar.scheme or parcalar.netloc or href.startswith(("mailto:", "#")):
                    continue
                hedef = (belge.parent / unquote(parcalar.path)).resolve()
                try:
                    hedef.relative_to(PROJE_KOKU.resolve())
                except ValueError:
                    hatalar.append(f"{belge}: proje dışına çıkan bağlantı: {href}")
                    continue
                if not hedef.exists():
                    hatalar.append(f"{belge}: bulunamayan bağlantı: {href}")
        self.assertEqual(hatalar, [])

    def test_vendor_ozetleri_belgelerle_uyumlu(self):
        vendor = PROJE_KOKU / "globalPlugins" / "mail" / "vendor"
        source = (vendor / "SOURCE.txt").read_text("utf-8")
        for ad in ("imaplib.py", "smtplib.py", "PYTHON_LICENSE.txt"):
            ozet = hashlib.sha256((vendor / ad).read_bytes()).hexdigest()
            self.assertIn(ozet, source, ad)

        sqlite_dir = vendor / "sqlite_native"
        sqlite_belgesi = (sqlite_dir / "README.txt").read_text("utf-8")
        for ad in ("_sqlite3.pyd", "sqlite3.dll"):
            ozet = hashlib.sha256((sqlite_dir / ad).read_bytes()).hexdigest()
            self.assertIn(ozet, sqlite_belgesi, ad)

    def test_sqlite_ikili_dosyalari_windows_x64(self):
        sqlite_dir = PROJE_KOKU / "globalPlugins" / "mail" / "vendor" / "sqlite_native"
        for ad in ("_sqlite3.pyd", "sqlite3.dll"):
            veri = (sqlite_dir / ad).read_bytes()
            self.assertTrue(veri.startswith(b"MZ"), ad)
            pe_konumu = struct.unpack_from("<I", veri, 0x3C)[0]
            self.assertEqual(veri[pe_konumu:pe_konumu + 4], b"PE\0\0", ad)
            makine = struct.unpack_from("<H", veri, pe_konumu + 4)[0]
            self.assertEqual(makine, 0x8664, ad)

    def test_uretim_kodunda_gelistirme_kalintisi_yok(self):
        desen = re.compile(r"\b(?:TODO|FIXME|HACK|breakpoint)\b|\bpdb\.", re.IGNORECASE)
        hatalar = []
        for yol in sorted((PROJE_KOKU / "globalPlugins" / "mail").rglob("*.py")):
            if "vendor" in yol.parts:
                continue
            for no, satir in enumerate(yol.read_text("utf-8").splitlines(), 1):
                if desen.search(satir):
                    hatalar.append(f"{yol.relative_to(PROJE_KOKU)}:{no}: {satir.strip()}")
        self.assertEqual(hatalar, [])

    def test_nvda_addon_temiz_ve_yeniden_uretilebilir(self):
        arac = _modul_yukle(
            "final_addon_builder",
            PROJE_KOKU / "tools" / "build_addon_package.py",
        )
        with tempfile.TemporaryDirectory() as gecici:
            ilk = Path(gecici) / "ilk.nvda-addon"
            ikinci = Path(gecici) / "ikinci.nvda-addon"
            arac.eklenti_paketi_olustur(PROJE_KOKU, ilk)
            arac.eklenti_paketi_olustur(PROJE_KOKU, ikinci)
            self.assertEqual(ilk.read_bytes(), ikinci.read_bytes())
            with zipfile.ZipFile(ilk) as arsiv:
                adlar = arsiv.namelist()
                self.assertIn("manifest.ini", adlar)
                self.assertIn("LICENSE", adlar)
                self.assertIn("doc/tr/readme.html", adlar)
                self.assertIn("globalPlugins/mail/__init__.py", adlar)
                self.assertFalse(any(ad.startswith("engelsiz_mail/") for ad in adlar))
                self.assertFalse(any(ad.startswith(("tests/", "tools/")) for ad in adlar))
                self.assertFalse(any("__pycache__" in ad for ad in adlar))
                self.assertFalse(any(ad.lower().endswith((".pyc", ".pyo")) for ad in adlar))
                self.assertEqual(len(adlar), len(set(adlar)))


if __name__ == "__main__":
    unittest.main()
