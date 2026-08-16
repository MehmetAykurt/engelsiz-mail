# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import ui
import wx

from ..config import IMZA_AZAMI_UZUNLUK
from ..ui_helpers import gorunum_denetimlerine_uygula

IMZA_SIL_ID = wx.ID_DELETE


class ImzaPenceresi(wx.Dialog):
    """Düz metin imza oluşturma ve düzenleme penceresi."""

    def __init__(self, parent, baslik, mevcut_imza=""):
        super().__init__(parent, title=baslik)

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(
            wx.StaticText(self, label=_("&İmza metni:")),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            8,
        )
        self.txt_imza = wx.TextCtrl(
            self,
            value=str(mevcut_imza or ""),
            style=wx.TE_MULTILINE | wx.TE_RICH2,
        )
        self.txt_imza.SetName(_("İmza metni"))
        self.txt_imza.SetMaxLength(IMZA_AZAMI_UZUNLUK)
        duzen.Add(self.txt_imza, 1, wx.ALL | wx.EXPAND, 8)

        dugmeler = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_sil = wx.Button(self, label=_("&Sil"))
        self.btn_kaydet = wx.Button(self, wx.ID_OK, _("&Kaydet"))
        self.btn_iptal = wx.Button(self, wx.ID_CANCEL, _("İ&ptal"))
        self.btn_sil.Enable(bool(str(mevcut_imza or "").strip()))
        self.btn_sil.Bind(wx.EVT_BUTTON, self.sil)
        self.btn_kaydet.Bind(wx.EVT_BUTTON, self.kaydet)
        dugmeler.Add(self.btn_sil, 0, wx.ALL, 5)
        dugmeler.Add(self.btn_kaydet, 0, wx.ALL, 5)
        dugmeler.Add(self.btn_iptal, 0, wx.ALL, 5)
        duzen.Add(dugmeler, 0, wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        gorunum_denetimlerine_uygula(self.txt_imza)
        self.SetSizer(duzen)
        self.SetSize((620, 430))
        self.CenterOnParent()
        wx.CallAfter(self.txt_imza.SetFocus)
        wx.CallAfter(self.txt_imza.SetInsertionPointEnd)

    def imzayi_al(self):
        return self.txt_imza.GetValue()

    def kaydet(self, event=None):
        if not self.imzayi_al().strip():
            ui.message(_("İmza metni boş bırakılamaz."))
            self.txt_imza.SetFocus()
            return
        self.EndModal(wx.ID_OK)

    def sil(self, event=None):
        self.EndModal(IMZA_SIL_ID)
