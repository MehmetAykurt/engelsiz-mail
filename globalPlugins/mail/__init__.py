# -*- coding: utf-8 -*-
# Engelsiz Mail
# Telif Hakkı (C) 2026 Mehmet Aykurt


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import globalPluginHandler
import gui
import wx
import ui as nvda_ui

from .logger import hata_kaydet
from .ui_helpers import (
    arka_plan_gorevlerinin_bitmesini_bekle,
    pencere_kullanilabilir_mi,
)
from .notifications import BildirimYoneticisi
from .startup_sync import BaslangicSenkronizasyonYoneticisi
from .pending_deletions import BekleyenSilmeYoneticisi


BILDIRIM_YONETICISI = None
BASLANGIC_SENKRONIZASYON_YONETICISI = None
BEKLEYEN_SILME_YONETICISI = None


def bildirim_yoneticisini_yenile():
    """Ayar değişikliğinden sonra arka plan bildirim yöneticisini günceller."""
    try:
        yonetici = globals().get("BILDIRIM_YONETICISI")
        if yonetici:
            yonetici.ayarlari_yenile()
    except Exception as e:
        hata_kaydet("Bildirim yöneticisi yenilenemedi.", e)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Engelsiz Mail")

    def __init__(self):
        super().__init__()
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        self.gelen_penceresi = None

        global BILDIRIM_YONETICISI
        BILDIRIM_YONETICISI = BildirimYoneticisi()
        global BASLANGIC_SENKRONIZASYON_YONETICISI
        BASLANGIC_SENKRONIZASYON_YONETICISI = BaslangicSenkronizasyonYoneticisi()
        global BEKLEYEN_SILME_YONETICISI
        BEKLEYEN_SILME_YONETICISI = BekleyenSilmeYoneticisi()

        self.main_item = self.tools_menu.Append(wx.ID_ANY, _("&Engelsiz Mail"))
        gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.ac_gelen, self.main_item)

    def terminate(self):
        global BILDIRIM_YONETICISI
        global BASLANGIC_SENKRONIZASYON_YONETICISI
        global BEKLEYEN_SILME_YONETICISI

        yoneticiler = (
            ("Bildirim yöneticisi", BILDIRIM_YONETICISI),
            ("Başlangıç senkronizasyon yöneticisi", BASLANGIC_SENKRONIZASYON_YONETICISI),
            ("Bekleyen silme yöneticisi", BEKLEYEN_SILME_YONETICISI),
        )
        # Önce küresel başvuruları temizle. Durdurma sırasında hata oluşsa bile
        # yeniden yüklenen eklenti eski yöneticileri etkin sanmamalıdır.
        BILDIRIM_YONETICISI = None
        BASLANGIC_SENKRONIZASYON_YONETICISI = None
        BEKLEYEN_SILME_YONETICISI = None

        for ad, yonetici in yoneticiler:
            if not yonetici:
                continue
            try:
                yonetici.durdur()
            except Exception as e:
                hata_kaydet(f"{ad} durdurulamadı.", e)

        try:
            arka_plan_gorevlerinin_bitmesini_bekle(0.5)
        except Exception as e:
            hata_kaydet("Arka plan görevlerinin kapanması beklenemedi.", e)

        try:
            main_item = getattr(self, "main_item", None)
            if main_item is not None:
                gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, id=main_item.GetId())
                try:
                    self.tools_menu.Remove(main_item)
                except Exception:
                    self.tools_menu.Remove(main_item.GetId())
        except Exception as e:
            hata_kaydet("Menü öğesi kaldırılırken hata oluştu.", e)

        try:
            pencere = getattr(self, "gelen_penceresi", None)
            if pencere_kullanilabilir_mi(pencere):
                pencere.Close()
        except Exception as e:
            hata_kaydet("Engelsiz Mail penceresi kapatılamadı.", e)
        finally:
            self.gelen_penceresi = None

        super().terminate()

    def ac_gelen(self, event):
        self.pencereyi_baslat(menuden_geldi=True)

    def script_gelen_ac(self, gesture):
        """Engelsiz Mail penceresini açar."""
        self.pencereyi_baslat(menuden_geldi=False)

    # NVDA Girdi Hareketleri iletişim kutusunda kullanılan açıklama.
    script_gelen_ac.__doc__ = _("Engelsiz Mail penceresini açar.")

    def _gelen_penceresi_kapandi(self, event):
        if event.GetEventObject() is self.gelen_penceresi:
            yonetici = globals().get("BILDIRIM_YONETICISI")
            if yonetici:
                yonetici.yeni_eposta_callback_ayarla(None)
            self.gelen_penceresi = None
        event.Skip()

    def pencereyi_one_getir(self, pencere):
        try:
            if hasattr(pencere, "one_getir_ve_odaklan"):
                return bool(pencere.one_getir_ve_odaklan())
            if pencere.IsIconized():
                pencere.Iconize(False)
            if not pencere.IsShown():
                pencere.Show(True)
            pencere.Raise()
            pencere.SetFocus()
            return True
        except Exception as e:
            hata_kaydet("Açık pencere öne getirilemedi.", e)
            return False

    def pencereyi_baslat(self, menuden_geldi=False):
        def ac():
            if pencere_kullanilabilir_mi(getattr(self, "gelen_penceresi", None)):
                getirildi = self.pencereyi_one_getir(self.gelen_penceresi)
                if not getirildi:
                    nvda_ui.message(_("Engelsiz Mail penceresi zaten açık, ancak öne getirilemedi."))
                return

            try:
                from .ui.main_window import GelenKutusuPenceresi
            except Exception as e:
                hata_kaydet("Engelsiz Mail ana penceresi yüklenemedi.", e)
                nvda_ui.message(_("Engelsiz Mail açılırken hata oluştu. Ayrıntılar için NVDA günlüğünü inceleyin."))
                return

            try:
                pencere = GelenKutusuPenceresi(gui.mainFrame, bildirim_yoneticisini_yenile)
                self.gelen_penceresi = pencere
                yonetici = globals().get("BILDIRIM_YONETICISI")
                if yonetici:
                    yonetici.yeni_eposta_callback_ayarla(
                        pencere.yeni_eposta_bildirimi_alindi
                    )
                pencere.Bind(wx.EVT_WINDOW_DESTROY, self._gelen_penceresi_kapandi)
                pencere.Show()
                pencere.Raise()

                if not pencere.hesap_bilgisi_var_mi():
                    wx.CallAfter(pencere.hesap_bilgisi_eksik_uyarisi_goster)
            except Exception as e:
                self.gelen_penceresi = None
                hata_kaydet("Engelsiz Mail ana penceresi açılamadı.", e)
                nvda_ui.message(_("Engelsiz Mail açılırken hata oluştu. Ayrıntılar için NVDA günlüğünü inceleyin."))
        wx.CallAfter(ac)

    __gestures = {"kb:nvda+shift+m": "gelen_ac"}
