# -*- coding: utf-8 -*-
"""11. çalışma / 7. aşama: yerelleştirme bütünlüğü ve dağıtım sözleşmeleri."""

from __future__ import annotations

import ast
import gettext
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re
import tempfile
import types
import unittest

from babel.messages import Catalog, pofile
from babel.messages.pofile import write_po

from support.module_loader import MAIL_ROOT, PROJECT_ROOT, load_mail_module, module


POT = PROJECT_ROOT / "locale" / "nvda.pot"
PO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.po"
MO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.mo"
BRACE = re.compile(r"\{[^{}]+\}")


def _modul_yukle(ad: str, yol: Path):
    spec = importlib.util.spec_from_file_location(ad, yol)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Modül yüklenemedi: {yol}")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _manifest_degerleri(yol: Path):
    sonuc = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        sonuc[anahtar.strip()] = deger.strip().strip('"')
    return sonuc


def _cagri_adi(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _harfli_sabit(node):
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.strip()
        and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", node.value)
    )


class _HtmlBilgisi(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = None
        self.idler = set()
        self.yerel_capalar = set()

    def handle_starttag(self, tag, attrs):
        degerler = dict(attrs)
        if tag.lower() == "html":
            self.html_lang = degerler.get("lang")
        if degerler.get("id"):
            self.idler.add(degerler["id"])
        href = degerler.get("href")
        if tag.lower() == "a" and href and href.startswith("#") and len(href) > 1:
            self.yerel_capalar.add(href[1:])


class YerellestirmeButunluguTestleri(unittest.TestCase):
    def test_pot_kaynaktan_bayt_duzeyinde_yeniden_uretilebilir(self):
        arac = _modul_yukle("stage11_extract", PROJECT_ROOT / "tools" / "extract_translations.py")
        with tempfile.TemporaryDirectory() as gecici:
            hedef = Path(gecici) / "nvda.pot"
            arac.ceviri_sablonunu_olustur(PROJECT_ROOT, hedef)
            self.assertEqual(POT.read_bytes(), hedef.read_bytes())

    def test_mo_po_dan_bayt_duzeyinde_yeniden_uretilebilir(self):
        arac = _modul_yukle("stage11_compile", PROJECT_ROOT / "tools" / "compile_translations.py")
        with tempfile.TemporaryDirectory() as gecici:
            hedef = Path(gecici) / "nvda.mo"
            arac.ceviriyi_derle(PO, hedef)
            self.assertEqual(MO.read_bytes(), hedef.read_bytes())

    def test_po_katalog_metadata_ve_durum_bilgileri_temiz(self):
        metin = PO.read_text(encoding="utf-8")
        with PO.open("r", encoding="utf-8") as dosya:
            katalog = pofile.read_po(dosya)
        version = _modul_yukle("stage11_version", MAIL_ROOT / "version.py")
        self.assertEqual("en", str(katalog.locale))
        self.assertEqual("Engelsiz Mail", katalog.project)
        self.assertEqual(version.EKLENTI_SURUMU, katalog.version)
        self.assertEqual([], [m.id for m in katalog if m.id and "fuzzy" in m.flags])
        self.assertEqual({}, katalog.obsolete)
        self.assertNotIn("FIRST AUTHOR <EMAIL@ADDRESS>", metin)
        self.assertNotIn("FULL NAME <EMAIL@ADDRESS>", metin)
        self.assertNotIn("LANGUAGE <LL@li.org>", metin)

    def test_po_ve_mo_tum_cevirilerde_birebir_uyumlu(self):
        with PO.open("r", encoding="utf-8") as dosya:
            katalog = pofile.read_po(dosya)
        with MO.open("rb") as dosya:
            ceviriler = gettext.GNUTranslations(dosya)
        sorunlar = []
        for mesaj in katalog:
            if not mesaj.id:
                continue
            if ceviriler.gettext(mesaj.id) != mesaj.string:
                sorunlar.append(mesaj.id)
        self.assertEqual([], sorunlar)

    def test_yer_tutucular_ve_python_brace_format_bayraklari_tam(self):
        sorunlar = []
        for yol in (POT, PO):
            with yol.open("r", encoding="utf-8") as dosya:
                katalog = pofile.read_po(dosya)
            for mesaj in katalog:
                if not mesaj.id:
                    continue
                kaynak = mesaj.id if isinstance(mesaj.id, str) else "\n".join(mesaj.id)
                ceviri = mesaj.string if isinstance(mesaj.string, str) else "\n".join(mesaj.string or ())
                kaynak_yer_tutucular = sorted(BRACE.findall(kaynak))
                if kaynak_yer_tutucular and "python-brace-format" not in mesaj.flags:
                    sorunlar.append(f"{yol.name}: brace bayrağı yok: {mesaj.id}")
                if yol == PO and kaynak_yer_tutucular != sorted(BRACE.findall(ceviri)):
                    sorunlar.append(f"{yol.name}: yer tutucu uyuşmazlığı: {mesaj.id}")
        self.assertEqual([], sorunlar)

    def test_ceviri_derleyicisi_belirsiz_ve_yer_tutucusu_bozuk_ceviriyi_reddeder(self):
        arac = _modul_yukle("stage11_compile_reject", PROJECT_ROOT / "tools" / "compile_translations.py")
        with tempfile.TemporaryDirectory() as gecici:
            gecici = Path(gecici)

            katalog = Catalog(locale="en")
            mesaj = katalog.add("Değer: {0}", "Value")
            po_yolu = gecici / "placeholder.po"
            with po_yolu.open("wb") as dosya:
                write_po(dosya, katalog)
            with self.assertRaisesRegex(ValueError, "yer tutucu uyuşmazlığı"):
                arac.ceviriyi_derle(po_yolu, gecici / "placeholder.mo")

            katalog = Catalog(locale="en")
            mesaj = katalog.add("Bağlan", "Connect")
            mesaj.flags.add("fuzzy")
            po_yolu = gecici / "fuzzy.po"
            with po_yolu.open("wb") as dosya:
                write_po(dosya, katalog)
            with self.assertRaisesRegex(ValueError, "fuzzy"):
                arac.ceviriyi_derle(po_yolu, gecici / "fuzzy.mo")

    def test_teknik_protokol_degerleri_ceviri_katalogunda_yok(self):
        with POT.open("r", encoding="utf-8") as dosya:
            katalog = pofile.read_po(dosya)
        msgidler = {m.id for m in katalog if m.id}
        self.assertNotIn(r"(\Seen)", msgidler)
        self.assertNotIn("/select,", msgidler)

        message_actions = (MAIL_ROOT / "ui" / "message_actions.py").read_text(encoding="utf-8")
        other_addons = (MAIL_ROOT / "ui" / "other_addons.py").read_text(encoding="utf-8")
        self.assertIn('"(\\\\Seen)"', message_actions)
        self.assertNotIn('_("(\\\\Seen)")', message_actions)
        self.assertIn('"/select,"', other_addons)
        self.assertNotIn('_("/select,")', other_addons)

    def test_genisletilmis_arayuz_taramasinda_ciplak_sabit_metin_yok(self):
        # İlk altyapı testindeki çağrılara ek olarak wx kurucularını ve menü
        # Append/AppendSubMenu çağrılarını da tarar.
        yontem_argumanlari = {
            "message": {0}, "messageBox": {0, 1}, "MessageBox": {0, 1},
            "MailHatasi": {0}, "SetName": {0}, "SetTitle": {0}, "SetLabel": {0},
            "SetToolTip": {0}, "InsertColumn": {1}, "Append": {1}, "AppendSubMenu": {1},
            "mesaj_soyle_ve_sonra_calistir": {0}, "bildirim_soyle": {0},
        }
        kurucu_pozisyonlari = {
            "Button": {2}, "StaticText": {2}, "CheckBox": {2}, "RadioButton": {2},
            "Dialog": {2}, "Frame": {2}, "MessageDialog": {1, 2},
            "SingleChoiceDialog": {1, 2}, "MultiChoiceDialog": {1, 2}, "TextEntryDialog": {1, 2},
        }
        kurucu_anahtarlar = {
            "Button": {"label"}, "StaticText": {"label"}, "CheckBox": {"label"},
            "RadioButton": {"label"}, "Dialog": {"title"}, "Frame": {"title"},
            "MessageDialog": {"message", "caption"},
            "SingleChoiceDialog": {"message", "caption"},
            "MultiChoiceDialog": {"message", "caption"},
            "TextEntryDialog": {"message", "caption"},
        }
        sorunlar = []
        for yol in MAIL_ROOT.rglob("*.py"):
            if "vendor" in yol.parts:
                continue
            agac = ast.parse(yol.read_text(encoding="utf-8"))
            for oge in ast.walk(agac):
                if not isinstance(oge, ast.Call):
                    continue
                ad = _cagri_adi(oge.func)
                for indeks in yontem_argumanlari.get(ad, ()):
                    if indeks < len(oge.args) and _harfli_sabit(oge.args[indeks]):
                        sorunlar.append(f"{yol.relative_to(PROJECT_ROOT)}:{oge.args[indeks].lineno}:{ad}")
                for indeks in kurucu_pozisyonlari.get(ad, ()):
                    if indeks < len(oge.args) and _harfli_sabit(oge.args[indeks]):
                        sorunlar.append(f"{yol.relative_to(PROJECT_ROOT)}:{oge.args[indeks].lineno}:{ad}")
                for anahtar in oge.keywords:
                    if anahtar.arg in kurucu_anahtarlar.get(ad, ()) and _harfli_sabit(anahtar.value):
                        sorunlar.append(f"{yol.relative_to(PROJECT_ROOT)}:{anahtar.value.lineno}:{ad}.{anahtar.arg}")
        self.assertEqual([], sorunlar)

    def test_ingilizce_manifest_yalniz_yerellestirilebilir_alanlari_icerir(self):
        kok = _manifest_degerleri(PROJECT_ROOT / "manifest.ini")
        en = _manifest_degerleri(PROJECT_ROOT / "locale" / "en" / "manifest.ini")
        self.assertEqual({"summary", "description"}, set(en))
        self.assertEqual(kok["summary"], en["summary"])
        self.assertTrue(en["description"].strip())
        self.assertFalse(any(h in en["description"] for h in "çğıöşüÇĞİÖŞÜ"))

    def test_belge_dili_en_varyantlarini_destekler_diger_diller_turkceye_doner(self):
        global_vars = module("globalVars", appArgs=types.SimpleNamespace(configPath="/tmp/nvda-test"))
        for dil, beklenen in (("en", "en"), ("en_US", "en"), ("en-GB", "en"), ("EN_us", "en"),
                              ("tr", "tr"), ("tr_TR", "tr"), ("de_DE", "tr"), ("", "tr")):
            with self.subTest(dil=dil):
                language = module("languageHandler", getLanguage=lambda d=dil: d)
                with load_mail_module("paths", stubs={"globalVars": global_vars, "languageHandler": language}) as paths:
                    self.assertEqual(beklenen, paths.belge_dili_klasoru())

        def hata():
            raise RuntimeError("language unavailable")
        language = module("languageHandler", getLanguage=hata)
        with load_mail_module("paths", stubs={"globalVars": global_vars, "languageHandler": language}) as paths:
            self.assertEqual("tr", paths.belge_dili_klasoru())

    def test_turkce_ve_ingilizce_html_belgeleri_dil_ve_capa_butunlugunu_korur(self):
        for ad in ("readme.html", "ne-yeni.html"):
            bilgiler = {}
            for dil in ("tr", "en"):
                yol = PROJECT_ROOT / "doc" / dil / ad
                parser = _HtmlBilgisi()
                parser.feed(yol.read_text(encoding="utf-8"))
                self.assertEqual(dil, parser.html_lang)
                self.assertEqual(set(), parser.yerel_capalar - parser.idler, f"{dil}/{ad}")
                bilgiler[dil] = parser
            # Yerelleştirilmiş belgelerde bağlantı verilen bölüm kimliklerinin yapısı korunmalıdır.
            self.assertEqual(bilgiler["tr"].yerel_capalar, bilgiler["en"].yerel_capalar, ad)

    def test_ingilizceyle_ayni_kalan_ceviriler_yalniz_bilincli_izin_listesinde(self):
        izin = {
            "Engelsiz Mail", "&Engelsiz Mail", "Normal", "Spam",
            "{0}, {1}.", "Engelsiz Nota",
        }
        with PO.open("r", encoding="utf-8") as dosya:
            katalog = pofile.read_po(dosya)
        ayni = {m.id for m in katalog if m.id and m.id == m.string}
        self.assertEqual(izin, ayni)


if __name__ == "__main__":
    unittest.main()
