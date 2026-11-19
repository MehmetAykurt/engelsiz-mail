# -*- coding: utf-8 -*-
"""Taslak düzenleme, kaydetme, gönderme sonrası temizlik ve silme yardımcıları."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import gui
import ui
import wx

from ..config import ayarlari_yukle
from ..errors import MailHatasi
from ..folders import VARSAYILAN_KLASOR_HARITASI, imap_klasor_adi_hazirla
from ..imap_client import ImapBaglantisi, imap_uidleri_kalici_sil, uidleri_ayristir, imap_uidvalidity_al, imap_x_gm_msgid_haritasi_al
from ..mail_store import klasor_uidlerini_pasif_yap, mesaj_onbellek_kimligini_al
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


def _taslak_silme_gorevi_baslat(pencere, ids, klasor, basari_mesaji, kimlik=None):
    uidler = tuple(str(uid) for uid in ids or [])
    ayarlar = dict(ayarlari_yukle())
    baglam = {
        "hesap": ayarlar.get("eposta", ""),
        "kategori": str(getattr(pencere, "secili_kategori", "") or ""),
        "klasor": str(klasor or ""),
        "uidler": uidler,
        "taslak_kimlikleri": {str(uid): dict(kimlik) for uid in uidler} if kimlik else {},
    }
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "posta_degistirme", baglam)
    return arka_planda_calistir(pencere.sunucudan_taslak_sil, uidler, klasor, basari_mesaji, ayarlar, jeton)


def taslak_penceresini_ac(pencere, veri):
    if not pencere_kullanilabilir_mi(pencere):
        return

    if veri.get("zengin_icerik_var"):
        cevap = gui.messageBox(
            _("Bu taslak biçimlendirme (bağlantı, resim, başlık gibi) içeriyor. "
              "Eklentide düzenleyip kaydederseniz bu biçimlendirme kaybolur ve özgün taslak silinir.\n\n"
              "Yine de düzenlemek istiyor musunuz?"),
            _("Taslak biçimlendirmesi"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            pencere,
        )
        if cevap != wx.YES:
            try:
                pencere.liste.SetFocus()
            except Exception:
                pass
            return

    pencere_ref = {}

    def guncel_taslak():
        compose = pencere_ref.get("pencere")
        kimlik = dict(getattr(compose, "_sunucu_taslak_kimligi", {}) or veri.get("taslak_kimligi", {}))
        if not kimlik.get("uid"):
            kimlik["uid"] = str(veri.get("id", ""))
        klasor = str(getattr(compose, "_sunucu_taslak_klasoru", "") or veri.get("klasor", ""))
        return kimlik, klasor

    def taslagi_sil():
        kimlik, klasor = guncel_taslak()
        return pencere.taslak_sil_iste(kimlik.get("uid"), klasor, kimlik)

    def gonderimden_sonra_sil():
        kimlik, klasor = guncel_taslak()
        return pencere.taslak_gonderildi(kimlik.get("uid"), klasor, kimlik)

    taslak_penceresi = YeniPostaPenceresi(
        pencere,
        varsayilan_kime=veri.get("kime", ""),
        varsayilan_bilgi=veri.get("bilgi", ""),
        varsayilan_gizli=veri.get("gizli", ""),
        varsayilan_konu=veri.get("konu", ""),
        varsayilan_icerik=veri.get("icerik", ""),
        baslik=_("Engelsiz Mail - Taslak Düzenle"),
        gonderildi_callback=gonderimden_sonra_sil,
        taslak_sil_callback=taslagi_sil,
        taslak_kaydet_callback=lambda: pencere.taslak_kaydedildi(),
        taslak_otokayit_sil_callback=lambda kimlik, klasor: pencere.taslak_gonderildi(
            kimlik.get("uid"), klasor, kimlik
        ),
        taslak_klasor_adaylari=pencere.taslak_klasor_adaylari(veri.get("klasor")),
        taslak_kimligi={**dict(veri.get("taslak_kimligi") or {}), "uid": str(veri.get("id", ""))},
        taslak_klasoru=veri.get("klasor", ""),
        yanit_basliklari={ad: veri[alan] for ad, alan in (("In-Reply-To", "in_reply_to"), ("References", "references")) if veri.get(alan)},
        hazir_ekler=veri.get("ekler", []),
    )
    pencere_ref["pencere"] = taslak_penceresi
    guvenli_modal_goster(taslak_penceresi, pencere.liste, pencere)


def taslak_gonderildi(pencere, mail_id, kaynak_klasor, kimlik=None):
    if not mail_id:
        return False
    _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, _("Taslak kaldırıldı."), kimlik)
    return True


def taslak_kaydedildi(pencere, mail_id=None, kaynak_klasor=None, kimlik=None):
    """Yeni taslak kaydedildikten sonra eski taslağı kaldırır veya Taslaklar listesini yeniler."""
    setattr(pencere, "_taslaklar_sunucudan_yenilensin", True)
    eski_taslak_var = bool(mail_id)
    if eski_taslak_var:
        _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, "", kimlik)
        return True

    if pencere.secili_kategori == "Taslaklar" and pencere.hesap_bilgisi_var_mi():
        pencere.yenilemeyi_gecikmeli_tetikle(None, pencere.secili_kategori, None, None, True)
    if pencere.hesap_bilgisi_var_mi():
        _taslak_sayilarini_yenile(pencere)
    return False


def taslak_sil_iste(pencere, mail_id, kaynak_klasor, kimlik=None):
    if not mail_id:
        ui.message(_("Silinecek taslak bulunamadı."))
        return False
    if not pencere.taslak_silme_onayi_al():
        pencere.liste.SetFocus()
        return False
    mesaj_soyle_ve_sonra_calistir(
        _("Taslak siliniyor."),
        lambda: _taslak_silme_gorevi_baslat(pencere, [mail_id], kaynak_klasor, "", kimlik),
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
        raise MailHatasi(_("Taslak UID listesi doğrulanamadı."))
    bulunanlar = {str(uid) for uid in uidleri_ayristir(veri)}
    return uid_kumesi.intersection(bulunanlar)


def sunucudan_taslak_sil(pencere, ids, klasor, basari_mesaji="", ayarlar=None, jeton=None):
    ayarlar = dict(ayarlar or ayarlari_yukle())
    kategori = jeton.baglam["kategori"] if jeton is not None else pencere.secili_kategori
    try:
        uidler = [str(uid) for uid in ids if str(uid or "").isdigit()]
        if not uidler or not klasor:
            raise MailHatasi(_("Silinecek taslak bulunamadı."))
        baglam = jeton.baglam if jeton is not None else {}
        beklenenler = dict(baglam.get("taslak_kimlikleri") or {})
        for uid in uidler:
            if uid not in beklenenler:
                beklenenler[uid] = mesaj_onbellek_kimligini_al(ayarlar.get("eposta", ""), klasor, uid)
            kimlik = beklenenler[uid]
            if not kimlik or not kimlik.get("gmail_message_id") or not int(kimlik.get("uidvalidity") or 0):
                raise MailHatasi(_("Taslak kimliği doğrulanamadığı için eski taslak korunuyor. Listeyi yenileyip yeniden deneyin."))
        with ImapBaglantisi(ayarlar) as imap:
            # A UID is never searched in another folder, even if its numeric value matches.
            tip, _secim = imap.select(klasor, readonly=False)
            if tip != "OK":
                raise MailHatasi(_("Taslak klasörü açılamadı."))
            uidvalidity = imap_uidvalidity_al(imap)
            if any(uidvalidity != int(k["uidvalidity"]) for k in beklenenler.values()):
                raise MailHatasi(_("Taslak klasörünün kimliği değişti; güvenli silme durduruldu."))
            mevcut = uidleri_klasorde_ara(imap, uidler)
            if mevcut != set(uidler):
                raise MailHatasi(_("Taslak özgün klasöründe bulunamadı; başka klasörde silme denenmedi."))
            gercek_idler = imap_x_gm_msgid_haritasi_al(imap, uidler)
            if any(str(gercek_idler.get(uid)) != str(beklenenler[uid]["gmail_message_id"]) for uid in uidler):
                raise MailHatasi(_("Taslağın Gmail ileti kimliği değişti; güvenli silme durduruldu."))
            imap_uidleri_kalici_sil(imap, ",".join(uidler), _("Taslak kalıcı olarak kaldırılamadı."))
            tip, _secim = imap.select(klasor, readonly=False)
            if tip != "OK" or imap_uidvalidity_al(imap) != uidvalidity:
                raise MailHatasi(_("Taslak silme sonucu doğrulanamadı. Eski taslağın durumu korunuyor."))
            if uidleri_klasorde_ara(imap, uidler):
                raise MailHatasi(_("Taslak silme sonrasında hâlâ görünüyor."))
        klasor_uidlerini_pasif_yap(ayarlar.get("eposta", ""), klasor, uidler)
        if basari_mesaji:
            gorev_veya_pencere_icin_call_after(pencere, jeton, ui.message, basari_mesaji)
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.listeden_mesajlari_kaldir, uidler)
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.yenilemeyi_gecikmeli_tetikle, None, kategori, None, None, True)
        gorev_veya_pencere_icin_call_after(pencere, jeton, _taslak_sayilarini_yenile, pencere)
    except Exception as e:
        hata_kaydet("Taslak silme tamamlanamadı.", e)
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.silme_hatasi_penceresi_goster, str(e), _("Taslak Silinemedi"))
        gorev_veya_pencere_icin_call_after(pencere, jeton, pencere.yenilemeyi_gecikmeli_tetikle, None, kategori, None, None, True)
