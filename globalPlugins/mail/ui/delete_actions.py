# -*- coding: utf-8 -*-
"""E-posta ve taslak silme işlemleri için yardımcılar."""

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

from ..config import (
    ayarlari_yukle,
    silme_onayi_ayari_yukle,
    silme_onayi_ayari_kaydet,
    kalici_silme_onayi_ayari_yukle,
    kalici_silme_onayi_ayari_kaydet,
)
from ..folders import VARSAYILAN_KLASOR_HARITASI
from ..logger import hata_kaydet
from ..text_utils import konu_gosterimini_duzenle
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..pending_deletions import (
    bekleyen_silmeleri_isle,
    silme_isteklerini_kuyruga_al,
)
from ..ui_helpers import (
    arka_plan_gorev_jetonu_olustur,
    arka_planda_calistir,
    guvenli_call_after,
)
from .archive_dialogs import KaliciSilmeOnayiPenceresi
from .folder_view import LISTE_MODU_EPOSTA
from ..conversation import secimleri_uidlere_genislet


def _degistirme_gorevi_baslat(pencere, hedef, ids, klasor, *ek_argumanlar):
    """Silme/taslak işlemini değişmez hesap ve seçim kopyasıyla başlatır."""
    uidler = tuple(str(uid) for uid in ids or [])
    ayarlar = dict(ayarlari_yukle())
    baglam = {
        "hesap": ayarlar.get("eposta", ""),
        "kategori": str(getattr(pencere, "secili_kategori", "") or ""),
        "klasor": str(klasor or ""),
        "uidler": uidler,
    }
    jeton = arka_plan_gorev_jetonu_olustur(pencere, "posta_degistirme", baglam)
    return arka_planda_calistir(hedef, uidler, klasor, *ek_argumanlar, ayarlar, jeton)


def _silme_gorevi_baslat(pencere, hedef, ids, klasor, *ek_argumanlar):
    listeden_mesajlari_kaldir(pencere, ids)
    return _degistirme_gorevi_baslat(pencere, hedef, ids, klasor, *ek_argumanlar)


def silme_hatasi_penceresi_goster(pencere, mesaj, baslik=_("Silme hatası")):
    try:
        gui.messageBox(
            str(mesaj or _("E-posta silinemedi.")),
            baslik,
            wx.OK | wx.ICON_ERROR,
            pencere,
        )
    except Exception as e:
        hata_kaydet("Silme hatası penceresi gösterilemedi.", e)
        ui.message(str(mesaj or _("E-posta silinemedi.")))


def _eposta_silme_istegini_kaydet(pencere, ids, klasor, kalici=False, ayarlar=None):
    """İsteği ve yerel gizlemeyi tek veritabanı işlemiyle kalıcılaştırır."""
    ayarlar = dict(ayarlar or ayarlari_yukle())
    eposta = str(ayarlar.get("eposta", "") or "").strip()
    kategori = str(getattr(pencere, "secili_kategori", "") or "")
    cop = pencere.klasor_haritasi.get(
        "Çöp Kutusu", VARSAYILAN_KLASOR_HARITASI["Çöp Kutusu"]
    )
    islem_turu = "permanent" if kalici or str(klasor) == str(cop) else "trash"
    kaynak_etiketi = ""
    kaynak_etiketi_kaldir = False
    if islem_turu == "trash":
        kaynak_kategori = pencere.kategori_adini_klasorden_bul(klasor)
        kaynak_etiketi_kaldir = pencere.kaynak_etiketi_kaldirilabilir_mi(
            klasor, kaynak_kategori
        )
        if kaynak_etiketi_kaldir:
            kaynak_etiketi = pencere.gmail_etiket_ifadesi(kaynak_kategori, klasor)
    silme_isteklerini_kuyruga_al(
        eposta,
        klasor,
        kategori,
        ids,
        islem_turu,
        cop,
        kaynak_etiketi,
        kaynak_etiketi_kaldir,
    )
    return ayarlar, eposta


def _eposta_silme_istegini_baslat(pencere, ids, klasor, kalici=False):
    """İsteği diske yazdıktan sonra listeyi günceller ve sessiz sunucu denemesi başlatır."""
    try:
        ayarlar, eposta = _eposta_silme_istegini_kaydet(
            pencere, ids, klasor, kalici=kalici
        )
    except Exception as e:
        hata_kaydet("Silme isteği yerel kuyruğa kaydedilemedi.", e)
        silme_hatasi_penceresi_goster(
            pencere,
            _("Silme işlemi yerel olarak kaydedilemedi."),
            _("E-posta Silinemedi"),
        )
        return False
    listeden_mesajlari_kaldir(pencere, ids)
    arka_planda_calistir(
        _silme_kuyrugunu_isle_ve_yenile,
        pencere,
        ayarlar,
        eposta,
        str(getattr(pencere, "secili_kategori", "") or ""),
    )
    return True


def _silme_sonrasi_arayuzu_yenile(pencere, kaynak_kategori):
    """Kaynak klasörü geri açmadan sayaçları ve görünür listeyi sessizce doğrular."""
    hedef_kategoriler = list(
        dict.fromkeys(
            kategori
            for kategori in (
                str(kaynak_kategori or "").strip(),
                "Çöp Kutusu",
                "Tüm Postalar",
            )
            if kategori
        )
    )
    try:
        pencere.sistem_klasor_sayilarini_guncelle_tetikle(hedef_kategoriler)
    except Exception as e:
        hata_kaydet("Silme sonrası klasör sayıları yenilenemedi.", e)
    if (
        getattr(pencere, "liste_modu", LISTE_MODU_EPOSTA) == LISTE_MODU_EPOSTA
        and str(getattr(pencere, "secili_kategori", "") or "")
        == str(kaynak_kategori or "")
    ):
        pencere.yenilemeyi_gecikmeli_tetikle(
            None, kaynak_kategori, None, None, True, 1500
        )
    try:
        wx.CallLater(
            5000,
            pencere.sistem_klasor_sayilarini_guncelle_tetikle,
            hedef_kategoriler,
        )
    except Exception as e:
        hata_kaydet("Silme sonrası gecikmeli sayaç doğrulaması başlatılamadı.", e)


def _silme_kuyrugunu_isle_ve_yenile(pencere, ayarlar, eposta, kaynak_kategori):
    sonuc = bekleyen_silmeleri_isle(ayarlar, eposta)
    guvenli_call_after(
        pencere,
        _silme_sonrasi_arayuzu_yenile,
        pencere,
        kaynak_kategori,
    )
    return sonuc


def taslak_silme_onayi_al(pencere, adet=1):
    if not silme_onayi_ayari_yukle():
        return True
    soru = (
        _("Bu taslağı kalıcı olarak silmek istiyor musunuz?")
        if adet == 1
        else _('Seçili {0} taslağı kalıcı olarak silmek istiyor musunuz?').format(adet)
    )
    return gui.messageBox(
        soru,
        _("Taslak silme onayı"),
        wx.YES_NO | wx.ICON_WARNING,
    ) == wx.YES


def mail_konusunu_bul(pencere, mail_id):
    hedef = str(mail_id or "")
    for mesaj in pencere.mailler:
        if str(mesaj.get("id", "")) == hedef:
            konu = str(mesaj.get("konu", "")).strip()
            return konu or "Konusuz"
    return "Konusuz"


def konu_ifadesi(konu):
    konu = konu_gosterimini_duzenle(str(konu or "").strip() or "Konusuz")
    return f"{konu} konulu"


class SilmeOnayiPenceresi(wx.Dialog):
    def __init__(self, parent, soru, baslik=_("Silme onayı")):
        super().__init__(parent, title=baslik)
        ana_duzen = wx.BoxSizer(wx.VERTICAL)
        metin = wx.StaticText(self, label=str(soru or ""))
        try:
            metin.Wrap(560)
        except Exception:
            pass
        ana_duzen.Add(metin, 0, wx.ALL | wx.EXPAND, 10)

        self.bir_daha_gosterme = wx.CheckBox(self, label=_("Bu uyarıyı bir daha gösterme"))
        ana_duzen.Add(self.bir_daha_gosterme, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dugme_duzen = wx.BoxSizer(wx.HORIZONTAL)
        evet_btn = wx.Button(self, wx.ID_YES, label=_("&Evet"))
        hayir_btn = wx.Button(self, wx.ID_NO, label=_("&Hayır"))
        evet_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_YES))
        hayir_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_NO))
        dugme_duzen.Add(evet_btn, 0, wx.ALL, 5)
        dugme_duzen.Add(hayir_btn, 0, wx.ALL, 5)
        ana_duzen.Add(dugme_duzen, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.SetSizerAndFit(ana_duzen)
        self.SetEscapeId(wx.ID_NO)
        try:
            hayir_btn.SetDefault()
        except Exception:
            pass
        self.CenterOnParent()
        wx.CallAfter(hayir_btn.SetFocus)

    def bir_daha_gosterme_secili_mi(self):
        try:
            return bool(self.bir_daha_gosterme.GetValue())
        except Exception:
            return False


def silme_onayi_al(pencere, adet, kaynak_klasor, konu=None):
    if not silme_onayi_ayari_yukle():
        return True
    if pencere.taslak_klasoru_mu(kaynak_klasor):
        return taslak_silme_onayi_al(pencere, adet)
    konu_etiketi = konu_ifadesi(konu) if adet == 1 and konu else _("Seçili")
    if pencere.cop_klasoru_mu(kaynak_klasor):
        soru = (
            _('{0} e-posta Çöp Kutusundan kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} e-posta Çöp Kutusundan kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(adet)
        )
        baslik = _("Kalıcı silme onayı")
    elif pencere.spam_klasoru_mu(kaynak_klasor):
        soru = (
            _('{0} spam e-postası Çöp Kutusuna taşınacaktır. Devam etmek istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} spam e-postası Çöp Kutusuna taşınacaktır. Devam etmek istiyor musunuz?').format(adet)
        )
        baslik = _("Spam silme uyarısı")
    elif pencere.tum_postalar_klasoru_mu(kaynak_klasor):
        soru = (
            _('{0} e-posta Tüm Postalar klasöründen Çöp Kutusuna taşınacaktır. Bu işlem, Gmail hesabınızda e-postayı Çöp Kutusuna taşıyabilir. Devam etmek istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} e-posta Tüm Postalar klasöründen Çöp Kutusuna taşınacaktır. Bu işlem, Gmail hesabınızda e-postaları Çöp Kutusuna taşıyabilir. Devam etmek istiyor musunuz?').format(adet)
        )
        baslik = _("Tüm Postalar silme uyarısı")
    else:
        soru = (
            _('{0} e-postayı Çöp Kutusuna taşımak istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} e-postayı Çöp Kutusuna taşımak istiyor musunuz?').format(adet)
        )
        baslik = _("Silme onayı")
    onay_penceresi = SilmeOnayiPenceresi(pencere, soru, baslik)
    sonuc = wx.ID_NO
    bir_daha_gosterme = False
    try:
        sonuc = onay_penceresi.ShowModal()
        bir_daha_gosterme = onay_penceresi.bir_daha_gosterme_secili_mi()
    finally:
        try:
            onay_penceresi.Destroy()
        except Exception as e:
            hata_kaydet("Silme onayı penceresi kapatılamadı.", e)
        try:
            pencere.liste.SetFocus()
        except Exception:
            pass
    if sonuc != wx.ID_YES:
        return False
    if bir_daha_gosterme and silme_onayi_ayari_kaydet(False):
        try:
            pencere.silme_onayi_menu_durumunu_guncelle(normal=False)
        except Exception as e:
            hata_kaydet("Silme onayı menü durumu güncellenemedi.", e)
    return True


def kalici_silme_onayi_al(pencere, adet, kaynak_klasor, konu=None):
    if not kalici_silme_onayi_ayari_yukle():
        return True

    konu_etiketi = konu_ifadesi(konu) if adet == 1 and konu else _("Seçili")
    if pencere.taslak_klasoru_mu(kaynak_klasor):
        soru = (
            _('{0} taslak kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} taslak kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(adet)
        )
    else:
        soru = (
            _('{0} e-posta kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(konu_etiketi)
            if adet == 1
            else _('Seçili {0} e-posta kalıcı olarak silinecektir. Devam etmek istiyor musunuz?').format(adet)
        )

    onay_penceresi = KaliciSilmeOnayiPenceresi(pencere, soru)
    sonuc = wx.ID_CANCEL
    bir_daha_gosterme = False
    try:
        sonuc = onay_penceresi.ShowModal()
        bir_daha_gosterme = onay_penceresi.bir_daha_gosterme_secili_mi()
    finally:
        try:
            onay_penceresi.Destroy()
        except Exception as e:
            hata_kaydet("Kalıcı silme onayı penceresi kapatılamadı.", e)
        try:
            pencere.liste.SetFocus()
        except Exception:
            pass

    if sonuc != wx.ID_YES:
        return False
    if bir_daha_gosterme and kalici_silme_onayi_ayari_kaydet(False):
        try:
            pencere.silme_onayi_menu_durumunu_guncelle(kalici=False)
        except Exception as e:
            hata_kaydet("Kalıcı silme onayı menü durumu güncellenemedi.", e)
    return True


def tek_mesaj_sil(pencere, mail_id, kaynak_klasor=None, konu=None):
    kaynak_klasor = kaynak_klasor or pencere.aktif_klasor()
    if not mail_id:
        ui.message(_("Silinecek e-posta bulunamadı."))
        return False
    if pencere.taslak_klasoru_mu(kaynak_klasor):
        if not taslak_silme_onayi_al(pencere, 1):
            pencere.liste.SetFocus()
            return False
        mesaj_soyle_ve_sonra_calistir(
            _("Taslak siliniyor."),
            lambda: _silme_gorevi_baslat(
                pencere,
                pencere.sunucudan_taslak_sil,
                [mail_id],
                kaynak_klasor,
                "",
            ),
            ad="Taslak silme",
        )
        return True
    silinecek_konu = konu or mail_konusunu_bul(pencere, mail_id)
    if not silme_onayi_al(pencere, 1, kaynak_klasor, silinecek_konu):
        return False
    return _eposta_silme_istegini_baslat(pencere, [mail_id], kaynak_klasor)


def konusma_sil(pencere, mail_ids, kaynak_klasor=None, konu=None):
    """Okuma penceresindeki konuşmanın bütün iletilerini birlikte siler."""
    kaynak_klasor = kaynak_klasor or pencere.aktif_klasor()
    uidler = list(dict.fromkeys(str(uid) for uid in (mail_ids or []) if str(uid)))
    if not uidler:
        ui.message(_("Silinecek e-posta bulunamadı."))
        return False
    if len(uidler) == 1:
        return tek_mesaj_sil(pencere, uidler[0], kaynak_klasor, konu)
    if not silme_onayi_al(pencere, len(uidler), kaynak_klasor, konu):
        return False
    return _eposta_silme_istegini_baslat(pencere, uidler, kaynak_klasor)


def secili_eposta_idlerini_al(pencere):
    if getattr(pencere, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
        return []
    secili_idler = list(pencere.isaretliler)
    if not secili_idler:
        indeks = pencere.liste.GetFocusedItem()
        if indeks != -1 and indeks < len(pencere.mailler):
            secili_idler.append(pencere.mailler[indeks]["id"])
    return secimleri_uidlere_genislet(pencere.mailler, secili_idler)


def posta_sil(pencere, event=None):
    secili_idler = secili_eposta_idlerini_al(pencere)
    if not secili_idler:
        ui.message(_("Lütfen silmek için e-posta seçin."))
        return

    adet = len(secili_idler)
    kaynak_klasor = pencere.aktif_klasor()
    if pencere.taslak_klasoru_mu(kaynak_klasor):
        if not taslak_silme_onayi_al(pencere, adet):
            pencere.liste.SetFocus()
            return
        mesaj_soyle_ve_sonra_calistir(
            _("Taslak siliniyor.") if adet == 1 else _("Taslaklar siliniyor."),
            lambda: _silme_gorevi_baslat(
                pencere,
                pencere.sunucudan_taslak_sil,
                secili_idler,
                kaynak_klasor,
                "",
            ),
            ad="Taslak silme",
        )
        return

    silinecek_konu = mail_konusunu_bul(pencere, secili_idler[0]) if adet == 1 else None
    if not silme_onayi_al(pencere, adet, kaynak_klasor, silinecek_konu):
        pencere.liste.SetFocus()
        return

    _eposta_silme_istegini_baslat(pencere, secili_idler, kaynak_klasor)


def posta_kalici_sil(pencere, event=None):
    secili_idler = secili_eposta_idlerini_al(pencere)
    if not secili_idler:
        ui.message(_("Lütfen kalıcı olarak silmek için e-posta seçin."))
        return

    adet = len(secili_idler)
    kaynak_klasor = pencere.aktif_klasor()
    silinecek_konu = mail_konusunu_bul(pencere, secili_idler[0]) if adet == 1 else None
    if not kalici_silme_onayi_al(pencere, adet, kaynak_klasor, silinecek_konu):
        pencere.liste.SetFocus()
        return

    if pencere.taslak_klasoru_mu(kaynak_klasor):
        basari_mesaji = ""
        _silme_gorevi_baslat(pencere, pencere.sunucudan_taslak_sil, secili_idler, kaynak_klasor, basari_mesaji)
        return

    _eposta_silme_istegini_baslat(
        pencere, secili_idler, kaynak_klasor, kalici=True
    )


def listeden_mesajlari_kaldir(pencere, ids):
    id_kumesi = {str(uid) for uid in ids}
    silinecek_indeksler = [
        i
        for i, mesaj in enumerate(pencere.mailler)
        if str(mesaj.get("id", "")) in id_kumesi
        or bool(
            id_kumesi.intersection(
                str(uid) for uid in (mesaj.get("ids") or [])
            )
        )
    ]
    hedef_indeks = min(silinecek_indeksler) if silinecek_indeksler else pencere.liste.GetFocusedItem()
    for indeks in reversed(silinecek_indeksler):
        try:
            pencere.liste.DeleteItem(indeks)
        except Exception:
            pass
        del pencere.mailler[indeks]
    pencere.isaretliler.difference_update(id_kumesi)
    if not pencere.mailler:
        pencere.liste_bilgi_satiri_goster(_("Bu klasörde gösterilecek e-posta yok."))
    else:
        try:
            secili_sayi = pencere.liste.GetSelectedItemCount()
        except Exception:
            secili_sayi = 0
        if secili_sayi > 0:
            hedef_indeks = max(0, min(int(hedef_indeks), len(pencere.mailler) - 1))
            try:
                odak_indeksi = pencere.liste.GetFocusedItem()
                if odak_indeksi < 0 or odak_indeksi >= len(pencere.mailler):
                    pencere.liste.Focus(hedef_indeks)
                pencere.liste.EnsureVisible(hedef_indeks)
            except Exception:
                pass
            wx.CallAfter(pencere.liste.SetFocus)
        else:
            pencere.liste_secim_ver(hedef_indeks)


def sunucudan_sil(pencere, ids, klasor, ayarlar=None, jeton=None):
    # Eski çağrı noktaları için uyumluluk: yeni yol kalıcı kuyruğu kullanır.
    ayarlar, eposta = _eposta_silme_istegini_kaydet(
        pencere, ids, klasor, kalici=False, ayarlar=ayarlar
    )
    return bekleyen_silmeleri_isle(ayarlar, eposta)


def sunucudan_kalici_sil(pencere, ids, klasor, ayarlar=None, jeton=None):
    ayarlar, eposta = _eposta_silme_istegini_kaydet(
        pencere, ids, klasor, kalici=True, ayarlar=ayarlar
    )
    return bekleyen_silmeleri_isle(ayarlar, eposta)
