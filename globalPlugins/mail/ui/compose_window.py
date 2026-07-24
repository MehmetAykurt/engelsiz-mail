# -*- coding: utf-8 -*-

import os

import gui
import ui
import wx

from ..config import ayarlari_yukle, adres_otomatik_kaydet_ayari_yukle
from ..contacts import kisileri_yukle, rehbere_ekle, rehberi_yukle
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
from ..validators import alici_listesi_yap
from .contacts_window import KisiSecPenceresi


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
        baslik="Engelsiz Mail - E-posta Yaz",
        gonderildi_callback=None,
        taslak_sil_callback=None,
        taslak_kaydet_callback=None,
        taslak_klasor_adaylari=None,
        hazir_ekler=None,
    ):
        super().__init__(parent, title=baslik)
        self.ek_kayitlari = []
        self.yanit_basliklari = dict(yanit_basliklari or {})
        self.gonderildi_callback = gonderildi_callback
        self.taslak_sil_callback = taslak_sil_callback
        self.taslak_kaydet_callback = taslak_kaydet_callback
        self.taslak_klasor_adaylari = taslak_klasor_adaylarini_temizle(taslak_klasor_adaylari)
        self._kapatildi = False
        self._taslak_kaydediliyor = False
        self._gonderiliyor = False
        self.Bind(wx.EVT_CLOSE, self.pencere_kapatiliyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)

        kime_duzen = wx.BoxSizer(wx.HORIZONTAL)
        kime_duzen.Add(wx.StaticText(self, label="&Kime (e-posta adresi):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        gecmis_adresler = rehberi_yukle()
        if varsayilan_kime and varsayilan_kime not in gecmis_adresler:
            gecmis_adresler.insert(0, varsayilan_kime)
        self.txt_kime = wx.ComboBox(self, value=varsayilan_kime, choices=gecmis_adresler, style=wx.CB_DROPDOWN)
        self.txt_kime.SetName("Alıcı e-posta adresleri")
        kime_duzen.Add(self.txt_kime, 1, wx.ALL | wx.EXPAND, 5)
        self.kisi_sec_btn = wx.Button(self, label="Kişilerden &Seç")
        self.kisi_sec_btn.Bind(wx.EVT_BUTTON, self.kisilerden_sec)
        kime_duzen.Add(self.kisi_sec_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.ana_duzen.Add(kime_duzen, 0, wx.EXPAND)

        bilgi_duzen = wx.BoxSizer(wx.HORIZONTAL)
        bilgi_duzen.Add(wx.StaticText(self, label="&Bilgi (e-posta adresi):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_bilgi = wx.TextCtrl(self, value=varsayilan_bilgi)
        self.txt_bilgi.SetName("Bilgi alıcılarının e-posta adresleri")
        bilgi_duzen.Add(self.txt_bilgi, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(bilgi_duzen, 0, wx.EXPAND)

        gizli_duzen = wx.BoxSizer(wx.HORIZONTAL)
        gizli_duzen.Add(wx.StaticText(self, label="&Gizli (e-posta adresi):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_gizli = wx.TextCtrl(self, value=varsayilan_gizli)
        self.txt_gizli.SetName("Gizli alıcıların e-posta adresleri")
        gizli_duzen.Add(self.txt_gizli, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(gizli_duzen, 0, wx.EXPAND)

        konu_duzen = wx.BoxSizer(wx.HORIZONTAL)
        konu_duzen.Add(wx.StaticText(self, label="K&onu:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.txt_konu = wx.TextCtrl(self, value=varsayilan_konu)
        self.txt_konu.SetName("E-posta konusu")
        konu_duzen.Add(self.txt_konu, 1, wx.ALL | wx.EXPAND, 5)
        self.ana_duzen.Add(konu_duzen, 0, wx.EXPAND)

        self.ana_duzen.Add(wx.StaticText(self, label="&E-posta metni:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.txt_icerik = wx.TextCtrl(self, value=varsayilan_icerik, style=wx.TE_MULTILINE | wx.TE_RICH2)
        self.txt_icerik.SetName("E-posta metni")
        self.ana_duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 5)

        ek_duzen = wx.BoxSizer(wx.HORIZONTAL)
        ek_duzen.Add(wx.StaticText(self, label="Ekli &dosyalar:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.liste_ekler = wx.ListBox(self, style=wx.LB_SINGLE, size=(-1, 60))
        self.liste_ekler.SetName("Ekli dosyalar listesi")
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
            if veri:
                self.ek_kayitlari.append({"tur": "hazir", "ad": guvenli_coz(dosya_adi or "ek_dosya"), "veri": veri})
                self.liste_ekler.Append(guvenli_coz(dosya_adi or "ek_dosya"))

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        self.ek_ekle_btn = wx.Button(self, label="Dosya e&kle")
        self.ek_ekle_btn.Bind(wx.EVT_BUTTON, self.dosya_ekle)
        btn_duzen.Add(self.ek_ekle_btn, 0, wx.ALL, 5)

        self.ek_kaldir_btn = wx.Button(self, label="Eki k&aldır")
        self.ek_kaldir_btn.Bind(wx.EVT_BUTTON, self.ek_kaldir)
        btn_duzen.Add(self.ek_kaldir_btn, 0, wx.ALL, 5)

        self.gonder_btn = wx.Button(self, label="Gönder\tCtrl+Enter")
        self.gonder_btn.Bind(wx.EVT_BUTTON, self.gonder_tiklandi)
        btn_duzen.Add(self.gonder_btn, 0, wx.ALL, 5)

        self.taslak_kaydet_btn = wx.Button(self, label="Taslaklara &Kaydet")
        self.taslak_kaydet_btn.Bind(wx.EVT_BUTTON, self.taslak_kaydet_tiklandi)
        btn_duzen.Add(self.taslak_kaydet_btn, 0, wx.ALL, 5)

        if self.taslak_sil_callback:
            self.taslak_sil_btn = wx.Button(self, label="Taslağı &Sil")
            self.taslak_sil_btn.Bind(wx.EVT_BUTTON, self.taslagi_sil)
            btn_duzen.Add(self.taslak_sil_btn, 0, wx.ALL, 5)
        else:
            self.taslak_sil_btn = None

        self.iptal_btn = wx.Button(self, label="İ&ptal")
        self.iptal_btn.Bind(wx.EVT_BUTTON, self.iptal_tiklandi)
        btn_duzen.Add(self.iptal_btn, 0, wx.ALL, 5)

        self.ana_duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(self.ana_duzen)
        self.SetSize((760, 720))
        self.CenterOnParent()

        self._baslangic_durumu = self.taslak_durumu_al()

        if varsayilan_kime:
            wx.CallAfter(self.txt_icerik.SetFocus)
            wx.CallAfter(self.txt_icerik.SetInsertionPoint, 0)
        else:
            wx.CallAfter(self.txt_kime.SetFocus)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            arka_plan_gorevlerini_gecersiz_kil(self)
        event.Skip()

    def pencere_kapatiliyor(self, event):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            try:
                if event.CanVeto():
                    event.Veto()
                    return
            except Exception:
                return
        event.Skip()

    def kisilerden_sec(self, event=None):
        kisiler = kisileri_yukle()
        if not kisiler:
            ui.message("Kayıtlı kişi yok. E-posta menüsünden Kişiler seçeneğiyle kişi oluşturabilirsiniz.")
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
            ui.message("Seçilen kişilerde geçerli e-posta adresi bulunamadı.")
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
        ui.message(f"{len(secilenler)} kişi alıcı alanına eklendi.")
        self.txt_kime.SetFocus()

    def dosya_ekle(self, event):
        dlg = wx.FileDialog(
            self,
            "Eklenecek dosyaları seçin",
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
                    ui.message(f"{eklenen_sayi} dosya eklendi.")
                wx.CallAfter(self.liste_ekler.SetFocus)
            else:
                wx.CallAfter(self.txt_icerik.SetFocus)
        finally:
            dlg.Destroy()

    def ek_kaldir(self, event):
        secili_indeks = self.liste_ekler.GetSelection()
        if secili_indeks == wx.NOT_FOUND:
            ui.message("Lütfen kaldırmak istediğiniz eki listeden seçin.")
            self.liste_ekler.SetFocus()
            return
        silinen_isim = self.liste_ekler.GetString(secili_indeks)
        del self.ek_kayitlari[secili_indeks]
        self.liste_ekler.Delete(secili_indeks)
        ui.message(f"Ek kaldırıldı: {silinen_isim}")
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
            ui.message("Taslak silme işlemi başlatılamadı.")

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
        if event.ControlDown() and tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.gonder_tiklandi(event)
            return
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.iptal_tiklandi(event)
            return
        event.Skip()

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
        return self.taslak_durumu_al() != getattr(self, "_baslangic_durumu", None)

    def taslak_verisini_al(self):
        return {
            "kime": self.txt_kime.GetValue().strip(),
            "bilgi": self.txt_bilgi.GetValue().strip(),
            "gizli": self.txt_gizli.GetValue().strip(),
            "konu": self.txt_konu.GetValue().strip(),
            "icerik": self.txt_icerik.GetValue(),
            "ek_kayitlari": list(self.ek_kayitlari),
            "yanit_basliklari": dict(self.yanit_basliklari),
        }

    def iptal_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if not self.taslak_icerigi_var_mi() or not self.taslak_degisti_mi():
            self.EndModal(wx.ID_CANCEL)
            return

        sonuc = gui.messageBox(
            "Bu e-posta gönderilmedi. Değişiklikler taslaklara kaydedilsin mi?",
            "Taslak Kaydet",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
            self,
        )
        if sonuc == wx.YES:
            self.taslak_kaydet_tiklandi(event)
        elif sonuc == wx.NO:
            self.EndModal(wx.ID_CANCEL)
        else:
            self.txt_icerik.SetFocus()

    def taslak_kaydet_tiklandi(self, event=None):
        if self._gonderiliyor:
            ui.message("E-posta gönderiliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        if self._taslak_kaydediliyor:
            return
        if not self.taslak_icerigi_var_mi():
            ui.message("Kaydedilecek taslak içeriği bulunamadı.")
            self.txt_icerik.SetFocus()
            return
        veri = self.taslak_verisini_al()
        self._taslak_kaydediliyor = True
        ayarlar = dict(ayarlari_yukle())
        jeton = arka_plan_gorev_jetonu_olustur(self, "taslak_kaydet", {"hesap": ayarlar.get("eposta", "")})

        def taslak_kaydetmeyi_baslat():
            if not pencere_kullanilabilir_mi(self):
                return
            self.alanlari_etkinlestir(False)
            arka_planda_calistir(self.arka_planda_taslak_kaydet, veri, ayarlar, jeton)

        mesaj_soyle_ve_sonra_calistir(
            "Taslaklara kaydediliyor.",
            taslak_kaydetmeyi_baslat,
            ad="Taslak kaydetme",
        )

    def arka_planda_taslak_kaydet(self, veri, ayarlar, jeton):
        try:
            taslagi_sunucuya_kaydet(
                veri.get("kime", ""),
                veri.get("bilgi", ""),
                veri.get("gizli", ""),
                veri.get("konu", ""),
                veri.get("icerik", ""),
                veri.get("ek_kayitlari", []),
                veri.get("yanit_basliklari", {}),
                self.taslak_klasor_adaylari,
                ayarlar,
            )
            gorev_icin_guvenli_call_after(jeton, self.taslak_kaydetme_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(jeton, self.taslak_kaydetme_hatali, str(e))
        except Exception as e:
            hata_kaydet("Taslak kaydedilemedi.", e)
            gorev_icin_guvenli_call_after(jeton, self.taslak_kaydetme_hatali, "Taslak kaydedilemedi. Lütfen bağlantınızı ve Google uygulama şifrenizi kontrol edin.")

    def taslak_kaydetme_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        callback_sonucu = False
        if self.taslak_kaydet_callback:
            try:
                callback_sonucu = bool(self.taslak_kaydet_callback())
            except Exception as e:
                hata_kaydet("Taslak kaydetme sonrası işlem başlatılamadı.", e)
        if callback_sonucu:
            ui.message("Taslaklara kaydedildi. Eski taslak kaldırılıyor.")
        else:
            ui.message("Taslaklara kaydedildi.")
        self.EndModal(wx.ID_OK)

    def taslak_kaydetme_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._taslak_kaydediliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()

    def gonder_tiklandi(self, event):
        if self._gonderiliyor:
            return
        if self._taslak_kaydediliyor:
            ui.message("Taslak kaydediliyor. Lütfen işlemin tamamlanmasını bekleyin.")
            return
        kime = self.txt_kime.GetValue().strip()
        bilgi = self.txt_bilgi.GetValue().strip()
        gizli = self.txt_gizli.GetValue().strip()
        konu = self.txt_konu.GetValue().strip()
        icerik = self.txt_icerik.GetValue()
        kime_alicilari = alici_listesi_yap(kime)
        bilgi_alicilari = alici_listesi_yap(bilgi)
        gizli_alicilar = alici_listesi_yap(gizli)

        if kime and not kime_alicilari:
            ui.message("Kime alanında geçerli bir e-posta adresi bulunamadı.")
            self.txt_kime.SetFocus()
            return
        if bilgi and not bilgi_alicilari:
            ui.message("Bilgi alanında geçerli bir e-posta adresi bulunamadı.")
            self.txt_bilgi.SetFocus()
            return
        if gizli and not gizli_alicilar:
            ui.message("Gizli alanında geçerli bir e-posta adresi bulunamadı.")
            self.txt_gizli.SetFocus()
            return

        alicilar = []
        gorulen_alicilar = set()
        for adres in (*kime_alicilari, *bilgi_alicilari, *gizli_alicilar):
            anahtar = adres.lower()
            if anahtar not in gorulen_alicilar:
                alicilar.append(adres)
                gorulen_alicilar.add(anahtar)

        if not alicilar:
            ui.message("Lütfen geçerli en az bir alıcı adresi girin.")
            self.txt_kime.SetFocus()
            return

        self._gonderiliyor = True
        if adres_otomatik_kaydet_ayari_yukle():
            for adres in reversed(alicilar):
                rehbere_ekle(adres)
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
                icerik,
                alicilar,
                list(self.ek_kayitlari),
                dict(self.yanit_basliklari),
                jeton,
            )

        mesaj_soyle_ve_sonra_calistir(
            "E-postanız gönderiliyor.",
            gonderimi_baslat,
            ad="E-posta gönderme",
        )

    def arka_planda_gonder(self, ayarlar, kime, bilgi, gizli, konu, icerik, alicilar, ek_kayitlari, yanit_basliklari, jeton):
        try:
            if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
                raise MailHatasi("Hesap bilgileri eksik.")

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
            )

            smtp_ssl_ile_gonder(ayarlar["eposta"], ayarlar["sifre"], alicilar, mesaj)
            gorev_icin_guvenli_call_after(jeton, self.gonderim_basarili)
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, str(e))
        except Exception as e:
            hata_kaydet("E-posta gönderilemedi.", e)
            gorev_icin_guvenli_call_after(jeton, self.gonderim_hatali, "Gönderim başarısız oldu. Lütfen bağlantınızı ve Google uygulama şifrenizi kontrol edin.")

    def gonderim_basarili(self):
        if not pencere_kullanilabilir_mi(self):
            return
        callback_sonucu = False
        if self.gonderildi_callback:
            try:
                callback_sonucu = bool(self.gonderildi_callback())
            except Exception as e:
                hata_kaydet("Gönderim sonrası işlem başlatılamadı.", e)
        if callback_sonucu:
            ui.message("E-posta başarıyla gönderildi. Taslak kaldırılıyor.")
        else:
            ui.message("E-posta başarıyla gönderildi.")
        self.EndModal(wx.ID_OK)

    def gonderim_hatali(self, mesaj):
        if not pencere_kullanilabilir_mi(self):
            return
        self._gonderiliyor = False
        ui.message(mesaj)
        self.alanlari_etkinlestir(True)
        self.txt_icerik.SetFocus()
