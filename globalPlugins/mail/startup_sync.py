# -*- coding: utf-8 -*-
"""NVDA açılışından sonra sessiz başlık önbelleği ısıtma hizmeti."""

import threading

import wx

from .config import ayarlari_yukle, onizleme_ayari_yukle
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


class BaslangicSenkronizasyonYoneticisi:
    """Tek seferlik ve iptal edilebilir sessiz başlangıç senkronizasyonunu yönetir."""

    def __init__(self, gecikme_ms=BASLANGIC_SENKRONIZASYON_GECIKMESI_MS):
        self._iptal = threading.Event()
        self._basladi = False
        self._zamanlayici = None
        try:
            self._zamanlayici = wx.CallLater(max(0, int(gecikme_ms)), self._baslat)
        except Exception as e:
            hata_kaydet("Başlangıç senkronizasyon zamanlayıcısı oluşturulamadı.", e)

    def _baslat(self):
        self._zamanlayici = None
        if self._iptal.is_set() or self._basladi:
            return
        self._basladi = True
        arka_planda_calistir(self._calistir)

    def durdur(self):
        self._iptal.set()
        zamanlayici = self._zamanlayici
        self._zamanlayici = None
        if zamanlayici:
            try:
                zamanlayici.Stop()
            except Exception as e:
                hata_kaydet("Başlangıç senkronizasyon zamanlayıcısı durdurulamadı.", e)

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
            return
        try:
            # Bos semayi da hesap ve ag kontrolunden bagimsiz olarak arka planda kur.
            veritabani_hazirla()
        except Exception as e:
            hata_kaydet("Baslangic veritabani hazirligi tamamlanamadi.", e)
            return
        ayarlar = ayarlari_yukle()
        eposta = str(ayarlar.get("eposta", "") or "").strip()
        sifre = str(ayarlar.get("sifre", "") or "").strip()
        if not eposta or not sifre:
            return
        # Senkronizasyon bekleyen bir silmeyi yeniden görünür yapmadan önce
        # çevrimdışı kuyruğu sunucuya uygulamayı dene.
        bekleyen_silmeleri_isle(ayarlar, eposta)
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, liste_verisi = imap.list()
                if tip != "OK":
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
                        govde_sonucu = klasor_govdelerini_senkronize_et(
                            imap,
                            eposta,
                            imap_klasoru,
                            sunucu_uidleri=list(reversed(sunucu_uidleri)),
                            iptal_edildi_mi=self._iptal.is_set,
                        )
                        if govde_sonucu.get("iptal_edildi"):
                            return
                        # Tam gövde kaydedilirken ön izleme de üretildiği için önce
                        # gövde eşitlemesini tamamla. Ön izleme açıksa yalnızca gövdesi
                        # alınamayan ve ön izlemesi hâlâ eksik iletilerin kısa bölümünü
                        # ayrıca indir; böylece aynı ileti gereksiz yere iki kez alınmaz.
                        if onizleme_ayari_yukle():
                            onizleme_sonucu = klasor_onizlemelerini_senkronize_et(
                                imap,
                                eposta,
                                imap_klasoru,
                                sunucu_uidleri=list(reversed(sunucu_uidleri)),
                                iptal_edildi_mi=self._iptal.is_set,
                            )
                            if onizleme_sonucu.get("iptal_edildi"):
                                return
                    except Exception as e:
                        if isinstance(e, (OSError, EOFError, imaplib.IMAP4.abort)):
                            uyari_kaydet(
                                "Başlangıç önbelleği sırasında IMAP bağlantısı kesildi; kalan klasörler sonraki çalışmaya bırakıldı.",
                                e,
                            )
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
