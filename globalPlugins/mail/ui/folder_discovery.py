# -*- coding: utf-8 -*-
"""Klasör keşfi, klasör haritası ve klasör sayı/ad JSON işlemleri."""

import wx

from .folder_view import LISTE_MODU_KLASOR
from ..config import (
    MESAJ_SAYISI_ALANI,
    VARSAYILAN_MESAJ_SAYISI,
    ayarlari_yukle,
    mesaj_sayisini_duzenle,
)
from ..folder_counts import (
    klasor_adlari_onbellegi_yukle,
    klasor_sayisi_bilgisini_duzenle,
    klasor_sayisi_onbellegi_kaydet,
    klasor_sayisi_onbellegi_yukle,
)
from ..folders import (
    SISTEM_KLASORLERI,
    VARSAYILAN_KLASOR_HARITASI,
    imap_liste_satiri_ayristir,
    imap_tirnakli_ham_ad,
)
from ..header_sync import klasor_basliklarini_senkronize_et
from ..imap_client import (
    ImapBaglantisi,
    imap_status_sayilarini_ayristir,
    uidleri_ayristir,
)
from ..logger import hata_kaydet
from ..mailbox_loader import yerel_eposta_listesi_hazirla
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_planda_calistir,
    gorev_icin_guvenli_call_after,
    pencere_kullanilabilir_mi,
)


def tum_kategoriler(self):
    """Sistem ve özel klasör adlarını tek listede döndürür."""
    kategoriler = []
    for kategori in list(self.kategori_isimleri) + list(self.ozel_klasorler):
        if kategori not in kategoriler:
            kategoriler.append(kategori)
    return kategoriler



def _aktif_eposta_adresi(self):
    """Kayıtlı hesabın e-posta adresini güvenli biçimde döndürür."""
    try:
        ayarlar = ayarlari_yukle()
        return str(ayarlar.get("eposta", "") or "").strip()
    except Exception as e:
        hata_kaydet("Aktif hesap adresi alınamadı.", e)
        return ""

def _klasor_sayisi_onbellegi_yukle(self):
    """Pencere açılışında son bilinen klasör sayılarını ve klasör adlarını kalıcı JSON dosyasından belleğe alır."""
    try:
        eposta = self._aktif_eposta_adresi()
        self._klasor_adlari_onbellegi_var = False
        if not eposta:
            return
        cache = klasor_sayisi_onbellegi_yukle(eposta)
        if isinstance(cache, dict) and cache:
            self._klasor_sayisi_cache.update(cache)

        klasor_verisi = klasor_adlari_onbellegi_yukle(eposta)
        if not isinstance(klasor_verisi, dict) or not klasor_verisi:
            return

        sistem_klasorler = klasor_verisi.get("sistem_klasorler")
        if isinstance(sistem_klasorler, list) and sistem_klasorler:
            self.kategori_isimleri = list(sistem_klasorler)

        klasor_haritasi = klasor_verisi.get("klasor_haritasi")
        if isinstance(klasor_haritasi, dict) and klasor_haritasi:
            yeni_harita = dict(VARSAYILAN_KLASOR_HARITASI)
            yeni_harita.update(klasor_haritasi)
            self.klasor_haritasi = yeni_harita

        ozel_klasorler = klasor_verisi.get("ozel_klasorler")
        if isinstance(ozel_klasorler, list):
            self.ozel_klasorler = list(ozel_klasorler)

        self._klasor_adlari_onbellegi_var = bool(self.tum_kategoriler())
    except Exception as e:
        hata_kaydet("Klasör sayı/ad önbelleği yüklenemedi.", e)

def _klasor_sayisi_onbellegi_kaydet(self):
    """Bellekteki klasör sayılarını, klasör adlarını ve IMAP haritasını kalıcı JSON dosyasına yazar."""
    try:
        eposta = self._aktif_eposta_adresi()
        if not eposta:
            return False
        return klasor_sayisi_onbellegi_kaydet(
            eposta,
            getattr(self, "_klasor_sayisi_cache", {}),
            klasor_haritasi=getattr(self, "klasor_haritasi", {}),
            ozel_klasorler=getattr(self, "ozel_klasorler", []),
            sistem_klasorler=getattr(self, "kategori_isimleri", []),
        )
    except Exception as e:
        hata_kaydet("Klasör sayı/ad önbelleği kaydedilemedi.", e)
        return False

def _klasor_sayisi_cache_guncelle(self, kategori_adi, klasor_bilgisi, kaydet=True):
    """Tek klasörün sayı bilgisini bellek ve isteğe bağlı kalıcı önbellekte günceller."""
    kategori_adi = str(kategori_adi or "").strip()
    temiz = klasor_sayisi_bilgisini_duzenle(klasor_bilgisi)
    if not kategori_adi or not temiz:
        return False
    try:
        self._klasor_sayisi_cache[kategori_adi] = temiz
        if kaydet:
            self._klasor_sayisi_onbellegi_kaydet()
        return True
    except Exception as e:
        hata_kaydet("Klasör sayı önbelleği güncellenemedi.", e)
        return False


def klasorleri_kesfet_tetikle(self, odak_ver=True):
    """E-posta yüklemeden IMAP klasör haritasını ve özel klasörleri arka planda keşfeder."""
    try:
        if getattr(self, "_klasor_kesfi_guncelleniyor", False):
            self._klasor_kesfi_tekrar_bekliyor = True
            if odak_ver:
                self._klasor_kesfi_sonucunda_odak_ver = True
            return
        if not self.hesap_bilgisi_var_mi():
            return
        self._klasor_kesfi_sonucunda_odak_ver = bool(odak_ver)
        self._klasor_kesfi_guncelleniyor = True
        jeton = arka_plan_gorev_jetonu_olustur(
            self,
            "klasor_kesfi",
            {"hesap": self._aktif_eposta_adresi(), "hedef": self.secili_kategori},
        )
        arka_planda_calistir(self.klasorleri_kesfet_thread, jeton)
    except Exception as e:
        self._klasor_kesfi_guncelleniyor = False
        hata_kaydet("Klasör keşfi başlatılamadı.", e)

def klasorleri_kesfet_thread(self, jeton):
    """IMAP LIST ve STATUS bilgilerini e-posta gövdelerini indirmeden hazırlar."""
    sonuc = {"harita": None, "ozeller": None, "sayilar": {}}
    try:
        ayarlar = ayarlari_yukle()
        if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
            return
        with ImapBaglantisi(ayarlar) as imap:
            yeni_harita, yeni_ozeller = self.klasor_haritasini_hazirla(imap)
            sonuc["harita"] = yeni_harita
            sonuc["ozeller"] = yeni_ozeller

            for kategori_adi in list(self.kategori_isimleri) + list(yeni_ozeller or []):
                klasor = str((yeni_harita or {}).get(kategori_adi) or "").strip()
                if not klasor:
                    continue
                try:
                    tip_status, status_verisi = imap.status(klasor, "(MESSAGES UNSEEN)")
                    if tip_status == "OK":
                        bilgi = imap_status_sayilarini_ayristir(status_verisi)
                        if bilgi:
                            sonuc["sayilar"][kategori_adi] = bilgi
                except Exception as e:
                    hata_kaydet(f"Klasör sayısı alınamadı: {kategori_adi}", e)
        gorev_icin_guvenli_call_after(jeton, self.klasorleri_kesfet_sonuc, sonuc)
    except Exception as e:
        hata_kaydet("Klasör keşfi tamamlanamadı.", e)
    finally:
        gorev_icin_guvenli_call_after(jeton, self.klasorleri_kesfet_bitti)

def klasorleri_kesfet_sonuc(self, sonuc):
    """Arka plan klasör keşfi sonucunu arayüze sessizce uygular."""
    if not pencere_kullanilabilir_mi(self) or not isinstance(sonuc, dict):
        return
    hedef = self.secili_kategori or "Gelen Kutusu"
    self.klasor_haritasini_uygula(
        sonuc.get("harita"),
        sonuc.get("ozeller"),
        hedef,
        yuklu_kategori_guncelle=False,
    )
    sayilar = sonuc.get("sayilar")
    degisti = False
    if isinstance(sayilar, dict):
        for kategori_adi, bilgi in sayilar.items():
            if self._klasor_sayisi_cache_guncelle(kategori_adi, bilgi, kaydet=False):
                degisti = True
    # Klasör adları/haritası, sayı değişmese bile aynı JSON dosyasına yazılır.
    self._klasor_sayisi_onbellegi_kaydet()

    if getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        odak_ver = bool(getattr(self, "_klasor_kesfi_sonucunda_odak_ver", False))
        self.klasor_gorunumunu_goster(self.secili_kategori, odak_ver=odak_ver)

def klasorleri_kesfet_bitti(self):
    self._klasor_kesfi_guncelleniyor = False
    tekrar_bekliyor = bool(getattr(self, "_klasor_kesfi_tekrar_bekliyor", False))
    tekrar_odak_ver = bool(getattr(self, "_klasor_kesfi_sonucunda_odak_ver", False))
    self._klasor_kesfi_tekrar_bekliyor = False
    try:
        if (
            self.hesap_bilgisi_var_mi()
            and getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR
            and getattr(self, "liste", None) is not None
            and self.liste.GetItemCount() == 0
        ):
            odak_ver = bool(getattr(self, "_klasor_kesfi_sonucunda_odak_ver", False))
            self.klasor_gorunumunu_goster(self.secili_kategori, odak_ver=odak_ver)
    except Exception as e:
        hata_kaydet("Klasör keşfi sonrası yedek klasör listesi gösterilemedi.", e)
    self._klasor_kesfi_sonucunda_odak_ver = False
    if tekrar_bekliyor and pencere_kullanilabilir_mi(self):
        self.klasorleri_kesfet_tetikle(odak_ver=tekrar_odak_ver)


def gonderim_sonrasi_esitle_tetikle(self, onceki_gonderilen_toplam=None, deneme=1):
    """Gönderimden sonra Gönderilenler başlıklarını ve klasör sayılarını sessizce eşitler."""
    try:
        if getattr(self, "_gonderim_sonrasi_esitleme_guncelleniyor", False):
            self._gonderim_sonrasi_esitleme_bekleyen = (
                onceki_gonderilen_toplam,
                int(deneme or 1),
            )
            return
        if not self.hesap_bilgisi_var_mi():
            return
        self._gonderim_sonrasi_esitleme_guncelleniyor = True
        jeton = arka_plan_gorev_jetonu_olustur(
            self,
            "gonderim_sonrasi_esitleme",
            {
                "hesap": self._aktif_eposta_adresi(),
                "onceki_gonderilen_toplam": onceki_gonderilen_toplam,
                "deneme": int(deneme or 1),
            },
        )
        arka_planda_calistir(
            self.gonderim_sonrasi_esitle_thread,
            jeton,
            onceki_gonderilen_toplam,
            int(deneme or 1),
        )
    except Exception as e:
        self._gonderim_sonrasi_esitleme_guncelleniyor = False
        hata_kaydet("Gönderim sonrası eşitleme başlatılamadı.", e)


def gonderim_sonrasi_esitle_thread(self, jeton, onceki_gonderilen_toplam=None, deneme=1):
    """Gönderilenler klasörünü ve bütün klasör sayaçlarını tek IMAP oturumunda günceller."""
    sonuc = {
        "hesap": "",
        "harita": None,
        "ozeller": None,
        "sayilar": {},
        "yeniden_dene": False,
        "onceki_gonderilen_toplam": onceki_gonderilen_toplam,
        "deneme": int(deneme or 1),
    }
    try:
        ayarlar = ayarlari_yukle()
        if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
            return
        sonuc["hesap"] = str(ayarlar.get("eposta", "") or "").strip()
        with ImapBaglantisi(ayarlar) as imap:
            yeni_harita, yeni_ozeller = self.klasor_haritasini_hazirla(imap)
            sonuc["harita"] = yeni_harita
            sonuc["ozeller"] = yeni_ozeller

            kategoriler = []
            for kategori_adi in list(SISTEM_KLASORLERI) + list((yeni_harita or {}).keys()):
                kategori_adi = str(kategori_adi or "").strip()
                if kategori_adi and kategori_adi not in kategoriler:
                    kategoriler.append(kategori_adi)
            for kategori_adi in kategoriler:
                klasor = str(
                    (yeni_harita or {}).get(kategori_adi)
                    or VARSAYILAN_KLASOR_HARITASI.get(kategori_adi, "")
                ).strip()
                if not klasor:
                    continue
                try:
                    tip_status, status_verisi = imap.status(klasor, "(MESSAGES UNSEEN)")
                    if tip_status == "OK":
                        bilgi = imap_status_sayilarini_ayristir(status_verisi)
                        if bilgi:
                            sonuc["sayilar"][kategori_adi] = bilgi
                except Exception as e:
                    hata_kaydet(f"Gönderim sonrası klasör sayısı alınamadı: {kategori_adi}", e)

            gonderilen_klasoru = str(
                (yeni_harita or {}).get("Gönderilen E-postalar")
                or VARSAYILAN_KLASOR_HARITASI["Gönderilen E-postalar"]
            ).strip()
            tip, _veri = imap.select(gonderilen_klasoru, readonly=True)
            if tip != "OK":
                sonuc["yeniden_dene"] = True
            else:
                tip, uid_verisi = imap.uid("SEARCH", "ALL")
                if tip != "OK":
                    sonuc["yeniden_dene"] = True
                else:
                    uidler = uidleri_ayristir(uid_verisi)
                    senkron_sonucu = klasor_basliklarini_senkronize_et(
                        imap,
                        ayarlar.get("eposta", ""),
                        "Gönderilen E-postalar",
                        gonderilen_klasoru,
                        sunucu_uidleri=uidler,
                    )
                    if bool((senkron_sonucu or {}).get("atlandi")):
                        sonuc["yeniden_dene"] = True
                    try:
                        onceki_toplam = int(onceki_gonderilen_toplam)
                    except (TypeError, ValueError):
                        onceki_toplam = None
                    guncel_bilgi = sonuc["sayilar"].get("Gönderilen E-postalar") or {}
                    try:
                        guncel_toplam = int(guncel_bilgi.get("messages"))
                    except (TypeError, ValueError):
                        guncel_toplam = len(uidler)
                    if onceki_toplam is not None and guncel_toplam <= onceki_toplam:
                        sonuc["yeniden_dene"] = True

        gorev_icin_guvenli_call_after(jeton, self.gonderim_sonrasi_esitle_sonuc, sonuc)
    except Exception as e:
        hata_kaydet("Gönderim sonrası Gönderilenler eşitlenemedi.", e)
        sonuc["yeniden_dene"] = True
        gorev_icin_guvenli_call_after(jeton, self.gonderim_sonrasi_esitle_sonuc, sonuc)
    finally:
        gorev_icin_guvenli_call_after(jeton, self.gonderim_sonrasi_esitle_bitti)


def gonderim_sonrasi_esitle_sonuc(self, sonuc):
    """Gönderim sonrası eşitlemeyi önbelleğe ve açık görünüme uygular."""
    if not pencere_kullanilabilir_mi(self) or not isinstance(sonuc, dict):
        return
    if str(sonuc.get("hesap") or "").strip() != self._aktif_eposta_adresi():
        return
    self.klasor_haritasini_uygula(
        sonuc.get("harita"),
        sonuc.get("ozeller"),
        self.secili_kategori,
        yuklu_kategori_guncelle=False,
    )
    sayilar = sonuc.get("sayilar")
    degisti = False
    if isinstance(sayilar, dict):
        for kategori_adi, bilgi in sayilar.items():
            if self._klasor_sayisi_cache_guncelle(kategori_adi, bilgi, kaydet=False):
                degisti = True
    if degisti:
        self._klasor_sayisi_onbellegi_kaydet()

    if getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        self.klasor_gorunumunu_goster(self.secili_kategori, odak_ver=False)
    elif self.secili_kategori == "Gönderilen E-postalar":
        try:
            ayarlar = ayarlari_yukle()
            mesaj_sayisi = mesaj_sayisini_duzenle(
                ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)
            )
            kaynak_klasor = self.klasor_haritasi.get(
                "Gönderilen E-postalar",
                VARSAYILAN_KLASOR_HARITASI["Gönderilen E-postalar"],
            )
            yerel_mailler = yerel_eposta_listesi_hazirla(
                ayarlar,
                "Gönderilen E-postalar",
                kaynak_klasor,
                mesaj_sayisi,
            )
            if yerel_mailler is not None:
                self.yerel_eposta_listesini_goster(
                    yerel_mailler,
                    "Gönderilen E-postalar",
                )
        except Exception as e:
            hata_kaydet("Gönderilen E-postalar görünümü yerel eşitlemeden sonra yenilenemedi.", e)

    if bool(sonuc.get("yeniden_dene")) and int(sonuc.get("deneme") or 1) < 2:
        self._gonderim_sonrasi_yeniden_deneme_timer = wx.CallLater(
            5000,
            self.gonderim_sonrasi_esitle_tetikle,
            sonuc.get("onceki_gonderilen_toplam"),
            2,
        )


def gonderim_sonrasi_esitle_bitti(self):
    self._gonderim_sonrasi_esitleme_guncelleniyor = False
    bekleyen = getattr(self, "_gonderim_sonrasi_esitleme_bekleyen", None)
    self._gonderim_sonrasi_esitleme_bekleyen = None
    if bekleyen and pencere_kullanilabilir_mi(self):
        self.gonderim_sonrasi_esitle_tetikle(*bekleyen)

def sistem_klasor_sayilarini_guncelle_tetikle(self):
    """Eklenti açılışında bilinen klasörlerin güncel toplam/okunmamış sayılarını arka planda alır."""
    try:
        if getattr(self, "_sistem_klasor_sayisi_guncelleniyor", False):
            return
        if not self.hesap_bilgisi_var_mi():
            return
        self._sistem_klasor_sayisi_guncelleniyor = True
        harita = dict(getattr(self, "klasor_haritasi", {}) or {})
        jeton = arka_plan_gorev_jetonu_olustur(
            self,
            "sistem_klasor_sayilari",
            {"hesap": self._aktif_eposta_adresi(), "harita": harita},
        )
        arka_planda_calistir(self.sistem_klasor_sayilarini_guncelle_thread, harita, jeton)
    except Exception as e:
        self._sistem_klasor_sayisi_guncelleniyor = False
        hata_kaydet("Klasör sayı güncellemesi başlatılamadı.", e)

def sistem_klasor_sayilarini_guncelle_thread(self, klasor_haritasi, jeton):
    """Sistem ve özel klasörlerin STATUS bilgilerini tek IMAP bağlantısıyla günceller."""
    sonuc = {}
    try:
        ayarlar = ayarlari_yukle()
        if not ayarlar.get("eposta") or not ayarlar.get("sifre"):
            return
        kategoriler = []
        for kategori_adi in list(SISTEM_KLASORLERI) + list((klasor_haritasi or {}).keys()):
            kategori_adi = str(kategori_adi or "").strip()
            if kategori_adi and kategori_adi not in kategoriler:
                kategoriler.append(kategori_adi)
        with ImapBaglantisi(ayarlar) as imap:
            for kategori_adi in kategoriler:
                klasor = str((klasor_haritasi or {}).get(kategori_adi) or VARSAYILAN_KLASOR_HARITASI.get(kategori_adi, "")).strip()
                if not klasor:
                    continue
                try:
                    tip_status, status_verisi = imap.status(klasor, "(MESSAGES UNSEEN)")
                    if tip_status == "OK":
                        bilgi = imap_status_sayilarini_ayristir(status_verisi)
                        if bilgi:
                            sonuc[kategori_adi] = bilgi
                except Exception as e:
                    hata_kaydet(f"Klasör sayısı alınamadı: {kategori_adi}", e)
        if sonuc:
            gorev_icin_guvenli_call_after(jeton, self.sistem_klasor_sayilarini_guncelle_sonuc, sonuc)
    except Exception as e:
        hata_kaydet("Klasör sayıları güncellenemedi.", e)
    finally:
        gorev_icin_guvenli_call_after(jeton, self.sistem_klasor_sayilarini_guncelle_bitti)

def sistem_klasor_sayilarini_guncelle_sonuc(self, sonuc):
    """Arka planda alınan klasör sayılarını bellek, JSON önbellek ve klasör görünümüne aktarır."""
    if not isinstance(sonuc, dict):
        return
    degisti = False
    for kategori_adi, bilgi in sonuc.items():
        if self._klasor_sayisi_cache_guncelle(kategori_adi, bilgi, kaydet=False):
            degisti = True
    if degisti:
        self._klasor_sayisi_onbellegi_kaydet()
        if getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
            self.klasor_gorunumunu_goster(self.secili_kategori, odak_ver=False)

def sistem_klasor_sayilarini_guncelle_bitti(self):
    self._sistem_klasor_sayisi_guncelleniyor = False


def klasor_haritasini_hazirla(self, imap):
    """IMAP klasör listesini arka planda hazırlar; wx denetimlerine dokunmaz."""
    tip, veri = imap.list()
    if tip != "OK" or not veri:
        return dict(self.klasor_haritasi), list(self.ozel_klasorler)
    yeni_ozeller = []
    yeni_harita = dict(VARSAYILAN_KLASOR_HARITASI)

    for satir in veri:
        sonuc = imap_liste_satiri_ayristir(satir)
        if not sonuc:
            continue
        bayraklar, imap_adi, gorunen_ad = sonuc
        imap_degeri = imap_tirnakli_ham_ad(imap_adi)

        if "\\SENT" in bayraklar:
            yeni_harita["Gönderilen E-postalar"] = imap_degeri
        elif "\\DRAFTS" in bayraklar:
            yeni_harita["Taslaklar"] = imap_degeri
        elif "\\TRASH" in bayraklar:
            yeni_harita["Çöp Kutusu"] = imap_degeri
        elif "\\JUNK" in bayraklar or "\\SPAM" in bayraklar:
            yeni_harita["Spam"] = imap_degeri
        elif "\\ALL" in bayraklar:
            yeni_harita["Tüm Postalar"] = imap_degeri
        elif imap_adi.upper() == "INBOX":
            yeni_harita["Gelen Kutusu"] = "INBOX"
        elif "\\NOSELECT" not in bayraklar and "[GMAIL]" not in imap_adi.upper():
            if gorunen_ad not in yeni_ozeller and gorunen_ad not in SISTEM_KLASORLERI:
                yeni_ozeller.append(gorunen_ad)
                yeni_harita[gorunen_ad] = imap_degeri

    return yeni_harita, yeni_ozeller

def klasor_haritasini_uygula(self, yeni_harita=None, yeni_ozeller=None, hedef_kategori=None, yuklu_kategori_guncelle=True):
    """Arka planda hazırlanan klasör bilgisini ana arayüz iş parçacığında uygular."""
    if isinstance(yeni_harita, dict):
        self.klasor_haritasi = dict(yeni_harita)
    if isinstance(yeni_ozeller, list):
        self.ozel_klasorler = list(yeni_ozeller)

    tum_kategoriler = self.kategori_isimleri + self.ozel_klasorler
    yeni_secim = hedef_kategori or self.secili_kategori
    if yeni_secim not in tum_kategoriler:
        yeni_secim = "Gelen Kutusu"
    self.secili_kategori = yeni_secim
    if yuklu_kategori_guncelle:
        self.yuklu_kategori = yeni_secim
