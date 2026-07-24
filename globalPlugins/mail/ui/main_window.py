# -*- coding: utf-8 -*-
# Engelsiz Mail - ana pencere ve ana pencere yardımcıları

import os

import gui
import ui
import wx

try:
    import versionInfo
except Exception:
    versionInfo = None

from .folder_view import (
    LISTE_MODU_EPOSTA,
    LISTE_MODU_KLASOR,
    klasor_ayrac_satiri_mi as folder_klasor_ayrac_satiri_mi,
    klasor_gorunumunu_goster as folder_klasor_gorunumunu_goster,
    klasor_liste_ogeleri as folder_klasor_liste_ogeleri,
    klasor_modunu_hazirla as folder_klasor_modunu_hazirla,
    klasor_secimini_odaktan_guncelle as folder_klasor_secimini_odaktan_guncelle,
    klasor_sutunlarini_ayarla as folder_klasor_sutunlarini_ayarla,
    secili_klasor_adini_al as folder_secili_klasor_adini_al,
)
from .message_list import (
    birinci_sutun_basligi as message_birinci_sutun_basligi,
    birinci_sutun_basligini_guncelle as message_birinci_sutun_basligini_guncelle,
    eposta_modunu_hazirla as message_eposta_modunu_hazirla,
    liste_bilgi_satiri_goster as message_liste_bilgi_satiri_goster,
    mesaji_listede_okundu_yap as message_mesaji_listede_okundu_yap,
    mesaj_liste_gosterimi as message_mesaj_liste_gosterimi,
)
from . import archive_actions
from . import delete_actions
from . import draft_actions
from . import folder_discovery
from . import message_actions
from . import keyboard_handlers

from ..connection_diagnostics import baglanti_denetimini_yap
from ..config import (
    MESAJ_SAYISI_ALANI,
    VARSAYILAN_MESAJ_SAYISI,
    GORUNUM_YAZI_TIPI_ALANI,
    GORUNUM_YAZI_BOYUTU_ALANI,
    GORUNUM_YAZI_STILI_ALANI,
    GORUNUM_METIN_RENGI_ALANI,
    GORUNUM_ARKA_PLAN_RENGI_ALANI,
    GORUNUM_SISTEM_RENKLERI_ALANI,
    GORUNUM_YAZI_BOYUTU_EN_AZ,
    GORUNUM_YAZI_BOYUTU_EN_COK,
    GORUNUM_YAZI_STILI_SECENEKLERI,
    GORUNUM_METIN_RENKLERI,
    GORUNUM_ARKA_PLAN_RENKLERI,
    mesaj_sayisini_duzenle,
    ayarlari_yukle,
    imza_yukle,
    imza_kaydet,
    imza_kaldir,
    hesap_bilgilerini_sil as kayitli_hesap_bilgilerini_sil,
    onizleme_ayari_yukle,
    onizleme_ayari_kaydet,
    silme_onayi_ayari_yukle,
    silme_onayi_ayari_kaydet,
    kalici_silme_onayi_ayari_yukle,
    kalici_silme_onayi_ayari_kaydet,
    adres_otomatik_kaydet_ayari_yukle,
    adres_otomatik_kaydet_ayari_kaydet,
    escape_kapat_ayari_yukle,
    escape_kapat_ayari_kaydet,
    konusmalari_grupla_ayari_yukle,
    konusmalari_grupla_ayari_kaydet,
    gorunum_ayarlari_yukle,
    gorunum_ayarlari_kaydet,
    gorunum_ayarlari_sifirla,
)
from ..errors import MailHatasi
from ..folder_counts import (
    klasor_sayisi_onbellegi_temizle,
)
from ..folders import (
    SISTEM_KLASORLERI,
    VARSAYILAN_KLASOR_HARITASI,
)
from ..gmail_actions import (
    kategori_adini_klasorden_bul as gmail_kategori_adini_klasorden_bul,
    gmail_etiket_ifadesi as gmail_etiket_ifadesi_olustur,
    kaynak_etiketi_kaldirilabilir_mi as gmail_kaynak_etiketi_kaldirilabilir_mi,
    gmail_etiket_ekle_ve_kaynak_kaldir as gmail_etiket_ekle_ve_kaynak_kaldir_akisi,
    okunmadi_etiketini_kaldir as okunmadi_etiket_metnini_kaldir,
    cop_klasoru_mu as gmail_cop_klasoru_mu,
    tum_postalar_klasoru_mu as gmail_tum_postalar_klasoru_mu,
    taslak_klasoru_mu as gmail_taslak_klasoru_mu,
    spam_klasoru_mu as gmail_spam_klasoru_mu,
)
from ..imap_client import (
    ImapBaglantisi,
    imap_gmail_etiket_store,
    imap_ok_mu,
    imap_gmail_etiket_destegini_dogrula,
    uid_kumesi_hazirla,
    uid_listesini_parcala,
    uidleri_ayristir,
    imap_uidleri_kalici_sil,
    imap_x_gm_msgid_haritasi_al,
)
from ..logger import hata_kaydet
from ..mail_store import (
    gmail_mesajlarini_yerelde_pasif_yap,
    klasor_uidlerini_pasif_yap,
    onizlemesi_eksik_uidleri_al,
)
from ..database_maintenance import gmail_mesajlarini_yerelden_sil, yerel_veritabanini_sifirla
from ..mailbox_state import POSTA_DURUM_KILIDI
from ..mailbox_loader import eposta_listesi_hazirla, yerel_eposta_listesi_hazirla
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..notifications import bildirim_soyle
from ..preview_sync import klasor_onizlemelerini_senkronize_et
from ..paths import EKLENTI_KOK_DIZINI
from ..smtp_client import (
    baglanti_hatasi_kullanici_mesaji,
)
from ..text_utils import konu_gosterimini_duzenle
from ..version import EKLENTI_SURUMU
from ..conversation import mesaj_uidlerini_al
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_plan_gorevlerini_gecersiz_kil,
    pencere_kullanilabilir_mi,
    guvenli_call_after,
    guvenli_modal_goster,
    odagi_listeye_guvenli_dondur,
    arka_planda_calistir,
    gorev_icin_guvenli_call_after,
    gorunum_denetimlerine_uygula,
)
from .contacts_window import KisilerPenceresi
from .feedback_dialog import OneriGorusPenceresi
from .other_addons import DIGER_EKLENTILER, DigerEklentiPenceresi
from .search_dialog import EpostalardaAraPenceresi
from .signature_dialog import IMZA_SIL_ID, ImzaPenceresi
from .settings_dialogs import (
    AyarlarPenceresi,
    BaglantiDenetimSonucPenceresi,
    MesajSayisiPenceresi,
    BildirimAyarlariPenceresi,
    yardim_belgesini_ac,
)
from .settings_transfer_dialog import AyarlariAktarmaPenceresi

EKLENTI_ADI = "Engelsiz Mail"
YENILEME_GECIKMESI_MS = 800
ILK_YUKLEME_GECIKMESI_MS = 150
GONDERIM_SONRASI_ESITLEME_GECIKMESI_MS = 5000

def ne_yeni_belgesini_ac():
    adaylar = [
        os.path.join(EKLENTI_KOK_DIZINI, "doc", "tr", "ne-yeni.html"),
    ]
    for yol in adaylar:
        if os.path.exists(yol):
            try:
                os.startfile(yol)
                return True
            except Exception as e:
                hata_kaydet("Yenilikler dosyası açılamadı.", e)
                break
    ui.message("Yenilikler dosyası bulunamadı. Lütfen doc/tr/ne-yeni.html dosyasını kontrol edin.")
    return False


def nvda_surumunu_al():
    try:
        if versionInfo is not None:
            surum = getattr(versionInfo, "version", "")
            if surum:
                return str(surum)
            yil = getattr(versionInfo, "version_year", None)
            ana = getattr(versionInfo, "version_major", None)
            alt = getattr(versionInfo, "version_minor", None)
            yapi = getattr(versionInfo, "version_build", None)
            parcalar = [str(x) for x in (yil, ana, alt, yapi) if x is not None]
            if parcalar:
                return ".".join(parcalar)
    except Exception as e:
        hata_kaydet("NVDA sürümü alınamadı.", e)
    return "Bilinmiyor"


def hakkinda_penceresini_ac(parent=None):
    metin = (
        f"{EKLENTI_ADI}\n\n"
        f"Eklenti sürümü: {EKLENTI_SURUMU}\n"
        f"NVDA sürümü: {nvda_surumunu_al()}\n"
        "Geliştirici: Mehmet Aykurt\n"
        "E-posta: m.aykurt38@gmail.com\n"
        "Lisans: GNU Genel Kamu Lisansı, sürüm 2.0\n\n"
        "Engelsiz Mail, NVDA ekran okuyucusu kullanıcıları için geliştirilen erişilebilir e-posta eklentisidir."
    )
    try:
        gui.messageBox(
            metin,
            f"{EKLENTI_ADI} Hakkında",
            wx.OK | wx.ICON_INFORMATION,
            parent,
        )
    except TypeError:
        gui.messageBox(metin, f"{EKLENTI_ADI} Hakkında", wx.OK | wx.ICON_INFORMATION)


class GelenKutusuPenceresi(wx.Frame):
    klasor_modunu_hazirla = folder_klasor_modunu_hazirla
    klasor_sutunlarini_ayarla = folder_klasor_sutunlarini_ayarla
    klasor_ayrac_satiri_mi = staticmethod(folder_klasor_ayrac_satiri_mi)
    klasor_liste_ogeleri = folder_klasor_liste_ogeleri
    klasor_gorunumunu_goster = folder_klasor_gorunumunu_goster
    secili_klasor_adini_al = folder_secili_klasor_adini_al
    klasor_secimini_odaktan_guncelle = folder_klasor_secimini_odaktan_guncelle
    liste_bilgi_satiri_goster = message_liste_bilgi_satiri_goster
    birinci_sutun_basligi = message_birinci_sutun_basligi
    birinci_sutun_basligini_guncelle = message_birinci_sutun_basligini_guncelle
    mesaj_liste_gosterimi = message_mesaj_liste_gosterimi
    mesaji_listede_okundu_yap = message_mesaji_listede_okundu_yap
    eposta_modunu_hazirla = message_eposta_modunu_hazirla

    tum_kategoriler = folder_discovery.tum_kategoriler
    _aktif_eposta_adresi = folder_discovery._aktif_eposta_adresi
    _klasor_sayisi_onbellegi_yukle = folder_discovery._klasor_sayisi_onbellegi_yukle
    _klasor_sayisi_onbellegi_kaydet = folder_discovery._klasor_sayisi_onbellegi_kaydet
    _klasor_sayisi_cache_guncelle = folder_discovery._klasor_sayisi_cache_guncelle
    klasorleri_kesfet_tetikle = folder_discovery.klasorleri_kesfet_tetikle
    klasorleri_kesfet_thread = folder_discovery.klasorleri_kesfet_thread
    klasorleri_kesfet_sonuc = folder_discovery.klasorleri_kesfet_sonuc
    klasorleri_kesfet_bitti = folder_discovery.klasorleri_kesfet_bitti
    gonderim_sonrasi_esitle_tetikle = folder_discovery.gonderim_sonrasi_esitle_tetikle
    gonderim_sonrasi_esitle_thread = folder_discovery.gonderim_sonrasi_esitle_thread
    gonderim_sonrasi_esitle_sonuc = folder_discovery.gonderim_sonrasi_esitle_sonuc
    gonderim_sonrasi_esitle_bitti = folder_discovery.gonderim_sonrasi_esitle_bitti
    sistem_klasor_sayilarini_guncelle_tetikle = folder_discovery.sistem_klasor_sayilarini_guncelle_tetikle
    sistem_klasor_sayilarini_guncelle_thread = folder_discovery.sistem_klasor_sayilarini_guncelle_thread
    sistem_klasor_sayilarini_guncelle_sonuc = folder_discovery.sistem_klasor_sayilarini_guncelle_sonuc
    sistem_klasor_sayilarini_guncelle_bitti = folder_discovery.sistem_klasor_sayilarini_guncelle_bitti
    klasor_haritasini_hazirla = folder_discovery.klasor_haritasini_hazirla
    klasor_haritasini_uygula = folder_discovery.klasor_haritasini_uygula

    def __init__(self, parent, bildirim_yenile_callback=None):
        super().__init__(parent, title="Engelsiz Mail")
        self._bildirim_yenile_callback = bildirim_yenile_callback or (lambda: None)
        self.mailler = []
        self.isaretliler = set()
        self.ozel_klasorler = []
        self.kategori_isimleri = list(SISTEM_KLASORLERI)
        self.klasor_haritasi = dict(VARSAYILAN_KLASOR_HARITASI)
        self.secili_kategori = "Gelen Kutusu"
        self.yuklu_kategori = self.secili_kategori
        # Tek liste modeli: aynı liste klasör veya e-posta modunda çalışır.
        self.liste_modu = LISTE_MODU_KLASOR
        self.yukleniyor = False
        self.ilk_yukleme = True
        self._yenileme_hedef_mail_id = None
        self._yenileme_hedef_indeks = None
        self._yenileme_sessiz = False
        self._kapatildi = False
        self._baglanti_denetleniyor = False
        self._hesap_bilgisi_eksik_uyarisi_gosterildi = False
        self._yukleme_islem_no = 0
        self._son_yukleme_hatasi = False
        self._klasor_sayisi_cache = {}
        self._klasor_sayisi_onbellegi_yukle()
        self._sistem_klasor_sayisi_guncelleniyor = False
        self._klasor_kesfi_guncelleniyor = False
        self._klasor_kesfi_tekrar_bekliyor = False
        self._gonderim_sonrasi_esitleme_guncelleniyor = False
        self._gonderim_sonrasi_esitleme_bekleyen = None
        self._gonderim_sonrasi_esitleme_timer = None
        self._gonderim_sonrasi_yeniden_deneme_timer = None
        self._sistem_klasor_sayisi_acilista_guncellendi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        # Tek liste modelinde Escape/Enter davranışı pencere düzeyinde de güvenceye alınır.
        self.Bind(wx.EVT_CHAR_HOOK, self.ana_pencere_tus_yakalandi)

        self.id_hesap_baglan = wx.NewId()
        self.id_hesap_sil = wx.NewId()
        self.id_baglanti_denetle = wx.NewId()
        self.id_yeni = wx.NewId()
        self.id_yanitla = wx.NewId()
        self.id_ilet = wx.NewId()
        self.id_eml_ac = wx.NewId()
        self.id_kaydet = wx.NewId()
        self.id_cikis = wx.NewId()
        self.id_tumunu = wx.NewId()
        self.id_kaldir = wx.NewId()
        self.id_arsiv = wx.NewId()
        self.id_arsiv_yonet = wx.NewId()
        self.id_kisiler = wx.NewId()
        self.id_imza = wx.NewId()
        self.id_ara = wx.NewId()
        self.id_sil = wx.NewId()
        self.id_kalici_sil = wx.NewId()
        self.id_yenile = wx.NewId()
        self.id_eposta_sayisi = wx.NewId()
        self.id_onizleme = wx.NewId()
        self.id_konusmalari_grupla = wx.NewId()
        self.id_silme_onayi = wx.NewId()
        self.id_kalici_silme_onayi = wx.NewId()
        self.id_adres_otomatik_kaydet = wx.NewId()
        self.id_escape_kapat = wx.NewId()
        self.id_bildirimler = wx.NewId()
        self.id_ayarlari_aktar = wx.NewId()
        self.id_veritabani_sifirla = wx.NewId()
        self.id_cop_kutusunu_bosalt = wx.NewId()
        self.id_spami_bosalt = wx.NewId()
        self.id_gonderilenleri_cope_tasi = wx.NewId()
        self.id_yazi_tipi = wx.NewId()
        self.id_yazi_boyutu = wx.NewId()
        self.id_yazi_stili = wx.NewId()
        self.id_metin_rengi = wx.NewId()
        self.id_arka_plan_rengi = wx.NewId()
        self.id_sistem_renkleri = wx.NewId()
        self.id_gorunum_sifirla = wx.NewId()
        self.id_yardim_kilavuzu = wx.NewId()
        self.id_ne_yeni = wx.NewId()
        self.id_hakkinda = wx.NewId()
        self.id_oneri_gorus = wx.NewId()
        self.diger_eklenti_menu_idleri = {
            wx.NewId(): eklenti for eklenti in DIGER_EKLENTILER
        }

        self.Bind(wx.EVT_MENU, self.hesap_baglan, id=self.id_hesap_baglan)
        self.Bind(wx.EVT_MENU, self.hesap_bilgilerini_sil, id=self.id_hesap_sil)
        self.Bind(wx.EVT_MENU, self.baglantiyi_denetle_menu, id=self.id_baglanti_denetle)
        self.Bind(wx.EVT_MENU, self.yeni_posta_yaz, id=self.id_yeni)
        self.Bind(wx.EVT_MENU, self.secili_mesaji_yanitla, id=self.id_yanitla)
        self.Bind(wx.EVT_MENU, self.secili_mesaji_ilet, id=self.id_ilet)
        self.Bind(wx.EVT_MENU, self.eml_dosyasini_ac, id=self.id_eml_ac)
        self.Bind(wx.EVT_MENU, self.secili_epostayi_kaydet, id=self.id_kaydet)
        self.Bind(wx.EVT_MENU, self.pencereyi_kapat, id=self.id_cikis)
        self.Bind(wx.EVT_CLOSE, self.pencereyi_kapat)
        self.Bind(wx.EVT_MENU, self.tumunu_isaretle, id=self.id_tumunu)
        self.Bind(wx.EVT_MENU, self.isaretleri_kaldir, id=self.id_kaldir)
        self.Bind(wx.EVT_MENU, self.arsive_gonder_menu, id=self.id_arsiv)
        self.Bind(wx.EVT_MENU, self.arsiv_klasorlerini_yonet, id=self.id_arsiv_yonet)
        self.Bind(wx.EVT_MENU, self.kisiler_penceresi_ac, id=self.id_kisiler)
        self.Bind(wx.EVT_MENU, self.imza_penceresini_ac, id=self.id_imza)
        self.Bind(wx.EVT_MENU, self.epostalarda_ara_ac, id=self.id_ara)
        self.Bind(wx.EVT_MENU, self.posta_sil, id=self.id_sil)
        self.Bind(wx.EVT_MENU, self.posta_kalici_sil, id=self.id_kalici_sil)
        self.Bind(wx.EVT_MENU, self.listeyi_yenile, id=self.id_yenile)
        self.Bind(wx.EVT_MENU, self.yazi_tipi_sec, id=self.id_yazi_tipi)
        self.Bind(wx.EVT_MENU, self.yazi_boyutu_sec, id=self.id_yazi_boyutu)
        self.Bind(wx.EVT_MENU, self.yazi_stili_sec, id=self.id_yazi_stili)
        self.Bind(wx.EVT_MENU, self.metin_rengi_sec, id=self.id_metin_rengi)
        self.Bind(wx.EVT_MENU, self.arka_plan_rengi_sec, id=self.id_arka_plan_rengi)
        self.Bind(wx.EVT_MENU, self.sistem_renkleri_ayari_degistir, id=self.id_sistem_renkleri)
        self.Bind(wx.EVT_MENU, self.gorunumu_varsayilana_dondur, id=self.id_gorunum_sifirla)
        self.Bind(wx.EVT_MENU, self.eposta_sayisi_ayari_ac, id=self.id_eposta_sayisi)
        self.Bind(wx.EVT_MENU, self.onizleme_ayari_degistir, id=self.id_onizleme)
        self.Bind(wx.EVT_MENU, self.konusmalari_grupla_ayari_degistir, id=self.id_konusmalari_grupla)
        self.Bind(wx.EVT_MENU, self.silme_onayi_ayari_degistir, id=self.id_silme_onayi)
        self.Bind(wx.EVT_MENU, self.kalici_silme_onayi_ayari_degistir, id=self.id_kalici_silme_onayi)
        self.Bind(wx.EVT_MENU, self.adres_otomatik_kaydet_ayari_degistir, id=self.id_adres_otomatik_kaydet)
        self.Bind(wx.EVT_MENU, self.escape_kapat_ayari_degistir, id=self.id_escape_kapat)
        self.Bind(wx.EVT_MENU, self.bildirim_ayarlari_ac, id=self.id_bildirimler)
        self.Bind(wx.EVT_MENU, self.ayarlari_aktarma_penceresi_ac, id=self.id_ayarlari_aktar)
        self.Bind(wx.EVT_MENU, self.yerel_veritabanini_sifirla_menu, id=self.id_veritabani_sifirla)
        self.Bind(wx.EVT_MENU, self.cop_kutusunu_bosalt, id=self.id_cop_kutusunu_bosalt)
        self.Bind(wx.EVT_MENU, self.spami_bosalt, id=self.id_spami_bosalt)
        self.Bind(wx.EVT_MENU, self.gonderilenleri_cope_tasi, id=self.id_gonderilenleri_cope_tasi)
        self.Bind(wx.EVT_MENU, self.yardim_kilavuzunu_ac, id=self.id_yardim_kilavuzu)
        self.Bind(wx.EVT_MENU, self.ne_yeni_ac, id=self.id_ne_yeni)
        self.Bind(wx.EVT_MENU, self.hakkinda_ac, id=self.id_hakkinda)
        self.Bind(wx.EVT_MENU, self.oneri_gorus_ac, id=self.id_oneri_gorus)
        for menu_id, eklenti in self.diger_eklenti_menu_idleri.items():
            self.Bind(
                wx.EVT_MENU,
                lambda event, secili_eklenti=eklenti: self.diger_eklenti_ac(
                    secili_eklenti
                ),
                id=menu_id,
            )

        self.menuleri_olustur()

        self.SetAcceleratorTable(
            wx.AcceleratorTable(
                [
                    (wx.ACCEL_CTRL, ord("N"), self.id_yeni),
                    (wx.ACCEL_CTRL, ord("O"), self.id_eml_ac),
                    (wx.ACCEL_CTRL, ord("S"), self.id_kaydet),
                    (wx.ACCEL_CTRL, ord("F"), self.id_ara),
                    (wx.ACCEL_ALT, wx.WXK_F4, self.id_cikis),
                    (wx.ACCEL_ALT, ord("B"), self.id_hesap_baglan),
                    (wx.ACCEL_NORMAL, wx.WXK_F9, self.id_baglanti_denetle),
                    (wx.ACCEL_CTRL, ord("A"), self.id_tumunu),
                    (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("A"), self.id_kaldir),
                    (wx.ACCEL_ALT, ord("R"), self.id_arsiv),
                    (wx.ACCEL_ALT | wx.ACCEL_SHIFT, ord("R"), self.id_arsiv_yonet),
                    (wx.ACCEL_ALT, ord("K"), self.id_kisiler),
                    (wx.ACCEL_ALT, ord("I"), self.id_imza),
                    (wx.ACCEL_CTRL, ord("R"), self.id_yanitla),
                    (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("F"), self.id_ilet),
                    (wx.ACCEL_ALT, ord("S"), self.id_sil),
                    (wx.ACCEL_SHIFT, wx.WXK_DELETE, self.id_kalici_sil),
                    (wx.ACCEL_NORMAL, wx.WXK_F5, self.id_yenile),
                    (wx.ACCEL_NORMAL, wx.WXK_F1, self.id_yardim_kilavuzu),
                ]
            )
        )

        # Tek liste modeli: pencere içinde tek odaklanabilir liste vardır.
        # Hesap varsa açılışta Gelen Kutusu doğrudan e-posta görünümüne yüklenir.
        self.ana_panel = wx.Panel(self)
        self.ana_duzen = wx.BoxSizer(wx.VERTICAL)
        self.liste = wx.ListCtrl(self.ana_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.liste.SetName("E-posta klasörleri")
        self.liste.InsertColumn(0, "Klasörler", width=360)
        self.liste.InsertColumn(1, " ", width=430)
        self.liste.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.liste_ogesi_odaklandi)
        self.liste.Bind(wx.EVT_KEY_DOWN, self.tusa_basildi)
        self.liste.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.liste_ogesi_aktiflestirildi)
        self.liste.Bind(wx.EVT_CONTEXT_MENU, self.sag_tik_menusu)
        self.liste.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.sag_tik_menusu)
        self.ana_duzen.Add(self.liste, 1, wx.ALL | wx.EXPAND, 5)
        self.gorunum_uygula()

        self.ana_panel.SetSizer(self.ana_duzen)
        self.SetSize((1050, 590))
        self.CenterOnParent()
        if self.hesap_bilgisi_var_mi():
            self.yuklu_kategori = None
            # Pencere gösterilirken Windows ve NVDA'nın liste odağını yerleştirmesi
            # için ilk veri yüklemesini kısa süre ertele. Bu gecikme yalnızca ilk
            # açılışa aittir; klasör değiştirme ve sonraki yenilemeleri etkilemez.
            wx.CallLater(
                ILK_YUKLEME_GECIKMESI_MS,
                self.verileri_yukle_tetikle,
                None,
                "Gelen Kutusu",
                None,
                None,
                False,
            )
        else:
            self.hesap_bilgisi_eksik_goster()

    def listeye_odaklan(self):
        """Ana listeye güvenli biçimde odak verir."""
        try:
            if not pencere_kullanilabilir_mi(self):
                return False
            if hasattr(self, "liste") and pencere_kullanilabilir_mi(self.liste):
                try:
                    if self.liste.GetItemCount() > 0 and self.liste.GetFocusedItem() < 0:
                        self.liste.Focus(0)
                        self.liste.Select(0)
                        self.liste.EnsureVisible(0)
                except Exception:
                    pass
                self.liste.SetFocus()
                return True
        except Exception as e:
            hata_kaydet("Ana pencere odağı listeye verilemedi.", e)
        return False

    def one_getir_ve_odaklan(self):
        """Açık Engelsiz Mail penceresini öne getirir ve mevcut liste odağını korur."""
        try:
            if self.IsIconized():
                self.Iconize(False)
            if not self.IsShown():
                self.Show(True)
            try:
                self.Raise()
            except Exception:
                pass
            try:
                self.SetFocus()
            except Exception:
                pass

            def odakla():
                if pencere_kullanilabilir_mi(self):
                    self.listeye_odaklan()

            try:
                wx.CallAfter(odakla)
            except Exception as e:
                hata_kaydet("Açık pencere için odak dönüşü planlanamadı.", e)
            try:
                wx.CallLater(150, odakla)
            except Exception as e:
                hata_kaydet("Açık pencere için gecikmeli odak dönüşü planlanamadı.", e)
            return True
        except Exception as e:
            hata_kaydet("Açık Engelsiz Mail penceresi öne getirilemedi.", e)
            return False

    def menuleri_olustur(self):
        menu_bar = wx.MenuBar()

        dosya_menu = wx.Menu()
        dosya_menu.Append(self.id_yeni, "&Yeni E-posta Yaz	CTRL+N")
        dosya_menu.Append(self.id_eml_ac, "&Aç...\tCTRL+O")
        dosya_menu.Append(self.id_kaydet, "&Kaydet...\tCTRL+S")
        dosya_menu.AppendSeparator()
        dosya_menu.Append(self.id_cikis, "&Çıkış	Alt+F4")
        menu_bar.Append(dosya_menu, "&Dosya")

        hesap_menu = wx.Menu()
        hesap_menu.Append(self.id_hesap_baglan, "&Bağlan...\tAlt+B")
        hesap_menu.Append(self.id_baglanti_denetle, "Bağlantıyı &Denetle...\tF9")
        hesap_menu.Append(self.id_hesap_sil, "Hesap Bilgilerini &Sil")
        menu_bar.Append(hesap_menu, "&Hesap")

        eposta_menu = wx.Menu()
        eposta_menu.Append(self.id_ara, "&Ara...\tCtrl+F")
        eposta_menu.AppendSeparator()
        eposta_menu.Append(self.id_tumunu, "&Tümünü İşaretle\tCtrl+A")
        eposta_menu.Append(self.id_kaldir, "İşaretleri &Kaldır\tCtrl+Shift+A")
        eposta_menu.AppendSeparator()
        arsiv_menu = wx.Menu()
        arsiv_menu.Append(self.id_arsiv, "A&rşive Gönder\tAlt+R")
        arsiv_menu.Append(self.id_arsiv_yonet, "Arşiv Klasörlerini &Yönet...\tAlt+Shift+R")
        eposta_menu.AppendSubMenu(arsiv_menu, "A&rşiv")
        eposta_menu.Append(self.id_kisiler, "Kişil&er...\tAlt+K")
        eposta_menu.Append(self.id_imza, "İm&za...\tAlt+I")
        sil_menu = wx.Menu()
        sil_menu.Append(self.id_sil, "&Sil\tAlt+S")
        sil_menu.Append(self.id_kalici_sil, "&Kalıcı Sil\tShift+Delete")
        eposta_menu.AppendSubMenu(sil_menu, "&Sil")
        eposta_menu.AppendSeparator()
        eposta_menu.Append(self.id_yenile, "&Yenile\tF5")
        menu_bar.Append(eposta_menu, "&E-posta")

        gorunum_menu = wx.Menu()
        gorunum_menu.Append(self.id_yazi_tipi, "&Yazı Tipi...")
        gorunum_menu.Append(self.id_yazi_boyutu, "Yazı &Boyutu...")
        gorunum_menu.Append(self.id_yazi_stili, "Yazı &Stili...")
        gorunum_menu.AppendSeparator()
        gorunum_menu.Append(self.id_metin_rengi, "&Metin Rengi...")
        gorunum_menu.Append(self.id_arka_plan_rengi, "&Arka Plan Rengi...")
        sistem_renkleri_item = gorunum_menu.AppendCheckItem(self.id_sistem_renkleri, "Sistem &Renklerini Kullan")
        try:
            sistem_renkleri_item.Check(gorunum_ayarlari_yukle().get(GORUNUM_SISTEM_RENKLERI_ALANI, False))
        except Exception as e:
            hata_kaydet("Sistem renkleri menü durumu okunamadı.", e)
        gorunum_menu.AppendSeparator()
        gorunum_menu.Append(self.id_gorunum_sifirla, "&Varsayılan Görünüme Dön")
        menu_bar.Append(gorunum_menu, "&Görünüm")

        ayarlar_menu = wx.Menu()
        ayarlar_menu.Append(self.id_eposta_sayisi, "&E-posta Sayısı...")
        ayarlar_menu.Append(self.id_bildirimler, "&Bildirimler...")
        onizleme_item = ayarlar_menu.AppendCheckItem(self.id_onizleme, "Ön İ&zleme")
        try:
            onizleme_item.Check(onizleme_ayari_yukle())
        except Exception:
            pass
        konusma_item = ayarlar_menu.AppendCheckItem(self.id_konusmalari_grupla, "&Konuşmaları Grupla")
        try:
            konusma_item.Check(konusmalari_grupla_ayari_yukle())
        except Exception:
            pass
        sil_ayar_menu = wx.Menu()
        silme_onayi_item = sil_ayar_menu.AppendCheckItem(self.id_silme_onayi, "Normal silmeden önce onay i&ste")
        self.silme_onayi_menu_item = silme_onayi_item
        try:
            silme_onayi_item.Check(silme_onayi_ayari_yukle())
        except Exception:
            pass
        kalici_silme_onayi_item = sil_ayar_menu.AppendCheckItem(self.id_kalici_silme_onayi, "&Kalıcı silmeden önce onay iste")
        self.kalici_silme_onayi_menu_item = kalici_silme_onayi_item
        try:
            kalici_silme_onayi_item.Check(kalici_silme_onayi_ayari_yukle())
        except Exception:
            pass
        ayarlar_menu.AppendSubMenu(sil_ayar_menu, "&Sil")
        adres_kaydet_item = ayarlar_menu.AppendCheckItem(self.id_adres_otomatik_kaydet, "Gönderilen e-posta adreslerini oto&matik kaydet")
        try:
            adres_kaydet_item.Check(adres_otomatik_kaydet_ayari_yukle())
        except Exception:
            pass
        escape_kapat_item = ayarlar_menu.AppendCheckItem(self.id_escape_kapat, "Escape tuşu ile eklentiyi kapa&t")
        try:
            escape_kapat_item.Check(escape_kapat_ayari_yukle())
        except Exception:
            pass
        ayarlar_menu.Append(self.id_ayarlari_aktar, "İçe / &Dışa Aktar...")
        ayarlar_menu.AppendSeparator()
        ayarlar_menu.Append(self.id_veritabani_sifirla, "&Yerel Veritabanını Sıfırla...")
        menu_bar.Append(ayarlar_menu, "&Ayarlar")

        yardim_menu = wx.Menu()
        yardim_menu.Append(self.id_yardim_kilavuzu, "&Yardım Kılavuzu\tF1")
        yardim_menu.Append(self.id_ne_yeni, "Ye&nilikler")
        diger_eklentiler_menu = wx.Menu()
        for menu_id, eklenti in self.diger_eklenti_menu_idleri.items():
            diger_eklentiler_menu.Append(menu_id, eklenti.ad)
        yardim_menu.AppendSubMenu(
            diger_eklentiler_menu,
            "Geliştiricinin Diğer &Eklentileri",
        )
        yardim_menu.AppendSeparator()
        yardim_menu.Append(self.id_hakkinda, "&Hakkında")
        yardim_menu.Append(self.id_oneri_gorus, "Öneri ve &Görüş Bildir...")
        menu_bar.Append(yardim_menu, "&Yardım")

        self.SetMenuBar(menu_bar)
        self.hesap_menusu_durumunu_guncelle()

    def hesap_menusu_durumunu_guncelle(self):
        """Kayıtlı hesap durumuna göre hesap menüsündeki işlemleri günceller."""
        try:
            menu_bar = self.GetMenuBar()
            if menu_bar is None:
                return
            menu_bar.Enable(self.id_hesap_sil, self.hesap_bilgisi_var_mi())
        except Exception as e:
            hata_kaydet("Hesap menüsü durumu güncellenemedi.", e)

    def silme_onayi_menu_durumunu_guncelle(self, normal=None, kalici=None):
        """Silme onayı ayarları değiştiğinde açık menü işaretlerini bellekte de günceller."""
        try:
            if normal is None:
                normal = silme_onayi_ayari_yukle()
            if kalici is None:
                kalici = kalici_silme_onayi_ayari_yukle()
            normal = bool(normal)
            kalici = bool(kalici)
            menu_bar = self.GetMenuBar()
            if menu_bar is not None:
                try:
                    menu_bar.Check(self.id_silme_onayi, normal)
                    menu_bar.Check(self.id_kalici_silme_onayi, kalici)
                except Exception:
                    pass
            try:
                self.silme_onayi_menu_item.Check(normal)
            except Exception:
                pass
            try:
                self.kalici_silme_onayi_menu_item.Check(kalici)
            except Exception:
                pass
        except Exception as e:
            hata_kaydet("Silme onayı menü durumu güncellenemedi.", e)

    def kisiler_penceresi_ac(self, event=None):
        pencere = KisilerPenceresi(self)
        guvenli_modal_goster(pencere, self.liste, self)

    def imza_penceresini_ac(self, event=None):
        mevcut_imza = imza_yukle()
        pencere = ImzaPenceresi(self, "İmza", mevcut_imza)
        try:
            sonuc = pencere.ShowModal()
            if sonuc == wx.ID_OK:
                if not imza_kaydet(pencere.imzayi_al()):
                    ui.message("İmza kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                    return
                ui.message("İmza kaydedildi.")
            elif sonuc == IMZA_SIL_ID:
                onay = gui.messageBox(
                    "Kayıtlı imzayı silmek istediğinizden emin misiniz?",
                    "İmzayı Sil",
                    wx.YES_NO | wx.ICON_QUESTION,
                    self,
                )
                if onay != wx.YES:
                    return
                if not imza_kaldir():
                    ui.message("İmza silinemedi. Lütfen dosya izinlerini kontrol edin.")
                    return
                ui.message("İmza silindi.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("İmza işlemi tamamlanamadı.", e)
            ui.message("İmza işlemi sırasında bir hata oluştu.")
        finally:
            pencere.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def epostalarda_ara_ac(self, event=None):
        if not self.hesap_bilgisi_var_mi():
            ui.message("Arama yapmak için önce Gmail hesabınızı bağlayın.")
            return
        pencere = EpostalardaAraPenceresi(self, self)
        guvenli_modal_goster(pencere, self.liste, self)

    def arama_sonucu_klasorune_git(self, imap_klasoru, uid):
        kategori = self.kategori_adini_klasorden_bul(imap_klasoru)
        if not kategori:
            ui.message("Arama sonucunun bulunduğu klasör açılamadı.")
            return
        self.secili_kategori = kategori
        self.verileri_yukle_tetikle(
            "E-postanın bulunduğu klasör açılıyor...",
            kategori_adi=kategori,
            korunan_mail_id=str(uid or ""),
        )

    def gorunum_uygula(self):
        """Ana pencere denetimlerine görünüm ayarlarını uygular."""
        gorunum_denetimlerine_uygula(self.liste)
        try:
            self.ana_panel.Layout()
            self.Layout()
        except Exception:
            pass

    def yazi_tipi_sec(self, event=None):
        mevcut_ayar = gorunum_ayarlari_yukle()
        mevcut_yazi_tipi = mevcut_ayar.get(GORUNUM_YAZI_TIPI_ALANI, "")
        if not mevcut_yazi_tipi:
            try:
                mevcut_yazi_tipi = self.liste.GetFont().GetFaceName()
            except Exception:
                mevcut_yazi_tipi = ""

        try:
            fontlar = sorted(set(wx.FontEnumerator.GetFacenames()), key=lambda x: x.lower())
        except Exception:
            fontlar = []
        if not fontlar:
            fontlar = ["Arial", "Calibri", "Courier New", "Tahoma", "Times New Roman", "Verdana"]
        if mevcut_yazi_tipi and mevcut_yazi_tipi not in fontlar:
            fontlar.insert(0, mevcut_yazi_tipi)

        dlg = wx.SingleChoiceDialog(
            self,
            "Yazı tipini seçin:",
            "Yazı Tipi",
            fontlar,
        )
        try:
            if mevcut_yazi_tipi in fontlar:
                dlg.SetSelection(fontlar.index(mevcut_yazi_tipi))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_tipi = dlg.GetStringSelection().strip()
            if not yazi_tipi:
                ui.message("Yazı tipi seçilemedi.")
                self.liste.SetFocus()
                return
            if not gorunum_ayarlari_kaydet(yazi_tipi=yazi_tipi):
                ui.message("Yazı tipi ayarı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.gorunum_uygula()
            ui.message(f"Yazı tipi {yazi_tipi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı tipi seçilemedi.", e)
            ui.message("Yazı tipi seçilemedi.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def yazi_boyutu_sec(self, event=None):
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_YAZI_BOYUTU_ALANI, 0)
        if not mevcut:
            try:
                mevcut = self.liste.GetFont().GetPointSize()
            except Exception:
                mevcut = 10
        dlg = wx.TextEntryDialog(
            self,
            f"Yazı tipi boyutunu {GORUNUM_YAZI_BOYUTU_EN_AZ} ile {GORUNUM_YAZI_BOYUTU_EN_COK} arasında yazın:",
            "Yazı Boyutu",
            str(mevcut or 10),
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_boyutu = int(str(dlg.GetValue()).strip())
            if not gorunum_ayarlari_kaydet(yazi_boyutu=yazi_boyutu):
                ui.message("Yazı tipi boyutu ayarı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.gorunum_uygula()
            ui.message(f"Yazı tipi boyutu {yazi_boyutu} olarak ayarlandı.")
        except ValueError:
            ui.message("Yazı tipi boyutu yalnızca rakamlardan oluşmalıdır.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı tipi boyutu ayarlanamadı.", e)
            ui.message("Yazı tipi boyutu ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def yazi_stili_sec(self, event=None):
        secenekler = list(GORUNUM_YAZI_STILI_SECENEKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_YAZI_STILI_ALANI, "") or "Normal"
        dlg = wx.SingleChoiceDialog(
            self,
            "Yazı stilini seçin:",
            "Yazı Stili",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            yazi_stili = dlg.GetStringSelection().strip()
            if not gorunum_ayarlari_kaydet(yazi_stili=yazi_stili):
                ui.message("Yazı stili ayarı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.gorunum_uygula()
            ui.message(f"Yazı stili {yazi_stili} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Yazı stili ayarlanamadı.", e)
            ui.message("Yazı stili ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def metin_rengi_sec(self, event=None):
        secenekler = list(GORUNUM_METIN_RENKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_METIN_RENGI_ALANI, "") or "Siyah"
        dlg = wx.SingleChoiceDialog(
            self,
            "Metin rengini seçin:",
            "Metin Rengi",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            metin_rengi = dlg.GetStringSelection().strip()
            if not gorunum_ayarlari_kaydet(metin_rengi=metin_rengi):
                ui.message("Metin rengi ayarı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.gorunum_uygula()
            ui.message(f"Metin rengi {metin_rengi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Metin rengi ayarlanamadı.", e)
            ui.message("Metin rengi ayarlanamadı.")
        finally:
            dlg.Destroy()
            odagi_listeye_guvenli_dondur(self, self.liste)

    def arka_plan_rengi_sec(self, event=None):
        secenekler = list(GORUNUM_ARKA_PLAN_RENKLERI.keys())
        mevcut = gorunum_ayarlari_yukle().get(GORUNUM_ARKA_PLAN_RENGI_ALANI, "") or "Beyaz"
        dlg = wx.SingleChoiceDialog(
            self,
            "Arka plan rengini seçin:",
            "Arka Plan Rengi",
            secenekler,
        )
        try:
            if mevcut in secenekler:
                dlg.SetSelection(secenekler.index(mevcut))
            if dlg.ShowModal() != wx.ID_OK:
                self.liste.SetFocus()
                return
            arka_plan_rengi = dlg.GetStringSelection().strip()
            if not gorunum_ayarlari_kaydet(arka_plan_rengi=arka_plan_rengi):
                ui.message("Arka plan rengi ayarı kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
                return
            self.gorunum_uygula()
            ui.message(f"Arka plan rengi {arka_plan_rengi} olarak ayarlandı.")
        except MailHatasi as e:
            ui.message(str(e))
        except Exception as e:
            hata_kaydet("Arka plan rengi ayarlanamadı.", e)
            ui.message("Arka plan rengi ayarlanamadı.")
        finally:
            dlg.Destroy()
            wx.CallAfter(self.liste.SetFocus)

    def sistem_renkleri_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not gorunum_ayarlari_yukle().get(GORUNUM_SISTEM_RENKLERI_ALANI, False)
            if gorunum_ayarlari_kaydet(sistem_renkleri=etkin):
                self.gorunum_uygula()
                ui.message("Sistem renkleri kullanılacak." if etkin else "Özel renk ayarları kullanılacak.")
            else:
                ui.message("Sistem renkleri ayarı kaydedilemedi.")
        except Exception as e:
            hata_kaydet("Sistem renkleri ayarı değiştirilemedi.", e)
            ui.message("Sistem renkleri ayarı değiştirilemedi.")
        wx.CallAfter(self.liste.SetFocus)

    def gorunumu_varsayilana_dondur(self, event=None):
        if gorunum_ayarlari_sifirla():
            self.gorunum_uygula()
            ui.message("Yazı tipi, yazı tipi boyutu, yazı stili, metin rengi ve arka plan rengi varsayılana döndürüldü.")
        else:
            ui.message("Görünüm ayarları sıfırlanamadı. Lütfen dosya izinlerini kontrol edin.")
        wx.CallAfter(self.liste.SetFocus)

    def hesap_bilgisi_var_mi(self):
        ayarlar = ayarlari_yukle()
        return bool(ayarlar.get("eposta") and ayarlar.get("sifre"))

    def hesap_bilgisi_eksik_goster(self):
        self.hesap_menusu_durumunu_guncelle()
        self.yukleniyor = False
        self.mailler = []
        self.isaretliler.clear()
        try:
            self.liste.DeleteAllItems()
        except Exception as e:
            hata_kaydet("Hesap bilgisi eksik durumunda liste temizlenemedi.", e)
        wx.CallAfter(self.liste.SetFocus)

    def hesap_bilgisi_eksik_uyarisi_goster(self):
        """Hesap yokken tek karar penceresini gösterir.

        Eski Tamam düğmeli hesap-yok uyarısı kaldırıldı. Hesap ekleme kararı
        artık yalnızca Evet/Hayır penceresiyle alınır.
        """
        if getattr(self, "_hesap_bilgisi_eksik_uyarisi_gosterildi", False):
            return
        if self.hesap_bilgisi_var_mi():
            return
        self._hesap_bilgisi_eksik_uyarisi_gosterildi = True
        try:
            sonuc = gui.messageBox(
                "Hesap bilgisi bulunamadı.\n"
                "Şimdi bir hesap eklemek ister misiniz?",
                "Engelsiz Mail",
                wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            if sonuc == wx.YES and not self.hesap_bilgisi_var_mi() and pencere_kullanilabilir_mi(self):
                wx.CallAfter(self.hesap_baglan)
        except Exception as e:
            hata_kaydet("Hesap bilgisi eksik uyarısı gösterilemedi.", e)

    def hesap_bilgilerini_sil(self, event=None):
        if not self.hesap_bilgisi_var_mi():
            self.hesap_menusu_durumunu_guncelle()
            ui.message("Silinecek kayıtlı hesap bilgisi yok.")
            return
        sonuc = gui.messageBox(
            "Kayıtlı hesap bilgilerini silmek istediğinizden emin misiniz?",
            "Hesap Bilgilerini Sil",
            wx.YES_NO | wx.ICON_QUESTION,
            self,
        )
        if sonuc != wx.YES:
            return
        try:
            if not kayitli_hesap_bilgilerini_sil():
                ui.message("Hesap bilgileri silinemedi. Lütfen dosya izinlerini kontrol edin.")
                return

            def silme_sonrasi_temizle():
                gui.messageBox(
                    "Hesap bilgileriniz silinmiştir.",
                    "Hesap Bilgileri Silindi",
                    wx.OK | wx.ICON_INFORMATION,
                    self,
                )
                klasor_sayisi_onbellegi_temizle()
                self._klasor_sayisi_cache = {}
                self._sistem_klasor_sayisi_acilista_guncellendi = False
                self.mailler = []
                self.isaretliler.clear()
                self.hesap_menusu_durumunu_guncelle()
                self.hesap_bilgisi_eksik_goster()

            mesaj_soyle_ve_sonra_calistir(
                "Hesap bilgileriniz silinmiştir.",
                silme_sonrasi_temizle,
                ad="Hesap bilgilerini silme sonrası temizliği",
            )
        except Exception as e:
            hata_kaydet("Hesap bilgileri silinemedi.", e)
            ui.message("Hesap bilgileri silinirken bir hata oluştu.")

    def baglantiyi_denetle_menu(self, event=None):
        if getattr(self, "_baglanti_denetleniyor", False):
            ui.message("Bağlantı denetimi zaten devam ediyor. Lütfen bekleyin.")
            return
        self._baglanti_denetleniyor = True
        mesaj_soyle_ve_sonra_calistir(
            "Bağlantı denetimi başlatıldı. Lütfen bekleyin.",
            lambda: arka_planda_calistir(self._baglantiyi_denetle_thread),
            ad="Bağlantı denetimi başlatma",
        )

    def _baglantiyi_denetle_thread(self):
        try:
            basarili, rapor = baglanti_denetimini_yap()
        except Exception as e:
            hata_kaydet("Bağlantı denetimi tamamlanamadı.", e)
            basarili = False
            rapor = "Bağlantı denetimi tamamlanamadı.\n\n" + baglanti_hatasi_kullanici_mesaji(e)
        guvenli_call_after(self, self._baglanti_denetimi_goster, basarili, rapor)

    def _baglanti_denetimi_goster(self, basarili, rapor):
        self._baglanti_denetleniyor = False
        pencere = BaglantiDenetimSonucPenceresi(self, basarili, rapor)
        guvenli_modal_goster(pencere, self.liste, self)

    def hesap_baglan(self, event=None):
        pencere = AyarlarPenceresi(self)
        sonuc = guvenli_modal_goster(pencere, self.liste, self)
        if sonuc == wx.ID_OK and pencere_kullanilabilir_mi(self):
            self.hesap_menusu_durumunu_guncelle()
            self._klasor_sayisi_cache = {}
            self._sistem_klasor_sayisi_acilista_guncellendi = False
            self._klasor_sayisi_onbellegi_yukle()
            self.verileri_yukle_tetikle(None, kategori_adi=self.secili_kategori)

    def eposta_sayisi_ayari_ac(self, event=None):
        pencere = MesajSayisiPenceresi(self)
        sonuc = guvenli_modal_goster(pencere, self.liste, self)
        if sonuc == wx.ID_OK and pencere_kullanilabilir_mi(self) and self.hesap_bilgisi_var_mi():
            self.verileri_yukle_tetikle("E-postalar yeni sayıya göre yükleniyor...", kategori_adi=self.secili_kategori)

    def silme_onayi_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not silme_onayi_ayari_yukle()
        except Exception:
            etkin = not silme_onayi_ayari_yukle()

        if silme_onayi_ayari_kaydet(etkin):
            self.silme_onayi_menu_durumunu_guncelle(normal=etkin)
            bildirim_soyle("Silerken onay sorulacak." if etkin else "Silerken onay sorulmayacak.", 350)
        else:
            bildirim_soyle("Silme onayı ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def kalici_silme_onayi_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not kalici_silme_onayi_ayari_yukle()
        except Exception:
            etkin = not kalici_silme_onayi_ayari_yukle()

        if kalici_silme_onayi_ayari_kaydet(etkin):
            self.silme_onayi_menu_durumunu_guncelle(kalici=etkin)
            bildirim_soyle("Kalıcı silerken onay sorulacak." if etkin else "Kalıcı silerken onay sorulmayacak.", 350)
        else:
            bildirim_soyle("Kalıcı silme onayı ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def adres_otomatik_kaydet_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not adres_otomatik_kaydet_ayari_yukle()
        except Exception:
            etkin = not adres_otomatik_kaydet_ayari_yukle()

        if adres_otomatik_kaydet_ayari_kaydet(etkin):
            bildirim_soyle("Gönderilen adresler otomatik kaydedilecek." if etkin else "Gönderilen adresler otomatik kaydedilmeyecek.", 350)
        else:
            bildirim_soyle("Adres otomatik kaydetme ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def escape_kapat_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not escape_kapat_ayari_yukle()
        except Exception:
            etkin = not escape_kapat_ayari_yukle()

        if escape_kapat_ayari_kaydet(etkin):
            bildirim_soyle("Escape tuşu eklentiyi kapatacak." if etkin else "Escape tuşu eklentiyi kapatmayacak.", 350)
        else:
            bildirim_soyle("Escape ile kapatma ayarı kaydedilemedi.", 350)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def bildirim_ayarlari_ac(self, event=None):
        pencere = BildirimAyarlariPenceresi(self, self._bildirim_yenile_callback)
        guvenli_modal_goster(pencere, self.liste, self)

    def ayarlari_aktarma_penceresi_ac(self, event=None):
        pencere = AyarlariAktarmaPenceresi(self)
        sonuc = guvenli_modal_goster(pencere, self.liste, self)
        if sonuc == wx.ID_OK and pencere_kullanilabilir_mi(self):
            self.hesap_menusu_durumunu_guncelle()

    def onizleme_ayari_degistir(self, event=None):
        try:
            etkin = bool(event.IsChecked()) if event is not None and hasattr(event, "IsChecked") else not onizleme_ayari_yukle()
        except Exception:
            etkin = not onizleme_ayari_yukle()

        if onizleme_ayari_kaydet(etkin):
            if etkin:
                if self.hesap_bilgisi_var_mi():
                    kategori_adi = self.secili_kategori
                    sonraki_islem = lambda: self.onizleme_etkinlestirildikten_sonra(kategori_adi)
                else:
                    sonraki_islem = lambda: None
                mesaj_soyle_ve_sonra_calistir(
                    "Ön izleme etkinleştirildi.",
                    sonraki_islem,
                    ad="Ön izlemeyi etkinleştirme",
                )
            else:
                mesaj_soyle_ve_sonra_calistir(
                    "Ön izleme kapatıldı.",
                    self.onizleme_kapatildiktan_sonra,
                    ad="Ön izlemeyi kapatma",
                )
        else:
            try:
                self.GetMenuBar().Check(self.id_onizleme, onizleme_ayari_yukle())
            except Exception:
                pass
            bildirim_soyle("Ön izleme ayarı kaydedilemedi.", 500)

    def onizleme_etkinlestirildikten_sonra(self, kategori_adi):
        if not pencere_kullanilabilir_mi(self) or not onizleme_ayari_yukle():
            return
        self.verileri_yukle_tetikle(
            "Ön izleme hazırlanıyor...",
            kategori_adi,
            None,
            None,
            False,
        )

    def onizleme_kapatildiktan_sonra(self):
        if not pencere_kullanilabilir_mi(self) or onizleme_ayari_yukle():
            return
        try:
            # Ön izleme konu satırına eklendiği için kapatılınca mevcut liste
            # yeniden çizilmelidir. Aksi hâlde eski ön izleme metni satırda kalır.
            self.arayuzu_yenile(self.mailler)
        except Exception as e:
            hata_kaydet("Ön izleme kapatıldıktan sonra liste yenilenemedi.", e)

    def konusmalari_grupla_ayari_degistir(self, event=None):
        etkin = bool(event.IsChecked()) if event is not None else not konusmalari_grupla_ayari_yukle()
        if not konusmalari_grupla_ayari_kaydet(etkin):
            try:
                self.GetMenuBar().Check(self.id_konusmalari_grupla, not etkin)
            except Exception:
                pass
            bildirim_soyle("Konuşma gruplama ayarı kaydedilemedi.", 400)
            return
        bildirim_soyle(
            "Konuşmalar gruplanacak." if etkin else "E-postalar ayrı ayrı gösterilecek.",
            350,
        )
        if getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_EPOSTA:
            self.verileri_yukle_tetikle(
                "Konuşmalar hazırlanıyor..." if etkin else "E-postalar hazırlanıyor...",
                kategori_adi=self.secili_kategori,
            )
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def gorunen_onizleme_uidlerini_al(self, mailler):
        sonuc = []
        gorulen = set()
        for mesaj in mailler or []:
            for uid in mesaj_uidlerini_al(mesaj):
                uid = str(uid or "").strip()
                if not uid.isdigit() or int(uid) <= 0 or uid in gorulen:
                    continue
                gorulen.add(uid)
                sonuc.append(uid)
        return sonuc

    def onizleme_onbellegini_hazirla(
        self,
        kategori_adi,
        kaynak_klasor,
        eksik_uidler,
        yukleme_islem_no=None,
    ):
        ayarlar = ayarlari_yukle()
        eposta = str(ayarlar.get("eposta", "") or "").strip()
        kaynak_klasor = str(kaynak_klasor or "").strip()
        eksik_uidler = [str(uid) for uid in eksik_uidler or [] if str(uid).isdigit()]
        if not eposta or not kaynak_klasor or not eksik_uidler:
            return

        def iptal_edildi_mi():
            if not pencere_kullanilabilir_mi(self) or not onizleme_ayari_yukle():
                return True
            if yukleme_islem_no is not None:
                return yukleme_islem_no != getattr(self, "_yukleme_islem_no", None)
            return False

        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _secim = imap.select(kaynak_klasor, readonly=True)
                imap_ok_mu(tip, "Ön izleme için klasör açılamadı.")
                sonuc = klasor_onizlemelerini_senkronize_et(
                    imap,
                    eposta,
                    kaynak_klasor,
                    sunucu_uidleri=eksik_uidler,
                    iptal_edildi_mi=iptal_edildi_mi,
                    kilidi_bekle=True,
                )
            if sonuc.get("iptal_edildi"):
                return
            # Görev kilidi beklerken başka bir eşitleme ön izlemeyi hazırlamış
            # olabilir. Kalan eksik sayısı azaldıysa bu görev kayıt yapmamış olsa
            # bile açık listenin yenilenmesi gerekir.
            kalan_uidler = onizlemesi_eksik_uidleri_al(
                eposta,
                kaynak_klasor,
                eksik_uidler,
            )
            if sonuc.get("kaydedilen") or len(kalan_uidler) < len(eksik_uidler):
                guvenli_call_after(
                    self,
                    self.onizleme_onbellegi_hazirlandi,
                    kategori_adi,
                    yukleme_islem_no,
                )
        except Exception as e:
            hata_kaydet("Ön izleme önbelleği hazırlanamadı.", e)

    def onizleme_onbellegi_hazirlandi(self, kategori_adi, yukleme_islem_no=None):
        if (
            self.secili_kategori == kategori_adi
            and onizleme_ayari_yukle()
            and (
                yukleme_islem_no is None
                or yukleme_islem_no == getattr(self, "_yukleme_islem_no", None)
            )
        ):
            self.yenilemeyi_gecikmeli_tetikle(None, kategori_adi, None, None, True)

    def yardim_kilavuzunu_ac(self, event=None):
        yardim_belgesini_ac()

    def ne_yeni_ac(self, event=None):
        ne_yeni_belgesini_ac()

    def hakkinda_ac(self, event=None):
        hakkinda_penceresini_ac(self)
        try:
            self.liste.SetFocus()
        except Exception:
            pass

    def oneri_gorus_ac(self, event=None):
        pencere = OneriGorusPenceresi(self)
        guvenli_modal_goster(pencere, self.liste, self)

    def diger_eklenti_ac(self, eklenti):
        pencere = DigerEklentiPenceresi(self, eklenti)
        guvenli_modal_goster(pencere, self.liste, self)

    def pencereyi_kapat(self, event=None):
        if event is not None and hasattr(event, "CanVeto"):
            event.Skip()
            return
        self.Close()

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
            for zamanlayici_adi in (
                "_gonderim_sonrasi_esitleme_timer",
                "_gonderim_sonrasi_yeniden_deneme_timer",
            ):
                zamanlayici = getattr(self, zamanlayici_adi, None)
                try:
                    if zamanlayici is not None:
                        zamanlayici.Stop()
                except Exception as e:
                    hata_kaydet("Gönderim sonrası eşitleme zamanlayıcısı durdurulamadı.", e)
                setattr(self, zamanlayici_adi, None)
            arka_plan_gorevlerini_gecersiz_kil(self)
            self._yukleme_islem_no += 1
        event.Skip()

    def aktif_klasor(self):
        return self.klasor_haritasi.get(self.secili_kategori, "INBOX")

    def kategori_adini_klasorden_bul(self, klasor):
        return gmail_kategori_adini_klasorden_bul(klasor, self.klasor_haritasi, self.secili_kategori, self.aktif_klasor())

    def gmail_etiket_ifadesi(self, kategori_adi=None, klasor=None):
        return gmail_etiket_ifadesi_olustur(kategori_adi, klasor, self.klasor_haritasi, self.secili_kategori, self.aktif_klasor())

    def kaynak_etiketi_kaldirilabilir_mi(self, kaynak_klasor, kaynak_kategori=None):
        return gmail_kaynak_etiketi_kaldirilabilir_mi(kaynak_klasor, self.klasor_haritasi, self.ozel_klasorler, kaynak_kategori, self.secili_kategori)

    def gmail_etiket_ekle_ve_kaynak_kaldir(self, imap, uidler, hedef_etiket, kaynak_klasor, hedef_hata, kaynak_hata):
        return gmail_etiket_ekle_ve_kaynak_kaldir_akisi(
            imap,
            uidler,
            hedef_etiket,
            kaynak_klasor,
            hedef_hata,
            kaynak_hata,
            self.klasor_haritasi,
            self.ozel_klasorler,
            self.secili_kategori,
        )

    def okunmadi_etiketini_kaldir(self, metin):
        return okunmadi_etiket_metnini_kaldir(metin)

    def cop_klasoru_mu(self, klasor):
        return gmail_cop_klasoru_mu(klasor, self.klasor_haritasi)

    def tum_postalar_klasoru_mu(self, klasor):
        return gmail_tum_postalar_klasoru_mu(klasor, self.klasor_haritasi)

    def taslak_klasoru_mu(self, klasor):
        return gmail_taslak_klasoru_mu(klasor, self.klasor_haritasi, self.secili_kategori)

    def spam_klasoru_mu(self, klasor):
        return gmail_spam_klasoru_mu(klasor, self.klasor_haritasi, self.secili_kategori)

    def taslak_silme_onayi_al(self, adet=1):
        return delete_actions.taslak_silme_onayi_al(self, adet)

    def tum_postalar_arsiv_onayi_al(self, adet):
        return archive_actions.tum_postalar_arsiv_onayi_al(adet)

    def tum_postalar_tasima_onayi_al(self, adet, hedef_adi):
        hedef_adi = str(hedef_adi or "").strip() or "hedef"
        soru = (
            f"Seçili e-postaya '{hedef_adi}' etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-posta burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} e-postaya '{hedef_adi}' etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-postalar burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
        )
        return gui.messageBox(soru, "Tüm Postalar Taşıma Uyarısı", wx.YES_NO | wx.ICON_WARNING) == wx.YES

    def mail_konusunu_bul(self, mail_id):
        return delete_actions.mail_konusunu_bul(self, mail_id)

    def konu_ifadesi(self, konu):
        return delete_actions.konu_ifadesi(konu)

    def silme_onayi_al(self, adet, kaynak_klasor, konu=None):
        return delete_actions.silme_onayi_al(self, adet, kaynak_klasor, konu)

    def kalici_silme_onayi_al(self, adet, kaynak_klasor, konu=None):
        return delete_actions.kalici_silme_onayi_al(self, adet, kaynak_klasor, konu)

    def liste_odak_bilgisi_al(self):
        indeks = -1
        mail_id = None
        try:
            indeks = self.liste.GetFocusedItem()
        except Exception:
            indeks = -1
        if indeks != -1 and indeks < len(self.mailler):
            mail_id = str(self.mailler[indeks].get("id", ""))
        return mail_id, indeks

    def liste_secim_ver(self, indeks, odak_ver=True):
        try:
            oge_sayisi = int(self.liste.GetItemCount())
        except Exception:
            oge_sayisi = 0
        if oge_sayisi <= 0:
            if odak_ver:
                wx.CallAfter(self.liste.SetFocus)
            return
        indeks = max(0, min(int(indeks), oge_sayisi - 1))
        try:
            self.liste.SelectAll(False)
        except Exception:
            pass
        try:
            self.liste.Focus(indeks)
            self.liste.Select(indeks)
            self.liste.EnsureVisible(indeks)
        except Exception:
            pass
        if odak_ver:
            wx.CallAfter(self.liste.SetFocus)

    def verileri_yukle_tetikle(self, liste_mesaji=None, kategori_adi=None, korunan_mail_id=None, korunan_indeks=None, sessiz=False):
        if not pencere_kullanilabilir_mi(self):
            return
        if self.yukleniyor:
            if sessiz:
                wx.CallLater(
                    YENILEME_GECIKMESI_MS,
                    self.verileri_yukle_tetikle,
                    liste_mesaji,
                    kategori_adi,
                    korunan_mail_id,
                    korunan_indeks,
                    sessiz,
                )
            else:
                ui.message("Devam eden işlem tamamlanınca e-posta listesi otomatik yenilenecek.")
                wx.CallLater(
                    YENILEME_GECIKMESI_MS,
                    self.verileri_yukle_tetikle,
                    liste_mesaji,
                    kategori_adi,
                    korunan_mail_id,
                    korunan_indeks,
                    True,
                )
            return

        hedef_kategori = kategori_adi or self.secili_kategori

        if (
            korunan_mail_id is None
            and korunan_indeks is None
            and hedef_kategori == self.secili_kategori
            and getattr(self, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_EPOSTA
        ):
            korunan_mail_id, korunan_indeks = self.liste_odak_bilgisi_al()

        self._yenileme_hedef_mail_id = str(korunan_mail_id) if korunan_mail_id else None
        self._yenileme_hedef_indeks = korunan_indeks if korunan_indeks is not None and korunan_indeks != -1 else None
        self._yenileme_sessiz = bool(sessiz)
        self._son_yukleme_hatasi = False

        self.secili_kategori = hedef_kategori
        self.eposta_modunu_hazirla()

        if liste_mesaji and not sessiz:
            self.liste_bilgi_satiri_goster(liste_mesaji)

        kaynak_klasor = self.klasor_haritasi.get(hedef_kategori, self.aktif_klasor())
        try:
            ayarlar = ayarlari_yukle()
            mesaj_sayisi = mesaj_sayisini_duzenle(
                ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)
            )
            yerel_mailler = yerel_eposta_listesi_hazirla(
                ayarlar, hedef_kategori, kaynak_klasor, mesaj_sayisi
            )
            if yerel_mailler is not None:
                self.yerel_eposta_listesini_goster(yerel_mailler, hedef_kategori)
        except Exception as e:
            hata_kaydet("Yerel e-posta listesi gösterilemedi.", e)

        self.yukleniyor = True

        self._yukleme_islem_no += 1
        yukleme_islem_no = self._yukleme_islem_no
        arka_planda_calistir(self.verileri_yukle, hedef_kategori, kaynak_klasor, yukleme_islem_no)

    def yerel_eposta_listesini_goster(self, mailler, hedef_kategori):
        """Senkronizasyon sürerken yerel başlıkları odağı bozmadan listeler."""
        if not pencere_kullanilabilir_mi(self) or mailler is None:
            return
        hedef_mail_id = self._yenileme_hedef_mail_id
        hedef_indeks = self._yenileme_hedef_indeks or 0
        self.mailler = mailler
        self.yuklu_kategori = hedef_kategori
        self.eposta_modunu_hazirla()
        self.liste.DeleteAllItems()
        if not mailler:
            if hedef_kategori == "Taslaklar":
                return
            self.liste_bilgi_satiri_goster("Bu klasörde gösterilecek e-posta yok.")
            return
        onizleme_etkin = onizleme_ayari_yukle()
        for i, mesaj in enumerate(mailler):
            self.liste.InsertItem(i, self.mesaj_liste_gosterimi(mesaj))
            konu = konu_gosterimini_duzenle(mesaj.get("konu", ""))
            onizleme = str(mesaj.get("onizleme", "") or "").strip()
            if onizleme_etkin and onizleme:
                konu = f"{konu}. {onizleme}"
            self.liste.SetItem(i, 1, konu)
            if hedef_mail_id and (
                str(mesaj.get("id")) == str(hedef_mail_id)
                or str(hedef_mail_id) in {
                    str(uid) for uid in (mesaj.get("ids") or [])
                }
            ):
                hedef_indeks = i
        self.liste_secim_ver(min(hedef_indeks, len(mailler) - 1), odak_ver=True)

    def yenilemeyi_gecikmeli_tetikle(self, liste_mesaji=None, kategori_adi=None, korunan_mail_id=None, korunan_indeks=None, sessiz=True, gecikme_ms=YENILEME_GECIKMESI_MS):
        """İşlem sonrası yenilemeyi kısa gecikmeyle başlatır; hızlı ardışık işlemlerde gereksiz uyarıyı engeller."""
        if not pencere_kullanilabilir_mi(self):
            return
        wx.CallLater(
            int(gecikme_ms),
            self.verileri_yukle_tetikle,
            liste_mesaji,
            kategori_adi,
            korunan_mail_id,
            korunan_indeks,
            sessiz,
        )

    def yeni_eposta_gonderildi(self):
        if not self.hesap_bilgisi_var_mi():
            return False
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) == LISTE_MODU_EPOSTA:
            self.yenilemeyi_gecikmeli_tetikle(
                None,
                self.secili_kategori,
                None,
                None,
                True,
            )
        try:
            onceki_gonderilen_bilgisi = (
                getattr(self, "_klasor_sayisi_cache", {}).get("Gönderilen E-postalar")
                or {}
            )
            onceki_gonderilen_toplam = onceki_gonderilen_bilgisi.get("messages")
            for zamanlayici_adi in (
                "_gonderim_sonrasi_esitleme_timer",
                "_gonderim_sonrasi_yeniden_deneme_timer",
            ):
                zamanlayici = getattr(self, zamanlayici_adi, None)
                if zamanlayici is not None:
                    try:
                        zamanlayici.Stop()
                    except Exception as e:
                        hata_kaydet("Eski gönderim sonrası eşitleme zamanlayıcısı durdurulamadı.", e)
                    setattr(self, zamanlayici_adi, None)
            self._gonderim_sonrasi_esitleme_timer = wx.CallLater(
                GONDERIM_SONRASI_ESITLEME_GECIKMESI_MS,
                self.gonderim_sonrasi_esitle_tetikle,
                onceki_gonderilen_toplam,
                1,
            )
        except Exception as e:
            hata_kaydet("Gönderim sonrası eşitleme planlanamadı.", e)
        return False

    def secili_eposta_idini_al(self):
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            return None
        indeks = self.liste.GetFocusedItem()
        if indeks == -1 or indeks >= len(self.mailler):
            return None
        return self.mailler[indeks]["id"]

    def eml_dosyasi_sec(self):
        return message_actions.eml_dosyasi_sec(self)

    def eml_dosyasini_ac(self, event=None):
        return message_actions.eml_dosyasini_ac(self, event)

    def sunucudan_eml_dosyasini_ac(self, dosya_yolu):
        return message_actions.sunucudan_eml_dosyasini_ac(self, dosya_yolu)

    def secili_epostayi_kaydet(self, event=None):
        return message_actions.secili_epostayi_kaydet(self, event)

    def txt_kayit_metni_olustur(self, mesaj, icerik, ekler, kaynak_klasor):
        return message_actions.txt_kayit_metni_olustur(self, mesaj, icerik, ekler, kaynak_klasor)

    def sunucudan_epostayi_kaydet(self, mail_id, kaynak_klasor, hedef_yol, bicim):
        return message_actions.sunucudan_epostayi_kaydet(self, mail_id, kaynak_klasor, hedef_yol, bicim)

    def yeni_posta_yaz(self, event=None):
        return message_actions.yeni_posta_yaz(self, event)

    def secili_mesaji_yanitla(self, event=None):
        return message_actions.secili_mesaji_yanitla(self, event)

    def secili_mesaji_ilet(self, event=None):
        return message_actions.secili_mesaji_ilet(self, event)

    def secili_mesaji_yanitla_veya_ilet(self, islem):
        return message_actions.secili_mesaji_yanitla_veya_ilet(self, islem)

    def sunucudan_yanit_veya_ilet_hazirla(self, mail_id, kaynak_klasor, islem):
        return message_actions.sunucudan_yanit_veya_ilet_hazirla(self, mail_id, kaynak_klasor, islem)

    def yanit_veya_ilet_penceresini_ac(self, veri, islem):
        return message_actions.yanit_veya_ilet_penceresini_ac(self, veri, islem)

    def listeyi_yenile(self, event=None):
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            self.klasor_secimini_odaktan_guncelle()
            mesaj_soyle_ve_sonra_calistir(
                "Klasörler güncelleniyor.",
                lambda: self.klasorleri_kesfet_tetikle(odak_ver=True),
                ad="Klasör listesini güncelleme",
            )
            return
        mesaj_soyle_ve_sonra_calistir(
            "E-posta listesi güncelleniyor.",
            lambda: self.verileri_yukle_tetikle(None),
            ad="E-posta listesini güncelleme",
        )

    def mesaj_oku(self, event):
        return message_actions.mesaj_oku(self, event)

    def sunucudan_icerik_indir(self, mail_id, kaynak_klasor, acma_callback=None):
        return message_actions.sunucudan_icerik_indir(
            self, mail_id, kaynak_klasor, acma_callback
        )

    def sunucudan_konusma_icerigi_indir(self, thread_id, uidler, kaynak_klasor):
        return message_actions.sunucudan_konusma_icerigi_indir(
            self, thread_id, uidler, kaynak_klasor
        )

    def taslak_penceresini_ac(self, veri):
        return draft_actions.taslak_penceresini_ac(self, veri)

    def taslak_gonderildi(self, mail_id, kaynak_klasor):
        return draft_actions.taslak_gonderildi(self, mail_id, kaynak_klasor)

    def taslak_kaydedildi(self, mail_id=None, kaynak_klasor=None):
        return draft_actions.taslak_kaydedildi(self, mail_id, kaynak_klasor)

    def taslak_sil_iste(self, mail_id, kaynak_klasor):
        return draft_actions.taslak_sil_iste(self, mail_id, kaynak_klasor)

    def taslak_klasor_adaylari(self, kaynak_klasor=None):
        return draft_actions.taslak_klasor_adaylari(self, kaynak_klasor)

    def uidleri_klasorde_ara(self, imap, uidler):
        return draft_actions.uidleri_klasorde_ara(imap, uidler)

    def sunucudan_taslak_sil(self, ids, klasor, basari_mesaji="", ayarlar=None, jeton=None):
        return draft_actions.sunucudan_taslak_sil(self, ids, klasor, basari_mesaji, ayarlar, jeton)

    def okuma_penceresini_ac(self, veri):
        return message_actions.okuma_penceresini_ac(self, veri)

    def arsiv_klasorlerini_yonet(self, event=None):
        return archive_actions.arsiv_klasorlerini_yonet(self, event)

    def arsiv_silindi_sonrasi_guncelle(self, silinen_klasor_adi):
        return archive_actions.arsiv_silindi_sonrasi_guncelle(self, silinen_klasor_adi)

    def arsiv_secim_goster(self, sids, kaynak_klasor=None):
        return archive_actions.arsiv_secim_goster(self, sids, kaynak_klasor)

    def arsiv_klasoru_olustur(self, klasor_adi):
        return archive_actions.arsiv_klasoru_olustur(self, klasor_adi)

    def sunucudan_arsiv_olustur_thread(self, klasor_adi, ayarlar, jeton):
        return archive_actions.sunucudan_arsiv_olustur_thread(self, klasor_adi, ayarlar, jeton)

    def arsiv_klasoru_yeniden_adlandir(self, eski_ad, yeni_ad):
        return archive_actions.arsiv_klasoru_yeniden_adlandir(self, eski_ad, yeni_ad)

    def sunucudan_arsiv_yeniden_adlandir_thread(self, eski_ad, yeni_ad, ayarlar, jeton):
        return archive_actions.sunucudan_arsiv_yeniden_adlandir_thread(self, eski_ad, yeni_ad, ayarlar, jeton)

    def arsiv_klasoru_sil(self, klasor_adi):
        return archive_actions.arsiv_klasoru_sil(self, klasor_adi)

    def sunucudan_arsiv_sil_thread(self, klasor_adi, ayarlar, jeton):
        return archive_actions.sunucudan_arsiv_sil_thread(self, klasor_adi, ayarlar, jeton)

    def sunucudan_ozel_arsivle(self, ids, hedef_isim, mevcut_klasor, ayarlar, jeton):
        return archive_actions.sunucudan_ozel_arsivle(self, ids, hedef_isim, mevcut_klasor, ayarlar, jeton)

    def tek_mesaj_sil(self, mail_id, kaynak_klasor=None, konu=None):
        return delete_actions.tek_mesaj_sil(self, mail_id, kaynak_klasor, konu)

    def konusma_sil(self, mail_ids, kaynak_klasor=None, konu=None):
        return delete_actions.konusma_sil(self, mail_ids, kaynak_klasor, konu)

    def secili_eposta_idlerini_al(self):
        return delete_actions.secili_eposta_idlerini_al(self)

    def posta_sil(self, event=None):
        return delete_actions.posta_sil(self, event)

    def posta_kalici_sil(self, event=None):
        return delete_actions.posta_kalici_sil(self, event)

    def listeden_mesajlari_kaldir(self, ids):
        return delete_actions.listeden_mesajlari_kaldir(self, ids)

    def silme_hatasi_penceresi_goster(self, mesaj, baslik="Silme Hatası"):
        return delete_actions.silme_hatasi_penceresi_goster(self, mesaj, baslik)

    def sunucudan_sil(self, ids, klasor, ayarlar=None, jeton=None):
        return delete_actions.sunucudan_sil(self, ids, klasor, ayarlar, jeton)

    def sunucudan_kalici_sil(self, ids, klasor, ayarlar=None, jeton=None):
        return delete_actions.sunucudan_kalici_sil(self, ids, klasor, ayarlar, jeton)

    def secili_klasoru_ac(self):
        """Klasör modunda Enter ile seçili klasörü açar."""
        hedef_kategori = self.secili_klasor_adini_al()
        if hedef_kategori:
            self.secili_kategori = hedef_kategori

        if self.yukleniyor:
            ui.message("Klasör yüklenirken lütfen bekleyin.")
            return True

        if not hedef_kategori:
            return True

        if hedef_kategori != self.yuklu_kategori:
            kaynak_klasor = self.klasor_haritasi.get(hedef_kategori, self.aktif_klasor())
            try:
                ayarlar = ayarlari_yukle()
                mesaj_sayisi = mesaj_sayisini_duzenle(
                    ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI)
                )
                yerel_mailler = yerel_eposta_listesi_hazirla(
                    ayarlar, hedef_kategori, kaynak_klasor, mesaj_sayisi
                )
                if yerel_mailler is not None:
                    taslaklar_yenilensin = (
                        hedef_kategori == "Taslaklar"
                        and bool(getattr(self, "_taslaklar_sunucudan_yenilensin", False))
                    )
                    if hedef_kategori == "Taslaklar" and not taslaklar_yenilensin:
                        bilgi = getattr(self, "_klasor_sayisi_cache", {}).get("Taslaklar", {})
                        try:
                            taslaklar_yenilensin = int(bilgi.get("messages", 0) or 0) > len(yerel_mailler)
                        except Exception:
                            taslaklar_yenilensin = False
                    if taslaklar_yenilensin:
                        self._taslaklar_sunucudan_yenilensin = False
                        raise MailHatasi("Taslaklar sunucudan yenilenecek.")
                    self._yenileme_hedef_mail_id = None
                    self._yenileme_hedef_indeks = None
                    self._yenileme_sessiz = True
                    self.yerel_eposta_listesini_goster(yerel_mailler, hedef_kategori)
                    return True
            except MailHatasi:
                pass
            except Exception as e:
                hata_kaydet("Yerel klasör listesi açılamadı.", e)
            self.verileri_yukle_tetikle(
                f"{hedef_kategori} yükleniyor...",
                kategori_adi=hedef_kategori,
            )
            return True

        # Aynı klasör zaten yüklüyse yeniden indirmeden e-posta moduna geç.
        self.eposta_modunu_hazirla()
        self.liste.DeleteAllItems()
        if not self.mailler:
            self.liste_bilgi_satiri_goster("Bu klasörde gösterilecek e-posta yok.")
        else:
            onizleme_etkin = onizleme_ayari_yukle()
            for i, mesaj in enumerate(self.mailler):
                self.liste.InsertItem(i, self.mesaj_liste_gosterimi(mesaj))
                konu_goster = konu_gosterimini_duzenle(mesaj.get("konu", ""))
                onizleme = str(mesaj.get("onizleme", "") or "").strip()
                if onizleme_etkin and onizleme:
                    konu_goster = f"{konu_goster}. {onizleme}"
                self.liste.SetItem(i, 1, konu_goster)
            self.liste_secim_ver(0, odak_ver=True)
        return True

    def ana_pencere_tus_yakalandi(self, event):
        return keyboard_handlers.ana_pencere_tus_yakalandi(self, event)

    def liste_ogesi_odaklandi(self, event):
        return keyboard_handlers.liste_ogesi_odaklandi(self, event)

    def liste_ogesi_aktiflestirildi(self, event):
        return keyboard_handlers.liste_ogesi_aktiflestirildi(self, event)

    def sag_tik_odagini_guncelle(self, event):
        try:
            indeks = -1
            if hasattr(event, "GetIndex"):
                try:
                    indeks = event.GetIndex()
                except Exception:
                    indeks = -1
            if indeks == -1 and hasattr(event, "GetPosition"):
                try:
                    konum = event.GetPosition()
                    if konum.x != -1 or konum.y != -1:
                        istemci_konum = self.liste.ScreenToClient(konum)
                        sonuc = self.liste.HitTest(istemci_konum)
                        indeks = sonuc[0] if isinstance(sonuc, tuple) else sonuc
                except Exception:
                    indeks = -1
            if indeks != -1 and indeks < len(self.mailler):
                self.liste.Focus(indeks)
                self.liste.Select(indeks)
                self.liste.EnsureVisible(indeks)
        except Exception:
            pass

    def tasima_hedefleri(self):
        hedefler = []

        def ekle(ad):
            ad = str(ad or "").strip()
            if not ad:
                return
            if ad == self.secili_kategori:
                return
            if ad not in self.klasor_haritasi:
                return
            if ad not in hedefler:
                hedefler.append(ad)

        ekle("Gelen Kutusu")
        for ad in self.ozel_klasorler:
            ekle(ad)
        return hedefler

    def tasima_onayi_al(self, adet, hedef_adi, konu=None):
        hedef_adi = str(hedef_adi or "").strip()
        konu_etiketi = self.konu_ifadesi(konu) if adet == 1 and konu else "Seçili"
        soru = (
            f"{konu_etiketi} e-posta '{hedef_adi}' klasörüne taşınacaktır. Devam etmek istiyor musunuz?"
            if adet == 1
            else f"Seçili {adet} e-posta '{hedef_adi}' klasörüne taşınacaktır. Devam etmek istiyor musunuz?"
        )
        return gui.messageBox(soru, "Taşıma Onayı", wx.YES_NO | wx.ICON_QUESTION) == wx.YES

    def tasi_menu(self, hedef_adi):
        secili_idler = self.secili_eposta_idlerini_al()
        if not secili_idler:
            ui.message("Lütfen taşımak için e-posta seçin.")
            return
        hedef_adi = str(hedef_adi or "").strip()
        if not hedef_adi or hedef_adi not in self.klasor_haritasi:
            ui.message("Hedef klasör bulunamadı.")
            return
        if hedef_adi == self.secili_kategori:
            ui.message("E-posta zaten seçili klasörde bulunuyor.")
            return
        kaynak_klasor = self.aktif_klasor()
        hedef_klasor = self.klasor_haritasi.get(hedef_adi)
        if str(kaynak_klasor) == str(hedef_klasor):
            ui.message("Kaynak ve hedef klasör aynı.")
            return
        adet = len(secili_idler)
        konu = self.mail_konusunu_bul(secili_idler[0]) if adet == 1 else None
        if self.tum_postalar_klasoru_mu(kaynak_klasor):
            if not self.tum_postalar_tasima_onayi_al(adet, hedef_adi):
                self.liste.SetFocus()
                return
        elif not self.tasima_onayi_al(adet, hedef_adi, konu):
            self.liste.SetFocus()
            return
        ayarlar = dict(ayarlari_yukle())
        kaynak_kategori = self.secili_kategori
        tum_postalar_kaynagi = self.tum_postalar_klasoru_mu(kaynak_klasor)
        if not tum_postalar_kaynagi:
            try:
                klasor_uidlerini_pasif_yap(
                    ayarlar.get("eposta", ""), kaynak_klasor, secili_idler
                )
            except Exception as e:
                hata_kaydet("Taşınan e-postalar yerel kaynak önbelleğinde pasif yapılamadı.", e)
            self.listeden_mesajlari_kaldir(secili_idler)
        baglam = {
            "hesap": ayarlar.get("eposta", ""),
            "kategori": kaynak_kategori,
            "kaynak_klasor": kaynak_klasor,
            "hedef_adi": hedef_adi,
            "hedef_klasor": hedef_klasor,
            "klasor_haritasi": dict(self.klasor_haritasi),
            "ozel_klasorler": tuple(self.ozel_klasorler),
            "tum_postalar_kaynagi": tum_postalar_kaynagi,
        }
        jeton = arka_plan_gorev_jetonu_olustur(self, "posta_degistirme", baglam)
        mesaj_soyle_ve_sonra_calistir(
            f"E-postalar '{hedef_adi}' klasörüne taşınıyor."
            if adet > 1
            else f"E-posta '{hedef_adi}' klasörüne taşınıyor.",
            lambda: arka_planda_calistir(
                self.sunucudan_tasi,
                tuple(secili_idler),
                kaynak_klasor,
                hedef_adi,
                ayarlar,
                jeton,
            ),
            ad="E-posta taşıma",
        )

    def sunucudan_tasi(self, ids, kaynak_klasor, hedef_adi, ayarlar, jeton):
        baglam = jeton.baglam
        klasor_haritasi = baglam["klasor_haritasi"]
        kaynak_kategori = baglam["kategori"]
        try:
            uidler = uid_kumesi_hazirla(ids, "Taşınacak e-posta bulunamadı.")
            hedef_adi = str(hedef_adi or "").strip()
            hedef_klasor = baglam["hedef_klasor"]
            if not hedef_klasor:
                raise MailHatasi("Hedef klasör bulunamadı.")
            if str(kaynak_klasor) == str(hedef_klasor):
                raise MailHatasi("Kaynak ve hedef klasör aynı.")
            with ImapBaglantisi(ayarlar) as imap:
                imap_gmail_etiket_destegini_dogrula(imap)
                tip, _veri = imap.select(kaynak_klasor, readonly=False)
                imap_ok_mu(tip, "Kaynak klasör açılamadı.")

                hedef_etiket = gmail_etiket_ifadesi_olustur(
                    hedef_adi,
                    hedef_klasor,
                    klasor_haritasi,
                    kaynak_kategori,
                    kaynak_klasor,
                )
                if not hedef_etiket:
                    raise MailHatasi("Hedef klasör etiketi hazırlanamadı.")
                gmail_etiket_ekle_ve_kaynak_kaldir_akisi(
                    imap,
                    uidler,
                    hedef_etiket,
                    kaynak_klasor,
                    "E-postalar hedef etikete eklenemedi.",
                    "E-postalar kaynak etiketinden kaldırılamadı.",
                    klasor_haritasi,
                    baglam["ozel_klasorler"],
                    kaynak_kategori,
                )
            if bool(baglam.get("tum_postalar_kaynagi")) or gmail_tum_postalar_klasoru_mu(kaynak_klasor, klasor_haritasi):
                mesaj = f"E-postaya '{hedef_adi}' etiketi eklendi. Tüm Postalar'da görünmeye devam edebilir." if len(ids) == 1 else f"E-postalara '{hedef_adi}' etiketi eklendi. Tüm Postalar'da görünmeye devam edebilirler."
            else:
                mesaj = f"E-posta '{hedef_adi}' klasörüne taşındı." if len(ids) == 1 else f"E-postalar '{hedef_adi}' klasörüne taşındı."
            arka_planda_calistir(
                archive_actions.hedef_arsiv_onbellegini_guncelle,
                dict(ayarlar),
                hedef_adi,
                hedef_klasor,
            )
            gorev_icin_guvenli_call_after(jeton, ui.message, mesaj)
            gorev_icin_guvenli_call_after(jeton, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kaynak_kategori, None, None, True)
        except MailHatasi as e:
            hata_kaydet(str(e))
            gorev_icin_guvenli_call_after(jeton, ui.message, str(e))
            gorev_icin_guvenli_call_after(jeton, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kaynak_kategori, None, None, False)
        except Exception as e:
            hata_kaydet("Taşıma işlemi başarısız oldu.", e)
            gorev_icin_guvenli_call_after(jeton, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Taşıma işlemi sırasında bir hata oluştu."))
            gorev_icin_guvenli_call_after(jeton, self.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kaynak_kategori, None, None, False)

    def yerel_veritabanini_sifirla_menu(self, event=None):
        soru = (
            "Yerel veritabanı, çevrimdışı e-posta içerikleri ve önbelleğe alınmış ekler "
            "tamamen silinecektir. Gmail hesabınızdaki e-postalar, hesap bilgileriniz, "
            "kişileriniz ve ayarlarınız silinmeyecektir. Devam etmek istiyor musunuz?"
        )
        if gui.messageBox(soru, "Yerel Veritabanını Sıfırla", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
            return
        jeton = arka_plan_gorev_jetonu_olustur(self, "veritabani_sifirla")
        ui.message("Yerel veritabanı sıfırlanıyor.")
        arka_planda_calistir(self._yerel_veritabanini_sifirla_thread, jeton)

    def _yerel_veritabanini_sifirla_thread(self, jeton):
        try:
            yerel_veritabanini_sifirla()
            gorev_icin_guvenli_call_after(jeton, self._veritabani_sifirlama_tamamlandi)
        except Exception as e:
            hata_kaydet("Yerel veritabanı sıfırlanamadı.", e)
            gorev_icin_guvenli_call_after(jeton, ui.message, str(e))

    def _veritabani_sifirlama_tamamlandi(self):
        self.mailler = []
        self.isaretliler.clear()
        self._klasor_sayisi_cache = {}
        klasor_sayisi_onbellegi_temizle()
        self.klasor_gorunumunu_goster("Gelen Kutusu", odak_ver=True)
        ui.message("Yerel veritabanı ve ek önbelleği sıfırlandı. E-postalar yeniden eşitlenecektir.")

    def cop_kutusunu_bosalt(self, event=None):
        ayarlar = dict(ayarlari_yukle())
        if not ayarlar.get("eposta"):
            ui.message("Önce Gmail hesabınıza bağlanın.")
            return
        soru = (
            "Çöp Kutusu'ndaki bütün e-postalar Gmail hesabınızdan kalıcı olarak silinecektir. "
            "Bu işlem geri alınamaz. Devam etmek istiyor musunuz?"
        )
        if gui.messageBox(soru, "Çöp Kutusunu Boşalt", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
            return
        cop_klasoru = self.klasor_haritasi.get("Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"])
        jeton = arka_plan_gorev_jetonu_olustur(self, "cop_kutusunu_bosalt")
        ui.message("Çöp Kutusu boşaltılıyor.")
        arka_planda_calistir(self._cop_kutusunu_bosalt_thread, ayarlar, cop_klasoru, jeton)

    def _cop_kutusunu_bosalt_thread(self, ayarlar, cop_klasoru, jeton):
        if not POSTA_DURUM_KILIDI.acquire(False):
            gorev_icin_guvenli_call_after(jeton, ui.message, "Başka bir e-posta işlemi devam ediyor. Lütfen daha sonra yeniden deneyin.")
            return
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(cop_klasoru, readonly=False)
                imap_ok_mu(tip, "Çöp Kutusu açılamadı.")
                tip, veri = imap.uid("SEARCH", None, "ALL")
                imap_ok_mu(tip, "Çöp Kutusu içeriği alınamadı.")
                uidler = uidleri_ayristir(veri)
                if not uidler:
                    gorev_icin_guvenli_call_after(jeton, ui.message, "Çöp Kutusu zaten boş.")
                    return
                gmail_haritasi = imap_x_gm_msgid_haritasi_al(imap, uidler)
                imap_uidleri_kalici_sil(
                    imap, uid_kumesi_hazirla(uidler), "Çöp Kutusu boşaltılamadı."
                )
            gmail_mesajlarini_yerelden_sil(ayarlar.get("eposta", ""), gmail_haritasi.values())
            gorev_icin_guvenli_call_after(jeton, self._cop_kutusunu_bosaltma_tamamlandi, len(uidler))
        except Exception as e:
            hata_kaydet("Çöp Kutusu boşaltılamadı.", e)
            gorev_icin_guvenli_call_after(
                jeton, ui.message,
                baglanti_hatasi_kullanici_mesaji(e, "Çöp Kutusu boşaltılırken bir hata oluştu."),
            )
        finally:
            POSTA_DURUM_KILIDI.release()

    def _cop_kutusunu_bosaltma_tamamlandi(self, adet):
        self._klasor_sayisi_cache.pop("Çöp Kutusu", None)
        self.klasor_gorunumunu_goster("Çöp Kutusu", odak_ver=True)
        ui.message(f"Çöp Kutusu boşaltıldı. {adet} e-posta kalıcı olarak silindi.")

    def spami_bosalt(self, event=None):
        ayarlar = dict(ayarlari_yukle())
        if not ayarlar.get("eposta"):
            ui.message("Önce Gmail hesabınıza bağlanın.")
            return
        soru = (
            "Spam klasöründeki bütün e-postalar Gmail hesabınızdan kalıcı olarak silinecektir. "
            "Bu işlem geri alınamaz. Devam etmek istiyor musunuz?"
        )
        if gui.messageBox(soru, "Spam Klasörünü Boşalt", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
            return
        spam_klasoru = self.klasor_haritasi.get("Spam", VARSAYILAN_KLASOR_HARITASI["Spam"])
        jeton = arka_plan_gorev_jetonu_olustur(self, "spami_bosalt")
        ui.message("Spam klasörü boşaltılıyor.")
        arka_planda_calistir(self._spami_bosalt_thread, ayarlar, spam_klasoru, jeton)

    def _spami_bosalt_thread(self, ayarlar, spam_klasoru, jeton):
        if not POSTA_DURUM_KILIDI.acquire(False):
            gorev_icin_guvenli_call_after(jeton, ui.message, "Başka bir e-posta işlemi devam ediyor. Lütfen daha sonra yeniden deneyin.")
            return
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(spam_klasoru, readonly=False)
                imap_ok_mu(tip, "Spam klasörü açılamadı.")
                tip, veri = imap.uid("SEARCH", None, "ALL")
                imap_ok_mu(tip, "Spam klasörü içeriği alınamadı.")
                uidler = uidleri_ayristir(veri)
                if not uidler:
                    gorev_icin_guvenli_call_after(jeton, ui.message, "Spam klasörü zaten boş.")
                    return
                gmail_haritasi = imap_x_gm_msgid_haritasi_al(imap, uidler)
                imap_uidleri_kalici_sil(
                    imap, uid_kumesi_hazirla(uidler), "Spam klasörü boşaltılamadı."
                )
            gmail_mesajlarini_yerelden_sil(ayarlar.get("eposta", ""), gmail_haritasi.values())
            gorev_icin_guvenli_call_after(jeton, self._spam_bosaltma_tamamlandi, len(uidler))
        except Exception as e:
            hata_kaydet("Spam klasörü boşaltılamadı.", e)
            gorev_icin_guvenli_call_after(
                jeton, ui.message,
                baglanti_hatasi_kullanici_mesaji(e, "Spam klasörü boşaltılırken bir hata oluştu."),
            )
        finally:
            POSTA_DURUM_KILIDI.release()

    def _spam_bosaltma_tamamlandi(self, adet):
        self._klasor_sayisi_cache.pop("Spam", None)
        self.klasor_gorunumunu_goster("Spam", odak_ver=True)
        ui.message(f"Spam klasörü boşaltıldı. {adet} e-posta kalıcı olarak silindi.")

    def gonderilenleri_cope_tasi(self, event=None):
        ayarlar = dict(ayarlari_yukle())
        if not ayarlar.get("eposta"):
            ui.message("Önce Gmail hesabınıza bağlanın.")
            return
        soru = (
            "Gönderilen E-postalar klasöründeki bütün e-postalar Çöp Kutusu'na taşınacaktır. "
            "Bu iletiler Çöp Kutusu boşaltılana kadar geri alınabilir. Devam etmek istiyor musunuz?"
        )
        if gui.messageBox(
            soru,
            "Gönderilenleri Çöp Kutusu'na Taşı",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            self,
        ) != wx.YES:
            return
        gonderilen_klasoru = self.klasor_haritasi.get(
            "Gönderilen E-postalar",
            VARSAYILAN_KLASOR_HARITASI["Gönderilen E-postalar"],
        )
        jeton = arka_plan_gorev_jetonu_olustur(self, "gonderilenleri_cope_tasi")
        ui.message("Gönderilen e-postalar Çöp Kutusu'na taşınıyor.")
        arka_planda_calistir(
            self._gonderilenleri_cope_tasi_thread,
            ayarlar,
            gonderilen_klasoru,
            jeton,
        )

    def _gonderilenleri_cope_tasi_thread(self, ayarlar, gonderilen_klasoru, jeton):
        if not POSTA_DURUM_KILIDI.acquire(False):
            gorev_icin_guvenli_call_after(
                jeton,
                ui.message,
                "Başka bir e-posta işlemi devam ediyor. Lütfen daha sonra yeniden deneyin.",
            )
            return
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _veri = imap.select(gonderilen_klasoru, readonly=False)
                imap_ok_mu(tip, "Gönderilen E-postalar klasörü açılamadı.")
                tip, veri = imap.uid("SEARCH", None, "ALL")
                imap_ok_mu(tip, "Gönderilen e-postalar alınamadı.")
                uidler = uidleri_ayristir(veri)
                if not uidler:
                    gorev_icin_guvenli_call_after(
                        jeton, ui.message, "Gönderilen E-postalar klasörü zaten boş."
                    )
                    return
                gmail_haritasi = imap_x_gm_msgid_haritasi_al(imap, uidler)
                imap_gmail_etiket_destegini_dogrula(imap)
                for uid_parcasi in uid_listesini_parcala(uidler, 200):
                    imap_gmail_etiket_store(
                        imap,
                        uid_kumesi_hazirla(uid_parcasi),
                        "+",
                        "\\Trash",
                        "Gönderilen e-postalar Çöp Kutusu'na taşınamadı.",
                    )
            eposta = ayarlar.get("eposta", "")
            klasor_uidlerini_pasif_yap(eposta, gonderilen_klasoru, uidler)
            gmail_mesajlarini_yerelde_pasif_yap(eposta, gmail_haritasi.values())
            gorev_icin_guvenli_call_after(
                jeton, self._gonderilenleri_tasima_tamamlandi, len(uidler)
            )
        except Exception as e:
            hata_kaydet("Gönderilen e-postalar Çöp Kutusu'na taşınamadı.", e)
            gorev_icin_guvenli_call_after(
                jeton,
                ui.message,
                baglanti_hatasi_kullanici_mesaji(
                    e, "Gönderilen e-postalar taşınırken bir hata oluştu."
                ),
            )
            return
        finally:
            POSTA_DURUM_KILIDI.release()

    def _gonderilenleri_tasima_tamamlandi(self, adet):
        self._klasor_sayisi_cache.pop("Gönderilen E-postalar", None)
        self.klasor_gorunumunu_goster("Gönderilen E-postalar", odak_ver=True)
        ui.message(
            f"Gönderilen E-postalar klasörü boşaltıldı. {adet} e-posta Çöp Kutusu'na taşındı."
        )

    def sag_tik_menusu(self, event):
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) == LISTE_MODU_KLASOR:
            try:
                indeks = event.GetIndex()
                if indeks >= 0:
                    self.liste.Select(indeks)
                    self.liste.Focus(indeks)
            except (AttributeError, TypeError):
                pass
            secili_klasor = self.secili_klasor_adini_al()
            if secili_klasor not in (
                "Gönderilen E-postalar",
                "Çöp Kutusu",
                "Spam",
            ):
                return
            menu = wx.Menu()
            if secili_klasor == "Gönderilen E-postalar":
                menu.Append(
                    self.id_gonderilenleri_cope_tasi,
                    "Gönderilenleri Çöp Kutusu'na &Taşı...",
                )
            elif secili_klasor == "Çöp Kutusu":
                menu.Append(self.id_cop_kutusunu_bosalt, "Çöp Kutusunu &Boşalt...")
            else:
                menu.Append(self.id_spami_bosalt, "Spam Klasörünü &Boşalt...")
            self.liste.PopupMenu(menu)
            menu.Destroy()
            return
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            return
        self.sag_tik_odagini_guncelle(event)
        menu = wx.Menu()
        menu.Append(self.id_yanitla, "&Yanıtla\tCtrl+R")
        menu.Append(self.id_ilet, "İ&let\tCtrl+Shift+F")
        menu.AppendSeparator()
        tasi_alt_menu = wx.Menu()
        hedefler = self.tasima_hedefleri()
        if hedefler:
            for hedef in hedefler:
                hedef_id = wx.NewId()
                tasi_alt_menu.Append(hedef_id, hedef)
                tasi_alt_menu.Bind(wx.EVT_MENU, lambda evt, hedef=hedef: self.tasi_menu(hedef), id=hedef_id)
        else:
            bos_item = tasi_alt_menu.Append(wx.ID_ANY, "Taşınabilecek klasör yok")
            bos_item.Enable(False)
        menu.AppendSubMenu(tasi_alt_menu, "&Taşı")

        menu.AppendSeparator()
        sil_alt_menu = wx.Menu()
        sil_alt_menu.Append(self.id_sil, "&Sil	Alt+S")
        sil_alt_menu.Append(self.id_kalici_sil, "&Kalıcı Sil	Shift+Delete")
        menu.AppendSubMenu(sil_alt_menu, "&Sil")
        self.liste.PopupMenu(menu)
        menu.Destroy()

    def arsive_gonder_menu(self, event=None):
        return archive_actions.arsive_gonder_menu(self, event)

    def tumunu_isaretle(self, event=None):
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            ui.message("İşaretlemek için önce bir klasöre girin.")
            return
        if not self.mailler:
            ui.message("İşaretlenecek e-posta yok.")
            return
        for i, mesaj in enumerate(self.mailler):
            if mesaj["id"] not in self.isaretliler:
                self.isaretliler.add(mesaj["id"])
                self.liste.SetItem(i, 0, "[İşaretli] " + self.mesaj_liste_gosterimi(mesaj))
        ui.message(f"{len(self.isaretliler)} e-posta işaretlendi.")

    def isaretleri_kaldir(self, event=None):
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            ui.message("Kaldırılacak işaret yok.")
            return
        if not self.isaretliler:
            ui.message("Kaldırılacak işaret yok.")
            return
        self.isaretliler.clear()
        for i, mesaj in enumerate(self.mailler):
            self.liste.SetItem(i, 0, self.mesaj_liste_gosterimi(mesaj))
        ui.message("İşaretler kaldırıldı.")

    def tusa_basildi(self, event):
        return keyboard_handlers.tusa_basildi(self, event)

    def verileri_yukle(self, kategori_adi=None, kaynak_klasor=None, yukleme_islem_no=None):
        ayarlar = ayarlari_yukle()
        mesaj_sayisi = mesaj_sayisini_duzenle(ayarlar.get(MESAJ_SAYISI_ALANI, VARSAYILAN_MESAJ_SAYISI))
        onizleme_etkin = onizleme_ayari_yukle()
        try:
            sonuc = eposta_listesi_hazirla(
                ayarlar,
                kategori_adi,
                kaynak_klasor,
                self.klasor_haritasini_hazirla,
                mesaj_sayisi,
                onizleme_etkin,
            )
            guvenli_call_after(
                self,
                self.arayuzu_yenile,
                sonuc["mailler"],
                sonuc["klasor_haritasi"],
                sonuc["ozel_klasorler"],
                sonuc["hedef_kategori"],
                yukleme_islem_no,
                sonuc["klasor_bilgisi"],
            )
            try:
                if onizleme_etkin:
                    hedef_kategori = sonuc["hedef_kategori"]
                    hedef_klasor = str(
                        sonuc["klasor_haritasi"].get(hedef_kategori, kaynak_klasor or "")
                        or ""
                    ).strip()
                    gorunen_uidler = self.gorunen_onizleme_uidlerini_al(sonuc["mailler"])
                    if hedef_klasor and gorunen_uidler:
                        eksik_uidler = onizlemesi_eksik_uidleri_al(
                            ayarlar.get("eposta", ""),
                            hedef_klasor,
                            gorunen_uidler,
                        )
                        if eksik_uidler:
                            arka_planda_calistir(
                                self.onizleme_onbellegini_hazirla,
                                hedef_kategori,
                                hedef_klasor,
                                eksik_uidler,
                                yukleme_islem_no,
                            )
            except Exception as e:
                # Ön izleme yardımcı bir özelliktir; hazırlanma sorunu başlıkları
                # yüklenmiş e-posta listesini başarısız duruma çevirmemelidir.
                hata_kaydet("Görünür e-postaların ön izleme hazırlığı başlatılamadı.", e)
        except MailHatasi as e:
            hata_kaydet(str(e))
            guvenli_call_after(self, self.yukleme_hatali, str(e), yukleme_islem_no)
        except Exception as e:
            hata_kaydet("E-posta listesi yüklenemedi.", e)
            guvenli_call_after(self, self.yukleme_hatali, baglanti_hatasi_kullanici_mesaji(e), yukleme_islem_no)

    def yukleme_hatali(self, mesaj, yukleme_islem_no=None):
        if not pencere_kullanilabilir_mi(self):
            return
        if yukleme_islem_no is not None and yukleme_islem_no != getattr(self, "_yukleme_islem_no", None):
            return
        self.yukleniyor = False
        self._yenileme_sessiz = False
        self._son_yukleme_hatasi = True
        try:
            gui.messageBox(
                mesaj,
                "Engelsiz Mail",
                wx.OK | wx.ICON_ERROR,
                self,
            )
        except Exception as e:
            hata_kaydet("Yükleme hatası uyarısı gösterilemedi.", e)
            ui.message(mesaj)

    def arayuzu_yenile(self, yeni_mailler, yeni_harita=None, yeni_ozeller=None, hedef_kategori=None, yukleme_islem_no=None, klasor_bilgisi=None):
        if not pencere_kullanilabilir_mi(self):
            return
        if yukleme_islem_no is not None and yukleme_islem_no != getattr(self, "_yukleme_islem_no", None):
            return
        # Yerel önbellek zaten gösterilmişse sunucu sonucu aynı öğeyi yeniden
        # odaklamasın. Mevcut ileti kimliği, liste modeli değiştirilmeden alınmalıdır.
        mevcut_odak_mail_id, mevcut_odak_indeks = self.liste_odak_bilgisi_al()
        self.klasor_haritasini_uygula(yeni_harita, yeni_ozeller, hedef_kategori)
        self.yukleniyor = False
        if isinstance(klasor_bilgisi, dict) and self.secili_kategori:
            self._klasor_sayisi_cache_guncelle(self.secili_kategori, klasor_bilgisi)
        self.mailler = yeni_mailler
        self.isaretliler.clear()

        tum_kategoriler = self.tum_kategoriler()
        if self.secili_kategori not in tum_kategoriler:
            self.secili_kategori = self.kategori_isimleri[0]

        self.yuklu_kategori = self.secili_kategori
        self.eposta_modunu_hazirla()
        hedef_indeks = 0
        hedef_acikca_istendi = bool(self._yenileme_hedef_mail_id)
        hedef_mail_id = self._yenileme_hedef_mail_id
        hedef_indeks_yedek = self._yenileme_hedef_indeks
        if not hedef_mail_id and mevcut_odak_mail_id:
            hedef_mail_id = mevcut_odak_mail_id
        if hedef_indeks_yedek is None and mevcut_odak_indeks != -1:
            hedef_indeks_yedek = mevcut_odak_indeks
        self._yenileme_hedef_mail_id = None
        self._yenileme_hedef_indeks = None
        self._yenileme_sessiz = False

        onizleme_etkin = onizleme_ayari_yukle()
        yeni_satirlar = []
        if not self.mailler:
            yeni_satirlar.append(("Bu klasörde gösterilecek e-posta yok.", ""))
        else:
            for mesaj in self.mailler:
                konu_goster = konu_gosterimini_duzenle(mesaj.get("konu", ""))
                onizleme = str(mesaj.get("onizleme", "") or "").strip()
                if onizleme_etkin and onizleme:
                    konu_goster = f"{konu_goster}. {onizleme}"
                yeni_satirlar.append((self.mesaj_liste_gosterimi(mesaj), konu_goster))

        mevcut_satirlar = []
        try:
            mevcut_satirlar = [
                (self.liste.GetItemText(i, 0), self.liste.GetItemText(i, 1))
                for i in range(self.liste.GetItemCount())
            ]
        except Exception:
            mevcut_satirlar = []
        liste_degisti = mevcut_satirlar != yeni_satirlar

        if liste_degisti:
            self.liste.DeleteAllItems()
            if not self.mailler:
                self.liste_bilgi_satiri_goster("Bu klasörde gösterilecek e-posta yok.")
            else:
                for i, (birinci_sutun, ikinci_sutun) in enumerate(yeni_satirlar):
                    self.liste.InsertItem(i, birinci_sutun)
                    self.liste.SetItem(i, 1, ikinci_sutun)
                    mesaj_uidleri = {
                        str(uid) for uid in (self.mailler[i].get("ids") or [])
                    }
                    if hedef_mail_id and (
                        str(self.mailler[i].get("id")) == str(hedef_mail_id)
                        or str(hedef_mail_id) in mesaj_uidleri
                    ):
                        hedef_indeks = i

        if self.mailler:
            if hedef_mail_id:
                for i, mesaj in enumerate(self.mailler):
                    if (
                        str(mesaj.get("id")) == str(hedef_mail_id)
                        or str(hedef_mail_id) in {
                            str(uid) for uid in (mesaj.get("ids") or [])
                        }
                    ):
                        hedef_indeks = i
                        break
            if hedef_mail_id and not any(
                str(mesaj.get("id")) == str(hedef_mail_id)
                or str(hedef_mail_id) in {
                    str(uid) for uid in (mesaj.get("ids") or [])
                }
                for mesaj in self.mailler
            ):
                if hedef_indeks_yedek is not None:
                    hedef_indeks = hedef_indeks_yedek
            elif not hedef_mail_id and hedef_indeks_yedek is not None:
                hedef_indeks = hedef_indeks_yedek

            # Satırlar aynıysa listeyi ve odağı hiç oynatma; NVDA aynı iletiyi
            # ikinci kez okumaz. Gerçek değişiklikte seçimi koruyarak yenile.
            if liste_degisti or hedef_acikca_istendi:
                self.liste_secim_ver(hedef_indeks, odak_ver=True)

        if self.ilk_yukleme:
            self.ilk_yukleme = False

        if not getattr(self, "_sistem_klasor_sayisi_acilista_guncellendi", False):
            self._sistem_klasor_sayisi_acilista_guncellendi = True
            self.sistem_klasor_sayilarini_guncelle_tetikle()
