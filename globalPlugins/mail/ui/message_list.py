# -*- coding: utf-8 -*-
# Engelsiz Mail - ana pencere e-posta liste görünümü yardımcıları

import re

import wx

from .folder_view import LISTE_MODU_EPOSTA
from ..logger import hata_kaydet

EK_VAR_ETIKETI = "Eki var. "


def liste_bilgi_satiri_goster(self, mesaj):
    """E-posta listesinde bilgi satırı gösterir ve odak/seçimi erişilebilir biçimde sabitler."""
    try:
        try:
            liste_zaten_odakta = wx.Window.FindFocus() is self.liste
        except Exception:
            liste_zaten_odakta = False
        self.liste.DeleteAllItems()
        self.liste.InsertItem(0, str(mesaj or "Bilgi yok."))
        try:
            if liste_zaten_odakta:
                self.liste.Focus(0)
                self.liste.Select(0)
            else:
                # Pencere ilk açılırken öğe odağını klavye odağından önce
                # vermek, NVDA'nın aynı satırı iki ayrı odak olayında okumasına
                # neden olur. Satırı seçmek yeterlidir; liste odağı aldığında
                # NVDA seçili satırı doğal olarak bir kez okuyacaktır.
                self.liste.Select(0)
            self.liste.EnsureVisible(0)
        except Exception:
            pass
        # Klasör ve e-posta görünümü aynı liste denetimini kullanır. Liste zaten
        # odaktayken yeniden SetFocus çağrısı yapmak NVDA'nın tek bilgi satırını
        # iki kez okumasına neden olur.
        if not liste_zaten_odakta:
            wx.CallAfter(self.liste.SetFocus)
    except Exception as e:
        hata_kaydet("Liste bilgi satırı gösterilemedi.", e)


def birinci_sutun_basligi(self):
    """Seçili klasöre göre birinci sütun başlığını döndürür."""
    if self.secili_kategori in ("Gönderilen E-postalar", "Taslaklar"):
        return "Kime"
    return "Kimden"


def birinci_sutun_basligini_guncelle(self):
    """Gönderilenler ve Taslaklar için liste başlığını Kime olarak günceller."""
    try:
        item = wx.ListItem()
        item.SetText(self.birinci_sutun_basligi())
        self.liste.SetColumn(0, item)
        self.liste.SetColumnWidth(0, 260)
    except Exception as e:
        hata_kaydet("Liste birinci sütun başlığı güncellenemedi.", e)


def mesaj_liste_gosterimi(self, mesaj):
    """E-posta listesinin birinci sütununda gösterilecek metni döndürür."""
    metin = str(mesaj.get("liste_gosterim") or mesaj.get("kimden") or "").strip()
    if mesaj.get("ek_var") and not metin.startswith(EK_VAR_ETIKETI):
        metin = EK_VAR_ETIKETI + metin
    return metin


def mesaji_listede_okundu_yap(self, mail_id):
    """Okundu işaretlenen e-postanın listedeki gösterimini günceller."""
    hedef = str(mail_id)
    for indeks, mesaj in enumerate(self.mailler):
        uidler = {str(uid) for uid in (mesaj.get("ids") or [])}
        if str(mesaj.get("id")) != hedef and hedef not in uidler:
            continue
        mesaj["kimden"] = self.okunmadi_etiketini_kaldir(mesaj.get("kimden", ""))
        if "liste_gosterim" in mesaj:
            mesaj["liste_gosterim"] = self.okunmadi_etiketini_kaldir(mesaj.get("liste_gosterim", ""))
        if mesaj.get("konusma_mi"):
            mesaj["okunmamis_sayisi"] = 0
            for alan in ("kimden", "liste_gosterim"):
                mesaj[alan] = re.sub(
                    r"^\d+ okunmamış,\s*", "", str(mesaj.get(alan, "")), count=1
                )
        gosterim = self.mesaj_liste_gosterimi(mesaj)
        if str(mesaj.get("id")) in self.isaretliler:
            gosterim = "[İşaretli] " + gosterim
        try:
            self.liste.SetItem(indeks, 0, gosterim)
        except Exception:
            pass
        break


def eposta_modunu_hazirla(self):
    """Ana listeyi e-posta görünümü için hazırlar."""
    self.liste_modu = LISTE_MODU_EPOSTA
    self.liste.SetName("E-posta listesi")
    self.birinci_sutun_basligini_guncelle()
