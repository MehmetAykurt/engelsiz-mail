# -*- coding: utf-8 -*-
"""Engelsiz Mail arşiv işlemleri."""

import wx
import gui
import ui

from ..config import ayarlari_yukle
from ..errors import MailHatasi
from ..folders import arsiv_klasor_adini_dogrula, imap_klasor_adi_hazirla
from ..imap_client import (
    ImapBaglantisi,
    imap_gmail_etiket_destegini_dogrula,
    imap_ok_mu,
    uid_kumesi_hazirla,
    uidleri_ayristir,
)
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..header_sync import klasor_basliklarini_senkronize_et
from ..gmail_actions import (
    gmail_etiket_ekle_ve_kaynak_kaldir,
    gmail_etiket_ifadesi,
    tum_postalar_klasoru_mu,
)
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_planda_calistir,
    gorev_icin_guvenli_call_after,
    guvenli_modal_goster,
)
from ..smtp_client import baglanti_hatasi_kullanici_mesaji
from ..text_utils import konu_gosterimini_duzenle
from ..mail_store import klasor_uidlerini_pasif_yap, klasoru_yerelde_pasif_yap
from .archive_dialogs import ArsivSecimPenceresi, ArsivYonetimPenceresi
from .folder_view import LISTE_MODU_EPOSTA, LISTE_MODU_KLASOR
from ..conversation import secimleri_uidlere_genislet


def _arsiv_gorev_baglami(pencere, kategori_korumali=False):
    baglam = {
        "klasor_haritasi": dict(pencere.klasor_haritasi),
        "ozel_klasorler": tuple(pencere.ozel_klasorler),
    }
    if kategori_korumali:
        baglam["kategori"] = str(pencere.secili_kategori or "")
    return baglam


def _konulu_eposta_ifadesi(konu):
    konu = konu_gosterimini_duzenle(str(konu or "").strip() or "Konusuz")
    return f"{konu} konulu e-posta"


def _arsiv_basari_mesaji(adet, hedef_isim, konu=None, tum_postalar=False):
    adet = max(1, int(adet or 1))
    hedef_isim = str(hedef_isim or "").strip() or "hedef"
    if tum_postalar:
        if adet == 1:
            return f"{_konulu_eposta_ifadesi(konu)} için {hedef_isim} arşiv etiketi eklendi. Tüm Postalar'da görünmeye devam edebilir."
        return f"{adet} e-postaya {hedef_isim} arşiv etiketi eklendi. Tüm Postalar'da görünmeye devam edebilirler."
    if adet == 1:
        return f"{_konulu_eposta_ifadesi(konu)} {hedef_isim} arşivine taşındı."
    return f"{adet} e-posta {hedef_isim} arşivine taşındı."


def _arsiv_yonetimi_sonrasi_klasorleri_guncelle(pencere, hedef_klasor=None, eski_klasor=None):
    hedef_klasor = str(hedef_klasor or "").strip()
    eski_klasor = str(eski_klasor or "").strip()
    try:
        if eski_klasor and hedef_klasor:
            if pencere.secili_kategori == eski_klasor:
                pencere.secili_kategori = hedef_klasor
            if pencere.yuklu_kategori == eski_klasor:
                pencere.yuklu_kategori = hedef_klasor
        elif hedef_klasor and getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
            pencere.secili_kategori = hedef_klasor
        pencere.klasorleri_kesfet_tetikle(
            odak_ver=getattr(pencere, "liste_modu", LISTE_MODU_EPOSTA) == LISTE_MODU_KLASOR
        )
    except Exception as e:
        hata_kaydet("Arşiv yönetimi sonrası klasör listesi güncellenemedi.", e)


def _hedef_arsiv_onbellegini_guncelle(ayarlar, hedef_isim, hedef_klasor):
    hedef_isim = str(hedef_isim or "").strip()
    hedef_klasor = str(hedef_klasor or "").strip()
    if not hedef_isim or not hedef_klasor:
        return
    try:
        with ImapBaglantisi(ayarlar) as imap:
            tip, _secim = imap.select(hedef_klasor, readonly=True)
            if tip != "OK":
                raise MailHatasi("Hedef arşiv klasörü önbellek için açılamadı.")
            tip, arama_verisi = imap.uid("SEARCH", "ALL")
            if tip != "OK":
                raise MailHatasi("Hedef arşiv UID listesi alınamadı.")
            klasor_basliklarini_senkronize_et(
                imap,
                ayarlar.get("eposta", ""),
                hedef_isim,
                hedef_klasor,
                sunucu_uidleri=uidleri_ayristir(arama_verisi),
            )
    except Exception as e:
        hata_kaydet(f"Hedef arşiv önbelleği güncellenemedi: {hedef_isim}", e)


def hedef_arsiv_onbellegini_guncelle(ayarlar, hedef_isim, hedef_klasor):
    return _hedef_arsiv_onbellegini_guncelle(ayarlar, hedef_isim, hedef_klasor)


def tum_postalar_arsiv_onayi_al(adet):
    soru = (
        "Seçili e-postaya özel arşiv etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-posta burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
        if adet == 1
        else f"Seçili {adet} e-postaya özel arşiv etiketi eklenecektir. Tüm Postalar Gmail'in ana görünümü olduğu için e-postalar burada görünmeye devam edebilir. Devam etmek istiyor musunuz?"
    )
    return gui.messageBox(soru, "Tüm Postalar Arşivleme Uyarısı", wx.YES_NO | wx.ICON_WARNING) == wx.YES


def arsiv_klasorlerini_yonet(pencere, event=None):
    if pencere.yukleniyor:
        ui.message("Devam eden işlem tamamlandıktan sonra yeniden deneyin.")
        return
    if not pencere.hesap_bilgisi_var_mi():
        ui.message("Arşiv klasörlerini yönetmek için önce Hesap menüsünden Bağlan seçeneğiyle Gmail hesabınızı bağlayın.")
        return
    dlg = ArsivYonetimPenceresi(pencere, pencere.ozel_klasorler, pencere)
    guvenli_modal_goster(dlg, pencere.liste, pencere)


def arsiv_silindi_sonrasi_guncelle(pencere, silinen_klasor_adi):
    silinen_klasor_adi = str(silinen_klasor_adi or "").strip()
    if silinen_klasor_adi:
        pencere.klasor_haritasi.pop(silinen_klasor_adi, None)
        if silinen_klasor_adi in pencere.ozel_klasorler:
            pencere.ozel_klasorler = [ad for ad in pencere.ozel_klasorler if ad != silinen_klasor_adi]
    silinen_aktif_klasor = pencere.secili_kategori == silinen_klasor_adi or pencere.yuklu_kategori == silinen_klasor_adi
    if silinen_aktif_klasor:
        pencere.secili_kategori = "Gelen Kutusu"
        pencere.yuklu_kategori = "Gelen Kutusu"
    if pencere.secili_kategori not in pencere.tum_kategoriler():
        pencere.secili_kategori = "Gelen Kutusu"
    if silinen_aktif_klasor:
        pencere.klasor_gorunumunu_goster(pencere.secili_kategori, odak_ver=True)
    elif getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        pencere.klasor_gorunumunu_goster(pencere.secili_kategori, odak_ver=True)
    else:
        _arsiv_yonetimi_sonrasi_klasorleri_guncelle(pencere)


def arsiv_secim_goster(pencere, sids, kaynak_klasor=None):
    if not sids:
        ui.message("Arşivlenecek e-posta bulunamadı.")
        return
    sids = tuple(str(sid) for sid in sids if str(sid or "").strip())
    if not sids:
        ui.message("Arşivlenecek e-posta bulunamadı.")
        return
    kaynak_klasor = kaynak_klasor or pencere.aktif_klasor()
    adet = len(sids)
    konu = pencere.mail_konusunu_bul(sids[0]) if adet == 1 else None
    if pencere.tum_postalar_klasoru_mu(kaynak_klasor) and not pencere.tum_postalar_arsiv_onayi_al(adet):
        pencere.liste.SetFocus()
        return
    dlg = ArsivSecimPenceresi(pencere, pencere.ozel_klasorler, pencere)
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return
        hedef = dlg.secilen_isim
        if not hedef:
            ui.message("Lütfen hedef arşiv klasörünü seçin. Arşiv yoksa E-posta menüsünden Arşiv Klasörlerini Yönet seçeneğiyle yeni arşiv oluşturun.")
            return

        baglam = _arsiv_gorev_baglami(pencere, kategori_korumali=True)
        ayarlar = dict(ayarlari_yukle())
        baglam["hesap"] = ayarlar.get("eposta", "")
        baglam["adet"] = adet
        baglam["konu"] = konu
        jeton = arka_plan_gorev_jetonu_olustur(pencere, "posta_degistirme", baglam)
        mesaj_soyle_ve_sonra_calistir(
            f"E-postalar {hedef} klasörüne arşivleniyor."
            if adet > 1
            else f"E-posta {hedef} klasörüne arşivleniyor.",
            lambda: arka_planda_calistir(
                pencere.sunucudan_ozel_arsivle,
                sids,
                hedef,
                kaynak_klasor,
                ayarlar,
                jeton,
            ),
            ad="Özel arşivleme",
        )
    finally:
        dlg.Destroy()


def arsiv_klasoru_olustur(pencere, klasor_adi):
    baglam = _arsiv_gorev_baglami(pencere)
    ayarlar = dict(ayarlari_yukle())
    baglam["hesap"] = ayarlar.get("eposta", "")
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "arsiv_klasor_yonetimi", baglam)
    mesaj_soyle_ve_sonra_calistir(
        "Arşiv oluşturuluyor.",
        lambda: arka_planda_calistir(
            pencere.sunucudan_arsiv_olustur_thread,
            klasor_adi,
            ayarlar,
            jeton,
        ),
        ad="Arşiv oluşturma",
    )


def sunucudan_arsiv_olustur_thread(pencere, klasor_adi, ayarlar, jeton):
    baglam = jeton.baglam
    try:
        klasor_adi = arsiv_klasor_adini_dogrula(klasor_adi, baglam["ozel_klasorler"])
        with ImapBaglantisi(ayarlar) as imap:
            hedef = imap_klasor_adi_hazirla(klasor_adi)
            tip, _veri = imap.create(hedef)
            if tip != "OK":
                raise MailHatasi("Arşiv klasörü oluşturulamadı.")
        gorev_icin_guvenli_call_after(jeton, ui.message, f"{klasor_adi} arşiv klasörü oluşturuldu.")
        gorev_icin_guvenli_call_after(jeton, _arsiv_yonetimi_sonrasi_klasorleri_guncelle, pencere, klasor_adi)
    except MailHatasi as e:
        hata_kaydet(str(e))
        gorev_icin_guvenli_call_after(jeton, ui.message, str(e))
    except Exception as e:
        hata_kaydet("Arşiv klasörü oluşturulamadı.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, "Arşiv klasörü oluşturulurken bir hata oluştu.")


def arsiv_klasoru_yeniden_adlandir(pencere, eski_ad, yeni_ad):
    baglam = _arsiv_gorev_baglami(pencere)
    ayarlar = dict(ayarlari_yukle())
    baglam["hesap"] = ayarlar.get("eposta", "")
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "arsiv_klasor_yonetimi", baglam)
    mesaj_soyle_ve_sonra_calistir(
        "Arşiv yeniden adlandırılıyor.",
        lambda: arka_planda_calistir(
            pencere.sunucudan_arsiv_yeniden_adlandir_thread,
            eski_ad,
            yeni_ad,
            ayarlar,
            jeton,
        ),
        ad="Arşiv yeniden adlandırma",
    )


def sunucudan_arsiv_yeniden_adlandir_thread(pencere, eski_ad, yeni_ad, ayarlar, jeton):
    baglam = jeton.baglam
    try:
        eski_ad = str(eski_ad or "").strip()
        if not eski_ad:
            raise MailHatasi("Arşiv adı boş olamaz.")
        yeni_ad = arsiv_klasor_adini_dogrula(yeni_ad, baglam["ozel_klasorler"], eski_ad)
        with ImapBaglantisi(ayarlar) as imap:
            eski_hedef = baglam["klasor_haritasi"].get(eski_ad, imap_klasor_adi_hazirla(eski_ad))
            yeni_hedef = imap_klasor_adi_hazirla(yeni_ad)
            tip, _veri = imap.rename(eski_hedef, yeni_hedef)
            if tip != "OK":
                raise MailHatasi("Arşiv klasörü yeniden adlandırılamadı.")
        try:
            klasoru_yerelde_pasif_yap(
                ayarlar.get("eposta", ""), eski_hedef
            )
        except Exception as e:
            hata_kaydet("Yeniden adlandırılan eski arşiv yerel veritabanında güncellenemedi.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, f"{eski_ad} arşivi {yeni_ad} olarak yeniden adlandırıldı.")
        gorev_icin_guvenli_call_after(jeton, _arsiv_yonetimi_sonrasi_klasorleri_guncelle, pencere, yeni_ad, eski_ad)
    except MailHatasi as e:
        hata_kaydet(str(e))
        gorev_icin_guvenli_call_after(jeton, ui.message, str(e))
    except Exception as e:
        hata_kaydet("Arşiv klasörü yeniden adlandırılamadı.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, "Arşiv klasörü yeniden adlandırılırken bir hata oluştu.")


def arsiv_klasoru_sil(pencere, klasor_adi):
    baglam = _arsiv_gorev_baglami(pencere)
    ayarlar = dict(ayarlari_yukle())
    baglam["hesap"] = ayarlar.get("eposta", "")
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "arsiv_klasor_yonetimi", baglam)
    mesaj_soyle_ve_sonra_calistir(
        "Arşiv siliniyor.",
        lambda: arka_planda_calistir(
            pencere.sunucudan_arsiv_sil_thread,
            klasor_adi,
            ayarlar,
            jeton,
        ),
        ad="Arşiv silme",
    )


def sunucudan_arsiv_sil_thread(pencere, klasor_adi, ayarlar, jeton):
    baglam = jeton.baglam
    try:
        with ImapBaglantisi(ayarlar) as imap:
            hedef = baglam["klasor_haritasi"].get(klasor_adi, imap_klasor_adi_hazirla(klasor_adi))
            tip, _veri = imap.delete(hedef)
            if tip != "OK":
                raise MailHatasi("Arşiv klasörü silinemedi.")
        try:
            klasoru_yerelde_pasif_yap(ayarlar.get("eposta", ""), hedef)
        except Exception as e:
            hata_kaydet("Silinen arşiv yerel veritabanında güncellenemedi.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, "Arşiv klasörü silindi.")
        gorev_icin_guvenli_call_after(jeton, pencere.arsiv_silindi_sonrasi_guncelle, klasor_adi)
    except MailHatasi as e:
        hata_kaydet(str(e))
        gorev_icin_guvenli_call_after(jeton, ui.message, str(e))
    except Exception as e:
        hata_kaydet("Arşiv klasörü silinemedi.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, baglanti_hatasi_kullanici_mesaji(e, "Silme işlemi sırasında bir hata oluştu."))


def sunucudan_ozel_arsivle(pencere, ids, hedef_isim, mevcut_klasor, ayarlar, jeton):
    baglam = jeton.baglam
    klasor_haritasi = baglam["klasor_haritasi"]
    kategori = baglam["kategori"]
    try:
        uidler = uid_kumesi_hazirla(ids, "Arşivlenecek e-posta bulunamadı.")
        adet = max(1, int(baglam.get("adet") or len(ids) or 1))
        konu = baglam.get("konu")
        tum_postalar = False
        hedef_klasor = klasor_haritasi.get(hedef_isim) or imap_klasor_adi_hazirla(hedef_isim)
        with ImapBaglantisi(ayarlar) as imap:
            imap_gmail_etiket_destegini_dogrula(imap)
            tip, _veri = imap.select(mevcut_klasor, readonly=False)
            imap_ok_mu(tip, "Kaynak klasör açılamadı.")

            hedef_etiket = gmail_etiket_ifadesi(hedef_isim, hedef_klasor, klasor_haritasi, kategori, mevcut_klasor)
            if not hedef_etiket:
                raise MailHatasi("Hedef arşiv etiketi hazırlanamadı.")
            gmail_etiket_ekle_ve_kaynak_kaldir(
                imap,
                uidler,
                hedef_etiket,
                mevcut_klasor,
                "E-postalar hedef arşiv etiketine eklenemedi.",
                "E-postalar kaynak etiketinden kaldırılamadı.",
                klasor_haritasi,
                baglam["ozel_klasorler"],
                kategori,
            )
            tum_postalar = tum_postalar_klasoru_mu(mevcut_klasor, klasor_haritasi)
        if tum_postalar:
            mesaj = _arsiv_basari_mesaji(adet, hedef_isim, konu, tum_postalar=True)
        else:
            mesaj = _arsiv_basari_mesaji(adet, hedef_isim, konu)
            try:
                klasor_uidlerini_pasif_yap(
                    ayarlar.get("eposta", ""), mevcut_klasor, ids
                )
            except Exception as e:
                hata_kaydet("Arşivlenen e-postalar yerel veritabanında güncellenemedi.", e)
            gorev_icin_guvenli_call_after(jeton, pencere.listeden_mesajlari_kaldir, ids)
        arka_planda_calistir(
            hedef_arsiv_onbellegini_guncelle,
            dict(ayarlar),
            hedef_isim,
            hedef_klasor,
        )
        gorev_icin_guvenli_call_after(jeton, ui.message, mesaj)
        gorev_icin_guvenli_call_after(jeton, pencere.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kategori, None, None, True)
    except MailHatasi as e:
        hata_kaydet(str(e))
        gorev_icin_guvenli_call_after(jeton, ui.message, str(e))
        gorev_icin_guvenli_call_after(jeton, pencere.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kategori, None, None, False)
    except Exception as e:
        hata_kaydet("Arşivleme işlemi başarısız oldu.", e)
        gorev_icin_guvenli_call_after(jeton, ui.message, "Arşivleme sırasında bir hata oluştu.")
        gorev_icin_guvenli_call_after(jeton, pencere.yenilemeyi_gecikmeli_tetikle, "Liste yenileniyor...", kategori, None, None, False)


def arsive_gonder_menu(pencere, event=None):
    if getattr(pencere, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
        ui.message("Arşivlemek için önce bir klasöre girin ve e-posta seçin.")
        return
    secili_idler = list(pencere.isaretliler)
    if not secili_idler:
        indeks = pencere.liste.GetFocusedItem()
        if indeks != -1 and indeks < len(pencere.mailler):
            secili_idler.append(pencere.mailler[indeks]["id"])
    if not secili_idler:
        ui.message("Lütfen arşive göndermek için e-posta seçin.")
        return
    pencere.arsiv_secim_goster(secimleri_uidlere_genislet(pencere.mailler, secili_idler))
