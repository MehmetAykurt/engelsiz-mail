# -*- coding: utf-8 -*-
"""Ayarları ZIP olarak içe ve dışa aktarma penceresi."""

import os
from datetime import datetime

import gui
import ui
import wx

from ..errors import MailHatasi
from ..logger import hata_kaydet
from ..settings_backup import ayarlari_disa_aktar, ayarlari_ice_aktar


def _belgeler_klasoru():
    try:
        yol = wx.StandardPaths.Get().GetDocumentsDir()
        if yol and os.path.isdir(yol):
            return yol
    except Exception:
        pass
    yol = os.path.join(os.path.expanduser("~"), "Documents")
    return yol if os.path.isdir(yol) else os.path.expanduser("~")


class AyarlariAktarmaPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - İçe / Dışa Aktar")
        duzen = wx.BoxSizer(wx.VERTICAL)
        bilgi = wx.StaticText(
            self,
            label=(
                "Engelsiz Mail ayarlarını ve hesap bilgilerini ZIP dosyası olarak "
                "yedekleyebilir veya daha önce oluşturulmuş bir yedeği geri yükleyebilirsiniz."
            ),
        )
        bilgi.Wrap(560)
        duzen.Add(bilgi, 0, wx.ALL | wx.EXPAND, 10)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        ice_aktar_btn = wx.Button(self, label="&İçe Aktar")
        ice_aktar_btn.Bind(wx.EVT_BUTTON, self.ice_aktar_basildi)
        btn_duzen.Add(ice_aktar_btn, 0, wx.ALL, 5)

        disa_aktar_btn = wx.Button(self, label="&Dışa Aktar")
        disa_aktar_btn.Bind(wx.EVT_BUTTON, self.disa_aktar_basildi)
        btn_duzen.Add(disa_aktar_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizerAndFit(duzen)
        self.SetMinSize((620, -1))
        self.CenterOnParent()
        wx.CallAfter(ice_aktar_btn.SetFocus)

    def disa_aktar_basildi(self, event=None):
        uyari = (
            "Bu yedek e-posta adresinizi ve Google uygulama şifrenizi içerir. "
            "ZIP dosyası şifrelenmez. Yedeği güvenli bir yerde saklayın.\n\n"
            "Devam etmek istiyor musunuz?"
        )
        sonuc = gui.messageBox(
            uyari,
            "Ayarları Dışa Aktar",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if sonuc != wx.YES:
            return
        dosya_adi = f"Engelsiz-Mail-Ayarlari-{datetime.now().strftime('%Y-%m-%d')}.zip"
        dlg = wx.FileDialog(
            self,
            "Engelsiz Mail ayar yedeğini kaydedin",
            defaultDir=_belgeler_klasoru(),
            defaultFile=dosya_adi,
            wildcard="ZIP dosyaları (*.zip)|*.zip",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            hedef_yol = dlg.GetPath()
        finally:
            dlg.Destroy()
        try:
            kaydedilen_yol = ayarlari_disa_aktar(hedef_yol)
            gui.messageBox(
                f"Ayar yedeği oluşturuldu.\n\n{kaydedilen_yol}",
                "Ayarlar Dışa Aktarıldı",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.EndModal(wx.ID_OK)
        except MailHatasi as e:
            hata_kaydet(str(e))
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Ayarlar dışa aktarılamadı.", e)
            ui.message("Ayarlar dışa aktarılamadı.")

    def ice_aktar_basildi(self, event=None):
        dlg = wx.FileDialog(
            self,
            "Engelsiz Mail ayar yedeğini seçin",
            defaultDir=_belgeler_klasoru(),
            wildcard="ZIP dosyaları (*.zip)|*.zip",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            kaynak_yol = dlg.GetPath()
        finally:
            dlg.Destroy()

        onay = gui.messageBox(
            "Mevcut Engelsiz Mail ayarları ve hesap bilgileri seçilen yedekle değiştirilecektir. Devam etmek istiyor musunuz?",
            "Ayarları İçe Aktar",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        )
        if onay != wx.YES:
            return
        try:
            ayarlari_ice_aktar(kaynak_yol)
            gui.messageBox(
                "Ayarlar içe aktarıldı. Değişikliklerin tamamının uygulanması için NVDA'yı yeniden başlatın.",
                "Ayarlar İçe Aktarıldı",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.EndModal(wx.ID_OK)
        except MailHatasi as e:
            hata_kaydet(str(e))
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Ayarlar içe aktarılamadı.", e)
            ui.message("Ayarlar içe aktarılamadı.")
