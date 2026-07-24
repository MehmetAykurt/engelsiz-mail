# -*- coding: utf-8 -*-
# Engelsiz Mail - kişiler arayüz pencereleri

import wx
import ui

from ..errors import MailHatasi
from ..logger import hata_kaydet
from ..validators import eposta_adresi_gecerli_mi
from ..contacts import (
    kisileri_yukle,
    kisileri_kaydet,
    kisi_ekle_veya_guncelle,
    kisi_gorunen_ad,
    kisi_eposta_basligi,
)
from ..ui_helpers import gorunum_denetimlerine_uygula


class KisiDuzenlemePenceresi(wx.Dialog):
    def __init__(self, parent, kisi=None, baslik="Kişi Oluştur"):
        super().__init__(parent, title=baslik)
        kisi = dict(kisi or {})
        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Ad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_ad = wx.TextCtrl(self, value=str(kisi.get("ad", "")))
        self.txt_ad.SetName("Kişi adı")
        duzen.Add(self.txt_ad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&Soyad:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_soyad = wx.TextCtrl(self, value=str(kisi.get("soyad", "")))
        self.txt_soyad.SetName("Kişi soyadı")
        duzen.Add(self.txt_soyad, 0, wx.ALL | wx.EXPAND, 5)

        duzen.Add(wx.StaticText(self, label="&E-posta adresi:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_eposta = wx.TextCtrl(self, value=str(kisi.get("eposta", "")))
        self.txt_eposta.SetName("Kişi e-posta adresi")
        duzen.Add(self.txt_eposta, 0, wx.ALL | wx.EXPAND, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, wx.ID_OK, "&Kaydet")
        iptal_btn = wx.Button(self, wx.ID_CANCEL, "İ&ptal")
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((420, 260))
        self.CenterOnParent()
        tamam_btn.Bind(wx.EVT_BUTTON, self.kaydet)
        gorunum_denetimlerine_uygula(self.txt_ad, self.txt_soyad, self.txt_eposta)
        wx.CallAfter(self.txt_ad.SetFocus)

    def veri_al(self):
        return {
            "ad": self.txt_ad.GetValue().strip(),
            "soyad": self.txt_soyad.GetValue().strip(),
            "eposta": self.txt_eposta.GetValue().strip(),
        }

    def kaydet(self, event):
        veri = self.veri_al()
        if not veri["ad"] and not veri["soyad"]:
            ui.message("Lütfen ad veya soyad alanlarından en az birini yazın.")
            self.txt_ad.SetFocus()
            return
        if not eposta_adresi_gecerli_mi(veri["eposta"]):
            ui.message("Lütfen geçerli bir e-posta adresi yazın.")
            self.txt_eposta.SetFocus()
            return
        self.EndModal(wx.ID_OK)


class KisilerPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Engelsiz Mail - Kişiler")
        self.kisiler = kisileri_yukle()
        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Kişiler:"), 0, wx.ALL, 5)
        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("Kişiler listesi")
        self.liste.InsertColumn(0, " ", width=700)
        self.liste.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.duzenle)
        duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        gorunum_denetimlerine_uygula(self.liste)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ekle_btn = wx.Button(self, label="&Ekle")
        self.duzenle_btn = wx.Button(self, label="&Düzenle")
        self.sil_btn = wx.Button(self, label="&Sil")
        kapat_btn = wx.Button(self, wx.ID_CANCEL, "&Kapat")
        self.ekle_btn.Bind(wx.EVT_BUTTON, self.ekle)
        self.duzenle_btn.Bind(wx.EVT_BUTTON, self.duzenle)
        self.sil_btn.Bind(wx.EVT_BUTTON, self.sil)
        btn_duzen.Add(self.ekle_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.duzenle_btn, 0, wx.ALL, 5)
        btn_duzen.Add(self.sil_btn, 0, wx.ALL, 5)
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((760, 520))
        self.CenterOnParent()
        self._rehber_acilis_duyuru_timer = None
        self._rehber_acilis_odak_timer = None
        self.listeyi_doldur(secim_yap=False)
        wx.CallAfter(self.rehber_acilisini_planla)

    def rehber_acilisini_planla(self):
        try:
            for timer_adi in ("_rehber_acilis_duyuru_timer", "_rehber_acilis_odak_timer"):
                timer = getattr(self, timer_adi, None)
                if timer:
                    try:
                        timer.Stop()
                    except Exception:
                        pass
                    setattr(self, timer_adi, None)
            self._rehber_acilis_duyuru_timer = wx.CallLater(550, self.rehber_durumunu_soyle)
            self._rehber_acilis_odak_timer = wx.CallLater(1100, self.rehber_acilis_liste_odagi_ver)
        except Exception as e:
            hata_kaydet("Kişiler penceresi açılış duyurusu planlanamadı.", e)
            try:
                self.rehber_durumunu_soyle()
                self.rehber_acilis_liste_odagi_ver()
            except Exception as e2:
                hata_kaydet("Kişiler penceresi açılış odağı ayarlanamadı.", e2)

    def rehber_acilis_liste_odagi_ver(self):
        try:
            if self.kisiler and self.liste.GetItemCount() > 0:
                self.liste.Select(0)
                self.liste.Focus(0)
            self.liste.SetFocus()
        except Exception as e:
            hata_kaydet("Kişiler listesine odak verilemedi.", e)

    def rehber_durum_metni(self):
        sayi = len(self.kisiler)
        if sayi <= 0:
            return "Rehberinizde kayıtlı kişi bulunamadı."
        return f"Rehberde {sayi} kişi listelendi."

    def rehber_durumunu_soyle(self, on_mesaj=None):
        mesajlar = []
        if on_mesaj:
            mesajlar.append(str(on_mesaj).strip())
        mesajlar.append(self.rehber_durum_metni())
        ui.message(" ".join(m for m in mesajlar if m))

    def rehber_durumunu_gecikmeli_soyle(self, on_mesaj=None, gecikme_ms=450):
        try:
            wx.CallLater(int(gecikme_ms), self.rehber_durumunu_soyle, on_mesaj)
        except Exception as e:
            hata_kaydet("Rehber durumu gecikmeli duyurulamadı.", e)
            try:
                self.rehber_durumunu_soyle(on_mesaj)
            except Exception as e2:
                hata_kaydet("Rehber durumu duyurulamadı.", e2)

    def listeyi_doldur(self, secilecek_eposta=None, secim_yap=True):
        self.liste.DeleteAllItems()
        secilecek_indeks = 0
        for indeks, kisi in enumerate(self.kisiler):
            self.liste.InsertItem(indeks, kisi_gorunen_ad(kisi))
            if secilecek_eposta and str(kisi.get("eposta", "")).lower() == secilecek_eposta.lower():
                secilecek_indeks = indeks
        if self.kisiler and secim_yap:
            self.liste.Select(secilecek_indeks)
            self.liste.Focus(secilecek_indeks)

    def secili_indeks(self):
        indeks = self.liste.GetFocusedItem()
        if indeks == wx.NOT_FOUND or indeks < 0 or indeks >= len(self.kisiler):
            return None
        return indeks

    def ekle(self, event):
        pencere = KisiDuzenlemePenceresi(self, baslik="Kişi Oluştur")
        kisi = None
        try:
            if pencere.ShowModal() == wx.ID_OK:
                kisi = pencere.veri_al()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi ekleme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.liste.SetFocus()
        except Exception:
            pass
        if kisi is not None:
            try:
                if not kisi_ekle_veya_guncelle(kisi):
                    ui.message("Kişi kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                    return
                self.kisiler = kisileri_yukle()
                self.listeyi_doldur(kisi.get("eposta", ""))
                self.rehber_durumunu_gecikmeli_soyle("Kişi kaydedildi.")
            except MailHatasi as e:
                ui.message(str(e))
            except Exception as e:
                hata_kaydet("Kişi kaydedilemedi.", e)
                ui.message("Kişi kaydedilemedi.")

    def duzenle(self, event=None):
        indeks = self.secili_indeks()
        if indeks is None:
            ui.message("Düzenlenecek kişi seçilmedi.")
            return
        eski = dict(self.kisiler[indeks])
        pencere = KisiDuzenlemePenceresi(self, eski, "Kişi Düzenle")
        kisi = None
        try:
            if pencere.ShowModal() == wx.ID_OK:
                kisi = pencere.veri_al()
        finally:
            try:
                pencere.Destroy()
            except Exception as e:
                hata_kaydet("Kişi düzenleme penceresi kapatılamadı.", e)
        try:
            self.Raise()
            self.liste.SetFocus()
        except Exception:
            pass
        if kisi is not None:
            try:
                if not kisi_ekle_veya_guncelle(kisi, eski_eposta=eski.get("eposta", "")):
                    ui.message("Kişi güncellenemedi. Lütfen dosya izinlerini kontrol edin.")
                    return
                self.kisiler = kisileri_yukle()
                self.listeyi_doldur(kisi.get("eposta", ""))
                self.rehber_durumunu_gecikmeli_soyle("Kişi güncellendi.")
            except MailHatasi as e:
                ui.message(str(e))
            except Exception as e:
                hata_kaydet("Kişi güncellenemedi.", e)
                ui.message("Kişi güncellenemedi.")

    def sil(self, event):
        indeks = self.secili_indeks()
        if indeks is None:
            ui.message("Silinecek kişi seçilmedi.")
            return
        kisi = self.kisiler[indeks]
        isim = kisi_gorunen_ad(kisi) or "seçili kişi"
        sonuc = wx.MessageBox(f"{isim} silinsin mi?", "Kişi Sil", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if sonuc != wx.YES:
            self.liste.SetFocus()
            return
        try:
            yeni_kisiler = list(self.kisiler)
            del yeni_kisiler[indeks]
            if not kisileri_kaydet(yeni_kisiler):
                ui.message("Kişi silinemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.kisiler = kisileri_yukle()
            self.listeyi_doldur()
            self.rehber_durumunu_gecikmeli_soyle("Kişi silindi.")
        except Exception as e:
            hata_kaydet("Kişi silinemedi.", e)
            ui.message("Kişi silinemedi.")


class KisiSecPenceresi(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Kişilerden Alıcı Seç")
        self.kisiler = kisileri_yukle()
        self.secili_kisiler = []
        self.isaretli_indeksler_kumesi = set()

        duzen = wx.BoxSizer(wx.VERTICAL)
        duzen.Add(wx.StaticText(self, label="&Kişiler:"), 0, wx.ALL, 5)

        # wx.CheckListBox bazı Windows/wx/NVDA birleşimlerinde boşluk tuşunu
        # denetimin varsayılan etkinleştirme davranışına bırakabiliyor. Bu da
        # işaretleme yerine beklenmeyen pencere/düzenleme davranışına yol açabiliyor.
        # Bu yüzden seçim penceresinde işaret durumunu biz yönetiyoruz.
        self.liste = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("Seçilecek kişiler listesi")
        self.liste.InsertColumn(0, "Durum", width=110)
        self.liste.InsertColumn(1, " ", width=560)
        self.liste.Bind(wx.EVT_KEY_DOWN, self.liste_tusuna_basildi)
        duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        gorunum_denetimlerine_uygula(self.liste)

        bilgi = wx.StaticText(self, label="Boşluk tuşuyla kişileri işaretleyip kaldırabilirsiniz. Ekle düğmesi işaretli kişileri alıcı alanına ekler.")
        duzen.Add(bilgi, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        tamam_btn = wx.Button(self, wx.ID_OK, "&Ekle")
        iptal_btn = wx.Button(self, wx.ID_CANCEL, "İ&ptal")
        tamam_btn.Bind(wx.EVT_BUTTON, self.tamam)
        btn_duzen.Add(tamam_btn, 0, wx.ALL, 5)
        btn_duzen.Add(iptal_btn, 0, wx.ALL, 5)
        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)

        self.SetSizer(duzen)
        self.SetSize((760, 480))
        self.CenterOnParent()
        self.listeyi_doldur()
        wx.CallAfter(self.liste.SetFocus)

    def listeyi_doldur(self):
        self.liste.DeleteAllItems()
        if not self.kisiler:
            return
        for indeks, kisi in enumerate(self.kisiler):
            durum = "İşaretli" if indeks in self.isaretli_indeksler_kumesi else "İşaretli değil"
            item = self.liste.InsertItem(indeks, durum)
            self.liste.SetItem(item, 1, kisi_gorunen_ad(kisi))
        self.liste.Select(0)
        self.liste.Focus(0)

    def secili_indeks(self):
        indeks = self.liste.GetFocusedItem()
        if indeks == wx.NOT_FOUND or indeks < 0 or indeks >= len(self.kisiler):
            return None
        return indeks

    def isaret_durumunu_soyle(self, indeks):
        if indeks is None or indeks < 0 or indeks >= len(self.kisiler):
            return
        durum = "işaretli" if indeks in self.isaretli_indeksler_kumesi else "işaretli değil"
        ad = kisi_gorunen_ad(self.kisiler[indeks])
        ui.message(f"{ad}, {durum}.")

    def isareti_degistir(self, indeks):
        if indeks is None or indeks < 0 or indeks >= len(self.kisiler):
            return
        if indeks in self.isaretli_indeksler_kumesi:
            self.isaretli_indeksler_kumesi.remove(indeks)
        else:
            self.isaretli_indeksler_kumesi.add(indeks)
        self.liste.SetItem(indeks, 0, "İşaretli" if indeks in self.isaretli_indeksler_kumesi else "İşaretli değil")
        self.liste.Select(indeks)
        self.liste.Focus(indeks)
        self.isaret_durumunu_soyle(indeks)

    def liste_tusuna_basildi(self, event):
        tus = event.GetKeyCode()
        if tus in (wx.WXK_SPACE, ord(" ")):
            self.isareti_degistir(self.secili_indeks())
            return
        if tus == wx.WXK_RETURN:
            self.tamam(event)
            return
        event.Skip()

    def tamam(self, event):
        if not self.kisiler:
            ui.message("Kayıtlı kişi yok.")
            return
        secimler = sorted(self.isaretli_indeksler_kumesi)
        if not secimler:
            ui.message("Lütfen boşluk tuşuyla en az bir kişi işaretleyin.")
            self.liste.SetFocus()
            return
        self.secili_kisiler = [self.kisiler[i] for i in secimler if 0 <= i < len(self.kisiler)]
        if not self.secili_kisiler:
            ui.message("Geçerli kişi seçilemedi.")
            return
        self.EndModal(wx.ID_OK)

    def secili_adresler(self):
        return [kisi_eposta_basligi(k) for k in self.secili_kisiler if kisi_eposta_basligi(k)]
