# -*- coding: utf-8 -*-
"""Sekizinci aşama: NVDA eklenti açılışı, pencere yaşam döngüsü ve kapanış testleri."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock


MAIL_KOKU = pathlib.Path(__file__).resolve().parents[1] / "globalPlugins" / "mail"


class _MenuItem:
    def __init__(self, item_id=7001):
        self.item_id = item_id

    def GetId(self):
        return self.item_id


class _Menu:
    def __init__(self):
        self.appended = []
        self.removed = []

    def Append(self, item_id, label):
        item = _MenuItem()
        self.appended.append((item_id, label, item))
        return item

    def Remove(self, item):
        self.removed.append(item)
        return True


class _Tray:
    def __init__(self):
        self.toolsMenu = _Menu()
        self.bound = []
        self.unbound = []

    def Bind(self, event, callback, item):
        self.bound.append((event, callback, item))

    def Unbind(self, event, **kwargs):
        self.unbound.append((event, kwargs))
        return True


class _MainFrame:
    def __init__(self):
        self.sysTrayIcon = _Tray()


class _BasePlugin:
    def __init__(self):
        self.base_initialized = True
        self.base_terminated = False

    def terminate(self):
        self.base_terminated = True


class _Event:
    def __init__(self, obj):
        self.obj = obj
        self.skipped = False

    def GetEventObject(self):
        return self.obj

    def Skip(self):
        self.skipped = True


def plugin_yukle(*, manager_factory=None, pencere_sinifi=None):
    manager_factory = manager_factory or (lambda ad: Mock(name=ad))
    managers = {
        "bildirim": manager_factory("bildirim"),
        "baslangic": manager_factory("baslangic"),
        "silme": manager_factory("silme"),
    }
    main_frame = _MainFrame()
    logs = []
    spoken = []

    wx = types.ModuleType("wx")
    wx.ID_ANY = -1
    wx.EVT_MENU = object()
    wx.EVT_WINDOW_DESTROY = object()
    wx.CallAfter = lambda callback, *args: callback(*args)

    gui = types.ModuleType("gui")
    gui.mainFrame = main_frame
    ui = types.ModuleType("ui")
    ui.message = lambda text: spoken.append(str(text))
    global_plugin_handler = types.ModuleType("globalPluginHandler")
    global_plugin_handler.GlobalPlugin = _BasePlugin

    stubs = {
        "wx": wx,
        "gui": gui,
        "ui": ui,
        "globalPluginHandler": global_plugin_handler,
        "mail.logger": types.SimpleNamespace(hata_kaydet=lambda mesaj, hata=None: logs.append((mesaj, hata))),
        "mail.ui_helpers": types.SimpleNamespace(
            arka_plan_gorevlerinin_bitmesini_bekle=Mock(),
            pencere_kullanilabilir_mi=lambda p: p is not None and not getattr(p, "destroyed", False),
        ),
        "mail.notifications": types.SimpleNamespace(BildirimYoneticisi=lambda: managers["bildirim"]),
        "mail.startup_sync": types.SimpleNamespace(BaslangicSenkronizasyonYoneticisi=lambda: managers["baslangic"]),
        "mail.pending_deletions": types.SimpleNamespace(BekleyenSilmeYoneticisi=lambda: managers["silme"]),
    }
    if pencere_sinifi is not None:
        ui_pkg = types.ModuleType("mail.ui")
        ui_pkg.__path__ = [str(MAIL_KOKU / "ui")]
        stubs["mail.ui"] = ui_pkg
        stubs["mail.ui.main_window"] = types.SimpleNamespace(GelenKutusuPenceresi=pencere_sinifi)

    touched = {"mail", *stubs.keys()}
    previous = {name: sys.modules.get(name) for name in touched}
    for name in touched:
        sys.modules.pop(name, None)
    package_spec = importlib.util.spec_from_file_location(
        "mail", MAIL_KOKU / "__init__.py", submodule_search_locations=[str(MAIL_KOKU)]
    )
    module = importlib.util.module_from_spec(package_spec)
    sys.modules["mail"] = module
    for name, stub in stubs.items():
        sys.modules[name] = stub
    try:
        package_spec.loader.exec_module(module)
    finally:
        # Modül test boyunca kullanılacağı için sahteler yerinde kalır; temizleyici döndürülür.
        pass

    def temizle():
        for name in list(touched):
            sys.modules.pop(name, None)
        for name, old in previous.items():
            if old is not None:
                sys.modules[name] = old

    return module, managers, main_frame, logs, spoken, temizle


class PluginYasamDongusuTestleri(unittest.TestCase):
    def test_baslangicta_uc_yonetici_ve_araclar_menusu_olusturulur(self):
        modul, managers, frame, _logs, _spoken, temizle = plugin_yukle()
        try:
            plugin = modul.GlobalPlugin()
            self.assertIs(managers["bildirim"], modul.BILDIRIM_YONETICISI)
            self.assertIs(managers["baslangic"], modul.BASLANGIC_SENKRONIZASYON_YONETICISI)
            self.assertIs(managers["silme"], modul.BEKLEYEN_SILME_YONETICISI)
            self.assertEqual("&Engelsiz Mail", frame.sysTrayIcon.toolsMenu.appended[0][1])
            self.assertEqual(1, len(frame.sysTrayIcon.bound))
            self.assertTrue(plugin.base_initialized)
        finally:
            temizle()

    def test_kapanista_yoneticiler_menu_ve_acik_pencere_temizlenir(self):
        modul, managers, frame, _logs, _spoken, temizle = plugin_yukle()
        try:
            plugin = modul.GlobalPlugin()
            pencere = Mock()
            pencere.destroyed = False
            plugin.gelen_penceresi = pencere
            bekle = sys.modules["mail.ui_helpers"].arka_plan_gorevlerinin_bitmesini_bekle

            plugin.terminate()

            for manager in managers.values():
                manager.durdur.assert_called_once_with()
            bekle.assert_called_once_with(0.5)
            pencere.Close.assert_called_once_with()
            self.assertIsNone(plugin.gelen_penceresi)
            self.assertEqual(1, len(frame.sysTrayIcon.unbound))
            self.assertTrue(frame.sysTrayIcon.toolsMenu.removed)
            self.assertTrue(plugin.base_terminated)
            self.assertIsNone(modul.BILDIRIM_YONETICISI)
            self.assertIsNone(modul.BASLANGIC_SENKRONIZASYON_YONETICISI)
            self.assertIsNone(modul.BEKLEYEN_SILME_YONETICISI)
        finally:
            temizle()

    def test_bir_yonetici_hata_verse_de_digerleri_ve_menu_temizlenir(self):
        def fabrika(ad):
            manager = Mock(name=ad)
            if ad == "bildirim":
                manager.durdur.side_effect = RuntimeError("durdurma hatası")
            return manager

        modul, managers, frame, logs, _spoken, temizle = plugin_yukle(manager_factory=fabrika)
        try:
            plugin = modul.GlobalPlugin()
            plugin.terminate()
            managers["baslangic"].durdur.assert_called_once_with()
            managers["silme"].durdur.assert_called_once_with()
            self.assertTrue(frame.sysTrayIcon.toolsMenu.removed)
            self.assertTrue(plugin.base_terminated)
            self.assertTrue(any("Bildirim yöneticisi" in mesaj for mesaj, _ in logs))
        finally:
            temizle()

    def test_acik_pencere_ikinci_kez_olusturulmaz_one_getirilir(self):
        class Pencere:
            olusturma = 0

            def __init__(self, *_args):
                type(self).olusturma += 1

        modul, _managers, _frame, _logs, _spoken, temizle = plugin_yukle(pencere_sinifi=Pencere)
        try:
            plugin = modul.GlobalPlugin()
            mevcut = Mock()
            mevcut.destroyed = False
            mevcut.one_getir_ve_odaklan.return_value = True
            plugin.gelen_penceresi = mevcut
            plugin.pencereyi_baslat()
            mevcut.one_getir_ve_odaklan.assert_called_once_with()
            self.assertEqual(0, Pencere.olusturma)
        finally:
            temizle()

    def test_ana_pencere_hatasinda_nvda_ui_mesaji_alt_paket_cakismasindan_etkilenmez(self):
        class BozukPencere:
            def __init__(self, *_args):
                raise RuntimeError("canli acilis benzetimi")

        modul, _managers, _frame, logs, spoken, temizle = plugin_yukle(pencere_sinifi=BozukPencere)
        try:
            plugin = modul.GlobalPlugin()
            # Python, mail.ui alt paketi yüklendiğinde parent package üzerindeki ``ui``
            # özniteliğini değiştirebilir. NVDA'nın ui modülü ayrı bir adla tutulmalıdır.
            modul.ui = sys.modules["mail.ui"]
            plugin.pencereyi_baslat()
            self.assertTrue(any("ana penceresi açılamadı" in mesaj for mesaj, _ in logs))
            self.assertIn(
                "Engelsiz Mail açılırken hata oluştu. Ayrıntılar için NVDA günlüğünü inceleyin.",
                spoken,
            )
        finally:
            temizle()

    def test_pencere_yok_edilince_bildirim_callbacki_temizlenir(self):
        modul, managers, _frame, _logs, _spoken, temizle = plugin_yukle()
        try:
            plugin = modul.GlobalPlugin()
            pencere = object()
            plugin.gelen_penceresi = pencere
            olay = _Event(pencere)
            plugin._gelen_penceresi_kapandi(olay)
            managers["bildirim"].yeni_eposta_callback_ayarla.assert_called_once_with(None)
            self.assertIsNone(plugin.gelen_penceresi)
            self.assertTrue(olay.skipped)
        finally:
            temizle()


if __name__ == "__main__":
    unittest.main()
