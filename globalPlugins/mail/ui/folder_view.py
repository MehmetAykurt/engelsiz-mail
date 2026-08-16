# -*- coding: utf-8 -*-
# Engelsiz Mail - ana pencere klasör görünümü yardımcıları


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import wx

from ..folder_counts import klasor_secimi_sayisi_mesaji
from ..folders import klasor_gorunen_adi
from ..logger import hata_kaydet
from ..ui_helpers import pencere_kullanilabilir_mi

LISTE_MODU_KLASOR = "klasor"
LISTE_MODU_EPOSTA = "eposta"


def klasor_liste_ogeleri(self):
    """Tek liste görünümünde gösterilecek eylemli klasör satırlarını döndürür."""
    ogeler = []
    for kategori in list(getattr(self, "kategori_isimleri", []) or []):
        if kategori and kategori not in ogeler:
            ogeler.append(kategori)

    ozel_klasorler = []
    for kategori in list(getattr(self, "ozel_klasorler", []) or []):
        if kategori and kategori not in ogeler and kategori not in ozel_klasorler:
            ozel_klasorler.append(kategori)

    ogeler.extend(ozel_klasorler)
    return ogeler


def klasor_modunu_hazirla(self):
    """Ana listeyi klasör görünümü için hazırlar."""
    self.liste_modu = LISTE_MODU_KLASOR
    self.liste.SetName(_("E-posta klasörleri"))
    self.klasor_sutunlarini_ayarla()

def klasor_sutunlarini_ayarla(self):
    try:
        self.liste.SetColumn(0, _sutun_ogesi(_("Klasörler")))
        self.liste.SetColumnWidth(0, 360)
        self.liste.SetColumn(1, _sutun_ogesi(" "))
        self.liste.SetColumnWidth(1, 430)
    except Exception as e:
        hata_kaydet("Klasör listesi sütunları ayarlanamadı.", e)

def klasor_gorunumunu_goster(self, secili_kategori=None, odak_ver=True):
    """Ana listede klasörleri gösterir."""
    if not pencere_kullanilabilir_mi(self):
        return
    if getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_EPOSTA:
        # Klasör görünümüne hangi yoldan dönülürse dönülsün, eski e-posta
        # yüklemesinin sonucu sonradan gelip listeyi yeniden açmasın.
        try:
            self._yukleme_islem_no += 1
            self.yukleniyor = False
            self._yenileme_sessiz = False
        except Exception as e:
            hata_kaydet("Klasör görünümüne geçerken eski yükleme geçersiz kılınamadı.", e)
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
    ham_cache = getattr(self, "_klasor_sayisi_cache", {}) or {}
    try:
        cache = self._bekleyen_toplu_islem_sayilarini_uygula(ham_cache)
    except Exception as e:
        hata_kaydet("Bekleyen silmeler klasör sayılarına uygulanamadı.", e)
        cache = ham_cache
    for i, kategori in enumerate(kategoriler):
        self.liste.InsertItem(i, klasor_gorunen_adi(kategori))
        bilgi = cache.get(kategori)
        ek = ""
        try:
            mesaj = klasor_secimi_sayisi_mesaji(kategori, bilgi)
            if mesaj:
                ek = mesaj.strip(" ,.-")
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

def klasor_sayilarini_gorunumde_guncelle(self, kategoriler):
    """Değişen klasör sayılarını listeyi ve odağı yeniden kurmadan günceller."""
    if (
        not pencere_kullanilabilir_mi(self)
        or getattr(self, "liste_modu", LISTE_MODU_KLASOR) != LISTE_MODU_KLASOR
    ):
        return
    ogeler = self.klasor_liste_ogeleri()
    indeksler = {kategori: indeks for indeks, kategori in enumerate(ogeler)}
    ham_cache = getattr(self, "_klasor_sayisi_cache", {}) or {}
    try:
        cache = self._bekleyen_toplu_islem_sayilarini_uygula(ham_cache)
    except Exception as e:
        hata_kaydet("Bekleyen silmeler klasör görünümüne uygulanamadı.", e)
        cache = ham_cache
    for kategori in dict.fromkeys(kategoriler or []):
        indeks = indeksler.get(kategori)
        if indeks is None:
            continue
        ek = ""
        try:
            mesaj = klasor_secimi_sayisi_mesaji(kategori, cache.get(kategori))
            if mesaj:
                ek = mesaj.replace(kategori, "", 1).strip(" ,.-")
        except Exception:
            ek = ""
        try:
            mevcut = self.liste.GetItemText(indeks, 1)
        except Exception:
            mevcut = None
        if mevcut != ek:
            self.liste.SetItem(indeks, 1, ek)


def secili_klasor_adini_al(self):
    """Klasör modunda seçili klasör adını döndürür."""
    try:
        indeks = self.liste.GetFocusedItem()
        kategoriler = self.klasor_liste_ogeleri()
        if 0 <= indeks < len(kategoriler):
            return kategoriler[indeks]
    except Exception as e:
        hata_kaydet("Seçili klasör adı listeden alınamadı.", e)
    return self.secili_kategori or "Gelen Kutusu"

def klasor_secimini_odaktan_guncelle(self):
    """Klasör modunda odaklanan klasörü geçerli seçim olarak tutar."""
    if getattr(self, "liste_modu", LISTE_MODU_KLASOR) != LISTE_MODU_KLASOR:
        return
    secim = self.secili_klasor_adini_al()
    if secim:
        self.secili_kategori = secim

def _sutun_ogesi(metin):
    """wx.ListCtrl sütun başlığı için uyumlu ListItem oluşturur."""
    oge = wx.ListItem()
    oge.SetText(metin)
    return oge
