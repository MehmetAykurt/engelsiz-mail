# -*- coding: utf-8 -*-
# Engelsiz Mail - Arşiv ve silme onayı pencereleri


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import wx
import ui
import gui

from ..errors import MailHatasi
from ..folders import arsiv_klasor_adini_dogrula
from ..logger import hata_kaydet


class ArsivSecimPenceresi(wx.Dialog):
    def __init__(self, parent, ozel_klasorler, ebeveyn_pencere):
        super().__init__(parent, title=_("Engelsiz Mail - Arşive gönderme"))
        self.secilen_isim = None
        self.ebeveyn = ebeveyn_pencere

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label=_("&Hedef arşivi seçin:")), 0, wx.ALL, 5)

        self.liste_kutu = wx.ListBox(self, choices=list(ozel_klasorler), style=wx.LB_SINGLE)
        self.liste_kutu.SetName(_("Hedef arşiv klasörleri"))
        if self.liste_kutu.GetCount() > 0:
            self.liste_kutu.SetSelection(0)
        duzen.Add(self.liste_kutu, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.tasi_btn = wx.Button(self, label=_("&Taşı"))
        self.tasi_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(self.tasi_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((560, 320))
        self.CenterOnParent()
        wx.CallAfter(self.liste_kutu.SetFocus)

    def tamam_basildi(self, event):
        secim = self.liste_kutu.GetSelection()
        if secim == wx.NOT_FOUND:
            ui.message(_("Lütfen hedef arşiv klasörünü seçin. Arşiv yoksa E-posta menüsünden Arşiv Klasörlerini Yönet seçeneğiyle yeni arşiv oluşturun."))
            self.liste_kutu.SetFocus()
            return
        self.secilen_isim = self.liste_kutu.GetString(secim)
        self.EndModal(wx.ID_OK)


class YeniKlasorPenceresi(wx.Dialog):
    def __init__(self, parent, mevcut_adlar=None):
        super().__init__(parent, title=_("Engelsiz Mail - Yeni arşiv klasörü"))
        self.klasor_adi = None
        self.mevcut_adlar = list(mevcut_adlar or [])

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label=_("&Yeni arşiv klasörünün adını yazın:")), 0, wx.ALL, 5)
        self.txt_isim = wx.TextCtrl(self)
        self.txt_isim.SetName(_("Yeni arşiv klasörü adı"))
        duzen.Add(self.txt_isim, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        olustur_btn = wx.Button(self, label=_("&Oluştur"))
        olustur_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(olustur_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((420, 180))
        self.CenterOnParent()
        wx.CallAfter(self.txt_isim.SetFocus)

    def tamam_basildi(self, event):
        try:
            isim = arsiv_klasor_adini_dogrula(self.txt_isim.GetValue(), self.mevcut_adlar)
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_isim.SetFocus()
            return
        self.klasor_adi = isim
        self.EndModal(wx.ID_OK)


class ArsivYenidenAdlandirPenceresi(wx.Dialog):
    def __init__(self, parent, eski_isim, mevcut_adlar=None):
        super().__init__(parent, title=_("Engelsiz Mail - Arşiv klasörünü yeniden adlandır"))
        self.eski_isim = str(eski_isim or "").strip()
        self.mevcut_adlar = list(mevcut_adlar or [])
        self.yeni_isim = None

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label=_("&Yeni arşiv klasörü adını yazın:")), 0, wx.ALL, 5)
        self.txt_isim = wx.TextCtrl(self, value=self.eski_isim)
        self.txt_isim.SetName(_("Yeni arşiv klasörü adı"))
        duzen.Add(self.txt_isim, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label=_("&Tamam"))
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((500, 190))
        self.CenterOnParent()
        wx.CallAfter(self.txt_isim.SetFocus)
        wx.CallAfter(self.txt_isim.SetSelection, 0, len(self.eski_isim))

    def tamam_basildi(self, event):
        try:
            yeni_isim = arsiv_klasor_adini_dogrula(
                self.txt_isim.GetValue(),
                self.mevcut_adlar,
                self.eski_isim,
            )
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_isim.SetFocus()
            try:
                self.txt_isim.SetSelection(0, self.txt_isim.GetLastPosition())
            except Exception:
                pass
            return

        if yeni_isim.strip().lower() == self.eski_isim.strip().lower():
            ui.message(_("Arşiv adı değişmedi. Lütfen farklı bir ad yazın veya iptal düğmesine basın."))
            self.txt_isim.SetFocus()
            try:
                self.txt_isim.SetSelection(0, self.txt_isim.GetLastPosition())
            except Exception:
                pass
            return

        self.yeni_isim = yeni_isim
        self.EndModal(wx.ID_OK)


class ArsivYonetimPenceresi(wx.Dialog):
    def __init__(self, parent, ozel_klasorler, ebeveyn_pencere):
        super().__init__(parent, title=_("Engelsiz Mail - Arşiv klasörlerini yönet"))
        self.ebeveyn = ebeveyn_pencere

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label=_("&Arşiv klasörleri:")), 0, wx.ALL, 5)

        self.liste_kutu = wx.ListBox(self, choices=list(ozel_klasorler), style=wx.LB_SINGLE)
        self.liste_kutu.SetName(_("Arşiv klasörleri listesi"))
        if self.liste_kutu.GetCount() > 0:
            self.liste_kutu.SetSelection(0)
        duzen.Add(self.liste_kutu, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)

        yeni_btn = wx.Button(self, label=_("&Yeni oluştur"))
        yeni_btn.Bind(wx.EVT_BUTTON, self.yeni_olustur_basildi)
        btn_duzen.Add(yeni_btn, 0, wx.ALL, 5)

        yeniden_btn = wx.Button(self, label=_("Yeniden &adlandır"))
        yeniden_btn.Bind(wx.EVT_BUTTON, self.yeniden_adlandir_basildi)
        btn_duzen.Add(yeniden_btn, 0, wx.ALL, 5)

        sil_btn = wx.Button(self, label=_("&Sil"))
        sil_btn.Bind(wx.EVT_BUTTON, self.sil_basildi)
        btn_duzen.Add(sil_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, wx.ID_CANCEL, label=_("&Kapat"))
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((620, 340))
        self.CenterOnParent()
        wx.CallAfter(self.liste_kutu.SetFocus)

    def secili_arsiv_adi(self):
        secim = self.liste_kutu.GetSelection()
        if secim == wx.NOT_FOUND:
            return ""
        return self.liste_kutu.GetString(secim)

    def yeni_olustur_basildi(self, event):
        dlg = YeniKlasorPenceresi(self, self.ebeveyn.ozel_klasorler)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            isim = dlg.klasor_adi
        finally:
            dlg.Destroy()
        if isim:
            self.ebeveyn.arsiv_klasoru_olustur(isim)
            self.EndModal(wx.ID_OK)

    def yeniden_adlandir_basildi(self, event):
        eski_isim = self.secili_arsiv_adi()
        if not eski_isim:
            ui.message(_("Lütfen yeniden adlandırmak istediğiniz arşivi seçin."))
            self.liste_kutu.SetFocus()
            return

        dlg = ArsivYenidenAdlandirPenceresi(self, eski_isim, self.ebeveyn.ozel_klasorler)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            yeni_isim = dlg.yeni_isim
        finally:
            try:
                dlg.Destroy()
            except Exception as e:
                hata_kaydet("Arşiv yeniden adlandırma penceresi kapatılamadı.", e)

        if not yeni_isim:
            self.liste_kutu.SetFocus()
            return

        self.ebeveyn.arsiv_klasoru_yeniden_adlandir(eski_isim, yeni_isim)
        self.EndModal(wx.ID_OK)

    def sil_basildi(self, event):
        isim = self.secili_arsiv_adi()
        if not isim:
            ui.message(_("Lütfen silmek istediğiniz arşivi seçin."))
            self.liste_kutu.SetFocus()
            return
        cevap = gui.messageBox(
            _('{0} adlı arşiv klasörünü silmek istiyor musunuz?').format(isim),
            _("Arşiv silme onayı"),
            wx.YES_NO | wx.ICON_WARNING,
            self,
        )
        if cevap == wx.YES:
            self.ebeveyn.arsiv_klasoru_sil(isim)
            self.EndModal(wx.ID_OK)


class KaliciSilmeOnayiPenceresi(wx.Dialog):
    def __init__(self, parent, soru):
        super().__init__(parent, title=_("Kalıcı silme onayı"))
        self._kapatildi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)

        ana_duzen = wx.BoxSizer(wx.VERTICAL)
        metin = wx.StaticText(self, label=str(soru or "") + _("\n\nBu işlem geri alınamaz."))
        try:
            metin.Wrap(560)
        except Exception:
            pass
        ana_duzen.Add(metin, 0, wx.ALL | wx.EXPAND, 10)

        self.bir_daha_gosterme = wx.CheckBox(self, label=_("Bu uyarıyı bir daha gösterme"))
        ana_duzen.Add(self.bir_daha_gosterme, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dugme_duzen = wx.BoxSizer(wx.HORIZONTAL)
        evet_btn = wx.Button(self, wx.ID_YES, label=_("&Evet"))
        hayir_btn = wx.Button(self, wx.ID_NO, label=_("&Hayır"))
        evet_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_YES))
        hayir_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_NO))
        dugme_duzen.Add(evet_btn, 0, wx.ALL, 5)
        dugme_duzen.Add(hayir_btn, 0, wx.ALL, 5)
        ana_duzen.Add(dugme_duzen, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.SetSizerAndFit(ana_duzen)
        self.SetEscapeId(wx.ID_NO)
        try:
            hayir_btn.SetDefault()
        except Exception:
            pass
        self.CenterOnParent()
        wx.CallAfter(hayir_btn.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def bir_daha_gosterme_secili_mi(self):
        try:
            return bool(self.bir_daha_gosterme.GetValue())
        except Exception:
            return False
