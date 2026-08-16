# -*- coding: utf-8 -*-
"""E-posta önbelleğinde erişilebilir arama penceresi."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import wx
import ui

from ..config import ayarlari_yukle
from ..logger import hata_kaydet
from ..folders import klasor_gorunen_adi
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..message_parser import gonderen_gosterimini_al
from ..search import epostalarda_ara
from ..text_utils import guvenli_coz, konu_gosterimini_duzenle, turkce_tarih_yap
from ..ui_helpers import (
    arka_planda_calistir,
    gorunum_denetimlerine_uygula,
    guvenli_call_after,
    guvenli_modal_goster,
)
from .message_view import MesajOkumaPenceresi


ARAMA_SECENEKLERI = (
    (_("Gönderen adına veya adresine göre"), "gonderen"),
    (_("Konuya göre"), "konu"),
    (_("E-posta içeriğine göre"), "icerik"),
    (_("Okunmamış e-postalar"), "okunmamis"),
    (_("Okunmuş e-postalar"), "okunmus"),
)
OKUNMA_DURUMU_ARAMA_TURLERI = {"okunmamis", "okunmus"}


class EpostalardaAraPenceresi(wx.Dialog):
    def __init__(self, parent, ebeveyn_pencere):
        super().__init__(parent, title=_("E-postalarda ara"))
        self.ebeveyn = ebeveyn_pencere
        self.sonuclar = []
        self._arama_no = 0
        self._eposta_aciliyor = False
        self._kapatildi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label=_("Arama &türünü seçin:")), 0, wx.ALL, 5)
        self.cmb_tur = wx.Choice(self, choices=[etiket for etiket, _deger in ARAMA_SECENEKLERI])
        self.cmb_tur.SetName(_("Arama türünü seçin"))
        self.cmb_tur.SetSelection(0)
        self.cmb_tur.Bind(wx.EVT_CHOICE, self.arama_turu_degisti)
        duzen.Add(self.cmb_tur, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("&Aranacak metin:")), 0, wx.ALL, 5)
        self.txt_aranan = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.txt_aranan.SetName(_("Aranacak metin"))
        self.txt_aranan.Bind(wx.EVT_TEXT_ENTER, self.aramayi_baslat)
        duzen.Add(self.txt_aranan, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        self.btn_ara = wx.Button(self, label=_("&Ara"))
        self.btn_ara.Bind(wx.EVT_BUTTON, self.aramayi_baslat)
        duzen.Add(self.btn_ara, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        self.durum = wx.StaticText(self, label=_("Arama ölçütlerini seçip aranacak metni yazın."))
        duzen.Add(self.durum, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName(_("Arama sonuçları"))
        self.liste.InsertColumn(0, _("Kimden"), width=235)
        self.liste.InsertColumn(1, _("Konu"), width=300)
        self.liste.InsertColumn(2, _("Klasör"), width=175)
        self.liste.InsertColumn(3, _("Tarih"), width=180)
        self.liste.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.epostayi_ac)
        duzen.Add(self.liste, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        dugmeler = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_ac = wx.Button(self, label=_("E-postayı &aç"))
        self.btn_klasor = wx.Button(self, label=_("&Klasöre git"))
        self.btn_kapat = wx.Button(self, wx.ID_CLOSE, _("&Kapat"))
        self.btn_ac.Bind(wx.EVT_BUTTON, self.epostayi_ac)
        self.btn_klasor.Bind(wx.EVT_BUTTON, self.klasore_git)
        self.btn_kapat.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        dugmeler.Add(self.btn_ac, 0, wx.ALL, 5)
        dugmeler.Add(self.btn_klasor, 0, wx.ALL, 5)
        dugmeler.Add(self.btn_kapat, 0, wx.ALL, 5)
        duzen.Add(dugmeler, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

        self.SetEscapeId(wx.ID_CLOSE)
        self.SetSizer(duzen)
        self.SetSize((980, 620))
        self.CenterOnParent()
        gorunum_denetimlerine_uygula(
            self.cmb_tur, self.txt_aranan, self.liste, self.durum
        )
        wx.CallAfter(self.cmb_tur.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            self._arama_no += 1
        event.Skip()

    def _secili_arama_turu(self):
        indeks = self.cmb_tur.GetSelection()
        if indeks < 0 or indeks >= len(ARAMA_SECENEKLERI):
            indeks = 0
        return ARAMA_SECENEKLERI[indeks][1]

    def arama_turu_degisti(self, event=None):
        arama_turu = self._secili_arama_turu()
        durum_aramasi = arama_turu in OKUNMA_DURUMU_ARAMA_TURLERI
        self.txt_aranan.Enable(not durum_aramasi)
        if arama_turu == "icerik":
            self.durum.SetLabel(
                _("İçerik araması önbelleğe alınmış e-posta metinlerinde yapılır.")
            )
        elif durum_aramasi:
            self.durum.SetLabel("")
        else:
            self.durum.SetLabel(_("Aranacak metni yazıp Enter tuşuna basın."))
        if event is not None:
            event.Skip()

    def aramayi_baslat(self, event=None):
        arama_turu = self._secili_arama_turu()
        aranan = self.txt_aranan.GetValue().strip()
        if not aranan and arama_turu not in OKUNMA_DURUMU_ARAMA_TURLERI:
            ui.message(_("Lütfen aranacak metni yazın."))
            self.txt_aranan.SetFocus()
            return
        ayarlar = dict(ayarlari_yukle())
        eposta = str(ayarlar.get("eposta", "") or "").strip()
        if not eposta:
            ui.message(_("Arama yapmak için önce Gmail hesabınızı bağlayın."))
            return
        self._arama_no += 1
        arama_no = self._arama_no
        self.btn_ara.Disable()
        self.liste.DeleteAllItems()
        self.sonuclar = []
        mesaj_soyle_ve_sonra_calistir(
            _("Aranıyor."),
            lambda: self._arama_gorevini_baslat(
                eposta, aranan, arama_turu, arama_no
            ),
            ad="E-posta aramasını başlatma",
        )

    def _arama_gorevini_baslat(self, eposta, aranan, arama_turu, arama_no):
        if self._kapatildi or arama_no != self._arama_no:
            return
        arka_planda_calistir(
            self._arama_gorevi, eposta, aranan, arama_turu, arama_no
        )

    def _arama_gorevi(self, eposta, aranan, arama_turu, arama_no):
        try:
            sonuclar = epostalarda_ara(eposta, aranan, arama_turu, sinir=501)
            guvenli_call_after(self, self._sonuclari_goster, sonuclar, arama_no, None)
        except Exception as e:
            hata_kaydet("E-posta araması başarısız oldu.", e)
            guvenli_call_after(self, self._sonuclari_goster, [], arama_no, e)

    def _sonuclari_goster(self, sonuclar, arama_no, hata):
        if arama_no != self._arama_no:
            return
        self.btn_ara.Enable()
        if hata is not None:
            self.durum.SetLabel(_("Arama sırasında bir hata oluştu."))
            ui.message(_("E-postalar aranırken bir hata oluştu."))
            if self.txt_aranan.IsEnabled():
                self.txt_aranan.SetFocus()
            else:
                self.cmb_tur.SetFocus()
            return
        tum_sonuclar = list(sonuclar or [])
        daha_fazla_sonuc_var = len(tum_sonuclar) > 500
        self.sonuclar = tum_sonuclar[:500]
        self.liste.DeleteAllItems()
        for indeks, sonuc in enumerate(self.sonuclar):
            kimden = gonderen_gosterimini_al(sonuc.get("sender", ""), "Bilinmiyor")
            konu = konu_gosterimini_duzenle(
                guvenli_coz(sonuc.get("subject", "") or "Konusuz") or "Konusuz"
            )
            klasor = klasor_gorunen_adi(str(sonuc.get("display_name") or sonuc.get("imap_name") or _("Bilinmiyor")))
            tarih = turkce_tarih_yap(sonuc.get("date_header", ""))
            satir = self.liste.InsertItem(indeks, kimden)
            self.liste.SetItem(satir, 1, konu)
            self.liste.SetItem(satir, 2, klasor)
            self.liste.SetItem(satir, 3, tarih)
        adet = len(self.sonuclar)
        self.durum.SetLabel(
            _("Sonuç bulunamadı.")
            if adet == 0
            else _('İlk {0} arama sonucu gösteriliyor.').format(adet)
            if daha_fazla_sonuc_var
            else _('{0} arama sonucu bulundu.').format(adet)
        )
        mesaj_soyle_ve_sonra_calistir(
            _("Arama sonucunda e-posta bulunamadı.")
            if adet == 0
            else _("Arama sonucunda 500'den fazla e-posta bulundu. İlk {0} sonuç gösteriliyor.").format(adet)
            if daha_fazla_sonuc_var
            else _('Arama sonucunda toplam {0} e-posta bulundu.').format(adet),
            lambda: self._arama_sonrasi_odakla(adet, arama_no),
            ad="Arama sonucu sayısını bildirme",
        )

    def _arama_sonrasi_odakla(self, adet, arama_no):
        if self._kapatildi or arama_no != self._arama_no:
            return
        if adet:
            self.liste.Select(0)
            self.liste.Focus(0)
            self.liste.SetFocus()
        elif self.txt_aranan.IsEnabled():
            self.txt_aranan.SetFocus()
        else:
            self.cmb_tur.SetFocus()

    def _secili_sonuc(self):
        indeks = self.liste.GetFocusedItem()
        if indeks < 0 or indeks >= len(self.sonuclar):
            ui.message(_("Lütfen bir arama sonucu seçin."))
            return None
        return self.sonuclar[indeks]

    def epostayi_ac(self, event=None):
        if self._eposta_aciliyor:
            return
        sonuc = self._secili_sonuc()
        if not sonuc:
            return
        self._eposta_aciliyor = True
        self.btn_ac.Disable()
        self.durum.SetLabel(_("E-posta açılıyor..."))
        arka_planda_calistir(
            self.ebeveyn.sunucudan_icerik_indir,
            str(sonuc.get("uid")),
            str(sonuc.get("imap_name")),
            self.eposta_verisini_goster,
        )

    def eposta_verisini_goster(self, veri):
        if self._kapatildi:
            return
        self._eposta_aciliyor = False
        self.btn_ac.Enable()
        if not veri:
            self.durum.SetLabel(_("E-posta açılamadı. Başka bir sonuç seçebilirsiniz."))
            self.liste.SetFocus()
            return
        pencere = MesajOkumaPenceresi(self, veri, self.ebeveyn)
        guvenli_modal_goster(pencere, self.liste, self)
        if self._secili_arama_turu() == "okunmamis":
            self.durum.SetLabel(_("Okunmamış e-postalar güncelleniyor..."))
            wx.CallAfter(self.aramayi_baslat)
            return
        self.durum.SetLabel(_('{0} arama sonucu bulundu.').format(len(self.sonuclar)))

    def klasore_git(self, event=None):
        sonuc = self._secili_sonuc()
        if not sonuc:
            return
        imap_klasoru = str(sonuc.get("imap_name") or "")
        uid = str(sonuc.get("uid") or "")
        self.EndModal(wx.ID_OK)
        wx.CallAfter(self.ebeveyn.arama_sonucu_klasorune_git, imap_klasoru, uid)
