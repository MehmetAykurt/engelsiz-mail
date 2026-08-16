# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import email
import email.utils
from email import policy as email_policy
import os
import threading

import wx

try:
    import winsound
except Exception:
    winsound = None

from .config import (
    BILDIRIM_ETKIN_ALANI,
    BILDIRIM_GONDEREN_ALANI,
    BILDIRIM_KONU_ALANI,
    BILDIRIM_MESAJ_ALANI,
    BILDIRIM_SES_ALANI,
    BILDIRIM_SES_DOSYASI_ALANI,
    BILDIRIM_SES_TURU_ALANI,
    BILDIRIM_SES_TURU_DOSYA,
    BILDIRIM_SES_TURU_SISTEM,
    ayarlari_yukle,
    bildirim_ayarlari_yukle,
    bildirim_baslatildi_mi,
    bildirim_son_uid_kaydet,
    bildirim_son_uid_oku,
    bildirim_tabanini_sifirla,
    bildirim_uidvalidity_oku,
)
from .imap_client import (
    ImapBaglantisi,
    imap_uidvalidity_al,
    uidleri_ayristir,
)
from .logger import hata_kaydet
from .header_sync import klasor_basliklarini_senkronize_et
from .body_sync import yeni_ileti_govdesini_ek_indirmeden_kaydet
from .message_center import mesaj_soyle_ve_sonra_calistir
from .message_parser import ham_mesaj_verisi_al, gonderen_gosterimini_al
from .text_utils import guvenli_coz, konu_gosterimini_duzenle
from .ui_helpers import arka_planda_calistir

BILDIRIM_SOYLE_TIMER = None
IDLE_ILK_YENIDEN_BAGLANMA_MS = 60000
IDLE_AZAMI_YENIDEN_BAGLANMA_MS = 5 * 60 * 1000


def _idle_icin_hesap_hazir_mi():
    """IDLE dinleyicisinin bağlanabileceği hesap bilgisi var mı döndürür."""
    try:
        ayarlar = ayarlari_yukle()
    except Exception as e:
        hata_kaydet("IDLE için hesap ayarları okunamadı.", e)
        return False
    return bool(
        str(ayarlar.get("eposta", "") or "").strip()
        and str(ayarlar.get("sifre", "") or "").strip()
    )


def bekleyen_bildirim_konusmasini_durdur():
    """Henüz konuşulmamış bildirim zamanlayıcısını güvenli biçimde iptal eder."""
    global BILDIRIM_SOYLE_TIMER
    zamanlayici = BILDIRIM_SOYLE_TIMER
    BILDIRIM_SOYLE_TIMER = None
    if not zamanlayici:
        return False
    try:
        zamanlayici.Stop()
        return True
    except Exception as e:
        hata_kaydet("Bekleyen bildirim konuşması durdurulamadı.", e)
        return False


def bildirim_soyle(mesaj, gecikme_ms=350):
    """Menü kapanışı veya hızlı arayüz yenilemesi sırasında NVDA konuşması kesilmesin diye bildirimi geciktirir."""
    global BILDIRIM_SOYLE_TIMER

    def soyle_ve_temizle():
        global BILDIRIM_SOYLE_TIMER
        BILDIRIM_SOYLE_TIMER = None
        mesaj_soyle_ve_sonra_calistir(
            mesaj,
            lambda: None,
            ad="Yeni e-posta bildirimi",
        )

    try:
        bekleyen_bildirim_konusmasini_durdur()

        if gecikme_ms and gecikme_ms > 0:
            BILDIRIM_SOYLE_TIMER = wx.CallLater(int(gecikme_ms), soyle_ve_temizle)
        else:
            soyle_ve_temizle()
    except Exception as e:
        hata_kaydet("Bildirim verilemedi.", e)

def bildirim_sesi_cal():
    """Yeni e-posta için ayara göre sistem sesi veya kullanıcı tanımlı WAV dosyası çalar."""
    try:
        ayarlar = bildirim_ayarlari_yukle()
        ses_turu = ayarlar.get(BILDIRIM_SES_TURU_ALANI, BILDIRIM_SES_TURU_SISTEM)
        ses_dosyasi = ayarlar.get(BILDIRIM_SES_DOSYASI_ALANI, "")

        if ses_turu == BILDIRIM_SES_TURU_DOSYA and ses_dosyasi and os.path.exists(ses_dosyasi) and ses_dosyasi.lower().endswith(".wav"):
            if winsound:
                winsound.PlaySound(ses_dosyasi, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                wx.Bell()
            return

        if winsound:
            winsound.Beep(880, 120)
            winsound.Beep(1175, 120)
        else:
            wx.Bell()
    except Exception as e:
        hata_kaydet("Bildirim sesi çalınamadı.", e)

def bildirim_mesaji_olustur(yeni_sayisi, son_eposta=None, ayarlar=None):
    """Ayar seçeneklerine göre kısa bildirim metni üretir."""
    ayarlar = ayarlar or {}
    son_eposta = son_eposta or {}

    if yeni_sayisi <= 1:
        parcalar = [_("Yeni e-postanız var.")]
    else:
        parcalar = [_('{0} yeni e-postanız var.').format(yeni_sayisi)]

    if ayarlar.get(BILDIRIM_GONDEREN_ALANI):
        kimden = str(son_eposta.get("kimden", "") or "").strip()
        if kimden:
            parcalar.append(_('Gönderen: {0}.').format(kimden))

    if ayarlar.get(BILDIRIM_KONU_ALANI):
        konu = konu_gosterimini_duzenle(
            str(son_eposta.get("konu", "") or "").strip()
        )
        if konu:
            parcalar.append(_('Konu: {0}.').format(konu))

    return " ".join(parcalar).strip()

def bildirim_eposta_basligi_al(imap, uid):
    """Yeni e-postanın gönderen ve konu bilgisini alır."""
    sonuc = {"uid": str(uid), "kimden": "", "konu": ""}
    try:
        tip, veri = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if tip != "OK":
            return sonuc
        ham = ham_mesaj_verisi_al(veri)
        if not ham:
            return sonuc
        mesaj = email.message_from_bytes(ham, policy=email_policy.default)
        _ad, adres = email.utils.parseaddr(mesaj.get("From", ""))
        sonuc["kimden"] = adres or gonderen_gosterimini_al(mesaj.get("From", ""), "")
        sonuc["konu"] = guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
    except Exception as e:
        hata_kaydet("Bildirim e-posta başlığı alınamadı.", e)
    return sonuc

def bildirim_gelen_kutusu_kontrol_et():
    """Yeni ileti verisini eşitler; bildirim açıksa bildirilecek sonucu döndürür."""
    bildirim_ayar = bildirim_ayarlari_yukle()
    hesap_ayar = ayarlari_yukle()
    eposta = str(hesap_ayar.get("eposta", "") or "").strip()
    sifre = str(hesap_ayar.get("sifre", "") or "").strip()
    if not eposta or not sifre:
        return None

    try:
        with ImapBaglantisi(hesap_ayar) as imap:
            tip, _secim_verisi = imap.select("INBOX", readonly=True)
            if tip != "OK":
                return None

            gecerli_uidvalidity = imap_uidvalidity_al(imap)
            kayitli_uidvalidity = bildirim_uidvalidity_oku(eposta)

            onceki_uid = bildirim_son_uid_oku(eposta)
            bildirim_baslatildi = bildirim_baslatildi_mi(eposta)

            if (
                bildirim_baslatildi
                and kayitli_uidvalidity
                and gecerli_uidvalidity
                and kayitli_uidvalidity != gecerli_uidvalidity
            ):
                # UIDVALIDITY değiştiyse eski UID tabanı artık güvenilir değildir.
                # Mevcut gelen kutusunu yeni saymadan tabanı sessizce yeniden kur.
                bildirim_tabanini_sifirla(eposta, gecerli_uidvalidity)
                bildirim_baslatildi = False
                onceki_uid = 0

            if not bildirim_baslatildi:
                tip, arama_sonucu = imap.uid("SEARCH", "ALL")
                if tip != "OK":
                    return None

                uidler = []
                for uid in uidleri_ayristir(arama_sonucu):
                    try:
                        uidler.append(int(uid))
                    except Exception:
                        pass

                # İlk kurulumda, hesap değiştiğinde veya UIDVALIDITY değiştiğinde mevcut postalar yeni sayılmaz;
                # ancak gelen kutusu boşsa bu durum ayrıca kaydedilir. Böylece daha sonra
                # gelen ilk e-posta bildirimsiz geçmez.
                bildirim_son_uid_kaydet(eposta, max(uidler) if uidler else 0, baslatildi=True, uidvalidity=gecerli_uidvalidity)
                return None

            tip, arama_sonucu = imap.uid("SEARCH", "UID", f"{onceki_uid + 1}:*")
            if tip != "OK":
                return None

            yeni_uidler = []
            for uid in uidleri_ayristir(arama_sonucu):
                try:
                    uid_sayi = int(uid)
                except Exception:
                    continue
                if uid_sayi > onceki_uid:
                    yeni_uidler.append(uid_sayi)

            if not yeni_uidler:
                return None

            yeni_uidler = sorted(yeni_uidler)
            en_son_uid = max(yeni_uidler)

            # UID'nin yeni olması tek başına bildirim nedeni değildir. Kullanıcı
            # eklenti veya başka bir istemci üzerinden iletiyi bu denetimden önce
            # okumuş olabilir. Bildirim yalnızca hâlâ okunmamış yeni UID'ler içindir.
            tip, okunmamis_sonucu = imap.uid(
                "SEARCH", "UID", f"{onceki_uid + 1}:*", "UNSEEN"
            )
            if tip != "OK":
                return None

            yeni_uid_kumesi = set(yeni_uidler)
            okunmamis_uidler = []
            for uid in uidleri_ayristir(okunmamis_sonucu):
                try:
                    uid_sayi = int(uid)
                except Exception:
                    continue
                if uid_sayi in yeni_uid_kumesi:
                    okunmamis_uidler.append(uid_sayi)

            okunmamis_uidler = sorted(set(okunmamis_uidler))

            # Bildirim sayacı ile yerel ileti listesi birbirinden kopmasın.
            # Yalnızca yeni UID'leri vermek klasördeki eski üyelikleri yanlışlıkla
            # pasifleştireceği için tam UID görüntüsüyle Gelen Kutusu'nu eşitle.
            esitleme_basarili = True
            try:
                tip, tum_uid_sonucu = imap.uid("SEARCH", "ALL")
                if tip == "OK":
                    klasor_basliklarini_senkronize_et(
                        imap,
                        eposta,
                        "Gelen Kutusu",
                        "INBOX",
                        sunucu_uidleri=uidleri_ayristir(tum_uid_sonucu),
                    )
                else:
                    esitleme_basarili = False
            except Exception as e:
                esitleme_basarili = False
                hata_kaydet(
                    "Yeni e-posta denetimi sırasında Gelen Kutusu başlıkları eşitlenemedi.",
                    e,
                )

            # Yalnızca yeni iletilerin metin MIME parçaları alınır. Ekler için
            # hiçbir indirme isteği yapılmaz; kullanıcı isterse daha sonra
            # "Ekleri Kaydet" komutunu kullanır.
            for uid in yeni_uidler:
                try:
                    if not yeni_ileti_govdesini_ek_indirmeden_kaydet(
                        imap, eposta, uid
                    ):
                        esitleme_basarili = False
                except Exception as e:
                    esitleme_basarili = False
                    hata_kaydet(
                        f"Yeni e-posta gövdesi ek indirmeden önbelleğe alınamadı: UID {uid}",
                        e,
                    )

            if not esitleme_basarili:
                # Son UID ilerletilmez. IDLE yöneticisi bağlantıyı kısa bir
                # gecikmeyle yenileyerek aynı UID'leri yeniden eşitler.
                return {"yeniden_dene": True}

            # Okunmuş yeni iletiler tekrar tekrar aday olmasın. Bildirim verilmese
            # bile taban, görülen en yüksek yeni UID'ye ilerletilir.
            bildirim_son_uid_kaydet(
                eposta, en_son_uid, uidvalidity=gecerli_uidvalidity
            )
            if (
                not bildirim_ayar.get(BILDIRIM_ETKIN_ALANI)
                or not okunmamis_uidler
            ):
                return None

            son_eposta = {}
            if bildirim_ayar.get(BILDIRIM_MESAJ_ALANI) and (
                bildirim_ayar.get(BILDIRIM_GONDEREN_ALANI)
                or bildirim_ayar.get(BILDIRIM_KONU_ALANI)
            ):
                son_eposta = bildirim_eposta_basligi_al(imap, okunmamis_uidler[-1])
            return {
                "sayi": len(okunmamis_uidler),
                "son_eposta": son_eposta,
                "ayarlar": bildirim_ayar,
            }
    except Exception as e:
        # İnternet yoksa veya Gmail bağlantısı kurulamazsa kullanıcı rahatsız edilmez.
        # Bir sonraki zamanlayıcı turunda yeniden denenir.
        hata_kaydet("Yeni e-posta bildirimi sessizce atlandı.", e)
        return None

class BildirimYoneticisi:
    """Gelen Kutusu'nu IMAP IDLE ile dinleyip yeni iletileri bildiren yönetici."""

    def __init__(self):
        self._durum_kilidi = threading.RLock()
        self._sonlandirildi = False
        self._zamanlayici = None
        self._dinleme_kimligi = 0
        self._aktif_dinleme_kimligi = None
        self._ardisik_idle_hatasi = 0
        self._idle_imap = None
        self._yeni_eposta_callback = None
        self.ayarlari_yenile(ilkcagri=True)

    def yeni_eposta_callback_ayarla(self, callback=None):
        self._yeni_eposta_callback = callback if callable(callback) else None

    def durdur(self):
        with self._durum_kilidi:
            self._sonlandirildi = True
            self._aktif_dinleme_kimligi = None
        self._zamanlayiciyi_durdur()
        self._idle_baglantisini_kapat()
        bekleyen_bildirim_konusmasini_durdur()

    def _idle_baglantisini_kapat(self):
        """IDLE beklemesini keserek arka plan iş parçacığının çıkmasını sağlar."""
        with self._durum_kilidi:
            imap = self._idle_imap
            self._idle_imap = None
        if not imap:
            return
        try:
            imap.shutdown()
        except Exception:
            pass

    def _idle_baglantisini_ayarla(self, dinleme_kimligi, imap):
        """Bağlantıyı yalnız hâlâ geçerli olan dinleyici adına kaydeder."""
        with self._durum_kilidi:
            if (
                self._sonlandirildi
                or dinleme_kimligi != self._aktif_dinleme_kimligi
            ):
                return False
            self._idle_imap = imap
            return True

    def _idle_baglantisini_temizle(self, dinleme_kimligi, imap=None):
        """Eski bir iş parçacığının yeni IDLE bağlantısını silmesini önler."""
        with self._durum_kilidi:
            if dinleme_kimligi != self._aktif_dinleme_kimligi:
                return
            if imap is None or self._idle_imap is imap:
                self._idle_imap = None

    def _zamanlayiciyi_durdur(self):
        try:
            if self._zamanlayici:
                self._zamanlayici.Stop()
        except Exception as e:
            hata_kaydet("Bildirim zamanlayıcısı durdurulamadı.", e)
        self._zamanlayici = None

    def ayarlari_yenile(self, ilkcagri=False):
        with self._durum_kilidi:
            if self._sonlandirildi:
                return
            # Eski iş parçacığını yeni zamanlayıcı kurulmadan önce geçersiz kıl.
            # Böylece iki saniyelik yeni başlangıç aktif eski kimliğe takılmaz.
            self._aktif_dinleme_kimligi = None
        self._zamanlayiciyi_durdur()
        self._idle_baglantisini_kapat()
        bekleyen_bildirim_konusmasini_durdur()

        # Eklenti/NVDA açılışında ilk bağlantı kısa süre sonra kurulur. Sonrasında
        # sunucu yeni iletiyi IDLE ile doğrudan eşitler. Bildirim tercihi bu
        # bağlantının çalışıp çalışmamasını değil, yalnız kullanıcı uyarısını belirler.
        ilk_gecikme_ms = 15000 if ilkcagri else 2000
        self._dinlemeyi_planla(ilk_gecikme_ms)

    def _dinlemeyi_planla(self, gecikme_ms):
        if self._sonlandirildi:
            return
        self._zamanlayiciyi_durdur()
        self._zamanlayici = wx.CallLater(int(gecikme_ms), self._dinleme_baslat)

    def _dinleme_baslat(self):
        self._zamanlayici = None

        if not _idle_icin_hesap_hazir_mi():
            # Hesap daha sonra kaydedilirse NVDA yeniden başlatılmadan IDLE başlasın.
            self._dinlemeyi_planla(IDLE_ILK_YENIDEN_BAGLANMA_MS)
            return

        with self._durum_kilidi:
            if self._sonlandirildi or self._aktif_dinleme_kimligi is not None:
                return
            self._dinleme_kimligi += 1
            dinleme_kimligi = self._dinleme_kimligi
            self._aktif_dinleme_kimligi = dinleme_kimligi
        try:
            arka_planda_calistir(self._arka_planda_dinle, dinleme_kimligi)
        except Exception as e:
            hata_kaydet("Gelen Kutusu IDLE iş parçacığı başlatılamadı.", e)
            self._dinleme_bitti(dinleme_kimligi, False)

    def _arka_planda_dinle(self, dinleme_kimligi):
        """Ayrı IMAP bağlantısında yalnızca Gelen Kutusu IDLE döngüsünü çalıştırır."""
        basarili = False
        try:
            # İlk tur, eski iletileri yeni saymadan bildirim tabanını kurar.
            sonuc = bildirim_gelen_kutusu_kontrol_et()
            if sonuc and sonuc.get("yeniden_dene"):
                raise RuntimeError("Yeni e-posta eşitlemesi tamamlanamadı.")
            if sonuc:
                wx.CallAfter(self._yeni_ileti_alindi, dinleme_kimligi, sonuc)

            while self._dinleme_aktif_mi(dinleme_kimligi):
                hesap_ayar = ayarlari_yukle()
                with ImapBaglantisi(hesap_ayar) as imap:
                    tip, _veri = imap.select("INBOX", readonly=True)
                    if tip != "OK":
                        raise RuntimeError("Gelen Kutusu IDLE için açılamadı.")

                    if not self._idle_baglantisini_ayarla(dinleme_kimligi, imap):
                        break
                    try:
                        with imap.idle() as idler:
                            olay = idler.wait()
                    finally:
                        self._idle_baglantisini_temizle(dinleme_kimligi, imap)

                if not self._dinleme_aktif_mi(dinleme_kimligi):
                    break
                if olay is None:
                    raise ConnectionError("IDLE bağlantısı sunucu tarafından kapatıldı.")
                with self._durum_kilidi:
                    self._ardisik_idle_hatasi = 0
                if olay in ("EXISTS", "OTHER"):
                    sonuc = bildirim_gelen_kutusu_kontrol_et()
                    if sonuc and sonuc.get("yeniden_dene"):
                        raise RuntimeError("Yeni e-posta eşitlemesi tamamlanamadı.")
                    if sonuc:
                        wx.CallAfter(self._yeni_ileti_alindi, dinleme_kimligi, sonuc)
                # RENEW, sunucunun yaklaşık 29 dakikalık IDLE sınırıdır; bağlantı
                # kapanıp aynı döngüde yeniden kurulur.
            basarili = True
        except Exception as e:
            if self._dinleme_aktif_mi(dinleme_kimligi):
                hata_kaydet("Gelen Kutusu IDLE dinleyicisi yeniden başlatılacak.", e)
        finally:
            self._idle_baglantisini_temizle(dinleme_kimligi)
            wx.CallAfter(self._dinleme_bitti, dinleme_kimligi, basarili)

    def _dinleme_aktif_mi(self, dinleme_kimligi):
        with self._durum_kilidi:
            return (
                not self._sonlandirildi
                and dinleme_kimligi == self._aktif_dinleme_kimligi
            )

    def _yeni_ileti_alindi(self, dinleme_kimligi, sonuc):
        with self._durum_kilidi:
            if (
                self._sonlandirildi
                or dinleme_kimligi != self._aktif_dinleme_kimligi
            ):
                return

        try:
            if sonuc:
                self._bildirim_ver(sonuc)
                callback = self._yeni_eposta_callback
                if callable(callback):
                    callback(sonuc)
        except Exception as e:
            hata_kaydet("Yeni e-posta bildirimi verilemedi.", e)

    def _dinleme_bitti(self, dinleme_kimligi, basarili):
        with self._durum_kilidi:
            if dinleme_kimligi != self._aktif_dinleme_kimligi:
                return
            self._aktif_dinleme_kimligi = None
            sonlandirildi = self._sonlandirildi
            if basarili:
                self._ardisik_idle_hatasi = 0
                gecikme_ms = 2000
            else:
                self._ardisik_idle_hatasi = min(
                    self._ardisik_idle_hatasi + 1, 4
                )
                gecikme_ms = min(
                    IDLE_ILK_YENIDEN_BAGLANMA_MS
                    * (2 ** (self._ardisik_idle_hatasi - 1)),
                    IDLE_AZAMI_YENIDEN_BAGLANMA_MS,
                )
        if sonlandirildi:
            return
        # IDLE kurulamazsa başlangıç denetimi yedek kontrol işlevi görür. Ağ ve
        # günlük yükünü sınırlamak için 1, 2, 4 ve en çok 5 dakikalık artan aralık kullan.
        self._dinlemeyi_planla(gecikme_ms)

    def _bildirim_ver(self, sonuc):
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return
        if ayarlar.get(BILDIRIM_SES_ALANI):
            arka_planda_calistir(bildirim_sesi_cal)
        if ayarlar.get(BILDIRIM_MESAJ_ALANI):
            bildirim_soyle(
                bildirim_mesaji_olustur(
                    int(sonuc.get("sayi", 1) or 1),
                    sonuc.get("son_eposta") or {}, ayarlar,
                ),
                300,
            )
