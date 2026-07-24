# -*- coding: utf-8 -*-
# Engelsiz Mail - ayar ve denetim pencereleri

import os
import webbrowser

import wx
import gui
import ui

try:
    import winsound
except Exception:
    winsound = None

from ..errors import MailHatasi
from ..logger import hata_kaydet
from ..validators import eposta_adresi_gecerli_mi
from ..imap_client import ImapBaglantisi
from ..config import (
    MESAJ_SAYISI_ALANI,
    VARSAYILAN_MESAJ_SAYISI,
    EN_AZ_MESAJ_SAYISI,
    EN_COK_MESAJ_SAYISI,
    BILDIRIM_ETKIN_ALANI,
    BILDIRIM_ARALIK_ALANI,
    BILDIRIM_SES_ALANI,
    BILDIRIM_SES_TURU_ALANI,
    BILDIRIM_SES_DOSYASI_ALANI,
    BILDIRIM_SES_TURU_SISTEM,
    BILDIRIM_SES_TURU_DOSYA,
    BILDIRIM_MESAJ_ALANI,
    BILDIRIM_GONDEREN_ALANI,
    BILDIRIM_KONU_ALANI,
    BILDIRIM_ARALIK_SECENEKLERI,
    VARSAYILAN_BILDIRIM_ARALIGI,
    ayarlari_yukle,
    ayarlari_kaydet,
    mesaj_sayisini_kaydet,
    bildirim_araligini_duzenle,
    bildirim_ayarlari_yukle,
    bildirim_ayarlari_kaydet,
)
from ..notifications import bildirim_soyle
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..paths import EKLENTI_KOK_DIZINI
from ..ui_helpers import (
    arka_plan_gorevlerini_gecersiz_kil,
    arka_planda_calistir,
    guvenli_call_after,
    pencere_kullanilabilir_mi,
    gorunum_denetimlerine_uygula,
)


def yardim_belgesini_ac():
    adaylar = [
        os.path.join(EKLENTI_KOK_DIZINI, "doc", "tr", "readme.html"),
    ]
    for yol in adaylar:
        if os.path.exists(yol):
            try:
                os.startfile(yol)
                return True
            except Exception as e:
                hata_kaydet("Yardım dosyası açılamadı.", e)
                break
    ui.message("Yardım dosyası bulunamadı. Lütfen eklenti klasörünü kontrol edin.")
    return False

def uygulama_sifresi_sayfasini_ac():
    url = "https://myaccount.google.com/apppasswords"
    try:
        os.startfile(url)
        return True
    except Exception as e:
        hata_kaydet("Uygulama şifresi sayfası os.startfile ile açılamadı.", e)
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        hata_kaydet("Uygulama şifresi sayfası webbrowser ile açılamadı.", e)
    ui.message("Uygulama şifresi sayfası açılamadı. Adresi tarayıcınızda açabilirsiniz: https://myaccount.google.com/apppasswords")
    return False

class AyarlarPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Hesaba Bağlan")
        ayarlar = ayarlari_yukle()
        self._kayitli_gorunen_ad = str(ayarlar.get("gorunen_ad", "") or "").strip()
        self._kayitli_eposta = str(ayarlar.get("eposta", "") or "").strip()
        self._kayitli_sifre = str(ayarlar.get("sifre", "") or "").strip().replace(" ", "")
        self._baglanti_kontrol_ediliyor = False
        self._kapatildi = False
        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)

        duzen = wx.BoxSizer(wx.VERTICAL)

        duzen.Add(wx.StaticText(self, label="&Görünen adınız:"), 0, wx.ALL, 5)
        self.txt_gorunen_ad = wx.TextCtrl(self, value=self._kayitli_gorunen_ad)
        self.txt_gorunen_ad.SetName("Görünen ad")
        duzen.Add(self.txt_gorunen_ad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&E-posta adresiniz:"), 0, wx.ALL, 5)
        self.txt_eposta = wx.TextCtrl(self, value=self._kayitli_eposta)
        self.txt_eposta.SetName("E-posta adresi")
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Google uygulama şifreniz (16 hane):"), 0, wx.ALL, 5)
        self.txt_sifre = wx.TextCtrl(self, value="", style=wx.TE_PASSWORD)
        self.txt_sifre.SetName("Google uygulama şifresi")
        duzen.Add(self.txt_sifre, 0, wx.ALL | wx.EXPAND, 5)
        if self._kayitli_sifre:
            bilgi = wx.StaticText(
                self,
                label="Kayıtlı uygulama şifresi korunacaktır. Değiştirmek istemiyorsanız bu alanı boş bırakabilirsiniz.",
            )
            duzen.Add(bilgi, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.kaydet_btn = wx.Button(self, label="&Kaydet ve Bağlan")
        self.kaydet_btn.Bind(wx.EVT_BUTTON, self.kaydet_basildi)
        btn_duzen.Add(self.kaydet_btn, 0, wx.ALL, 5)

        sifre_olustur_btn = wx.Button(self, label="Şifre &Oluştur")
        sifre_olustur_btn.Bind(wx.EVT_BUTTON, self.sifre_olustur_basildi)
        btn_duzen.Add(sifre_olustur_btn, 0, wx.ALL, 5)

        yardim_btn = wx.Button(self, label="Uygulama Şifresi &Yardımı")
        yardim_btn.Bind(wx.EVT_BUTTON, self.yardim_basildi)
        btn_duzen.Add(yardim_btn, 0, wx.ALL, 5)

        self.iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((650, 365 if self._kayitli_sifre else 325))
        self.CenterOnParent()
        wx.CallAfter(self.txt_gorunen_ad.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            arka_plan_gorevlerini_gecersiz_kil(self)
        event.Skip()

    def pencere_kapatiliyor(self, event):
        if self._baglanti_kontrol_ediliyor:
            ui.message("Bağlantı denetleniyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        event.Skip()

    def sifre_olustur_basildi(self, event):
        uygulama_sifresi_sayfasini_ac()

    def yardim_basildi(self, event):
        yardim_belgesini_ac()

    def alanlari_etkinlestir(self, etkin=True):
        for denetim in (self.txt_gorunen_ad, self.txt_eposta, self.txt_sifre, self.kaydet_btn, self.iptal_btn):
            try:
                denetim.Enable(etkin)
            except Exception:
                pass

    def kaydet_basildi(self, event):
        if self._baglanti_kontrol_ediliyor:
            return

        gorunen_ad = self.txt_gorunen_ad.GetValue().strip()
        eposta = self.txt_eposta.GetValue().strip()
        sifre = self.txt_sifre.GetValue().strip().replace(" ", "")

        eposta_degisti = eposta.lower() != self._kayitli_eposta.lower()
        etkin_sifre = sifre or ("" if eposta_degisti else self._kayitli_sifre)

        if not eposta:
            ui.message("Lütfen e-posta adresi alanını doldurun.")
            self.txt_eposta.SetFocus()
            return
        if not eposta_adresi_gecerli_mi(eposta):
            ui.message("Lütfen geçerli bir e-posta adresi yazın.")
            self.txt_eposta.SetFocus()
            return
        if not etkin_sifre:
            if eposta_degisti:
                ui.message("E-posta adresini değiştirdiğiniz için yeni Google uygulama şifresini yazmanız gerekir.")
            else:
                ui.message("Lütfen Google uygulama şifresi alanını doldurun.")
            self.txt_sifre.SetFocus()
            return
        if len(etkin_sifre) < 12:
            ui.message("Uygulama şifresi eksik görünüyor. Lütfen Google tarafından verilen şifreyi boşluksuz yazın.")
            self.txt_sifre.SetFocus()
            return

        self._baglanti_kontrol_ediliyor = True
        self.alanlari_etkinlestir(False)

        def baglanti_denetimini_baslat():
            if not pencere_kullanilabilir_mi(self):
                return
            arka_planda_calistir(self._baglantiyi_denetle, eposta, etkin_sifre, gorunen_ad)

        mesaj_soyle_ve_sonra_calistir(
            "Bağlantı denetleniyor. Lütfen bekleyin.",
            baglanti_denetimini_baslat,
            ad="Bağlantı denetimini başlat",
        )

    def _baglantiyi_denetle(self, eposta, sifre, gorunen_ad):
        try:
            with ImapBaglantisi({"eposta": eposta, "sifre": sifre}):
                pass
            guvenli_call_after(self, self._baglanti_basarili, eposta, sifre, gorunen_ad)
        except Exception as e:
            hata_kaydet("Hesap bağlantısı doğrulanamadı.", e)
            guvenli_call_after(self, self._baglanti_hatali)

    def _baglanti_basarili(self, eposta, sifre, gorunen_ad):
        if not pencere_kullanilabilir_mi(self):
            return
        self._baglanti_kontrol_ediliyor = False
        if ayarlari_kaydet(eposta, sifre, gorunen_ad=gorunen_ad):
            gui.messageBox(
                "Gmail bağlantısı kuruldu. E-posta adresiniz ve uygulama şifreniz kaydedildi.",
                "Bağlantı Başarılı",
                wx.OK | wx.ICON_INFORMATION,
            )
            self.EndModal(wx.ID_OK)
        else:
            self.alanlari_etkinlestir(True)
            ui.message("Hesap bilgileri kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")

    def _baglanti_hatali(self):
        if not pencere_kullanilabilir_mi(self):
            return
        self._baglanti_kontrol_ediliyor = False
        self.alanlari_etkinlestir(True)
        gui.messageBox(
            "Gmail hesabına bağlanılamadı. Lütfen e-posta adresinizi, Google uygulama şifrenizi ve internet bağlantınızı kontrol edin. Ayrıntılı denetim için Hesap menüsündeki Bağlantıyı Denetle seçeneğini kullanabilirsiniz.",
            "Bağlantı Başarısız",
            wx.OK | wx.ICON_ERROR,
        )
        self.txt_sifre.SetFocus()

def mesaj_sayisi_metnini_dogrula(metin):
    """Ayar penceresindeki mesaj sayısı alanını doğrular."""
    metin = str(metin or "").strip()
    if not metin:
        raise MailHatasi("Listelenecek e-posta sayısı boş bırakılamaz.")
    try:
        sayi = int(metin)
    except Exception as e:
        raise MailHatasi("Listelenecek e-posta sayısı yalnızca rakamlardan oluşmalıdır.") from e
    if sayi < EN_AZ_MESAJ_SAYISI or sayi > EN_COK_MESAJ_SAYISI:
        raise MailHatasi(f"Listelenecek e-posta sayısı {EN_AZ_MESAJ_SAYISI} ile {EN_COK_MESAJ_SAYISI} arasında olmalıdır.")
    return sayi


class BaglantiDenetimSonucPenceresi(wx.Dialog):
    def __init__(self, parent, basarili, rapor):
        super().__init__(parent, title="Engelsiz Mail - Bağlantı Denetimi")
        self.rapor = str(rapor or "")
        self.detay_gosteriliyor = False

        ozet = self.ozet_metni_olustur(bool(basarili), self.rapor)

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="Bağlantı denetimi özeti:"), 0, wx.ALL, 5)
        self.txt_ozet = wx.TextCtrl(self, value=ozet, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_ozet.SetName("Bağlantı denetimi özeti")
        duzen.Add(self.txt_ozet, 0, wx.ALL | wx.EXPAND, 5)

        self.txt_ayrinti = wx.TextCtrl(self, value=self.rapor, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_ayrinti.SetName("Bağlantı denetimi ayrıntıları")
        duzen.Add(self.txt_ayrinti, 1, wx.ALL | wx.EXPAND, 5)
        self.txt_ayrinti.Hide()
        gorunum_denetimlerine_uygula(self.txt_ozet, self.txt_ayrinti)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ayrinti_btn = wx.Button(self, label="&Ayrıntıları Görüntüle")
        self.ayrinti_btn.Bind(wx.EVT_BUTTON, self.ayrintilari_goster)
        btn_duzen.Add(self.ayrinti_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, wx.ID_OK, label="&Kapat")
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 5)

        self.SetSizer(duzen)
        self.SetSize((760, 420))
        self.CenterOnParent()
        wx.CallAfter(self.txt_ozet.SetFocus)

    def ozet_metni_olustur(self, basarili, rapor):
        rapor = rapor or ""
        rapor_kucuk = rapor.lower()
        if "tamamlanamadı" in rapor_kucuk or "sonuç: sorun bulundu" in rapor_kucuk:
            return "Bağlantı denetimi tamamlandı. Sorun algılandı. Ayrıntıları görüntüleyerek sorunun hangi aşamada oluştuğunu inceleyebilirsiniz."
        if "uyarı var" in rapor_kucuk:
            return "Bağlantı denetimi tamamlandı. Bağlantınız çalışıyor; ancak uyarı var. Ayrıntıları görüntüleyerek uyarıları inceleyebilirsiniz."
        if basarili:
            return "Bağlantı denetimi tamamlandı. Bağlantınız başarılı. Herhangi bir sorun algılanmadı."
        return "Bağlantı denetimi tamamlandı. Sonuç kesin olarak doğrulanamadı. Ayrıntıları görüntüleyerek denetim adımlarını inceleyebilirsiniz."

    def ayrintilari_goster(self, event):
        if not self.detay_gosteriliyor:
            self.detay_gosteriliyor = True
            self.txt_ayrinti.Show()
            self.ayrinti_btn.SetLabel("Ayrıntıları &Gizle")
            self.Layout()
            self.SetSize((760, 600))
            wx.CallAfter(self.txt_ayrinti.SetFocus)
        else:
            self.detay_gosteriliyor = False
            self.txt_ayrinti.Hide()
            self.ayrinti_btn.SetLabel("&Ayrıntıları Görüntüle")
            self.Layout()
            self.SetSize((760, 420))
            wx.CallAfter(self.txt_ozet.SetFocus)


class MesajSayisiPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - E-posta Sayısı")
        ayarlar = ayarlari_yukle()

        duzen = wx.BoxSizer(wx.VERTICAL)
        bilgi = f"Listelenecek e-posta sayısı ({EN_AZ_MESAJ_SAYISI} ile {EN_COK_MESAJ_SAYISI} arasında):"
        duzen.Add(wx.StaticText(self, label="&" + bilgi), 0, wx.ALL, 5)
        self.txt_mesaj_sayisi = wx.TextCtrl(
            self,
            value=str(ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)),
        )
        self.txt_mesaj_sayisi.SetName("Listelenecek e-posta sayısı")
        duzen.Add(self.txt_mesaj_sayisi, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label="&Tamam")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER)
        self.SetSizer(duzen)
        self.SetSize((460, 170))
        self.CenterOnParent()
        wx.CallAfter(self.txt_mesaj_sayisi.SetFocus)

    def tamam_basildi(self, event):
        try:
            mesaj_sayisi = mesaj_sayisi_metnini_dogrula(self.txt_mesaj_sayisi.GetValue())
        except MailHatasi as e:
            ui.message(str(e))
            self.txt_mesaj_sayisi.SetFocus()
            return

        if mesaj_sayisini_kaydet(mesaj_sayisi):
            ui.message(f"Listelenecek e-posta sayısı {mesaj_sayisi} olarak kaydedildi.")
            self.EndModal(wx.ID_OK)
        else:
            ui.message("E-posta sayısı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")


class BildirimAyarlariPenceresi(wx.Dialog):
    def __init__(self, parent, bildirim_yoneticisi_yenile=None):
        super().__init__(parent, title="Engelsiz Mail - Bildirimler")
        self._bildirim_yoneticisi_yenile = bildirim_yoneticisi_yenile
        ayarlar = bildirim_ayarlari_yukle()

        duzen = wx.BoxSizer(wx.VERTICAL)

        bilgi = (
            "Yeni e-posta bildirimleri, NVDA çalışırken arka planda belirli aralıklarla "
            "Gelen Kutusu denetlenerek kullanılacaktır. Bu pencerede yalnızca bildirim ayarları kaydedilir."
        )
        duzen.Add(wx.StaticText(self, label=bilgi), 0, wx.ALL | wx.EXPAND, 5)

        self.chk_bildirim = wx.CheckBox(self, label="&Yeni e-posta bildirimi")
        self.chk_bildirim.SetValue(ayarlar.get(BILDIRIM_ETKIN_ALANI, False))
        duzen.Add(self.chk_bildirim, 0, wx.ALL, 5)

        duzen.Add(wx.StaticText(self, label="Kaç dakikada bir &bakılsın:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.cmb_aralik = wx.Choice(
            self,
            choices=[f"{dakika} dakika" for dakika in BILDIRIM_ARALIK_SECENEKLERI],
        )
        self.cmb_aralik.SetName("Bildirim kontrol aralığı")
        mevcut_aralik = bildirim_araligini_duzenle(ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI))
        try:
            self.cmb_aralik.SetSelection(BILDIRIM_ARALIK_SECENEKLERI.index(mevcut_aralik))
        except Exception:
            self.cmb_aralik.SetSelection(BILDIRIM_ARALIK_SECENEKLERI.index(VARSAYILAN_BILDIRIM_ARALIGI))
        duzen.Add(self.cmb_aralik, 0, wx.ALL | wx.EXPAND, 5)

        self.chk_ses = wx.CheckBox(self, label="&Sesle bildir")
        self.chk_ses.SetValue(ayarlar.get(BILDIRIM_SES_ALANI, True))
        self.chk_ses.Bind(wx.EVT_CHECKBOX, self.ses_alanlarini_guncelle)
        duzen.Add(self.chk_ses, 0, wx.ALL, 5)

        ses_kutusu = wx.StaticBox(self, label="Bildirim sesi")
        ses_duzen = wx.StaticBoxSizer(ses_kutusu, wx.VERTICAL)

        self.rb_sistem_sesi = wx.RadioButton(self, label="&Varsayılan sistem sesini kullan", style=wx.RB_GROUP)
        self.rb_ozel_ses = wx.RadioButton(self, label="&Kullanıcı tanımlı WAV dosyası kullan")
        self.rb_sistem_sesi.Bind(wx.EVT_RADIOBUTTON, self.ses_alanlarini_guncelle)
        self.rb_ozel_ses.Bind(wx.EVT_RADIOBUTTON, self.ses_alanlarini_guncelle)

        ses_turu = ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        self.rb_ozel_ses.SetValue(ses_turu == BILDIRIM_SES_TURU_DOSYA)
        self.rb_sistem_sesi.SetValue(ses_turu != BILDIRIM_SES_TURU_DOSYA)

        ses_duzen.Add(self.rb_sistem_sesi, 0, wx.ALL, 5)
        ses_duzen.Add(self.rb_ozel_ses, 0, wx.ALL, 5)

        dosya_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_ses_dosyasi = wx.TextCtrl(self, value=ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, ""))
        self.txt_ses_dosyasi.SetName("Bildirim sesi dosyası")
        dosya_duzen.Add(self.txt_ses_dosyasi, 1, wx.ALL | wx.EXPAND, 5)

        self.btn_ses_sec = wx.Button(self, label="G&özat...")
        self.btn_ses_sec.Bind(wx.EVT_BUTTON, self.ses_dosyasi_sec)
        dosya_duzen.Add(self.btn_ses_sec, 0, wx.ALL, 5)

        self.btn_ses_dinle = wx.Button(self, label="&Dinle")
        self.btn_ses_dinle.Bind(wx.EVT_BUTTON, self.ses_dosyasi_dinle)
        dosya_duzen.Add(self.btn_ses_dinle, 0, wx.ALL, 5)

        ses_duzen.Add(dosya_duzen, 0, wx.EXPAND)
        duzen.Add(ses_duzen, 0, wx.ALL | wx.EXPAND, 5)

        self.chk_mesaj = wx.CheckBox(self, label="&Mesajla bildir")
        self.chk_mesaj.SetValue(ayarlar.get(BILDIRIM_MESAJ_ALANI, True))
        duzen.Add(self.chk_mesaj, 0, wx.ALL, 5)

        self.chk_gonderen = wx.CheckBox(self, label="Gönderen &adresini bildir")
        self.chk_gonderen.SetValue(ayarlar.get(BILDIRIM_GONDEREN_ALANI, False))
        duzen.Add(self.chk_gonderen, 0, wx.ALL, 5)

        self.chk_konu = wx.CheckBox(self, label="&Konuyu bildir")
        self.chk_konu.SetValue(ayarlar.get(BILDIRIM_KONU_ALANI, False))
        duzen.Add(self.chk_konu, 0, wx.ALL, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, label="&Tamam")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam_basildi)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)

        iptal_btn = wx.Button(self, wx.ID_CANCEL, label="İ&ptal")
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((640, 560))
        self.CenterOnParent()
        self.ses_alanlarini_guncelle()
        wx.CallAfter(self.chk_bildirim.SetFocus)

    def secili_araligi_al(self):
        secim = self.cmb_aralik.GetSelection()
        if secim == wx.NOT_FOUND:
            return VARSAYILAN_BILDIRIM_ARALIGI
        try:
            return BILDIRIM_ARALIK_SECENEKLERI[secim]
        except Exception:
            return VARSAYILAN_BILDIRIM_ARALIGI

    def secili_ses_turunu_al(self):
        if self.rb_ozel_ses.GetValue():
            return BILDIRIM_SES_TURU_DOSYA
        return BILDIRIM_SES_TURU_SISTEM

    def ses_alanlarini_guncelle(self, event=None):
        sesle_bildir = self.chk_ses.GetValue()
        ozel_ses = self.rb_ozel_ses.GetValue()
        try:
            self.rb_sistem_sesi.Enable(sesle_bildir)
            self.rb_ozel_ses.Enable(sesle_bildir)
            self.txt_ses_dosyasi.Enable(sesle_bildir and ozel_ses)
            self.btn_ses_sec.Enable(sesle_bildir and ozel_ses)
            self.btn_ses_dinle.Enable(sesle_bildir and ozel_ses)
        except Exception:
            pass
        if event is not None:
            event.Skip()

    def ses_dosyasi_sec(self, event=None):
        mevcut_yol = self.txt_ses_dosyasi.GetValue().strip()
        mevcut_klasor = os.path.dirname(mevcut_yol) if mevcut_yol else os.path.expanduser("~")
        if not os.path.isdir(mevcut_klasor):
            mevcut_klasor = os.path.expanduser("~")

        dlg = wx.FileDialog(
            self,
            "Bildirim sesi olarak kullanılacak WAV dosyasını seçin",
            defaultDir=mevcut_klasor,
            wildcard="WAV dosyaları (*.wav)|*.wav",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.txt_ses_dosyasi.SetValue(dlg.GetPath())
                self.rb_ozel_ses.SetValue(True)
                self.rb_sistem_sesi.SetValue(False)
                self.ses_alanlarini_guncelle()
        finally:
            dlg.Destroy()

    def ses_dosyasi_dinle(self, event=None):
        ses_dosyasi = self.txt_ses_dosyasi.GetValue().strip()
        if not ses_dosyasi:
            ui.message("Dinlenecek WAV dosyası seçilmedi.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if not ses_dosyasi.lower().endswith(".wav"):
            ui.message("Yalnızca WAV uzantılı bildirim sesi dinlenebilir.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if not os.path.exists(ses_dosyasi):
            ui.message("Seçilen bildirim sesi dosyası bulunamadı.")
            self.txt_ses_dosyasi.SetFocus()
            return
        if winsound is None:
            ui.message("Bu sistemde ses dinleme desteği kullanılamıyor.")
            return
        try:
            winsound.PlaySound(ses_dosyasi, winsound.SND_FILENAME | winsound.SND_ASYNC)
            ui.message("Bildirim sesi çalınıyor.")
        except Exception as e:
            hata_kaydet("Bildirim sesi dinletilemedi.", e)
            ui.message("Bildirim sesi çalınamadı.")

    def tamam_basildi(self, event):
        if not self.chk_ses.GetValue() and not self.chk_mesaj.GetValue():
            ui.message("Bildirim için sesle bildir veya mesajla bildir seçeneklerinden en az biri işaretli olmalıdır.")
            self.chk_ses.SetFocus()
            return

        ses_turu = self.secili_ses_turunu_al()
        ses_dosyasi = self.txt_ses_dosyasi.GetValue().strip()

        if self.chk_ses.GetValue() and ses_turu == BILDIRIM_SES_TURU_DOSYA:
            if not ses_dosyasi:
                ui.message("Kullanıcı tanımlı ses için bir WAV dosyası seçilmelidir.")
                self.txt_ses_dosyasi.SetFocus()
                return
            if not ses_dosyasi.lower().endswith(".wav"):
                ui.message("Bildirim sesi için WAV uzantılı bir dosya seçilmelidir.")
                self.txt_ses_dosyasi.SetFocus()
                return
            if not os.path.exists(ses_dosyasi):
                ui.message("Seçilen bildirim sesi dosyası bulunamadı.")
                self.txt_ses_dosyasi.SetFocus()
                return

        if bildirim_ayarlari_kaydet(
            self.chk_bildirim.GetValue(),
            self.secili_araligi_al(),
            self.chk_ses.GetValue(),
            ses_turu,
            ses_dosyasi,
            self.chk_mesaj.GetValue(),
            self.chk_gonderen.GetValue(),
            self.chk_konu.GetValue(),
        ):
            if callable(self._bildirim_yoneticisi_yenile):
                self._bildirim_yoneticisi_yenile()
            bildirim_soyle("Bildirim ayarları kaydedildi.", 350)
            self.EndModal(wx.ID_OK)
        else:
            ui.message("Bildirim ayarları kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
