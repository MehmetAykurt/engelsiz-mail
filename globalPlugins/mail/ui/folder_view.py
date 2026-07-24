# -*- coding: utf-8 -*-
# Engelsiz Mail - ana pencere klasör görünümü yardımcıları

import wx

from ..folder_counts import klasor_secimi_sayisi_mesaji
from ..logger import hata_kaydet
from ..ui_helpers import pencere_kullanilabilir_mi

LISTE_MODU_KLASOR = "klasor"
LISTE_MODU_EPOSTA = "eposta"
KULLANICI_KLASORLERI_BASLIK = "Kullanıcı Klasörleri"


def klasor_ayrac_satiri_mi(deger):
    """Klasör listesinde eylemsiz ayraç satırı olup olmadığını döndürür."""
    return str(deger or "").strip() == KULLANICI_KLASORLERI_BASLIK


def klasor_liste_ogeleri(self):
    """Tek liste görünümünde gösterilecek klasör/ayraç satırlarını döndürür."""
    ogeler = []
    for kategori in list(getattr(self, "kategori_isimleri", []) or []):
        if kategori and kategori not in ogeler:
            ogeler.append(kategori)

    ozel_klasorler = []
    for kategori in list(getattr(self, "ozel_klasorler", []) or []):
        if kategori and kategori not in ogeler and kategori not in ozel_klasorler:
            ozel_klasorler.append(kategori)

    if ozel_klasorler:
        ogeler.append(KULLANICI_KLASORLERI_BASLIK)
        ogeler.extend(ozel_klasorler)
    return ogeler


def klasor_modunu_hazirla(self):
    """Ana listeyi klasör görünümü için hazırlar."""
    self.liste_modu = LISTE_MODU_KLASOR
    self.liste.SetName("E-posta klasörleri")
    self.klasor_sutunlarini_ayarla()

def klasor_sutunlarini_ayarla(self):
    try:
        self.liste.SetColumn(0, wx.ListItem(text="Klasörler"))
        self.liste.SetColumnWidth(0, 360)
        self.liste.SetColumn(1, wx.ListItem(text=" "))
        self.liste.SetColumnWidth(1, 430)
    except Exception as e:
        hata_kaydet("Klasör listesi sütunları ayarlanamadı.", e)

def klasor_gorunumunu_goster(self, secili_kategori=None, odak_ver=True):
    """Ana listede klasörleri gösterir."""
    if not pencere_kullanilabilir_mi(self):
        return
    self.klasor_modunu_hazirla()
    try:
        if not self.liste.IsEnabled():
            self.liste.Enable()
    except Exception as e:
        hata_kaydet("Klasör listesi yeniden etkinleştirilemedi.", e)
    kategoriler = self.klasor_liste_ogeleri()
    hedef = secili_kategori or self.secili_kategori or "Gelen Kutusu"
    if hedef not in kategoriler and self.tum_kategoriler():
        hedef = self.tum_kategoriler()[0]
    self.secili_kategori = hedef
    self.liste.DeleteAllItems()
    secili_indeks = 0
    cache = getattr(self, "_klasor_sayisi_cache", {}) or {}
    for i, kategori in enumerate(kategoriler):
        self.liste.InsertItem(i, kategori)
        if klasor_ayrac_satiri_mi(kategori):
            self.liste.SetItem(i, 1, "")
            continue
        bilgi = cache.get(kategori)
        ek = ""
        try:
            mesaj = klasor_secimi_sayisi_mesaji(kategori, bilgi)
            if mesaj:
                ek = mesaj.replace(kategori, "", 1).strip(" ,.-")
        except Exception:
            ek = ""
        if ek:
            self.liste.SetItem(i, 1, ek)
        if kategori == hedef:
            secili_indeks = i
    if kategoriler:
        self.liste_secim_ver(secili_indeks, odak_ver=odak_ver)
    elif odak_ver:
        wx.CallAfter(self.liste.SetFocus)

def secili_klasor_adini_al(self):
    """Klasör modunda seçili klasör adını döndürür."""
    try:
        indeks = self.liste.GetFocusedItem()
        kategoriler = self.klasor_liste_ogeleri()
        if 0 <= indeks < len(kategoriler):
            secim = kategoriler[indeks]
            if klasor_ayrac_satiri_mi(secim):
                return ""
            return secim
    except Exception as e:
        hata_kaydet("Seçili klasör adı listeden alınamadı.", e)
    return self.secili_kategori or "Gelen Kutusu"

def klasor_secimini_odaktan_guncelle(self):
    """Klasör modunda odaklanan klasörü geçerli seçim olarak tutar."""
    if getattr(self, "liste_modu", LISTE_MODU_KLASOR) != LISTE_MODU_KLASOR:
        return
    secim = self.secili_klasor_adini_al()
    if secim and not klasor_ayrac_satiri_mi(secim):
        self.secili_kategori = secim
