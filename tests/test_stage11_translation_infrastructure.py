# -*- coding: utf-8 -*-
"""11. çalışma / 4. aşama: NVDA çeviri altyapısı sözleşmeleri."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import tempfile
import types
import unittest
import zipfile

from support.module_loader import MAIL_ROOT, load_mail_module, module

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _addon_handler_cevirisi(harita):
    fake = types.ModuleType("addonHandler")

    def initTranslation():
        hedef = inspect.currentframe().f_back.f_globals
        hedef["_"] = lambda metin: harita.get(metin, metin)

    fake.initTranslation = initTranslation
    return fake


class CeviriAltyapisiTestleri(unittest.TestCase):
    def test_cevirilebilir_python_modulleri_init_translation_cagirir(self):
        eksikler = []
        for yol in MAIL_ROOT.rglob("*.py"):
            if "vendor" in yol.parts:
                continue
            kaynak = yol.read_text(encoding="utf-8")
            agac = ast.parse(kaynak)
            ceviri_var = any(
                isinstance(oge, ast.Call)
                and isinstance(oge.func, ast.Name)
                and oge.func.id in {"_", "ngettext", "pgettext", "npgettext"}
                for oge in ast.walk(agac)
            )
            if ceviri_var and "addonHandler.initTranslation()" not in kaynak:
                eksikler.append(yol.relative_to(PROJECT_ROOT).as_posix())
        self.assertEqual([], eksikler)

    def test_sistem_klasoru_ic_degeri_sabit_gorunumu_cevrilebilir(self):
        addon_handler = _addon_handler_cevirisi({"Gelen Kutusu": "Inbox"})
        logger = module("mail.logger", hata_kaydet=lambda *args, **kwargs: None)
        with load_mail_module(
            "folders",
            stubs={"addonHandler": addon_handler, "mail.logger": logger},
        ) as folders:
            self.assertEqual("Gelen Kutusu", folders.SISTEM_KLASORLERI[0])
            self.assertEqual("INBOX", folders.VARSAYILAN_KLASOR_HARITASI["Gelen Kutusu"])
            self.assertEqual("Inbox", folders.klasor_gorunen_adi("Gelen Kutusu"))
            self.assertEqual("Özel Arşiv", folders.klasor_gorunen_adi("Özel Arşiv"))


    def test_gorunum_ayarlarinin_ic_anahtarlari_sabit_gorunen_adlari_cevrilebilir(self):
        from support.fakes import FakeWx
        addon_handler = _addon_handler_cevirisi({
            "Kalın": "Bold",
            "Siyah": "Black",
            "Açık Mavi": "Light Blue",
        })
        wx = FakeWx()
        stubs = {
            "addonHandler": addon_handler,
            "wx": wx,
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.paths": module("mail.paths", AYARLAR_DOSYASI="settings.json"),
            "mail.security": module("mail.security", uygulama_sifresini_sifrele=lambda x: x, uygulama_sifresini_coz=lambda x: x),
            "mail.storage": module("mail.storage", guvenli_json_oku=lambda *a, **k: {}, guvenli_json_guncelle=lambda *a, **k: True),
            "mail.validators": module("mail.validators", bildirim_ses_dosyasi_duzenle=lambda x: x),
        }
        with load_mail_module("config", stubs=stubs) as config:
            self.assertIn("Kalın", config.GORUNUM_YAZI_STILI_SECENEKLERI)
            self.assertIn("Siyah", config.GORUNUM_METIN_RENKLERI)
            self.assertIn("Açık Mavi", config.GORUNUM_ARKA_PLAN_RENKLERI)
            self.assertEqual("Bold", config.gorunum_yazi_stili_gorunen_adi("Kalın"))
            self.assertEqual("Black", config.gorunum_metin_rengi_gorunen_adi("Siyah"))
            self.assertEqual("Light Blue", config.gorunum_arka_plan_rengi_gorunen_adi("Açık Mavi"))

    def test_okunmadi_etiketi_cevrilmis_ve_eski_turkce_bicimleri_tanir(self):
        addon_handler = _addon_handler_cevirisi({
            "[Okunmadı] ": "[Unread] ",
            "Okunmadı - ": "Unread - ",
        })
        folders = module(
            "mail.folders",
            VARSAYILAN_KLASOR_HARITASI={
                "Gelen Kutusu": "INBOX", "Çöp Kutusu": "Trash", "Spam": "Spam",
                "Gönderilen E-postalar": "Sent", "Taslaklar": "Drafts", "Tüm Postalar": "All",
            },
            imap_klasor_adi_hazirla=lambda x: x,
        )
        imap_client = module(
            "mail.imap_client",
            imap_gmail_etiket_store=lambda *a, **k: None,
            imap_uidleri_kaynak_klasorden_cikar=lambda *a, **k: None,
        )
        with load_mail_module(
            "gmail_actions",
            stubs={
                "addonHandler": addon_handler,
                "mail.folders": folders,
                "mail.imap_client": imap_client,
            },
        ) as actions:
            self.assertEqual("Mehmet", actions.okunmadi_etiketini_kaldir("[Unread] Mehmet"))
            self.assertEqual("Mehmet", actions.okunmadi_etiketini_kaldir("[Okunmadı] Mehmet"))

    def test_paketleyici_locale_dosyalarini_alir_po_pot_dosyalarini_almaz(self):
        import importlib.util
        arac_yolu = PROJECT_ROOT / "tools" / "build_addon_package.py"
        spec = importlib.util.spec_from_file_location("build_addon_package_stage11", arac_yolu)
        arac = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(arac)
        with tempfile.TemporaryDirectory() as gecici:
            kok = Path(gecici) / "src"
            (kok / "globalPlugins").mkdir(parents=True)
            (kok / "doc").mkdir()
            (kok / "locale" / "en" / "LC_MESSAGES").mkdir(parents=True)
            (kok / "manifest.ini").write_text("name = engelsizMail\nsummary = Engelsiz Mail\n", encoding="utf-8")
            (kok / "LICENSE").write_text("test", encoding="utf-8")
            (kok / "globalPlugins" / "a.py").write_text("x=1\n", encoding="utf-8")
            (kok / "doc" / "x.txt").write_text("doc", encoding="utf-8")
            (kok / "locale" / "en" / "manifest.ini").write_text("summary=Accessible Mail\n", encoding="utf-8")
            (kok / "locale" / "en" / "LC_MESSAGES" / "nvda.mo").write_bytes(b"MO")
            (kok / "locale" / "en" / "LC_MESSAGES" / "nvda.po").write_text("PO", encoding="utf-8")
            (kok / "locale" / "nvda.pot").write_text("POT", encoding="utf-8")
            hedef = Path(gecici) / "test.nvda-addon"
            arac.eklenti_paketi_olustur(kok, hedef)
            with zipfile.ZipFile(hedef) as zf:
                adlar = set(zf.namelist())
            self.assertIn("locale/en/manifest.ini", adlar)
            self.assertIn("locale/en/LC_MESSAGES/nvda.mo", adlar)
            self.assertNotIn("locale/en/LC_MESSAGES/nvda.po", adlar)
            self.assertNotIn("locale/nvda.pot", adlar)

    def test_ortak_kullanici_arayuzu_cagrilarinda_ciplak_metin_yok(self):
        cagrilar = {
            "message": {0}, "messageBox": {0, 1}, "MessageBox": {0, 1}, "MailHatasi": {0},
            "SetName": {0}, "SetTitle": {0}, "SetLabel": {0}, "SetToolTip": {0},
            "InsertColumn": {1}, "mesaj_soyle_ve_sonra_calistir": {0}, "bildirim_soyle": {0},
        }
        sorunlar = []
        for yol in MAIL_ROOT.rglob("*.py"):
            if "vendor" in yol.parts:
                continue
            agac = ast.parse(yol.read_text(encoding="utf-8"))
            for oge in ast.walk(agac):
                if not isinstance(oge, ast.Call):
                    continue
                if isinstance(oge.func, ast.Name):
                    ad = oge.func.id
                elif isinstance(oge.func, ast.Attribute):
                    ad = oge.func.attr
                else:
                    continue
                for indeks in cagrilar.get(ad, set()):
                    if indeks >= len(oge.args):
                        continue
                    arg = oge.args[indeks]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.strip():
                        sorunlar.append(f"{yol.name}:{arg.lineno}:{ad}:{arg.value}")
        self.assertEqual([], sorunlar)


if __name__ == "__main__":
    unittest.main()
