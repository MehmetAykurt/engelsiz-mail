# -*- coding: utf-8 -*-
"""NVDA açılışından sonra sessiz başlık önbelleği ısıtma hizmeti."""

import threading

import wx

from .config import (
    MESAJ_SAYISI_ALANI,
    VARSAYILAN_MESAJ_SAYISI,
    ayarlari_yukle,
    mesaj_sayisini_duzenle,
    onizleme_ayari_yukle,
)
from .folders import (
    SISTEM_KLASORLERI,
    imap_klasor_haritasi_olustur,
    imap_liste_satiri_ayristir,
    imap_tirnakli_ham_ad,
)
from .body_sync import klasor_govdelerini_senkronize_et
from .header_sync import klasor_basliklarini_senkronize_et
from .preview_sync import klasor_onizlemelerini_senkronize_et
from .imap_client import ImapBaglantisi, uidleri_ayristir
from .logger import hata_kaydet, uyari_kaydet
from .ui_helpers import arka_planda_calistir
from .database_maintenance import temel_bakim_yap
from .database import veritabani_hazirla
from .mail_store import hesap_klasor_envanterini_uzlastir
from .pending_deletions import bekleyen_silmeleri_isle
from .vendor import imaplib


BASLANGIC_SENKRONIZASYON_GECIKMESI_MS = 15000
BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS = 5000
BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS = 60000


def son_uidleri_sinirla(uidler, sinir):
    """Sunucunun artan UID listesinden en yeni kayıtları, yeniden eskiye döndürür."""
    sinir = mesaj_sayisini_duzenle(sinir, VARSAYILAN_MESAJ_SAYISI)
    temiz_uidler = list(uidler or [])
    return list(reversed(temiz_uidler[-sinir:]))


class BaslangicSenkronizasyonYoneticisi:
    """Başarılı olana kadar yeniden denenebilen sessiz başlangıç eşitlemesini yönetir."""

    def __init__(self, gecikme_ms=BASLANGIC_SENKRONIZASYON_GECIKMESI_MS):
        self._iptal = threading.Event()
        self._durum_kilidi = threading.Lock()
        self._baglanti_kilidi = threading.Lock()
        self._aktif_baglanti = None
        self._calisiyor = False
        self._tamamlandi = False
        self._zamanlayici = None
        self._zamanlayiciyi_ayarla(gecikme_ms)

    def _zamanlayiciyi_ayarla(self, gecikme_ms):
        """Yalnız wx ana iş parçacığında yeni çalışma zamanlayıcısını kurar."""
        if self._iptal.is_set() or self._tamamlandi:
            return
        try:
            if self._zamanlayici:
                self._zamanlayici.Stop()
            self._zamanlayici = wx.CallLater(max(0, int(gecikme_ms)), self._baslat)
        except Exception as e:
            self._zamanlayici = None
            hata_kaydet("Başlangıç senkronizasyon zamanlayıcısı oluşturulamadı.", e)

    def _calisma_bitti(self, yeniden_dene_ms=None):
        """İşçi sonucunu ana iş parçacığında kaydeder ve gerekirse yeniden planlar."""
        with self._durum_kilidi:
            self._calisiyor = False
            if yeniden_dene_ms is None:
                self._tamamlandi = True
        if yeniden_dene_ms is not None and not self._iptal.is_set():
            self._zamanlayiciyi_ayarla(yeniden_dene_ms)

    def _sonucu_ana_is_parcacigina_aktar(self, yeniden_dene_ms=None):
        try:
            wx.CallAfter(self._calisma_bitti, yeniden_dene_ms)
        except Exception as e:
            hata_kaydet("Başlangıç senkronizasyon sonucu ana iş parçacığına aktarılamadı.", e)
            with self._durum_kilidi:
                self._calisiyor = False

    def _baslat(self):
        self._zamanlayici = None
        with self._durum_kilidi:
            if self._iptal.is_set() or self._calisiyor or self._tamamlandi:
                return
            self._calisiyor = True
        try:
            arka_planda_calistir(self._calistir)
        except Exception as e:
            hata_kaydet("Başlangıç senkronizasyon iş parçacığı başlatılamadı.", e)
            self._calisma_bitti()

    def durdur(self):
        self._iptal.set()
        zamanlayici = self._zamanlayici
        self._zamanlayici = None
        if zamanlayici:
            try:
                zamanlayici.Stop()
            except Exception as e:
                hata_kaydet("Başlangıç senkronizasyon zamanlayıcısı durdurulamadı.", e)
        with self._baglanti_kilidi:
            aktif_baglanti = self._aktif_baglanti
        if aktif_baglanti is not None:
            try:
                aktif_baglanti.shutdown()
            except Exception as e:
                hata_kaydet("Başlangıç senkronizasyonunun etkin IMAP bağlantısı kapatılamadı.", e)

    def _klasor_sirasi(self, klasor_haritasi, ozel_klasorler):
        oncelik = [
            "Gelen Kutusu",
            "Gönderilen E-postalar",
            "Taslaklar",
            "Tüm Postalar",
            "Çöp Kutusu",
            "Spam",
        ]
        sonuc = []
        gorulen = set()
        for kategori in oncelik + list(ozel_klasorler or []):
            imap_klasoru = klasor_haritasi.get(kategori)
            if not imap_klasoru or imap_klasoru in gorulen:
                continue
            sonuc.append((kategori, imap_klasoru))
            gorulen.add(imap_klasoru)
        for kategori, imap_klasoru in klasor_haritasi.items():
            if kategori in SISTEM_KLASORLERI and imap_klasoru not in gorulen:
                sonuc.append((kategori, imap_klasoru))
                gorulen.add(imap_klasoru)
        return sonuc

    def _calistir(self):
        if self._iptal.is_set():
            self._sonucu_ana_is_parcacigina_aktar()
            return
        try:
            # Bos semayi da hesap ve ag kontrolunden bagimsiz olarak arka planda kur.
            veritabani_hazirla()
        except Exception as e:
            hata_kaydet("Baslangic veritabani hazirligi tamamlanamadi.", e)
            self._sonucu_ana_is_parcacigina_aktar()
            return
        try:
            ayarlar = ayarlari_yukle()
        except Exception as e:
            hata_kaydet("Başlangıç senkronizasyon ayarları okunamadı.", e)
            self._sonucu_ana_is_parcacigina_aktar()
            return
        eposta = str(ayarlar.get("eposta", "") or "").strip()
        sifre = str(ayarlar.get("sifre", "") or "").strip()
        if not eposta or not sifre:
            self._sonucu_ana_is_parcacigina_aktar()
            return
        mesaj_sayisi = mesaj_sayisini_duzenle(
            ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)
        )
        # Senkronizasyon bekleyen bir silmeyi yeniden görünür yapmadan önce
        # çevrimdışı kuyruğu sunucuya uygulamayı dene.
        try:
            silme_sonucu = bekleyen_silmeleri_isle(ayarlar, eposta)
        except Exception as e:
            uyari_kaydet(
                "Bekleyen silmeler başlangıçta uygulanamadı; eşitleme daha sonra yeniden denenecek.",
                e,
            )
            self._sonucu_ana_is_parcacigina_aktar(
                BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS
            )
            return
        if bool((silme_sonucu or {}).get("kilitli")):
            # Aynı anda başlayan kuyruk yöneticisi bitmeden normal eşitleme
            # eski sunucu görünümünü yeniden yazmasın; kısa süre sonra tekrar dene.
            if not self._iptal.is_set():
                self._sonucu_ana_is_parcacigina_aktar(
                    BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS
                )
            return
        yeniden_dene_ms = None
        baglanti = ImapBaglantisi(ayarlar)
        with self._baglanti_kilidi:
            if self._iptal.is_set():
                self._sonucu_ana_is_parcacigina_aktar()
                return
            self._aktif_baglanti = baglanti
        try:
            with baglanti as imap:
                tip, liste_verisi = imap.list()
                if tip != "OK":
                    yeniden_dene_ms = BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS
                    return
                klasor_haritasi, ozel_klasorler = imap_klasor_haritasi_olustur(liste_verisi)
                # Ancak LIST cevabinin tum satirlari anlasilabiliyorsa envanteri
                # uzlastir. Kismi/bozuk bir cevap eski veriyi yanlislikla pasiflestirmesin.
                ayristirilanlar = [imap_liste_satiri_ayristir(satir) for satir in (liste_verisi or [])]
                if ayristirilanlar and all(sonuc is not None for sonuc in ayristirilanlar):
                    secilebilirler = {
                        imap_tirnakli_ham_ad(imap_adi)
                        for bayraklar, imap_adi, _gorunen_ad in ayristirilanlar
                        if "\\NOSELECT" not in bayraklar
                    }
                    hesap_klasor_envanterini_uzlastir(eposta, secilebilirler)
                govde_onbellegi_durdu = False
                for kategori, imap_klasoru in self._klasor_sirasi(
                    klasor_haritasi, ozel_klasorler
                ):
                    if self._iptal.is_set():
                        return
                    try:
                        tip, _secim = imap.select(imap_klasoru, readonly=True)
                        if tip != "OK":
                            continue
                        tip, arama_verisi = imap.uid("SEARCH", "ALL")
                        if tip != "OK":
                            continue
                        sunucu_uidleri = uidleri_ayristir(arama_verisi)
                        onbellek_uidleri = son_uidleri_sinirla(
                            sunucu_uidleri, mesaj_sayisi
                        )
                        sonuc = klasor_basliklarini_senkronize_et(
                            imap,
                            eposta,
                            kategori,
                            imap_klasoru,
                            sunucu_uidleri=sunucu_uidleri,
                            iptal_edildi_mi=self._iptal.is_set,
                        )
                        if sonuc.get("iptal_edildi"):
                            return
                        if sonuc.get("atlandi"):
                            yeniden_dene_ms = (
                                BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS
                            )
                            continue
                        if not govde_onbellegi_durdu:
                            govde_sonucu = klasor_govdelerini_senkronize_et(
                                imap,
                                eposta,
                                imap_klasoru,
                                sunucu_uidleri=onbellek_uidleri,
                                iptal_edildi_mi=self._iptal.is_set,
                            )
                            if govde_sonucu.get("iptal_edildi"):
                                return
                            if govde_sonucu.get("atlandi"):
                                yeniden_dene_ms = (
                                    BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS
                                )
                            govde_onbellegi_durdu = bool(
                                govde_sonucu.get("sinira_ulasti")
                            )
                        # Tam gövde kaydedilirken ön izleme de üretildiği için önce
                        # gövde eşitlemesini tamamla. Ön izleme açıksa yalnızca gövdesi
                        # alınamayan ve ön izlemesi hâlâ eksik iletilerin kısa bölümünü
                        # ayrıca indir; böylece aynı ileti gereksiz yere iki kez alınmaz.
                        if onizleme_ayari_yukle():
                            onizleme_sonucu = klasor_onizlemelerini_senkronize_et(
                                imap,
                                eposta,
                                imap_klasoru,
                                sunucu_uidleri=onbellek_uidleri,
                                iptal_edildi_mi=self._iptal.is_set,
                            )
                            if onizleme_sonucu.get("iptal_edildi"):
                                return
                            if onizleme_sonucu.get("atlandi"):
                                yeniden_dene_ms = (
                                    BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS
                                )
                    except Exception as e:
                        if isinstance(e, (OSError, EOFError, imaplib.IMAP4.abort)):
                            uyari_kaydet(
                                "Başlangıç önbelleği sırasında IMAP bağlantısı kesildi; eşitleme daha sonra yeniden denenecek.",
                                e,
                            )
                            yeniden_dene_ms = BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS
                            break
                        hata_kaydet(
                            f"Başlangıçta klasör önbelleği eşitlenemedi: {kategori}", e
                        )
            if not self._iptal.is_set():
                try:
                    temel_bakim_yap(temizlik=True)
                except Exception as e:
                    hata_kaydet("Başlangıç veritabanı bakımı tamamlanamadı.", e)
        except Exception as e:
            # Sessiz önbellek ısıtması kullanıcıya açılış hatası göstermemelidir.
            uyari_kaydet(
                "Başlangıç e-posta senkronizasyonu bağlantı nedeniyle tamamlanamadı; daha sonra yeniden denenecek.",
                e,
            )
            yeniden_dene_ms = BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS
        finally:
            with self._baglanti_kilidi:
                if self._aktif_baglanti is baglanti:
                    self._aktif_baglanti = None
            self._sonucu_ana_is_parcacigina_aktar(yeniden_dene_ms)
