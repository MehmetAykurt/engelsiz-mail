# -*- coding: utf-8 -*-
"""Taslak düzenleme, kaydetme, gönderme sonrası temizlik ve silme yardımcıları."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import ui
import wx

from ..config import ayarlari_yukle
from ..errors import MailHatasi
from ..folders import VARSAYILAN_KLASOR_HARITASI, imap_klasor_adi_hazirla
from ..imap_client import ImapBaglantisi, imap_uidleri_kalici_sil, uidleri_ayristir
from ..mail_store import klasor_uidlerini_pasif_yap
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_planda_calistir,
    gorev_veya_pencere_icin_call_after,
    guvenli_modal_goster,
    pencere_kullanilabilir_mi,
)
from .compose_window import YeniPostaPenceresi


def _taslak_sayilarini_yenile(pencere):
    hedefler = ["Taslaklar", "Tüm Postalar"]
    pencere.sistem_klasor_sayilarini_guncelle_tetikle(hedefler)
    wx.CallLater(
        5000,
        pencere.sistem_klasor_sayilarini_guncelle_tetikle,
        hedefler,
    )


def _taslak_silme_gorevi_baslat(pencere, ids, klasor, basari_mesaji):
    uidler = tuple(str(uid) for uid in ids or [])
    ayarlar = dict(ayarlari_yukle())
    baglam = {
        "hesap": ayarlar.get("eposta", ""),
        "kategori": str(getattr(pencere, "secili_kategori", "") or ""),
        "klasor": str(klasor or ""),
        "uidler": uidler,
    }
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "posta_degistirme", baglam)
    return arka_planda_calistir(pencere.sunucudan_taslak_sil, uidler, klasor, basari_mesaji, ayarlar, jeton)


def taslak_penceresini_ac(pencere, veri):
    if not pencere_kullanilabilir_mi(pencere):
        return

    taslak_penceresi = YeniPostaPenceresi(
        pencere,
        varsayilan_kime=veri.get("kime", ""),
        varsayilan_bilgi=veri.get("bilgi", ""),
        varsayilan_gizli=veri.get("gizli", ""),
        varsayilan_konu=veri.get("konu", ""),
        varsayilan_icerik=veri.get("icerik", ""),
        baslik=_("Engelsiz Mail - Taslak Düzenle"),
        gonderildi_callback=lambda: pencere.taslak_gonderildi(veri.get("id"), veri.get("klasor")),
        taslak_sil_callback=lambda: pencere.taslak_sil_iste(veri.get("id"), veri.get("klasor")),
        taslak_kaydet_callback=lambda: pencere.taslak_kaydedildi(veri.get("id"), veri.get("klasor")),
        taslak_klasor_adaylari=pencere.taslak_klasor_adaylari(veri.get("klasor")),
        hazir_ekler=veri.get("ekler", []),
    )
    guvenli_modal_goster(taslak_penceresi, pencere.liste, pencere)


def taslak_gonderildi(pencere, mail_id, kaynak_klasor):
    if not mail_id:
        return False
    _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, _("Taslak kaldırıldı."))
    return True


def taslak_kaydedildi(pencere, mail_id=None, kaynak_klasor=None):
    """Yeni taslak kaydedildikten sonra eski taslağı kaldırır veya Taslaklar listesini yeniler."""
    setattr(pencere, "_taslaklar_sunucudan_yenilensin", True)
    eski_taslak_var = bool(mail_id)
    if eski_taslak_var:
        _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, "")
        return True

    if pencere.secili_kategori == "Taslaklar" and pencere.hesap_bilgisi_var_mi():
        pencere.yenilemeyi_gecikmeli_tetikle(None, pencere.secili_kategori, None, None, True)
    if pencere.hesap_bilgisi_var_mi():
        _taslak_sayilarini_yenile(pencere)
    return False


def taslak_sil_iste(pencere, mail_id, kaynak_klasor):
    if not mail_id:
        ui.message(_("Silinecek taslak bulunamadı."))
        return False
    if not pencere.taslak_silme_onayi_al():
        pencere.liste.SetFocus()
        return False
    mesaj_soyle_ve_sonra_calistir(
        _("Taslak siliniyor."),
        lambda: _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, ""),
        ad="Taslak silme",
    )
    return True


def taslak_klasor_adaylari(pencere, kaynak_klasor=None):
    adaylar = []

    def ekle(deger):
        deger = str(deger or "").strip()
        if deger and deger not in adaylar:
            adaylar.append(deger)

    ekle(kaynak_klasor)
    ekle(pencere.klasor_haritasi.get("Taslaklar"))
    ekle(VARSAYILAN_KLASOR_HARITASI.get("Taslaklar"))
    ekle('"[Gmail]/Drafts"')
    ekle('"[Google Mail]/Drafts"')
    ekle(imap_klasor_adi_hazirla("Taslaklar"))
    ekle(imap_klasor_adi_hazirla("Drafts"))
    return adaylar


def uidleri_klasorde_ara(imap, uidler):
    uid_kumesi = {str(uid) for uid in uidler if str(uid or "").strip()}
    if not uid_kumesi:
        return set()
    uid_araligi = ",".join(sorted(uid_kumesi, key=lambda x: int(x) if x.isdigit() else x))
    tip, veri = imap.uid("SEARCH", "UID", uid_araligi)
    if tip != "OK":
        return set()
    bulunanlar = {str(uid) for uid in uidleri_ayristir(veri)}
    return uid_kumesi.intersection(bulunanlar)


def sunucudan_taslak_sil(pencere, ids, klasor, basari_mesaji="", ayarlar=None, jeton=None):
    ayarlar = dict(ayarlar or ayarlari_yukle())
    kategori = jeton.baglam["kategori"] if jeton is not None else pencere.secili_kategori
    try:
        uidler = [str(uid) for uid in ids if str(uid or "").strip()]
        if not uidler:
            raise MailHatasi(_("Silinecek taslak bulunamadı."))

        silindi = False
        silinen_klasor = None
        silinen_uidler = set()
        son_hata = ""
        with ImapBaglantisi(ayarlar) as imap:
            for aday_klasor in pencere.taslak_klasor_adaylari(klasor):
                try:
                    tip, _veri = imap.select(aday_klasor, readonly=False)
                    if tip != "OK":
                        son_hata = _('Taslaklar klasörü açılamadı: {0}').format(aday_klasor)
                        continue

                    mevcut_uidler = uidleri_klasorde_ara(imap, uidler)
                    if not mevcut_uidler:
                        son_hata = _('Taslak UID bu klasörde bulunamadı: {0}').format(aday_klasor)
                        continue

                    uid_seti = ",".join(sorted(mevcut_uidler, key=lambda x: int(x) if x.isdigit() else x))
                    try:
                        imap_uidleri_kalici_sil(imap, uid_seti, _('Taslak kalıcı olarak kaldırılamadı: {0}').format(aday_klasor))
                    except MailHatasi as e:
                        son_hata = str(e)
                        continue

                    try:
                        imap.select(aday_klasor, readonly=False)
                        kalan_uidler = uidleri_klasorde_ara(imap, mevcut_uidler)
                    except Exception:
                        kalan_uidler = set()

                    if not kalan_uidler:
                        silindi = True
                        silinen_klasor = aday_klasor
                        silinen_uidler = set(mevcut_uidler)
                        break

                    son_hata = _('Taslak silme sonrasında hâlâ görünüyor: {0}').format(aday_klasor)
                except Exception as e:
                    son_hata = _('Taslak silme denemesi başarısız: {0}').format(aday_klasor)
                    hata_kaydet(son_hata, e)
                    continue

        if not silindi:
            hata_kaydet(son_hata or "Taslak silinemedi.")
            raise MailHatasi(_("Taslak, Gmail tarafından kaldırılmadı. Liste yenileniyor."))

        try:
            klasor_uidlerini_pasif_yap(
                ayarlar.get("eposta", ""), silinen_klasor or klasor, silinen_uidler or uidler
            )
        except Exception as e:
            hata_kaydet("Silinen taslaklar yerel veritabanında güncellenemedi.", e)

        if basari_mesaji:
            gorev_veya_pencere_icin_call_after(pencere, jeton, ui.message, basari_mesaji)
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.listeden_mesajlari_kaldir, uidler)
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.yenilemeyi_gecikmeli_tetikle, None, kategori, None, None, True)
        gorev_veya_pencere_icin_call_after(
            pencere, jeton, _taslak_sayilarini_yenile, pencere
        )
    except MailHatasi as e:
        hata_kaydet(str(e))
        gorev_veya_pencere_icin_call_after(
            pencere,
            jeton,
            pencere.silme_hatasi_penceresi_goster,
            str(e),
            _("Taslak Silinemedi"),
        )
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.yenilemeyi_gecikmeli_tetikle, None, kategori, None, None, True)
    except Exception as e:
        hata_kaydet("Taslak silinemedi.", e)
        gorev_veya_pencere_icin_call_after(
            pencere,
            jeton,
            pencere.silme_hatasi_penceresi_goster,
            _("Taslak silinemedi."),
            _("Taslak Silinemedi"),
        )
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.yenilemeyi_gecikmeli_tetikle, None, kategori, None, None, True)
