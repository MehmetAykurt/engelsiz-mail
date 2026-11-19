# -*- coding: utf-8 -*-
# Engelsiz Mail - Tablo Ekleme Penceresi

try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    _ = lambda metin: metin

import wx

from ..ui_helpers import gorunum_denetimlerine_uygula


def tablo_sablonu_olustur(satir_sayisi, sutun_sayisi, baslik_var=True):
    """Verilen satır ve sütun sayısına göre erişilebilir metin tablosu şablonu üretir."""
    satir_sayisi = max(1, min(100, int(satir_sayisi or 3)))
    sutun_sayisi = max(1, min(20, int(sutun_sayisi or 2)))

    # Başlıksız tabloda işaret bunu belirtir; HTML üretimi ilk satırı başlık yapmaz.
    satirlar = ["[Tablo Başlangıcı]" if baslik_var else "[Tablo Başlangıcı, başlıksız]"]

    hucre_no = 1
    if baslik_var:
        baslik_hucreleri = [f"Başlık {c}" for c in range(1, sutun_sayisi + 1)]
        satirlar.append("| " + " | ".join(baslik_hucreleri) + " |")
        satir_sayisi -= 1

    for r in range(satir_sayisi):
        hucreler = []
        for c in range(sutun_sayisi):
            hucreler.append(f"Hücre {hucre_no}")
            hucre_no += 1
        satirlar.append("| " + " | ".join(hucreler) + " |")

    satirlar.append("[Tablo Bitişi]")
    return "\n".join(satirlar)


class TabloEklePenceresi(wx.Dialog):
    """Satır ve sütun sayılarını alarak e-posta metnine tablo şablonu ekleyen diyalog penceresi."""

    def __init__(self, parent):
        super().__init__(parent, title=_("Tablo Ekle"))
        self.sonuc_sablonu = ""

        duzen = wx.BoxSizer(wx.VERTICAL)

        # Satır sayısı
        duzen.Add(wx.StaticText(self, label=_("&Satır sayısı:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.spn_satir = wx.SpinCtrl(self, min=1, max=50, initial=3)
        self.spn_satir.SetName(_("Satır sayısı"))
        duzen.Add(self.spn_satir, 0, wx.ALL | wx.EXPAND, 10)

        # Sütun sayısı
        duzen.Add(wx.StaticText(self, label=_("&Sütun sayısı:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.spn_sutun = wx.SpinCtrl(self, min=1, max=20, initial=2)
        self.spn_sutun.SetName(_("Sütun sayısı"))
        duzen.Add(self.spn_sutun, 0, wx.ALL | wx.EXPAND, 10)

        # Başlık onay kutusu
        self.chk_baslik = wx.CheckBox(self, label=_("&İlk satır tablo başlığı olsun"))
        self.chk_baslik.SetValue(True)
        duzen.Add(self.chk_baslik, 0, wx.ALL, 10)

        # Düğmeler
        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.tamam_btn = wx.Button(self, wx.ID_OK, label=_("&Tamam"))
        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        self.tamam_btn.SetDefault()

        btn_duzen.Add(self.tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)

        self.SetSizer(duzen)
        self.SetSize((380, 290))
        self.CenterOnParent()

        self.tamam_btn.Bind(wx.EVT_BUTTON, self.onayla)
        gorunum_denetimlerine_uygula(self.spn_satir, self.spn_sutun, self.chk_baslik)

        wx.CallAfter(self.spn_satir.SetFocus)

    def onayla(self, event=None):
        satir = self.spn_satir.GetValue()
        sutun = self.spn_sutun.GetValue()
        baslik = self.chk_baslik.GetValue()
        self.sonuc_sablonu = tablo_sablonu_olustur(satir, sutun, baslik_var=baslik)
        self.EndModal(wx.ID_OK)
