# -*- coding: utf-8 -*-
# Engelsiz Mail - Bağlantı Ekleme ve Düzenleme Penceresi


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import ui
import wx

from ..html_composer import baglanti_olustur, url_guvenli_yap
from ..ui_helpers import gorunum_denetimlerine_uygula


class BaglantiEklePenceresi(wx.Dialog):
    """HTML e-posta için bağlantı (köprü) metni ve URL adresi alan veya düzenleyen diyalog penceresi."""

    def __init__(self, parent, varsayilan_metin="", varsayilan_url="", duzenleme_modu=False):
        baslik = _("Bağlantıyı Düzenle") if duzenleme_modu else _("Bağlantı Ekle")
        super().__init__(parent, title=baslik)
        self.sonuc_etiketi = ""
        self.sonuc_metin = ""
        self.sonuc_url = ""
        self.baglanti_silindi = False

        varsayilan_metin = str(varsayilan_metin or "").strip()
        aday_url = str(varsayilan_url or "").strip()
        if not aday_url and varsayilan_metin.lower().startswith(("http://", "https://", "www.")):
            aday_url = varsayilan_metin

        duzen = wx.BoxSizer(wx.VERTICAL)

        duzen.Add(wx.StaticText(self, label=_("&Görünen metin:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_metin = wx.TextCtrl(self, value=varsayilan_metin)
        self.txt_metin.SetName(_("Görünen metin"))
        duzen.Add(self.txt_metin, 0, wx.ALL | wx.EXPAND, 10)

        duzen.Add(wx.StaticText(self, label=_("&Web adresi (URL):")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_url = wx.TextCtrl(self, value=aday_url)
        self.txt_url.SetName(_("Web adresi (URL)"))
        duzen.Add(self.txt_url, 0, wx.ALL | wx.EXPAND, 10)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)

        if duzenleme_modu:
            self.baglanti_kaldir_btn = wx.Button(self, label=_("Bağlantıyı &Kaldır"))
            self.baglanti_kaldir_btn.Bind(wx.EVT_BUTTON, self.baglantiyi_kaldir)
            btn_duzen.Add(self.baglanti_kaldir_btn, 0, wx.ALL, 5)

        self.tamam_btn = wx.Button(self, wx.ID_OK, label=_("&Tamam"))
        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        self.tamam_btn.SetDefault()

        btn_duzen.Add(self.tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)

        self.SetSizer(duzen)
        self.SetSize((460, 240))
        self.CenterOnParent()

        self.tamam_btn.Bind(wx.EVT_BUTTON, self.onayla)
        gorunum_denetimlerine_uygula(self.txt_metin, self.txt_url)

        if varsayilan_metin and not aday_url:
            wx.CallAfter(self.txt_url.SetFocus)
        else:
            wx.CallAfter(self.txt_metin.SetFocus)

    def baglantiyi_kaldir(self, event=None):
        self.baglanti_silindi = True
        self.EndModal(wx.ID_OK)

    def onayla(self, event=None):
        url = self.txt_url.GetValue().strip()
        if not url:
            ui.message(_("Lütfen bir web adresi yazın."))
            self.txt_url.SetFocus()
            return

        metin = self.txt_metin.GetValue().strip()
        if not metin:
            metin = url

        self.sonuc_metin = metin
        self.sonuc_url = url_guvenli_yap(url)
        self.sonuc_etiketi = baglanti_olustur(metin, url)
        self.EndModal(wx.ID_OK)
