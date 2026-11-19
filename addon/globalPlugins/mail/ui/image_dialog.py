# -*- coding: utf-8 -*-
# Engelsiz Mail - Resim Açıklaması Penceresi

try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    _ = lambda metin: metin

import ui
import wx

from ..ui_helpers import gorunum_denetimlerine_uygula


class ResimAciklamasiPenceresi(wx.Dialog):
    """Panodan yapıştırılan resim için ekran okuyucu açıklaması (alt metin) alan diyalog penceresi."""

    def __init__(self, parent, varsayilan_aciklama=""):
        super().__init__(parent, title=_("Resim Açıklaması"))
        self.sonuc_aciklama = ""

        varsayilan_aciklama = str(varsayilan_aciklama or "").strip()

        duzen = wx.BoxSizer(wx.VERTICAL)

        duzen.Add(
            wx.StaticText(
                self,
                label=_("&Resim açıklaması (ekran okuyucular için isteğe bağlı):"),
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )
        self.txt_aciklama = wx.TextCtrl(self, value=varsayilan_aciklama)
        self.txt_aciklama.SetName(_("Resim açıklaması"))
        self.txt_aciklama.SetHelpText(_("Resmi betimleyen kısa bir açıklama yazabilirsiniz. Boş bırakırsanız varsayılan isim kullanılır."))
        duzen.Add(self.txt_aciklama, 0, wx.ALL | wx.EXPAND, 10)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.tamam_btn = wx.Button(self, wx.ID_OK, label=_("&Tamam"))
        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        self.tamam_btn.SetDefault()

        btn_duzen.Add(self.tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)

        self.SetSizer(duzen)
        self.SetSize((440, 200))
        self.CenterOnParent()

        self.tamam_btn.Bind(wx.EVT_BUTTON, self.onayla)
        gorunum_denetimlerine_uygula(self.txt_aciklama)

        wx.CallAfter(self.txt_aciklama.SetFocus)

    def onayla(self, event=None):
        aciklama = self.txt_aciklama.GetValue().strip()
        self.sonuc_aciklama = aciklama
        self.EndModal(wx.ID_OK)
