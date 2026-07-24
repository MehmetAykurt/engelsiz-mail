# -*- coding: utf-8 -*-

import email
import email.utils
from email import policy as email_policy
import os

import wx

try:
    import winsound
except Exception:
    winsound = None

from .config import (
    BILDIRIM_ARALIK_ALANI,
    BILDIRIM_ETKIN_ALANI,
    BILDIRIM_GONDEREN_ALANI,
    BILDIRIM_KONU_ALANI,
    BILDIRIM_MESAJ_ALANI,
    BILDIRIM_SES_ALANI,
    BILDIRIM_SES_DOSYASI_ALANI,
    BILDIRIM_SES_TURU_ALANI,
    BILDIRIM_SES_TURU_DOSYA,
    BILDIRIM_SES_TURU_SISTEM,
    VARSAYILAN_BILDIRIM_ARALIGI,
    ayarlari_yukle,
    bildirim_araligini_duzenle,
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
from .message_center import mesaj_soyle_ve_sonra_calistir
from .message_parser import ham_mesaj_verisi_al, gonderen_gosterimini_al
from .text_utils import guvenli_coz, konu_gosterimini_duzenle
from .ui_helpers import arka_planda_calistir

BILDIRIM_SOYLE_TIMER = None


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
        try:
            if BILDIRIM_SOYLE_TIMER:
                BILDIRIM_SOYLE_TIMER.Stop()
        except Exception as e:
            hata_kaydet("Bekleyen konuşma zamanlayıcısı durdurulamadı.", e)
        BILDIRIM_SOYLE_TIMER = None

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
        parcalar = ["Yeni e-postanız var."]
    else:
        parcalar = [f"{yeni_sayisi} yeni e-postanız var."]

    if ayarlar.get(BILDIRIM_GONDEREN_ALANI):
        kimden = str(son_eposta.get("kimden", "") or "").strip()
        if kimden:
            parcalar.append(f"Gönderen: {kimden}.")

    if ayarlar.get(BILDIRIM_KONU_ALANI):
        konu = konu_gosterimini_duzenle(
            str(son_eposta.get("konu", "") or "").strip()
        )
        if konu:
            parcalar.append(f"Konu: {konu}.")

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
        sonuc["kimden"] = gonderen_gosterimini_al(mesaj.get("From", ""), "")
        sonuc["konu"] = guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
    except Exception as e:
        hata_kaydet("Bildirim e-posta başlığı alınamadı.", e)
    return sonuc

def bildirim_gelen_kutusu_kontrol_et():
    """Gelen Kutusu'nda yeni UID var mı diye sessiz denetim yapar."""
    bildirim_ayar = bildirim_ayarlari_yukle()
    if not bildirim_ayar.get(BILDIRIM_ETKIN_ALANI):
        return None

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

            # Okunmuş yeni iletiler tekrar tekrar aday olmasın. Bildirim verilmese
            # bile taban, görülen en yüksek yeni UID'ye ilerletilir.
            bildirim_son_uid_kaydet(
                eposta, en_son_uid, uidvalidity=gecerli_uidvalidity
            )
            if not okunmamis_uidler:
                return None

            son_eposta = {}
            if bildirim_ayar.get(BILDIRIM_GONDEREN_ALANI) or bildirim_ayar.get(BILDIRIM_KONU_ALANI):
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
    """NVDA açıkken Engelsiz Mail yeni e-posta bildirimlerini zamanlayan yönetici."""

    def __init__(self):
        self._sonlandirildi = False
        self._kontrol_suruyor = False
        self._zamanlayici = None
        self._kontrol_kimligi = 0
        self._aktif_kontrol_kimligi = None
        self.ayarlari_yenile(ilkcagri=True)

    def durdur(self):
        self._sonlandirildi = True
        self._aktif_kontrol_kimligi = None
        self._kontrol_suruyor = False
        self._zamanlayiciyi_durdur()

    def _zamanlayiciyi_durdur(self):
        try:
            if self._zamanlayici:
                self._zamanlayici.Stop()
        except Exception as e:
            hata_kaydet("Bildirim zamanlayıcısı durdurulamadı.", e)
        self._zamanlayici = None

    def ayarlari_yenile(self, ilkcagri=False):
        if self._sonlandirildi:
            return
        self._zamanlayiciyi_durdur()
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        # Eklenti/NVDA açılışında ilk kontrol kısa süre sonra yapılır.
        # Sonraki denetimler kullanıcının seçtiği dakika aralığına göre sürer.
        ilk_gecikme_ms = 15000 if ilkcagri else 2000
        self._sonraki_kontrolu_planla(ilk_gecikme_ms)

    def _sonraki_kontrolu_planla(self, gecikme_ms=None):
        if self._sonlandirildi:
            return
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            self._zamanlayiciyi_durdur()
            return

        if gecikme_ms is None:
            dakika = bildirim_araligini_duzenle(ayarlar.get(BILDIRIM_ARALIK_ALANI, VARSAYILAN_BILDIRIM_ARALIGI))
            gecikme_ms = dakika * 60 * 1000

        self._zamanlayiciyi_durdur()
        self._zamanlayici = wx.CallLater(int(gecikme_ms), self._zamanlayici_tetiklendi)

    def _zamanlayici_tetiklendi(self):
        if self._sonlandirildi:
            return
        self._zamanlayici = None

        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        if self._kontrol_suruyor:
            self._sonraki_kontrolu_planla()
            return

        self._kontrol_kimligi += 1
        kontrol_kimligi = self._kontrol_kimligi
        self._aktif_kontrol_kimligi = kontrol_kimligi
        self._kontrol_suruyor = True
        arka_planda_calistir(self._arka_plan_kontrolu, kontrol_kimligi)

    def _arka_plan_kontrolu(self, kontrol_kimligi):
        sonuc = bildirim_gelen_kutusu_kontrol_et()
        wx.CallAfter(self._kontrol_bitti, kontrol_kimligi, sonuc)

    def _kontrol_bitti(self, kontrol_kimligi, sonuc):
        if self._sonlandirildi:
            return
        if kontrol_kimligi != self._aktif_kontrol_kimligi:
            return

        self._aktif_kontrol_kimligi = None
        self._kontrol_suruyor = False

        try:
            if sonuc:
                self._bildirim_ver(sonuc)
        except Exception as e:
            hata_kaydet("Yeni e-posta bildirimi verilemedi.", e)

        self._sonraki_kontrolu_planla()

    def _bildirim_ver(self, sonuc):
        ayarlar = bildirim_ayarlari_yukle()
        if not ayarlar.get(BILDIRIM_ETKIN_ALANI):
            return

        if ayarlar.get(BILDIRIM_SES_ALANI):
            arka_planda_calistir(bildirim_sesi_cal)

        if ayarlar.get(BILDIRIM_MESAJ_ALANI):
            mesaj = bildirim_mesaji_olustur(
                int(sonuc.get("sayi", 1) or 1),
                sonuc.get("son_eposta") or {},
                ayarlar,
            )
            bildirim_soyle(mesaj, 300)
