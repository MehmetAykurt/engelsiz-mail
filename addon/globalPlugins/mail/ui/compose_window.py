# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import os
import re

import gui
import ui
import wx

from ..config import ayarlari_yukle, adres_otomatik_kaydet_ayari_yukle
from ..contacts import adres_anahtari, kisileri_yukle, rehbere_ekle, rehberi_yukle
from ..errors import MailHatasi
from ..folders import taslak_klasor_adaylarini_temizle
from ..draft_service import taslagi_sunucuya_kaydet
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..message_parser import adres_basligini_duzenle
from ..smtp_client import eposta_mesaji_olustur, smtp_ssl_ile_gonder
from ..text_utils import guvenli_coz
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_plan_gorevlerini_gecersiz_kil,
    arka_planda_calistir,
    gorev_icin_guvenli_call_after,
    gorunum_denetimlerine_uygula,
    pencere_kullanilabilir_mi,
)
from ..validators import alici_basligini_cozumle
from ..clipboard_helpers import ResimCokBuyukHatasi, panodan_resim_al, panodan_tablo_al
from ..html_composer import (
    metni_etiketle,
    zengin_metinden_htmle_donustur,
    zengin_metinden_duz_metne_donustur,
    RE_BAGLANTI_ETIKETI,
    aralik_sozlugunu_kaydir,
    metin_degisimini_bul,
)
from .contacts_window import KisiSecPenceresi
from .link_dialog import BaglantiEklePenceresi
from .image_dialog import ResimAciklamasiPenceresi
from .table_dialog import TabloEklePenceresi


class YeniPostaPenceresi(wx.Dialog):
    def __init__(
        self,
        parent,
        varsayilan_kime="",
        varsayilan_bilgi="",
        varsayilan_gizli="",
        varsayilan_konu="",
        varsayilan_icerik="",
        yanit_basliklari=None,
        baslik=_("Engelsiz Mail - E-posta yaz"),
        gonderildi_callback=None,
        taslak_sil_callback=None,
        taslak_kaydet_callback=None,
        taslak_klasor_adaylari=None,
        hazir_ekler=None,
        taslak_kimligi=None,
        taslak_klasoru=None,
        taslak_otokayit_sil_callback=None,
    ):
        stil = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX
        super().__init__(parent, title=baslik, style=stil)
        self.ek_kayitlari = []
        self.yanit_basliklari = dict(yanit_basliklari or {})
        self.gonderildi_callback = gonderildi_callback
        self.taslak_sil_callback = taslak_sil_callback
        self.taslak_kaydet_callback = taslak_kaydet_callback
        self.taslak_klasor_adaylari = taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari)
        self.taslak_otokayit_sil_callback = taslak_otokayit_sil_callback
        self._baslangic_taslak_kimligi = dict(taslak_kimligi or {})
        self._sunucu_taslak_kimligi = dict(taslak_kimligi or {})
        self._sunucu_taslak_klasoru = str(taslak_klasoru or "")
        self._kapatildi = False
        self._taslak_kaydediliyor = False
        self._gonderiliyor = False
        self._sunucu_otokayit_yapiliyor = False
        self._sunucu_otokayit_durduruldu = False
        self._sunucu_otokayit_hata_bildirildi = False
        self._sunucu_otokayit_yeni_taslak_var = False
        self._sunucu_otokayit_son_durum = None
        self._baglantilar = {}
        self._ekli_resimler = {}
        self._hizalamalar = {}
        self._basliklar = {}
        self._aktif_yazma_stili = {"b": False, "i": False, "u": False}
        self._sunucu_otokayit_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._sunucu_taslagini_otomatik_kaydet, self._sunucu_otokayit_timer)
        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_ACTIVATE, self._pencere_aktiflesme)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)

        kime_duzen = wx.BoxSizer(wx.HORIZONTAL)
        kime_duzen.Add(wx.StaticText(self, label=_("&Kime (e-posta adresi):")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        gecmis_adresler = rehberi_yukle()
        if varsayilan_kime and all(
            adres_anahtari(varsayilan_kime) != adres_anahtari(adres)
            for adres in gecmis_adresler
        ):
            gecmis_adresler.insert(0, varsayilan_kime)
        self.txt_kime = wx.ComboBox(self, value=varsayilan_kime, choices=gecmis_adresler, style=wx.CB_DROPDOWN)
        self.txt_kime.SetName(_("Alıcı e-posta adresleri"))
        kime_duzen.Add(self.txt_kime, 1, wx.ALL | wx.EXPAND, 5)
        self.kisi_sec_btn = wx.Button(self, label=_("Kişilerden &seç"))
        self.kisi_sec_btn.Bind(wx.EVT_BUTTON, self.kisilerden_sec)
        kime_duzen.Add(self.kisi_sec_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.ana_duzen.Add(kime_duzen, 0, wx.EXPAND)

        bilgi_duzen = wx.BoxSizer(wx.HORIZONTAL)
        bilgi_duzen.Add(wx.StaticText(self, label=_("&Bilgi (e-posta adresi):")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_bilgi = wx.TextCtrl(self, value=varsayilan_bilgi)
        self.txt_bilgi.SetName(_("Bilgi alıcılarının e-posta adresleri"))
        bilgi_duzen.Add(self.txt_bilgi, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(bilgi_duzen, 0, wx.EXPAND)

        gizli_duzen = wx.BoxSizer(wx.HORIZONTAL)
        gizli_duzen.Add(wx.StaticText(self, label=_("&Gizli (e-posta adresi):")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_gizli = wx.TextCtrl(self, value=varsayilan_gizli)
        self.txt_gizli.SetName(_("Gizli alıcıların e-posta adresleri"))
        gizli_duzen.Add(self.txt_gizli, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(gizli_duzen, 0, wx.EXPAND)

        konu_duzen = wx.BoxSizer(wx.HORIZONTAL)
        konu_duzen.Add(wx.StaticText(self, label=_("K&onu:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_konu = wx.TextCtrl(self, value=varsayilan_konu)
        self.txt_konu.SetName(_("E-posta konusu"))
        konu_duzen.Add(self.txt_konu, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(konu_duzen, 0, wx.EXPAND)

        self.ana_duzen.Add(wx.StaticText(self, label=_("&E-posta metni:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_icerik = wx.TextCtrl(self, value=varsayilan_icerik, style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_AUTO_URL)
        self.txt_icerik.SetName(_("E-posta metni"))
        self.txt_icerik.SetHelpText(_("Kalın: Ctrl+B, İtalik: Ctrl+I, Altı çizili: Ctrl+U, Bağlantı: Ctrl+K, Tablo: Ctrl+Shift+T veya sağ tık menüsü"))
        self.txt_icerik.Bind(wx.EVT_CONTEXT_MENU, self.metin_baglam_menusu_goster)
        self._onceki_metin = self.txt_icerik.GetValue()
        self.txt_icerik.Bind(wx.EVT_TEXT, self._metin_degisti)
        self.ana_duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 5)

        ek_duzen = wx.BoxSizer(wx.HORIZONTAL)
        ek_duzen.Add(wx.StaticText(self, label=_("&Ekler:")), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.liste_ekler = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 60))
        self.liste_ekler.SetName(_("Ekler listesi"))
        ek_duzen.Add(self.liste_ekler, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(ek_duzen, 0, wx.EXPAND)
        gorunum_denetimlerine_uygula(
            self.txt_kime,
            self.kisi_sec_btn,
            self.txt_bilgi,
            self.txt_gizli,
            self.txt_konu,
            self.txt_icerik,
            self.liste_ekler,
        )

        for dosya_adi, veri in hazir_ekler or []:
            if veri is not None:
                self.ek_kayitlari.append({"tur": "hazir", "ad": guvenli_coz(dosya_adi or "ek_dosya"), "veri": veri})
                self.liste_ekler.Append(guvenli_coz(dosya_adi or "ek_dosya"))

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ek_ekle_btn = wx.Button(self, label=_("Dosya e&kle"))
        self.ek_ekle_btn.Bind(wx.EVT_BUTTON, self.dosya_ekle)
        btn_duzen.Add(self.ek_ekle_btn, 0, wx.ALL, 5)

        self.ek_kaldir_btn = wx.Button(self, label=_("Eki k&aldır"))
        self.ek_kaldir_btn.Bind(wx.EVT_BUTTON, self.ek_kaldir)
        btn_duzen.Add(self.ek_kaldir_btn, 0, wx.ALL, 5)

        self.gonder_btn = wx.Button(self, label=_("Gönder\tCtrl+Enter"))
        self.gonder_btn.Bind(wx.EVT_BUTTON, self.gonder_tiklandi)
        btn_duzen.Add(self.gonder_btn, 0, wx.ALL, 5)

        self.taslak_kaydet_btn = wx.Button(self, label=_("Taslaklara &kaydet"))
        self.taslak_kaydet_btn.Bind(wx.EVT_BUTTON, self.taslak_kaydet_tiklandi)
        btn_duzen.Add(self.taslak_kaydet_btn, 0, wx.ALL, 5)

        if self.taslak_sil_callback:
            self.taslak_sil_btn = wx.Button(self, label=_("Taslağı &sil"))
            self.taslak_sil_btn.Bind(wx.EVT_BUTTON, self.taslagi_sil)
            btn_duzen.Add(self.taslak_sil_btn, 0, wx.ALL, 5)
        else:
            self.taslak_sil_btn = None

        self.iptal_btn = wx.Button(self, label=_("İ&ptal"))
        self.iptal_btn.Bind(wx.EVT_BUTTON, self.iptal_tiklandi)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        self.ana_duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(self.ana_duzen)
        self.SetSize((960, 720))
        self.CenterOnParent()

        self._baslangic_durumu = self.taslak_durumu_al()
        self._sunucu_otokayit_son_durum = self._baslangic_durumu
        if ayarlari_yukle().get("eposta"):
            saniye = ayarlari_yukle().get("taslak_otokayit_araligi", 60)
            self._sunucu_otokayit_timer.Start(max(1, min(60, int(saniye))) * 1000)

        if varsayilan_kime:
            wx.CallAfter(self.txt_icerik.SetFocus)
            wx.CallAfter(self.txt_icerik.SetInsertionPoint, 0)
        else:
            wx.CallAfter(self.txt_kime.SetFocus)

    def _metin_degisti(self, event):
        """Metin düzenlenince bağlantı, hizalama ve başlık konumlarını metinle birlikte kaydırır."""
        try:
            yeni = self.txt_icerik.GetValue()
            eski = getattr(self, "_onceki_metin", yeni)
            if yeni != eski:
                try:
                    imlec = self.txt_icerik.GetInsertionPoint()
                except Exception:
                    imlec = None
                degisim = metin_degisimini_bul(eski, yeni, imlec=imlec)
                if degisim:
                    for ad, satir in (("_baglantilar", False), ("_hizalamalar", True), ("_basliklar", True)):
                        sozluk = getattr(self, ad, None)
                        if sozluk:
                            setattr(self, ad, aralik_sozlugunu_kaydir(sozluk, *degisim, satir_araligi=satir))
                self._onceki_metin = yeni
        except Exception as e:
            hata_kaydet("Biçimlendirme konumları güncellenemedi.", e)
        finally:
            event.Skip()

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            try:
                self._sunucu_otokayit_timer.Stop()
            except Exception:
                pass
            arka_plan_gorevlerini_gecersiz_kil(self)
        event.Skip()

    def _pencere_aktiflesme(self, event):
        if event.GetActive():
            def _odak_kontrol():
                try:
                    if self._kapatildi or not self:
                        return
                    odak = self.FindFocus()
                    if odak is None or odak is self:
                        if hasattr(self, "txt_icerik") and self.txt_icerik:
                            self.txt_icerik.SetFocus()
                except Exception:
                    pass
            wx.CallAfter(_odak_kontrol)
        event.Skip()

    def pencere_kapatiliyor(self, event):
        if self._gonderiliyor:
            ui.message(_("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        if self._taslak_kaydediliyor:
            ui.message(_("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        if getattr(self, "_sunucu_otokayit_yapiliyor", False):
            ui.message(_("Taslak Gmail'e kaydediliyor. Lütfen tamamlanmasını bekleyin."))
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        if not event.CanVeto():
            event.Skip()
            return
        # Esc, İptal ve normal kapatma aynı kaydetme kararından geçer.
        event.Veto()
        self.iptal_tiklandi(event)

    def kisilerden_sec(self, event=None):
        kisiler = kisileri_yukle()
        if not kisiler:
            ui.message(_("Kayıtlı kişi yok. E-posta menüsünden Kişiler seçeneğiyle kişi oluşturabilirsiniz."))
            self.txt_kime.SetFocus()
            return
        pencere = KisiSecPenceresi(self)
        secilenler = []
        try:
            if pencere.ShowModal() == wx.ID_OK:
                secilenler = pencere.secili_adresler()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi seçme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.txt_kime.SetFocus()
        except Exception:
            pass
        if not secilenler:
            ui.message(_("Seçilen kişilerde geçerli e-posta adresi bulunamadı."))
            self.txt_kime.SetFocus()
            return
        mevcut = self.txt_kime.GetValue().strip()
        parcalar = []
        if mevcut:
            duzenli = adres_basligini_duzenle(mevcut)
            parcalar.extend([p.strip() for p in duzenli.split(",") if p.strip()] if duzenli else [mevcut])
        parcalar.extend(secilenler)
        birlesik = adres_basligini_duzenle(", ".join(parcalar))
        self.txt_kime.SetValue(birlesik)
        try:
            self.txt_kime.SetInsertionPointEnd()
        except Exception:
            pass
        ui.message(_('{0} kişi alıcı alanına eklendi.').format(len(secilenler)))
        self.txt_kime.SetFocus()

    def dosya_ekle(self, event):
        dlg = wx.FileDialog(
            self,
            _("Eklenecek dosyaları seçin"),
            "",
            "",
            "*.*",
            wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        )
        try:
            if dlg.ShowModal() == wx.ID_OK:
                eklenen_sayi = 0
                mevcut_yollar = {kayit.get("yol") for kayit in self.ek_kayitlari if kayit.get("tur") == "dosya"}
                for yol in dlg.GetPaths():
                    if yol not in mevcut_yollar:
                        self.ek_kayitlari.append({"tur": "dosya", "yol": yol})
                        self.liste_ekler.Append(os.path.basename(yol))
                        mevcut_yollar.add(yol)
                        eklenen_sayi += 1
                if eklenen_sayi:
                    ui.message(_('{0} dosya eklendi.').format(eklenen_sayi))
                wx.CallAfter(self.liste_ekler.SetFocus)
            else:
                wx.CallAfter(self.txt_icerik.SetFocus)
        finally:
            dlg.Destroy()

    def ek_kaldir(self, event):
        secili_indeks = self.liste_ekler.GetSelection()
        if secili_indeks == wx.NOT_FOUND:
            ui.message(_("Lütfen kaldırmak istediğiniz eki listeden seçin."))
            self.liste_ekler.SetFocus()
            return
        silinen_isim = self.liste_ekler.GetString(secili_indeks)
        del self.ek_kayitlari[secili_indeks]
        self.liste_ekler.Delete(secili_indeks)
        ui.message(_('Ek kaldırıldı: {0}').format(silinen_isim))
        if self.liste_ekler.GetCount() > 0:
            self.liste_ekler.SetSelection(min(secili_indeks, self.liste_ekler.GetCount() - 1))
        self.liste_ekler.SetFocus()

    def taslagi_sil(self, event):
        if not self.taslak_sil_callback:
            return
        try:
            if self.taslak_sil_callback():
                self.EndModal(wx.ID_OK)
        except Exception as e:
            hata_kaydet("Taslak silme isteği başlatılamadı.", e)
            ui.message(_("Taslak silme işlemi başlatılamadı."))

    def alanlari_etkinlestir(self, etkin=True):
        denetimler = [
            self.txt_kime,
            self.kisi_sec_btn,
            self.txt_bilgi,
            self.txt_gizli,
            self.txt_konu,
            self.txt_icerik,
            self.gonder_btn,
            self.taslak_kaydet_btn,
            self.ek_ekle_btn,
            self.ek_kaldir_btn,
            self.liste_ekler,
            self.iptal_btn,
        ]
        if self.taslak_sil_btn:
            denetimler.append(self.taslak_sil_btn)
        for denetim in denetimler:
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def tus_yakalandi(self, event):
        tus = event.GetKeyCode()
        if event.ControlDown() and not event.AltDown():
            if tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.gonder_tiklandi(event)
                return
            metin_odakta = self.FindFocus() is self.txt_icerik
            if metin_odakta and event.ShiftDown():
                if tus in (ord("T"), ord("t")):
                    self.tablo_ekle_diyalogu_ac()
                    return
                if tus in (ord("L"), ord("l")):
                    self.liste_degistir()
                    return
            if metin_odakta and not event.ShiftDown():
                if tus in (ord("B"), ord("b")):
                    self.bicimlendir("b", _("Kalın"))
                    return
                if tus in (ord("I"), ord("i")):
                    self.bicimlendir("i", _("İtalik"))
                    return
                if tus in (ord("U"), ord("u")):
                    self.bicimlendir("u", _("Altı çizili"))
                    return
                if tus in (ord("E"), ord("e")):
                    self.metni_hizala("center")
                    return
                if tus in (ord("R"), ord("r")):
                    self.metni_hizala("right")
                    return
                if tus in (ord("L"), ord("l")):
                    self.metni_hizala("left")
                    return
                if tus in (ord("K"), ord("k")):
                    self.baglanti_ekle_diyalogu_ac()
                    return
                if tus in (ord("V"), ord("v")):
                    if self.panodan_resim_yapistir():
                        return
                    if self.panodan_tablo_yapistir():
                        return
        if event.ControlDown() and event.AltDown():
            metin_odakta = self.FindFocus() is self.txt_icerik
            if metin_odakta:
                if tus in (ord("1"), getattr(wx, "WXK_NUMPAD1", 325)):
                    self.baslik_yap(1)
                    return
                if tus in (ord("2"), getattr(wx, "WXK_NUMPAD2", 326)):
                    self.baslik_yap(2)
                    return
                if tus in (ord("3"), getattr(wx, "WXK_NUMPAD3", 327)):
                    self.baslik_yap(3)
                    return
                if tus in (ord("4"), getattr(wx, "WXK_NUMPAD4", 328)):
                    self.baslik_yap(4)
                    return
                if tus in (ord("5"), getattr(wx, "WXK_NUMPAD5", 329)):
                    self.baslik_yap(5)
                    return
                if tus in (ord("6"), getattr(wx, "WXK_NUMPAD6", 330)):
                    self.baslik_yap(6)
                    return
                if tus in (ord("0"), getattr(wx, "WXK_NUMPAD0", 324)):
                    self.baslik_yap(0)
                    return
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.iptal_tiklandi(event)
            return
        event.Skip()

    def bicimlendir(self, etiket, etiket_adi):
        try:
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()
            if secim_sonu > secim_basi:
                attr = wx.TextAttr()
                try:
                    self.txt_icerik.GetStyle(secim_basi, attr)
                except Exception:
                    pass

                yeni_attr = wx.TextAttr()
                kaldirildi = False

                if etiket == "b":
                    mevcut = (attr.GetFontWeight() == wx.FONTWEIGHT_BOLD)
                    yeni_attr.SetFontWeight(wx.FONTWEIGHT_NORMAL if mevcut else wx.FONTWEIGHT_BOLD)
                    kaldirildi = mevcut
                elif etiket == "i":
                    mevcut = (attr.GetFontStyle() == wx.FONTSTYLE_ITALIC)
                    yeni_attr.SetFontStyle(wx.FONTSTYLE_NORMAL if mevcut else wx.FONTSTYLE_ITALIC)
                    kaldirildi = mevcut
                elif etiket == "u":
                    mevcut = bool(attr.GetFontUnderlined())
                    yeni_attr.SetFontUnderlined(not mevcut)
                    kaldirildi = mevcut

                self.txt_icerik.SetStyle(secim_basi, secim_sonu, yeni_attr)
                self.txt_icerik.SetSelection(secim_basi, secim_sonu)
                mesaj = _("{0} kaldırıldı.").format(etiket_adi) if kaldirildi else _("{0} yapıldı.").format(etiket_adi)
            else:
                if not hasattr(self, "_aktif_yazma_stili"):
                    self._aktif_yazma_stili = {"b": False, "i": False, "u": False}
                yeni_durum = not self._aktif_yazma_stili.get(etiket, False)
                self._aktif_yazma_stili[etiket] = yeni_durum

                varsayilan_attr = wx.TextAttr()
                if self._aktif_yazma_stili.get("b"):
                    varsayilan_attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                else:
                    varsayilan_attr.SetFontWeight(wx.FONTWEIGHT_NORMAL)

                if self._aktif_yazma_stili.get("i"):
                    varsayilan_attr.SetFontStyle(wx.FONTSTYLE_ITALIC)
                else:
                    varsayilan_attr.SetFontStyle(wx.FONTSTYLE_NORMAL)

                if self._aktif_yazma_stili.get("u"):
                    varsayilan_attr.SetFontUnderlined(True)
                else:
                    varsayilan_attr.SetFontUnderlined(False)

                self.txt_icerik.SetDefaultStyle(varsayilan_attr)
                mesaj = _("{0} açık.").format(etiket_adi) if yeni_durum else _("{0} kapalı.").format(etiket_adi)

            mesaj_soyle_ve_sonra_calistir(
                mesaj,
                lambda: self.txt_icerik.SetFocus(),
                ad="Biçimlendirme bildirimi",
            )
        except Exception as e:
            hata_kaydet("Metin biçimlendirilemedi.", e)

    def metni_hizala(self, hizalama="left"):
        try:
            tam_metin = str(self.txt_icerik.GetValue() or "")
            uzunluk = len(tam_metin)
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()

            if secim_sonu > secim_basi:
                bas = tam_metin.rfind("\n", 0, secim_basi)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", secim_sonu)
                bit = uzunluk if bit == -1 else bit
            else:
                konum = self.txt_icerik.GetInsertionPoint()
                bas = tam_metin.rfind("\n", 0, konum)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", konum)
                bit = uzunluk if bit == -1 else bit

            attr = wx.TextAttr()
            if hizalama == "center":
                attr.SetAlignment(wx.TEXT_ALIGNMENT_CENTRE)
                mesaj = _("Ortalandı.")
            elif hizalama == "right":
                attr.SetAlignment(wx.TEXT_ALIGNMENT_RIGHT)
                mesaj = _("Sağa yaslandı.")
            else:
                attr.SetAlignment(wx.TEXT_ALIGNMENT_LEFT)
                mesaj = _("Sola hizalandı.")

            try:
                self.txt_icerik.SetStyle(bas, bit, attr)
            except Exception:
                pass

            if not hasattr(self, "_hizalamalar"):
                self._hizalamalar = {}
            self._hizalamalar[(bas, bit)] = hizalama

            mesaj_soyle_ve_sonra_calistir(
                mesaj,
                lambda: self.txt_icerik.SetFocus(),
                ad="Metin hizalama bildirimi",
            )
        except Exception as e:
            hata_kaydet("Metin hizalanamadı.", e)

    def baslik_yap(self, seviye=1):
        try:
            tam_metin = str(self.txt_icerik.GetValue() or "")
            uzunluk = len(tam_metin)
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()

            if secim_sonu > secim_basi:
                bas = tam_metin.rfind("\n", 0, secim_basi)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", secim_sonu)
                bit = uzunluk if bit == -1 else bit
            else:
                konum = self.txt_icerik.GetInsertionPoint()
                bas = tam_metin.rfind("\n", 0, konum)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", konum)
                bit = uzunluk if bit == -1 else bit

            attr = wx.TextAttr()
            if seviye == 1:
                attr.SetFontSize(16)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                mesaj = _("Başlık 1 yapıldı.")
            elif seviye == 2:
                attr.SetFontSize(14)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                mesaj = _("Başlık 2 yapıldı.")
            elif seviye == 3:
                attr.SetFontSize(13)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                mesaj = _("Başlık 3 yapıldı.")
            elif seviye == 4:
                attr.SetFontSize(12)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                mesaj = _("Başlık 4 yapıldı.")
            elif seviye == 5:
                attr.SetFontSize(11)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                mesaj = _("Başlık 5 yapıldı.")
            elif seviye == 6:
                attr.SetFontSize(10)
                attr.SetFontWeight(wx.FONTWEIGHT_BOLD)
                attr.SetFontStyle(wx.FONTSTYLE_ITALIC)
                mesaj = _("Başlık 6 yapıldı.")
            else:
                attr.SetFontSize(11)
                attr.SetFontWeight(wx.FONTWEIGHT_NORMAL)
                attr.SetFontStyle(wx.FONTSTYLE_NORMAL)
                mesaj = _("Normal metin yapıldı.")

            try:
                self.txt_icerik.SetStyle(bas, bit, attr)
            except Exception:
                pass

            if not hasattr(self, "_basliklar"):
                self._basliklar = {}

            # Çakışan veya aynı satırdaki eski başlık kaydını temizle
            self._basliklar = {
                (b, s): sev for (b, s), sev in self._basliklar.items()
                if not (bas <= b < bit or bas < s <= bit or (b <= bas and bit <= s))
            }
            if seviye > 0:
                self._basliklar[(bas, bit)] = seviye

            mesaj_soyle_ve_sonra_calistir(
                mesaj,
                lambda: self.txt_icerik.SetFocus(),
                ad="Başlık seviyesi bildirimi",
            )
        except Exception as e:
            hata_kaydet("Başlık seviyesi ayarlanamadı.", e)

    def liste_degistir(self, hedef_tur=None):
        try:
            tam_metin = str(self.txt_icerik.GetValue() or "")
            uzunluk = len(tam_metin)
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()

            if secim_sonu > secim_basi:
                bas = tam_metin.rfind("\n", 0, secim_basi)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", secim_sonu)
                bit = uzunluk if bit == -1 else bit
            else:
                konum = self.txt_icerik.GetInsertionPoint()
                bas = tam_metin.rfind("\n", 0, konum)
                bas = 0 if bas == -1 else bas + 1
                bit = tam_metin.find("\n", konum)
                bit = uzunluk if bit == -1 else bit

            secili_blok = tam_metin[bas:bit]
            satirlar = secili_blok.split("\n")

            dolu_satirlar = [s.strip() for s in satirlar if s.strip()]
            madde_sayisi = sum(1 for s in dolu_satirlar if s.startswith("• ") or s.startswith("* ") or s.startswith("- "))
            numara_sayisi = sum(1 for s in dolu_satirlar if re.match(r'^\d+[\.\)]\s*', s))

            mevcut_tur = "none"
            if dolu_satirlar and madde_sayisi == len(dolu_satirlar):
                mevcut_tur = "bullet"
            elif dolu_satirlar and numara_sayisi == len(dolu_satirlar):
                mevcut_tur = "numbered"

            if hedef_tur is None:
                if mevcut_tur == "none":
                    hedef = "bullet"
                elif mevcut_tur == "bullet":
                    hedef = "numbered"
                else:
                    hedef = "none"
            else:
                hedef = hedef_tur

            re_on_ek = re.compile(r'^(?:[•\*\-]\s*|\d+[\.\)]\s*)')

            def _satir_temizle(s):
                return re_on_ek.sub('', s)

            yeni_satirlar = []
            if hedef == "bullet":
                for s in satirlar:
                    if s.strip():
                        yeni_satirlar.append(f"• {_satir_temizle(s)}")
                    else:
                        yeni_satirlar.append(s)
                mesaj = _("Madde işaretli liste yapıldı.")
            elif hedef == "numbered":
                sayac = 1
                for s in satirlar:
                    if s.strip():
                        yeni_satirlar.append(f"{sayac}. {_satir_temizle(s)}")
                        sayac += 1
                    else:
                        yeni_satirlar.append(s)
                mesaj = _("Numaralı liste yapıldı.")
            else:
                for s in satirlar:
                    yeni_satirlar.append(_satir_temizle(s))
                mesaj = _("Liste kaldırıldı.")

            yeni_blok = "\n".join(yeni_satirlar)
            self.txt_icerik.Replace(bas, bit, yeni_blok)
            self.txt_icerik.SetSelection(bas, bas + len(yeni_blok))

            mesaj_soyle_ve_sonra_calistir(
                mesaj,
                lambda: self.txt_icerik.SetFocus(),
                ad="Liste bildirimi",
            )
        except Exception as e:
            hata_kaydet("Liste işlemi yapılamadı.", e)

    def baglanti_ekle_diyalogu_ac(self):
        try:
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()
            tam_metin = self.txt_icerik.GetValue()
            konum = self.txt_icerik.GetInsertionPoint()

            # İmleç veya seçim var olan bir bağlantının üzerinde mi?
            mevcut_aralik = None
            mevcut_url = ""
            baglantilar = getattr(self, "_baglantilar", {})
            for (bas, bit), url in baglantilar.items():
                if secim_sonu > secim_basi:
                    if not (secim_sonu <= bas or secim_basi >= bit):
                        mevcut_aralik = (bas, bit)
                        mevcut_url = url
                        break
                else:
                    if bas <= konum <= bit:
                        mevcut_aralik = (bas, bit)
                        mevcut_url = url
                        break

            duzenleme_modu = (mevcut_aralik is not None)
            if duzenleme_modu:
                secim_basi, secim_sonu = mevcut_aralik
                secili = tam_metin[secim_basi:secim_sonu]
                aday_url = mevcut_url
            else:
                secili = tam_metin[secim_basi:secim_sonu] if secim_sonu > secim_basi else ""
                aday_url = ""

            dlg = BaglantiEklePenceresi(
                self,
                varsayilan_metin=secili,
                varsayilan_url=aday_url,
                duzenleme_modu=duzenleme_modu,
            )
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    if getattr(dlg, "baglanti_silindi", False):
                        if mevcut_aralik and mevcut_aralik in self._baglantilar:
                            del self._baglantilar[mevcut_aralik]
                        norm_attr = wx.TextAttr()
                        norm_attr.SetFontUnderlined(False)
                        try:
                            norm_attr.SetURL("")
                        except Exception:
                            pass
                        norm_attr.SetTextColour(wx.Colour(0, 0, 0))
                        self.txt_icerik.SetStyle(secim_basi, secim_sonu, norm_attr)
                        mesaj_soyle_ve_sonra_calistir(
                            _("Bağlantı kaldırıldı."),
                            lambda: self.txt_icerik.SetFocus(),
                            ad="Bağlantı kaldırma bildirimi",
                        )
                        return

                    gorunen_metin = getattr(dlg, "sonuc_metin", "") or getattr(dlg, "sonuc_etiketi", "")
                    link_url = getattr(dlg, "sonuc_url", "")
                    if not link_url and "<a href=" in gorunen_metin:
                        m = RE_BAGLANTI_ETIKETI.search(gorunen_metin)
                        if m:
                            link_url = m.group("url")
                            gorunen_metin = m.group("metin")

                    if gorunen_metin:
                        if duzenleme_modu and mevcut_aralik in self._baglantilar:
                            del self._baglantilar[mevcut_aralik]

                        if secim_sonu > secim_basi:
                            self.txt_icerik.Replace(secim_basi, secim_sonu, gorunen_metin)
                            aralik_basi = secim_basi
                            aralik_sonu = secim_basi + len(gorunen_metin)
                        else:
                            konum = self.txt_icerik.GetInsertionPoint()
                            self.txt_icerik.WriteText(gorunen_metin)
                            aralik_basi = konum
                            aralik_sonu = konum + len(gorunen_metin)

                        link_attr = wx.TextAttr()
                        if link_url:
                            try:
                                link_attr.SetURL(link_url)
                            except Exception:
                                pass
                        link_attr.SetFontUnderlined(True)
                        link_attr.SetTextColour(wx.Colour(0, 102, 204))
                        self.txt_icerik.SetStyle(aralik_basi, aralik_sonu, link_attr)

                        if not hasattr(self, "_baglantilar"):
                            self._baglantilar = {}
                        self._baglantilar[(aralik_basi, aralik_sonu)] = link_url

                        self.txt_icerik.SetInsertionPoint(aralik_sonu)
                        varsayilan_attr = wx.TextAttr()
                        varsayilan_attr.SetFontUnderlined(False)
                        try:
                            varsayilan_attr.SetURL("")
                        except Exception:
                            pass
                        varsayilan_attr.SetTextColour(wx.Colour(0, 0, 0))
                        self.txt_icerik.SetDefaultStyle(varsayilan_attr)

                        mesaj = _("Bağlantı güncellendi.") if duzenleme_modu else _("Bağlantı eklendi.")
                        mesaj_soyle_ve_sonra_calistir(
                            mesaj,
                            lambda: self.txt_icerik.SetFocus(),
                            ad="Bağlantı ekleme bildirimi",
                        )
            finally:
                dlg.Destroy()
                if self.FindFocus() is not self.txt_icerik:
                    self.txt_icerik.SetFocus()
        except Exception as e:
            hata_kaydet("Bağlantı ekleme penceresi açılamadı.", e)

    def panodan_resim_yapistir(self):
        try:
            resim_bilgisi = panodan_resim_al()
            if not resim_bilgisi:
                return False
            baytlar, uzanti, aday_ad = resim_bilgisi
            dlg = ResimAciklamasiPenceresi(self, varsayilan_aciklama=aday_ad)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    aciklama = dlg.sonuc_aciklama or aday_ad or _("Resim")
                    if not hasattr(self, "_ekli_resimler"):
                        self._ekli_resimler = {}
                    cid = f"resim_{len(self._ekli_resimler) + 1}"
                    etiket = f"[Resim: {aciklama}]"
                    self._ekli_resimler[cid] = {
                        "bayt": baytlar,
                        "uzanti": uzanti,
                        "alt": aciklama,
                        "etiket": etiket,
                    }
                    secim_basi, secim_sonu = self.txt_icerik.GetSelection()
                    if secim_sonu > secim_basi:
                        self.txt_icerik.Replace(secim_basi, secim_sonu, etiket)
                        self.txt_icerik.SetInsertionPoint(secim_basi + len(etiket))
                    else:
                        konum = self.txt_icerik.GetInsertionPoint()
                        self.txt_icerik.WriteText(etiket)
                        self.txt_icerik.SetInsertionPoint(konum + len(etiket))

                    mesaj_soyle_ve_sonra_calistir(
                        _("Resim eklendi: {0}").format(aciklama),
                        lambda: self.txt_icerik.SetFocus(),
                        ad="Resim ekleme bildirimi",
                    )
                    return True
                else:
                    return True
            finally:
                dlg.Destroy()
                if self.FindFocus() is not self.txt_icerik:
                    self.txt_icerik.SetFocus()
        except ResimCokBuyukHatasi:
            ui.message(_("Resim çok büyük. E-postaya en çok 10 MB boyutunda resim eklenebilir."))
            return True
        except Exception as e:
            hata_kaydet("Panodan resim yapıştırılamadı.", e)
            return False

    def tablo_ekle_diyalogu_ac(self):
        try:
            dlg = TabloEklePenceresi(self)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    sablon = getattr(dlg, "sonuc_sablonu", "")
                    if sablon:
                        secim_basi, secim_sonu = self.txt_icerik.GetSelection()
                        if secim_sonu > secim_basi:
                            self.txt_icerik.Replace(secim_basi, secim_sonu, sablon)
                            self.txt_icerik.SetInsertionPoint(secim_basi + len(sablon))
                        else:
                            konum = self.txt_icerik.GetInsertionPoint()
                            self.txt_icerik.WriteText(sablon)
                            self.txt_icerik.SetInsertionPoint(konum + len(sablon))

                        mesaj_soyle_ve_sonra_calistir(
                            _("Tablo eklendi."),
                            lambda: self.txt_icerik.SetFocus(),
                            ad="Tablo ekleme bildirimi",
                        )
            finally:
                dlg.Destroy()
                if self.FindFocus() is not self.txt_icerik:
                    self.txt_icerik.SetFocus()
        except Exception as e:
            hata_kaydet("Tablo ekleme penceresi açılamadı.", e)

    def panodan_tablo_yapistir(self):
        try:
            tablo_metni = panodan_tablo_al()
            if not tablo_metni:
                return False

            secim_basi, secim_sonu = self.txt_icerik.GetSelection()
            if secim_sonu > secim_basi:
                self.txt_icerik.Replace(secim_basi, secim_sonu, tablo_metni)
                self.txt_icerik.SetInsertionPoint(secim_basi + len(tablo_metni))
            else:
                konum = self.txt_icerik.GetInsertionPoint()
                self.txt_icerik.WriteText(tablo_metni)
                self.txt_icerik.SetInsertionPoint(konum + len(tablo_metni))

            mesaj_soyle_ve_sonra_calistir(
                _("Tablo yapıştırıldı."),
                lambda: self.txt_icerik.SetFocus(),
                ad="Tablo yapıştırma bildirimi",
            )
            return True
        except Exception as e:
            hata_kaydet("Panodan tablo yapıştırılamadı.", e)
            return False

    def metin_baglam_menusu_goster(self, event=None):
        try:
            menu = wx.Menu()

            tablo_ogesi = menu.Append(wx.ID_ANY, _("Tablo Ekle...\tCtrl+Shift+T"))
            self.Bind(wx.EVT_MENU, lambda e: self.tablo_ekle_diyalogu_ac(), tablo_ogesi)

            link_ogesi = menu.Append(wx.ID_ANY, _("Bağlantı Ekle...\tCtrl+K"))
            self.Bind(wx.EVT_MENU, lambda e: self.baglanti_ekle_diyalogu_ac(), link_ogesi)

            menu.AppendSeparator()

            kalin_ogesi = menu.Append(wx.ID_ANY, _("Kalın\tCtrl+B"))
            self.Bind(wx.EVT_MENU, lambda e: self.bicimlendir("b", _("Kalın")), kalin_ogesi)

            italik_ogesi = menu.Append(wx.ID_ANY, _("İtalik\tCtrl+I"))
            self.Bind(wx.EVT_MENU, lambda e: self.bicimlendir("i", _("İtalik")), italik_ogesi)

            alticizili_ogesi = menu.Append(wx.ID_ANY, _("Altı çizili\tCtrl+U"))
            self.Bind(wx.EVT_MENU, lambda e: self.bicimlendir("u", _("Altı çizili")), alticizili_ogesi)

            menu.AppendSeparator()

            hizala_menusu = wx.Menu()
            sola_ogesi = hizala_menusu.Append(wx.ID_ANY, _("Sola Hizala\tCtrl+L"))
            self.Bind(wx.EVT_MENU, lambda e: self.metni_hizala("left"), sola_ogesi)
            ortala_ogesi = hizala_menusu.Append(wx.ID_ANY, _("Ortala\tCtrl+E"))
            self.Bind(wx.EVT_MENU, lambda e: self.metni_hizala("center"), ortala_ogesi)
            saga_ogesi = hizala_menusu.Append(wx.ID_ANY, _("Sağa Yasla\tCtrl+R"))
            self.Bind(wx.EVT_MENU, lambda e: self.metni_hizala("right"), saga_ogesi)
            menu.AppendSubMenu(hizala_menusu, _("Hizala"))

            baslik_menusu = wx.Menu()
            for sev in range(1, 7):
                b_ogesi = baslik_menusu.Append(wx.ID_ANY, _("Başlık {0}\tCtrl+Alt+{0}").format(sev))
                self.Bind(wx.EVT_MENU, lambda e, s=sev: self.baslik_yap(s), b_ogesi)
            baslik_menusu.AppendSeparator()
            normal_ogesi = baslik_menusu.Append(wx.ID_ANY, _("Normal Metin\tCtrl+Alt+0"))
            self.Bind(wx.EVT_MENU, lambda e: self.baslik_yap(0), normal_ogesi)
            menu.AppendSubMenu(baslik_menusu, _("Başlıklar"))

            liste_menusu = wx.Menu()
            madde_ogesi = liste_menusu.Append(wx.ID_ANY, _("Madde İşaretli Liste\tCtrl+Shift+L"))
            self.Bind(wx.EVT_MENU, lambda e: self.liste_degistir("bullet"), madde_ogesi)
            numarali_ogesi = liste_menusu.Append(wx.ID_ANY, _("Numaralı Liste"))
            self.Bind(wx.EVT_MENU, lambda e: self.liste_degistir("numbered"), numarali_ogesi)
            liste_menusu.AppendSeparator()
            liste_kaldir_ogesi = liste_menusu.Append(wx.ID_ANY, _("Listeyi Kaldır"))
            self.Bind(wx.EVT_MENU, lambda e: self.liste_degistir("none"), liste_kaldir_ogesi)
            menu.AppendSubMenu(liste_menusu, _("Liste"))

            menu.AppendSeparator()

            kes_ogesi = menu.Append(wx.ID_CUT, _("Kes\tCtrl+X"))
            self.Bind(wx.EVT_MENU, lambda e: self.txt_icerik.Cut(), kes_ogesi)

            kopyala_ogesi = menu.Append(wx.ID_COPY, _("Kopyala\tCtrl+C"))
            self.Bind(wx.EVT_MENU, lambda e: self.txt_icerik.Copy(), kopyala_ogesi)

            yapistir_ogesi = menu.Append(wx.ID_PASTE, _("Yapıştır\tCtrl+V"))
            self.Bind(wx.EVT_MENU, lambda e: self._baglam_yapistir(), yapistir_ogesi)

            self.PopupMenu(menu)
            menu.Destroy()
        except Exception as e:
            hata_kaydet("Metin bağlam menüsü açılamadı.", e)

    def _baglam_yapistir(self):
        if self.panodan_resim_yapistir():
            return
        if self.panodan_tablo_yapistir():
            return
        self.txt_icerik.Paste()

    def taslak_durumu_al(self):
        ekler = []
        for kayit in self.ek_kayitlari:
            if isinstance(kayit, str):
                ekler.append(("dosya", kayit))
            elif kayit.get("tur") == "hazir":
                ekler.append(("hazir", kayit.get("ad", ""), len(kayit.get("veri") or b"")))
            else:
                ekler.append((kayit.get("tur", ""), kayit.get("yol", "")))
        return (
            self.txt_kime.GetValue().strip(),
            self.txt_bilgi.GetValue().strip(),
            self.txt_gizli.GetValue().strip(),
            self.txt_konu.GetValue().strip(),
            self.txt_icerik.GetValue(),
            tuple(ekler),
        )

    def taslak_icerigi_var_mi(self):
        kime, bilgi, gizli, konu, icerik, ekler = self.taslak_durumu_al()
        return bool(kime or bilgi or gizli or konu or str(icerik or "").strip() or ekler)

    def taslak_degisti_mi(self):
        return self.taslak_durumu_al() != getattr(self, "_sunucu_otokayit_son_durum", None)

    def taslak_verisini_al(self):
        baglantilar = getattr(self, "_baglantilar", {})
        ekli_resimler = getattr(self, "_ekli_resimler", {})
        hizalamalar = getattr(self, "_hizalamalar", {})
        basliklar = getattr(self, "_basliklar", {})
        duz_donustur = globals().get("zengin_metinden_duz_metne_donustur")
        if callable(duz_donustur):
            duz_icerik = duz_donustur(self.txt_icerik, imza="", baglantilar=baglantilar)
        elif hasattr(self.txt_icerik, "GetValue"):
            duz_icerik = self.txt_icerik.GetValue()
        else:
            duz_icerik = str(self.txt_icerik or "")

        html_donustur = globals().get("zengin_metinden_htmle_donustur")
        if callable(html_donustur):
            html_icerik = html_donustur(self.txt_icerik, imza="", baglantilar=baglantilar, ekli_resimler=ekli_resimler, hizalamalar=hizalamalar, basliklar=basliklar)
        else:
            html_icerik = ""
        return {
            "kime": self.txt_kime.GetValue().strip(),
            "bilgi": self.txt_bilgi.GetValue().strip(),
            "gizli": self.txt_gizli.GetValue().strip(),
            "konu": self.txt_konu.GetValue().strip(),
            "icerik": duz_icerik,
            "html_icerik": html_icerik,
            "ekli_resimler": dict(ekli_resimler),
            "ek_kayitlari": list(self.ek_kayitlari),
            "yanit_basliklari": dict(self.yanit_basliklari),
        }

    def _sunucu_taslagini_otomatik_kaydet(self, event=None):
        if (self._kapatildi or self._gonderiliyor or self._taslak_kaydediliyor
                or self._sunucu_otokayit_durduruldu or self._sunucu_otokayit_yapiliyor):
            return
        saniye = ayarlari_yukle().get("taslak_otokayit_araligi", 60)
        aralik_ms = max(1, min(60, int(saniye))) * 1000
        if self._sunucu_otokayit_timer.GetInterval() != aralik_ms:
            self._sunucu_otokayit_timer.Start(aralik_ms)
        durum = self.taslak_durumu_al()
        if not self.taslak_icerigi_var_mi() or durum == self._sunucu_otokayit_son_durum:
            return
        self._sunucu_otokayit_yapiliyor = True
        veri = self.taslak_verisini_al()
        ayarlar = dict(ayarlari_yukle())
        jeton = arka_plan_gorev_jetonu_olustur(self, "taslak_otokayit", {"hesap": ayarlar.get("eposta", "")})
        arka_planda_calistir(self._sunucu_otokayit_gorevini_yurut, veri, durum, ayarlar, jeton)

    def _sunucu_otokayit_gorevini_yurut(self, veri, durum, ayarlar, jeton):
        try:
            sonuc = taslagi_sunucuya_kaydet(
                veri.get("kime", ""), veri.get("bilgi", ""), veri.get("gizli", ""),
                veri.get("konu", ""), veri.get("icerik", ""), veri.get("ek_kayitlari", []),
                veri.get("yanit_basliklari", {}), self.taslak_klasor_adaylari, ayarlar,
                onceki_taslak_kimligi=self._sunucu_taslak_kimligi or None,
                onceki_taslak_klasoru=self._sunucu_taslak_klasoru or None,
                kimlik_dondur=True,
                html_icerik=veri.get("html_icerik", None),
                ekli_resimler=veri.get("ekli_resimler"),
            )
            gorev_icin_guvenli_call_after(jeton, self._sunucu_otokayit_basarili, durum, sonuc)
        except Exception as e:
            hata_kaydet("Gmail taslağı otomatik kaydedilemedi.", e)
            gorev_icin_guvenli_call_after(
                jeton,
                self._sunucu_otokayit_hatali,
                str(e),
                getattr(e, "belirsiz_kayit", False),
            )

    def _sunucu_otokayit_basarili(self, durum, sonuc):
        self._sunucu_otokayit_yapiliyor = False
        self._sunucu_otokayit_hata_bildirildi = False
        if isinstance(sonuc, dict):
            self._sunucu_taslak_kimligi = dict(sonuc.get("kimlik") or {})
            self._sunucu_taslak_klasoru = str(sonuc.get("klasor", "") or "")
            self._sunucu_otokayit_yeni_taslak_var = True
            self._sunucu_otokayit_son_durum = durum
            if not sonuc.get("eski_taslak_silindi", True):
                self._sunucu_otokayit_durduruldu = True
                self._sunucu_otokayit_timer.Stop()
                ui.message(_("Yeni Gmail taslağı kaydedildi ancak önceki taslak kaldı. Kopya oluşmaması için otomatik kayıt durduruldu; Taslaklar klasörünü denetleyin."))
                return
            return
        self._sunucu_otokayit_hatali(
            _("Gmail taslağının yeni kimliği doğrulanamadı. Önceki taslak korunuyor."),
            belirsiz_kayit=True,
        )

    def _sunucu_otokayit_hatali(self, mesaj, belirsiz_kayit=False):
        self._sunucu_otokayit_yapiliyor = False
        if not self._sunucu_otokayit_hata_bildirildi and pencere_kullanilabilir_mi(self):
            self._sunucu_otokayit_hata_bildirildi = True
            if belirsiz_kayit:
                self._sunucu_otokayit_durduruldu = True
                self._sunucu_otokayit_timer.Stop()
            ui.message(_("Gmail'e otomatik taslak kaydedilemedi. Önceki taslak korunuyor. {0}").format(mesaj))

    def _taslak_otokayit_sonrasi_yenile(self):
        if not getattr(self, "_sunucu_otokayit_yeni_taslak_var", False):
            return
        self._sunucu_otokayit_yeni_taslak_var = False
        callback = getattr(self, "taslak_kaydet_callback", None)
        if callable(callback):
            try:
                callback()
            except Exception as e:
                hata_kaydet("Otomatik taslak sonrası liste yenilenemedi.", e)

    def _otokayit_taslagini_sunucudan_sil(self):
        kimlik = getattr(self, "_sunucu_taslak_kimligi", None)
        callback = getattr(self, "taslak_otokayit_sil_callback", None)
        klasor = getattr(self, "_sunucu_taslak_klasoru", "")
        if kimlik and callback:
            try:
                callback(dict(kimlik), klasor)
                self._sunucu_taslak_kimligi = {}
                self._sunucu_otokayit_yeni_taslak_var = False
            except Exception as e:
                hata_kaydet("İptal edilen e-postanın otomatik taslağı silinemedi.", e)

    def iptal_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message(_("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            return
        if self._taslak_kaydediliyor:
            ui.message(_("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            return
        if getattr(self, "_sunucu_otokayit_yapiliyor", False):
            ui.message(_("Taslak Gmail'e kaydediliyor. Lütfen tamamlanmasını bekleyin."))
            return
        timer = getattr(self, "_sunucu_otokayit_timer", None)
        if timer:
            timer.Stop()
        self._sunucu_otokayit_durduruldu = True

        if not self.taslak_icerigi_var_mi():
            if not getattr(self, "_baslangic_taslak_kimligi", None) and getattr(self, "_sunucu_taslak_kimligi", None):
                self._otokayit_taslagini_sunucudan_sil()
            self._taslak_otokayit_sonrasi_yenile()
            self.EndModal(wx.ID_CANCEL)
            return

        sonuc = gui.messageBox(
            _("Bu e-posta gönderilmedi. Değişiklikler taslaklara kaydedilsin mi?"),
            _("Taslağı kaydet"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
            self,
        )
        if sonuc == wx.YES:
            self.taslak_kaydet_tiklandi(event)
        elif sonuc == wx.NO:
            if not getattr(self, "_baslangic_taslak_kimligi", None) and getattr(self, "_sunucu_taslak_kimligi", None):
                self._otokayit_taslagini_sunucudan_sil()
            self._taslak_otokayit_sonrasi_yenile()
            self.EndModal(wx.ID_CANCEL)
        else:
            self.txt_icerik.SetFocus()

    def taslak_kaydet_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message(_("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            return
        if self._taslak_kaydediliyor:
            return
        if not self.taslak_icerigi_var_mi():
            ui.message(_("Kaydedilecek taslak içeriği bulunamadı."))
            self.txt_icerik.SetFocus()
            return
        veri = self.taslak_verisini_al()
        timer = getattr(self, "_sunucu_otokayit_timer", None)
        if timer:
            timer.Stop()
        kimlik = getattr(self, "_sunucu_taslak_kimligi", {})
        if kimlik and self.taslak_durumu_al() == getattr(self, "_sunucu_otokayit_son_durum", None):
            self.taslak_kaydetme_basarili({
                "kimlik": kimlik,
                "klasor": getattr(self, "_sunucu_taslak_klasoru", ""),
                "eski_taslak_silindi": True,
            })
            return
        self._taslak_kaydediliyor = True
        self.alanlari_etkinlestir(False)
        ayarlar = dict(ayarlari_yukle())
        jeton = arka_plan_gorev_jetonu_olustur(self, "taslak_kaydet", {"hesap": ayarlar.get("eposta", "")})

        def taslak_kaydetmeyi_baslat():
            if not pencere_kullanilabilir_mi(self):
                return
            self.alanlari_etkinlestir(False)
            arka_planda_calistir(self.arka_planda_taslak_kaydet, veri, ayarlar, jeton)

        mesaj_soyle_ve_sonra_calistir(
            _("Taslaklara kaydediliyor."),
            taslak_kaydetmeyi_baslat,
            ad="Taslak kaydetme",
        )

    def arka_planda_taslak_kaydet(self, veri, ayarlar, jeton):
        try:
            sonuc = taslagi_sunucuya_kaydet(
                veri.get("kime", ""),
                veri.get("bilgi", ""),
                veri.get("gizli", ""),
                veri.get("konu", ""),
                veri.get("icerik", ""),
                veri.get("ek_kayitlari", []),
                veri.get("yanit_basliklari", {}),
                self.taslak_klasor_adaylari,
                ayarlar,
                onceki_taslak_kimligi=self._sunucu_taslak_kimligi or None,
                onceki_taslak_klasoru=self._sunucu_taslak_klasoru or None,
                kimlik_dondur=True,
                html_icerik=veri.get("html_icerik", None),
                ekli_resimler=veri.get("ekli_resimler"),
            )
            gorev_icin_guvenli_call_after(jeton, self.taslak_kaydetme_basarili, sonuc)
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(
                jeton,
                self.taslak_kaydetme_hatali,
                str(e),
                getattr(e, "belirsiz_kayit", False),
            )
        except Exception as e:
            hata_kaydet("Taslak kaydedilemedi.", e)
            gorev_icin_guvenli_call_after(jeton, self.taslak_kaydetme_hatali, _("Taslak kaydedilemedi. Lütfen bağlantınızı ve Google uygulama şifrenizi denetleyin."))

    def taslak_kaydetme_basarili(self, sonuc=None):
        if not pencere_kullanilabilir_mi(self):
            return
        if isinstance(sonuc, dict) and sonuc.get("kimlik"):
            self._sunucu_taslak_kimligi = dict(sonuc["kimlik"])
            self._sunucu_taslak_klasoru = str(sonuc.get("klasor", "") or "")
            self._sunucu_otokayit_son_durum = self.taslak_durumu_al()
            self._sunucu_otokayit_yeni_taslak_var = True
        callback_sonucu = False
        if self.taslak_kaydet_callback:
            try:
                callback_sonucu = bool(self.taslak_kaydet_callback())
            except Exception as e:
                hata_kaydet("Taslak kaydetme sonrası işlem başlatılamadı.", e)
        ui.message(_("Taslak Gmail'in Taslaklar klasörüne kaydedildi."))
        if isinstance(sonuc, dict) and not sonuc.get("eski_taslak_silindi", True):
            ui.message(_("Önceki taslak da kaldı. Taslaklar klasörünü denetleyin."))
        self._sunucu_otokayit_yeni_taslak_var = False
        self.EndModal(wx.ID_OK)

    def taslak_kaydetme_hatali(self, mesaj, belirsiz_kayit=False):
        if not pencere_kullanilabilir_mi(self):
            return
        self._taslak_kaydediliyor = False
        if belirsiz_kayit:
            self._sunucu_otokayit_durduruldu = True
            self._sunucu_otokayit_timer.Stop()
        if ayarlari_yukle().get("eposta") and not self._sunucu_otokayit_durduruldu:
            saniye = ayarlari_yukle().get("taslak_otokayit_araligi", 60)
            self._sunucu_otokayit_timer.Start(max(1, min(60, int(saniye))) * 1000)
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()

    def gonder_tiklandi(self, event):
        if self._gonderiliyor:
            return
        if self._taslak_kaydediliyor:
            ui.message(_("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin."))
            return
        kime = self.txt_kime.GetValue().strip()
        bilgi = self.txt_bilgi.GetValue().strip()
        gizli = self.txt_gizli.GetValue().strip()
        konu = self.txt_konu.GetValue().strip()
        baglantilar = getattr(self, "_baglantilar", {})
        ekli_resimler = getattr(self, "_ekli_resimler", {})
        hizalamalar = getattr(self, "_hizalamalar", {})
        basliklar = getattr(self, "_basliklar", {})
        duz_donustur = globals().get("zengin_metinden_duz_metne_donustur")
        if callable(duz_donustur):
            duz_icerik = duz_donustur(self.txt_icerik, imza="", baglantilar=baglantilar)
        elif hasattr(self.txt_icerik, "GetValue"):
            duz_icerik = self.txt_icerik.GetValue()
        else:
            duz_icerik = str(self.txt_icerik or "")

        html_donustur = globals().get("zengin_metinden_htmle_donustur")
        if callable(html_donustur):
            html_icerik = html_donustur(self.txt_icerik, imza="", baglantilar=baglantilar, ekli_resimler=ekli_resimler, hizalamalar=hizalamalar, basliklar=basliklar)
        else:
            html_icerik = ""
        kime_alicilari, kime_gecersizleri = alici_basligini_cozumle(kime)
        bilgi_alicilari, bilgi_gecersizleri = alici_basligini_cozumle(bilgi)
        gizli_alicilar, gizli_gecersizleri = alici_basligini_cozumle(gizli)

        for alan_adi, alan_degeri, adresler, gecersizler, denetim in (
            (_("Kime"), kime, kime_alicilari, kime_gecersizleri, self.txt_kime),
            (_("Bilgi"), bilgi, bilgi_alicilari, bilgi_gecersizleri, self.txt_bilgi),
            (_("Gizli"), gizli, gizli_alicilar, gizli_gecersizleri, self.txt_gizli),
        ):
            if gecersizler:
                ui.message(_('{0} alanında geçersiz e-posta adresi bulundu: {1}').format(alan_adi, gecersizler[0]))
                denetim.SetFocus()
                return
            if alan_degeri and not adresler:
                ui.message(_('{0} alanında geçerli bir e-posta adresi bulunamadı.').format(alan_adi))
                denetim.SetFocus()
                return

        alicilar = []
        gorulen_alicilar = set()
        for adres in (*kime_alicilari, *bilgi_alicilari, *gizli_alicilar):
            anahtar = adres.lower()
            if anahtar not in gorulen_alicilar:
                alicilar.append(adres)
                gorulen_alicilar.add(anahtar)

        if not alicilar:
            ui.message(_("Lütfen geçerli en az bir alıcı adresi girin."))
            self.txt_kime.SetFocus()
            return

        if not konu:
            yanit = gui.messageBox(
                _("Bu e-postanın konusu boş. Yine de göndermek istiyor musunuz?"),
                _("Konu boş"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            if yanit != wx.YES:
                self.txt_konu.SetFocus()
                return

        self._gonderiliyor = True
        timer = getattr(self, "_sunucu_otokayit_timer", None)
        if timer:
            timer.Stop()
        self.alanlari_etkinlestir(False)
        ayarlar = dict(ayarlari_yukle())
        jeton = arka_plan_gorev_jetonu_olustur(self, "eposta_gonder", {"hesap": ayarlar.get("eposta", ""), "alicilar": tuple(alicilar)})

        def gonderimi_baslat():
            if not pencere_kullanilabilir_mi(self):
                return
            self.alanlari_etkinlestir(False)
            arka_planda_calistir(
                self.arka_planda_gonder,
                ayarlar,
                kime,
                bilgi,
                gizli,
                konu,
                duz_icerik,
                alicilar,
                list(self.ek_kayitlari),
                dict(self.yanit_basliklari),
                jeton,
                html_icerik,
                dict(ekli_resimler),
            )

        mesaj_soyle_ve_sonra_calistir(
            _("E-postanız gönderiliyor."),
            gonderimi_baslat,
            ad="E-posta gönderme",
        )

    def arka_planda_gonder(self, ayarlar, kime, bilgi, gizli, konu, icerik, alicilar, ek_kayitlari, yanit_basliklari, jeton, html_icerik=None, ekli_resimler=None):
        try:
            if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
                raise MailHatasi(_("Hesap bilgileri eksik."))

            mesaj = eposta_mesaji_olustur(
                ayarlar["eposta"],
                kime,
                konu,
                icerik,
                ek_kayitlari,
                ek_basliklar=yanit_basliklari,
                taslak=False,
                gorunen_ad=ayarlar.get("gorunen_ad", ""),
                bilgi_basligi=bilgi,
                gizli_basligi=gizli,
                html_icerik=html_icerik,
                ekli_resimler=ekli_resimler,
            )

            smtp_ssl_ile_gonder(ayarlar["eposta"], ayarlar["sifre"], alicilar, mesaj)
            gorev_icin_guvenli_call_after(
                jeton,
                self.gonderim_basarili,
                tuple(alicilar),
            )
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, str(e))
        except Exception as e:
            hata_kaydet("E-posta gönderilemedi.", e)
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, _("Gönderim başarısız oldu. Lütfen bağlantınızı ve Google uygulama şifrenizi denetleyin."))

    def gonderim_basarili(self, alicilar=()):
        if not pencere_kullanilabilir_mi(self):
            return
        otomatik_kaydet = False
        try:
            otomatik_kaydet = bool(adres_otomatik_kaydet_ayari_yukle())
        except Exception as e:
            hata_kaydet("Adres geçmişi ayarı okunamadı.", e)
        if otomatik_kaydet:
            for adres in reversed(tuple(alicilar or ())):
                try:
                    rehbere_ekle(adres)
                except Exception as e:
                    hata_kaydet("Gönderilen alıcı adres geçmişine kaydedilemedi.", e)

        def gonderim_sonrasini_tamamla():
            if not pencere_kullanilabilir_mi(self):
                return
            if (getattr(self, "_sunucu_taslak_kimligi", None)
                    and getattr(self, "taslak_otokayit_sil_callback", None)):
                try:
                    self.taslak_otokayit_sil_callback(
                        dict(self._sunucu_taslak_kimligi),
                        getattr(self, "_sunucu_taslak_klasoru", ""),
                    )
                except Exception as e:
                    hata_kaydet("Gönderim sonrası otomatik Gmail taslağı silinemedi.", e)
            elif self.gonderildi_callback:
                try:
                    self.gonderildi_callback()
                except Exception as e:
                    hata_kaydet("Gönderim sonrası işlem başlatılamadı.", e)
            if pencere_kullanilabilir_mi(self):
                self.EndModal(wx.ID_OK)

        mesaj_soyle_ve_sonra_calistir(
            _("E-posta başarıyla gönderildi."),
            gonderim_sonrasini_tamamla,
            ad="E-posta gönderim sonucu",
        )

    def gonderim_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._gonderiliyor = False
        if ayarlari_yukle().get("eposta") and not self._sunucu_otokayit_durduruldu:
            saniye = ayarlari_yukle().get("taslak_otokayit_araligi", 60)
            self._sunucu_otokayit_timer.Start(max(1, min(60, int(saniye))) * 1000)
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()
