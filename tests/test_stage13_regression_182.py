# -*- coding: utf-8 -*-
"""1.8.2 açılış regresyonu düzeltmeleri ve paket sözleşmeleri."""

from pathlib import Path
import ast
import types
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RegresyonSurumu182Testleri(unittest.TestCase):
    def test_wx_newidref_referanslari_erken_kaybedilmiyor(self):
        kaynak = (PROJECT_ROOT / "globalPlugins/mail/ui/main_window.py").read_text(encoding="utf-8")
        self.assertNotIn("wx.NewId()", kaynak)
        self.assertNotIn("int(wx.NewIdRef())", kaynak)
        self.assertIn("self._wx_id_refs = []", kaynak)
        self.assertIn("kimlik_ref = wx.NewIdRef()", kaynak)
        self.assertIn("self._wx_id_refs.append(kimlik_ref)", kaynak)
        self.assertIn("return int(kimlik_ref)", kaynak)
        self.assertIn("hedef_id_refleri = []", kaynak)
        self.assertIn("hedef_id_refleri.append(hedef_id_ref)", kaynak)

    def test_yeni_wx_id_gercek_metot_govdesi_referansi_sakliyor(self):
        kaynak_yolu = PROJECT_ROOT / "globalPlugins/mail/ui/main_window.py"
        agac = ast.parse(kaynak_yolu.read_text(encoding="utf-8"))
        sinif = next(dugum for dugum in agac.body if isinstance(dugum, ast.ClassDef) and dugum.name == "GelenKutusuPenceresi")
        metot = next(dugum for dugum in sinif.body if isinstance(dugum, ast.FunctionDef) and dugum.name == "_yeni_wx_id")
        modul_agaci = ast.Module(body=[metot], type_ignores=[])
        ast.fix_missing_locations(modul_agaci)

        class Ref:
            def __init__(self, deger):
                self.deger = deger

            def __int__(self):
                return self.deger

        uretilen = []
        wx = types.SimpleNamespace(NewIdRef=lambda: uretilen.append(Ref(7301)) or uretilen[-1])
        alan = {"wx": wx}
        exec(compile(modul_agaci, str(kaynak_yolu), "exec"), alan)
        nesne = types.SimpleNamespace(_wx_id_refs=[])
        sonuc = alan["_yeni_wx_id"](nesne)
        self.assertEqual(7301, sonuc)
        self.assertEqual(1, len(nesne._wx_id_refs))
        self.assertIs(uretilen[0], nesne._wx_id_refs[0])

    def test_imza_silme_standart_wx_kimligi_kullaniyor(self):
        kaynak = (PROJECT_ROOT / "globalPlugins/mail/ui/signature_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("wx.NewId()", kaynak)
        self.assertNotIn("wx.NewIdRef()", kaynak)
        self.assertIn("IMZA_SIL_ID = wx.ID_DELETE", kaynak)

    def test_nvda_ui_modulu_alt_paketle_cakismiyor(self):
        kaynak = (PROJECT_ROOT / "globalPlugins/mail/__init__.py").read_text(encoding="utf-8")
        self.assertIn("import ui as nvda_ui", kaynak)
        self.assertNotIn("\nimport ui\n", kaynak)
        self.assertIn("nvda_ui.message(", kaynak)
        self.assertNotIn("ui.message(", kaynak.replace("nvda_ui.message(", ""))

    def test_mime_iyilestirmesi_korundu(self):
        kaynak = (PROJECT_ROOT / "globalPlugins/mail/body_sync.py").read_text(encoding="utf-8")
        self.assertIn("_bodystructure_yapraklarini_bul", kaynak)
        self.assertIn("yalnızca o parçayı alarak iletinin tamamını gereksiz yere reddetmeyiz", kaynak)

    def test_dosya_arsivim_katalogda_var(self):
        kaynak = (PROJECT_ROOT / "globalPlugins/mail/ui/other_addons.py").read_text(encoding="utf-8")
        self.assertIn('anahtar="dosya_arsivim"', kaynak)
        self.assertIn('_("Dosya Arşivim")', kaynak)
        self.assertIn("dosya-arsivim/main/update.json", kaynak)

    def test_dosya_arsivim_ingilizce_ceviride_var(self):
        po = (PROJECT_ROOT / "locale/en/LC_MESSAGES/nvda.po").read_text(encoding="utf-8")
        self.assertIn('msgid "Dosya Arşivim"', po)
        self.assertIn('msgstr "My File Archive"', po)

    def test_surumu_182(self):
        manifest = (PROJECT_ROOT / "manifest.ini").read_text(encoding="utf-8")
        version_py = (PROJECT_ROOT / "globalPlugins/mail/version.py").read_text(encoding="utf-8")
        self.assertIn('version = "1.8.2"', manifest)
        self.assertIn('EKLENTI_SURUMU = "1.8.2"', version_py)


if __name__ == "__main__":
    unittest.main()
