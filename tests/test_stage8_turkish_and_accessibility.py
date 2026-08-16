# -*- coding: utf-8 -*-
"""Sekizinci aşama: Türkçe metin, arama, erişilebilirlik ve klavye sözleşmeleri."""

from __future__ import annotations

import ast
import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock

from support import load_mail_module, module, temporary_database


KOK = pathlib.Path(__file__).resolve().parents[1]
UI_KOKU = KOK / "globalPlugins" / "mail" / "ui"


class TurkceMetinTestleri(unittest.TestCase):
    def test_windows_1254_turkce_govde_dogru_cozulur(self):
        with load_mail_module("text_utils") as text_utils:
            metin = "Şehit Ali Örnek Ortaokulu, Çağrı ve Işık".encode("windows-1254")
            sonuc = text_utils.eposta_baytlarini_metne_coz(metin, "windows-1254")
        self.assertEqual("Şehit Ali Örnek Ortaokulu, Çağrı ve Işık", sonuc)

    def test_utf8_mojibake_turkce_metin_onarilir(self):
        with load_mail_module("text_utils") as text_utils:
            bozuk = "İçimdeki Fısıltı".encode("utf-8").decode("latin-1")
            self.assertEqual("İçimdeki Fısıltı", text_utils.metin_kodlama_bozulmasini_duzelt(bozuk))

    def test_guvenli_dosya_adi_turkce_harfleri_korur(self):
        with load_mail_module("text_utils") as text_utils:
            sonuc = text_utils.guvenli_dosya_adi("Çağrı: Şiir / Gülşen?.txt")
        self.assertEqual("Çağrı_ Şiir _ Gülşen_.txt", sonuc)

    def test_konu_onekleri_turkce_okunur_hale_gelir(self):
        with load_mail_module("text_utils") as text_utils:
            sonuc = text_utils.konu_gosterimini_duzenle("Fwd: Re: İstanbul ve Işık")
        self.assertEqual("İletilmiş: Yanıtlanmış: İstanbul ve Işık", sonuc)

    def test_birikmis_re_ve_ynt_onekleri_tek_yanitlanmis_etiketine_indirilir(self):
        konu = (
            "Re: YNT: YNT: Dosya Arşivim Eklentisi Hakkında. "
            "Ha Bu Arada Gözüm Aydın"
        )
        with load_mail_module("text_utils") as text_utils:
            sonuc = text_utils.konu_gosterimini_duzenle(konu)
        self.assertEqual(
            "Yanıtlanmış: Dosya Arşivim Eklentisi Hakkında. "
            "Ha Bu Arada Gözüm Aydın",
            sonuc,
        )

    def test_gruplanmis_yanit_konusu_eposta_sayisini_tekrarlamaz(self):
        with load_mail_module("text_utils") as text_utils:
            sonuc = text_utils.konu_gosterimini_duzenle("Re: YNT: Toplantı")
        self.assertEqual("Yanıtlanmış: Toplantı", sonuc)

    def test_turkce_arama_katlama_dort_i_ve_aksanlari_esitler(self):
        with temporary_database():
            search = importlib.import_module("mail.search")
            degerler = {
                search.arama_metnini_katla("IŞIK"),
                search.arama_metnini_katla("ışık"),
                search.arama_metnini_katla("İşık"),
                search.arama_metnini_katla("isik"),
            }
            self.assertEqual({"isik"}, degerler)
            self.assertEqual("cagri gulsum", search.arama_metnini_katla("Çağrı Gülsüm"))

    def test_turkce_buyuk_harf_ve_aksansiz_arama_varsayilan_fts_ile_bulunur(self):
        with temporary_database():
            store = importlib.import_module("mail.mail_store")
            search = importlib.import_module("mail.search")
            hesap_id, klasor_id, _ = store.hesap_ve_klasor_hazirla(
                "kullanici@example.com", "INBOX", "Gelen Kutusu", 77
            )
            store.baslik_paketini_kaydet(
                hesap_id,
                klasor_id,
                77,
                [{
                    "uid": 1,
                    "gmail_message_id": "gm1",
                    "subject": "Işık, Çağrı ve Gülsüm",
                    "sender": "Şule <sule@example.com>",
                    "recipients_to": "kullanici@example.com",
                    "internal_date": 100,
                    "flags": [],
                }],
            )
            store.klasor_senkronizasyonunu_tamamla(klasor_id, 77, [1])
            store.mesaj_govdesini_kaydet(
                "kullanici@example.com", "INBOX", 1,
                "İçimdeki Fısıltı, bağlama ve şiir", 40,
            )
            sorgular = (
                ("ISIK", "konu"),
                ("CAGRI", "konu"),
                ("GULSUM", "konu"),
                ("SULE", "gonderen"),
                ("FISILTI", "icerik"),
            )
            for metin, tur in sorgular:
                with self.subTest(metin=metin, tur=tur):
                    sonuc = search.epostalarda_ara(
                        "kullanici@example.com", metin, tur, fts_kullan=True
                    )
                    self.assertEqual([1], [satir["uid"] for satir in sonuc])


class ErisilebilirlikSozlesmesiTestleri(unittest.TestCase):
    GIRIS_DENETIMLERI = {
        "TextCtrl", "ListCtrl", "Choice", "ComboBox", "SpinCtrl",
    }

    def test_butun_kalici_giris_ve_liste_denetimlerinin_erisilebilir_adi_var(self):
        eksikler = []
        for yol in sorted(UI_KOKU.glob("*.py")):
            agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
            for sinif in [n for n in ast.walk(agac) if isinstance(n, ast.ClassDef)]:
                olusturulan = []
                adlandirilan = set()
                for dugum in ast.walk(sinif):
                    if isinstance(dugum, ast.Assign) and isinstance(dugum.value, ast.Call):
                        cagri = dugum.value.func
                        if (
                            isinstance(cagri, ast.Attribute)
                            and isinstance(cagri.value, ast.Name)
                            and cagri.value.id == "wx"
                            and cagri.attr in self.GIRIS_DENETIMLERI
                        ):
                            for hedef in dugum.targets:
                                if (
                                    isinstance(hedef, ast.Attribute)
                                    and isinstance(hedef.value, ast.Name)
                                    and hedef.value.id == "self"
                                ):
                                    olusturulan.append((hedef.attr, dugum.lineno, cagri.attr))
                    if (
                        isinstance(dugum, ast.Call)
                        and isinstance(dugum.func, ast.Attribute)
                        and dugum.func.attr == "SetName"
                        and isinstance(dugum.func.value, ast.Attribute)
                        and isinstance(dugum.func.value.value, ast.Name)
                        and dugum.func.value.value.id == "self"
                    ):
                        adlandirilan.add(dugum.func.value.attr)
                for ad, satir, tur in olusturulan:
                    if ad not in adlandirilan:
                        eksikler.append(f"{yol.name}:{satir} self.{ad} ({tur})")
        self.assertEqual([], eksikler)

    def test_ana_liste_klasor_ve_eposta_modunda_ayri_adlandirilir(self):
        ana = (UI_KOKU / "main_window.py").read_text(encoding="utf-8")
        liste = (UI_KOKU / "message_list.py").read_text(encoding="utf-8")
        klasor = (UI_KOKU / "folder_view.py").read_text(encoding="utf-8")
        self.assertIn('SetName(_("E-posta klasörleri"))', ana)
        self.assertIn('SetName(_("E-posta listesi"))', liste)
        self.assertIn('SetName(_("E-posta klasörleri"))', klasor)

    def test_temel_klavye_kisayollari_hizlandirici_tablosunda_bulunur(self):
        kaynak = (UI_KOKU / "main_window.py").read_text(encoding="utf-8")
        for ifade in (
            '(wx.ACCEL_CTRL, ord("N"), self.id_yeni)',
            '(wx.ACCEL_CTRL, ord("F"), self.id_ara)',
            '(wx.ACCEL_CTRL, ord("R"), self.id_yanitla)',
            '(wx.ACCEL_SHIFT, wx.WXK_DELETE, self.id_kalici_sil)',
            '(wx.ACCEL_NORMAL, wx.WXK_F5, self.id_yenile)',
            '(wx.ACCEL_NORMAL, wx.WXK_F1, self.id_yardim_kilavuzu)',
        ):
            with self.subTest(ifade=ifade):
                self.assertIn(ifade, kaynak)


class _TusOlayi:
    def __init__(self, tus, shift=False):
        self.tus = tus
        self.shift = shift
        self.atlandi = False

    def GetKeyCode(self):
        return self.tus

    def ShiftDown(self):
        return self.shift

    def Skip(self):
        self.atlandi = True


class KlavyeDavranisiTestleri(unittest.TestCase):
    @staticmethod
    def _yukle(escape_kapat=False):
        wx = module(
            "wx",
            WXK_ESCAPE=27,
            WXK_RETURN=13,
            WXK_NUMPAD_ENTER=370,
            WXK_SPACE=32,
            WXK_DELETE=127,
            Window=types.SimpleNamespace(FindFocus=lambda: None),
        )
        ui = module("ui", message=Mock())
        stubs = {
            "wx": wx,
            "ui": ui,
            "mail.ui.folder_view": module(
                "mail.ui.folder_view", LISTE_MODU_EPOSTA="eposta", LISTE_MODU_KLASOR="klasor"
            ),
            "mail.config": module(
                "mail.config", escape_kapat_ayari_yukle=lambda: escape_kapat
            ),
        }
        return load_mail_module("ui.keyboard_handlers", stubs=stubs), wx, ui

    def test_escape_eposta_modundan_klasor_gorunumune_doner(self):
        cm, wx, _ui = self._yukle()
        with cm as klavye:
            liste = Mock()
            wx.Window.FindFocus = lambda: liste
            pencere = types.SimpleNamespace(
                liste=liste, liste_modu="eposta", secili_kategori="Gelen Kutusu",
                klasor_gorunumunu_goster=Mock(), pencereyi_kapat=Mock(),
            )
            klavye.ana_pencere_tus_yakalandi(pencere, _TusOlayi(27))
            pencere.klasor_gorunumunu_goster.assert_called_once_with("Gelen Kutusu", odak_ver=True)
            pencere.pencereyi_kapat.assert_not_called()

    def test_escape_ayara_gore_klasor_modunda_pencereyi_kapatir(self):
        cm, wx, _ui = self._yukle(True)
        with cm as klavye:
            liste = Mock()
            wx.Window.FindFocus = lambda: liste
            pencere = types.SimpleNamespace(liste=liste, liste_modu="klasor", pencereyi_kapat=Mock())
            klavye.ana_pencere_tus_yakalandi(pencere, _TusOlayi(27))
            pencere.pencereyi_kapat.assert_called_once_with()

    def test_enter_klasoru_acar(self):
        cm, wx, _ui = self._yukle()
        with cm as klavye:
            liste = Mock()
            wx.Window.FindFocus = lambda: liste
            pencere = types.SimpleNamespace(liste=liste, liste_modu="klasor", secili_klasoru_ac=Mock())
            klavye.ana_pencere_tus_yakalandi(pencere, _TusOlayi(13))
            pencere.secili_klasoru_ac.assert_called_once_with()

    def test_delete_ve_shift_delete_ayri_islemleri_cagirir(self):
        cm, _wx, _ui = self._yukle()
        with cm as klavye:
            pencere = types.SimpleNamespace(liste_modu="eposta", posta_sil=Mock(), posta_kalici_sil=Mock())
            klavye.tusa_basildi(pencere, _TusOlayi(127, False))
            klavye.tusa_basildi(pencere, _TusOlayi(127, True))
            pencere.posta_sil.assert_called_once_with()
            pencere.posta_kalici_sil.assert_called_once_with()

    def test_bosluk_epostayi_isaretler_ve_isareti_kaldirir(self):
        cm, _wx, ui = self._yukle()
        with cm as klavye:
            liste = Mock()
            liste.GetFocusedItem.return_value = 0
            pencere = types.SimpleNamespace(
                liste_modu="eposta", liste=liste,
                mailler=[{"id": "12", "kimden": "Mehmet"}], isaretliler=set(),
                mesaj_liste_gosterimi=lambda m: m["kimden"],
            )
            klavye.tusa_basildi(pencere, _TusOlayi(32))
            self.assertEqual({"12"}, pencere.isaretliler)
            klavye.tusa_basildi(pencere, _TusOlayi(32))
            self.assertEqual(set(), pencere.isaretliler)
            self.assertEqual(2, ui.message.call_count)


if __name__ == "__main__":
    unittest.main()
