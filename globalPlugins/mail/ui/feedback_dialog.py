# -*- coding: utf-8 -*-
# Engelsiz Mail - öneri ve görüş penceresi


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import wx
import gui
import ui

from ..errors import MailHatasi
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..validators import eposta_adresi_gecerli_mi
from ..text_utils import eposta_basligi_tek_satir_yap
from ..config import ayarlari_yukle
from ..smtp_client import eposta_mesaji_olustur, smtp_ssl_ile_gonder
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_plan_gorevlerini_gecersiz_kil,
    arka_planda_calistir,
    gorev_icin_guvenli_call_after,
    pencere_kullanilabilir_mi,
)


ONERI_GORUS_ALICI = "m.aykurt38@gmail.com"


class OneriGorusPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=_("Engelsiz Mail - Öneri ve görüş bildir"))
        self._kapatildi = False
        self._gonderiliyor = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        duzen = wx.BoxSizer(wx.VERTICAL)
        bilgi = (
            _("İletişim formu\n"
            "Öneri, görüş ve düşüncelerinizi bize iletebilirsiniz.\n"
            "Bildiriminiz, bağlı Gmail hesabınız üzerinden gönderilecektir.\n"
            "Bildiriminiz değerlendirilecek ve size en kısa sürede yanıt verilecektir.")
        )
        duzen.Add(wx.StaticText(self, label=bilgi), 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("&Ad:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_ad = wx.TextCtrl(self)
        self.txt_ad.SetName(_("Ad"))
        duzen.Add(self.txt_ad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("&Soyad:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_soyad = wx.TextCtrl(self)
        self.txt_soyad.SetName(_("Soyad"))
        duzen.Add(self.txt_soyad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("Yanıt için &e-posta adresiniz:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label=_("Lütfen e-posta adresinizi doğru yazdığınızdan emin olun.")
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_eposta = wx.TextCtrl(self)
        self.txt_eposta.SetName(_("Yanıt için e-posta adresi"))
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("&Konu:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label=_("Bildiriminizin konusu")
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_konu = wx.TextCtrl(self)
        self.txt_konu.SetName(_("Konu"))
        duzen.Add(self.txt_konu, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label=_("&Bildirim metni:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        duzen.Add(
            wx.StaticText(
                self,
                label=_("Bildirim metniniz")
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            5,
        )
        self.txt_mesaj = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_RICH2)
        self.txt_mesaj.SetName(_("Bildirim metni"))
        duzen.Add(self.txt_mesaj, 1, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.gonder_btn = wx.Button(self, label=_("&Gönder"))
        self.gonder_btn.Bind(wx.EVT_BUTTON, self.gonder_tiklandi)
        btn_duzen.Add(self.gonder_btn, 0, wx.ALL, 5)

        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label=_("İ&ptal"))
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((640, 560))
        self.CenterOnParent()
        wx.CallAfter(self.txt_ad.SetFocus)

    def tus_yakalandi(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            if not self._gonderiliyor:
                self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()

    def alanlari_etkinlestir(self, etkin=True):
        for denetim in (
            self.txt_ad,
            self.txt_soyad,
            self.txt_eposta,
            self.txt_konu,
            self.txt_mesaj,
            self.gonder_btn,
            self.iptal_btn,
        ):
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def form_verisini_al(self):
        return {
            "ad": self.txt_ad.GetValue().strip(),
            "soyad": self.txt_soyad.GetValue().strip(),
            "eposta": self.txt_eposta.GetValue().strip(),
            "konu": self.txt_konu.GetValue().strip(),
            "mesaj": self.txt_mesaj.GetValue().strip(),
        }

    def formu_dogrula(self, veri):
        if not veri["ad"]:
            self.txt_ad.SetFocus()
            raise MailHatasi(_("Lütfen ad alanını doldurun."))
        if not veri["soyad"]:
            self.txt_soyad.SetFocus()
            raise MailHatasi(_("Lütfen soyad alanını doldurun."))
        if not eposta_adresi_gecerli_mi(veri["eposta"]):
            self.txt_eposta.SetFocus()
            raise MailHatasi(_("Size yanıt verilebilmesi için lütfen geçerli bir e-posta adresi yazın."))
        if not veri["konu"]:
            self.txt_konu.SetFocus()
            raise MailHatasi(_("Lütfen konu alanını doldurun."))
        if not veri["mesaj"]:
            self.txt_mesaj.SetFocus()
            raise MailHatasi(_("Lütfen bildirim metni alanını doldurun."))

    def gonder_tiklandi(self, event=None):
        if self._gonderiliyor:
            return
        ayarlar = ayarlari_yukle()
        if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
            gui.messageBox(
                _("Öneri ve görüş göndermek için önce Hesap menüsünden Bağlan seçeneğiyle Gmail hesabınızı bağlayın."),
                _("Hesap bilgisi eksik"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return
        veri = self.form_verisini_al()
        try:
            self.formu_dogrula(veri)
        except MailHatasi as e:
            ui.message(str(e))
            return

        self._gonderiliyor = True
        ayarlar = dict(ayarlar)
        veri = dict(veri)
        jeton = arka_plan_gorev_jetonu_olustur(self, "geri_bildirim_gonder", {"hesap": ayarlar.get("eposta", "")})

        def gonderimi_baslat():
            if not pencere_kullanilabilir_mi(self):
                return
            self.alanlari_etkinlestir(False)
            arka_planda_calistir(self.arka_planda_gonder, ayarlar, veri, jeton)

        mesaj_soyle_ve_sonra_calistir(
            _("Öneri ve görüş gönderiliyor."),
            gonderimi_baslat,
            ad="Öneri ve görüş gönderme",
        )

    def arka_planda_gonder(self, ayarlar, veri, jeton):
        try:
            konu = eposta_basligi_tek_satir_yap(veri.get("konu", "")) or _("Konu belirtilmedi")
            baslik = _('[Engelsiz Mail] Öneri ve Görüş: {0}').format(konu)
            icerik = (
                _('Engelsiz Mail eklentisi üzerinden öneri ve görüş bildirimi gönderildi.\n\nAd: {0}\nSoyad: {1}\nYanıt için e-posta: {2}\nEklenti: Engelsiz Mail\nGönderen Gmail hesabı: {3}\nKonu: {4}\n\nBildirim metni:\n{5}\n').format(veri.get('ad', ''), veri.get('soyad', ''), veri.get('eposta', ''), ayarlar.get('eposta', ''), konu, veri.get('mesaj', ''))
            )
            mesaj = eposta_mesaji_olustur(
                ayarlar["eposta"],
                ONERI_GORUS_ALICI,
                baslik,
                icerik,
                [],
                ek_basliklar={"Reply-To": veri.get("eposta", "")},
                taslak=False,
                gorunen_ad=ayarlar.get("gorunen_ad", ""),
            )
            smtp_ssl_ile_gonder(ayarlar["eposta"], ayarlar["sifre"], [ONERI_GORUS_ALICI], mesaj)
            gorev_icin_guvenli_call_after(jeton, self.gonderim_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, str(e))
        except Exception as e:
            hata_kaydet("Öneri ve görüş gönderilemedi.", e)
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, _("Öneri ve görüş gönderilemedi. Lütfen bağlantınızı ve Google uygulama şifrenizi denetleyin."))

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            arka_plan_gorevlerini_gecersiz_kil(self)
        event.Skip()

    def gonderim_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        ui.message(_("Öneri ve görüşünüz gönderildi."))
        self.EndModal(wx.ID_OK)

    def gonderim_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._gonderiliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_mesaj.SetFocus()
