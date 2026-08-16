# -*- coding: utf-8 -*-
"""Başlangıç eşitlemesinin ağ ve sınır davranışları için bağımsız testler."""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock


EKLENTI_KOKU = pathlib.Path(__file__).resolve().parents[1]
MAIL_KOKU = EKLENTI_KOKU / "globalPlugins" / "mail"


class SahteZamanlayici:
    def __init__(self, gecikme, callback, args):
        self.gecikme = gecikme
        self.callback = callback
        self.args = args
        self.durduruldu = False

    def Stop(self):
        self.durduruldu = True


class SahteWx(types.ModuleType):
    def __init__(self):
        super().__init__("wx")
        self.zamanlayicilar = []
        self.call_after_cagrilari = []

    def CallLater(self, gecikme, callback, *args):
        zamanlayici = SahteZamanlayici(gecikme, callback, args)
        self.zamanlayicilar.append(zamanlayici)
        return zamanlayici

    def CallAfter(self, callback, *args):
        self.call_after_cagrilari.append((callback, args))
        return callback(*args)


def _modul(ad, **uyeler):
    sonuc = types.ModuleType(ad)
    for uye_adi, deger in uyeler.items():
        setattr(sonuc, uye_adi, deger)
    return sonuc


def startup_sync_yukle(
    imap_sinifi=None,
    ayarlar=None,
    silme_sonucu=None,
    onizleme=True,
    klasor_haritasi=None,
):
    wx = SahteWx()
    paket = _modul("mail")
    paket.__path__ = [str(MAIL_KOKU)]

    if imap_sinifi is None:
        class Imap:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def list(self):
                return "OK", [b"INBOX"]

            def select(self, _klasor, readonly=True):
                return "OK", [b"4"]

            def uid(self, *_args):
                return "OK", [b"1 2 3 4"]

        imap_sinifi = Imap

    ayarlar = ayarlar or {
        "eposta": "kullanici@example.com",
        "sifre": "uygulama-sifresi",
        "mesaj_sayisi": 2,
    }
    silme_sonucu = {} if silme_sonucu is None else silme_sonucu
    klasor_haritasi = klasor_haritasi or {"Gelen Kutusu": "INBOX"}

    baslik_esitle = Mock(return_value={"iptal_edildi": False})
    govde_esitle = Mock(return_value={"iptal_edildi": False})
    onizleme_esitle = Mock(return_value={"iptal_edildi": False})
    arka_plan = Mock(side_effect=lambda hedef, *args: hedef(*args))

    siniflandirma = {
        "wx": wx,
        "mail": paket,
        "mail.config": _modul(
            "mail.config",
            MESAJ_SAYISI_ALANI="mesaj_sayisi",
            VARSAYILAN_MESAJ_SAYISI=25,
            ayarlari_yukle=Mock(return_value=ayarlar),
            mesaj_sayisini_duzenle=lambda deger, varsayilan=25: max(1, min(100, int(deger or varsayilan))),
            onizleme_ayari_yukle=Mock(return_value=onizleme),
        ),
        "mail.folders": _modul(
            "mail.folders",
            SISTEM_KLASORLERI={"Gelen Kutusu"},
            imap_klasor_haritasi_olustur=Mock(return_value=(klasor_haritasi, [])),
            imap_liste_satiri_ayristir=Mock(return_value=(set(), "INBOX", "Gelen Kutusu")),
            imap_tirnakli_ham_ad=lambda ad: ad,
        ),
        "mail.body_sync": _modul("mail.body_sync", klasor_govdelerini_senkronize_et=govde_esitle),
        "mail.header_sync": _modul("mail.header_sync", klasor_basliklarini_senkronize_et=baslik_esitle),
        "mail.preview_sync": _modul("mail.preview_sync", klasor_onizlemelerini_senkronize_et=onizleme_esitle),
        "mail.imap_client": _modul(
            "mail.imap_client",
            ImapBaglantisi=lambda _ayarlar: imap_sinifi(),
            uidleri_ayristir=lambda _veri: ["1", "2", "3", "4"],
        ),
        "mail.logger": _modul("mail.logger", hata_kaydet=Mock(), uyari_kaydet=Mock()),
        "mail.ui_helpers": _modul("mail.ui_helpers", arka_planda_calistir=arka_plan),
        "mail.database_maintenance": _modul("mail.database_maintenance", temel_bakim_yap=Mock()),
        "mail.database": _modul("mail.database", veritabani_hazirla=Mock()),
        "mail.mail_store": _modul("mail.mail_store", hesap_klasor_envanterini_uzlastir=Mock()),
        "mail.pending_deletions": _modul(
            "mail.pending_deletions", bekleyen_silmeleri_isle=Mock(return_value=silme_sonucu)
        ),
        "mail.vendor": _modul(
            "mail.vendor",
            imaplib=types.SimpleNamespace(IMAP4=types.SimpleNamespace(abort=ConnectionError)),
        ),
    }
    eski_moduller = {ad: sys.modules.get(ad) for ad in siniflandirma}
    sys.modules.update(siniflandirma)
    try:
        sys.modules.pop("mail.startup_sync", None)
        spec = importlib.util.spec_from_file_location(
            "mail.startup_sync", MAIL_KOKU / "startup_sync.py"
        )
        modul = importlib.util.module_from_spec(spec)
        sys.modules["mail.startup_sync"] = modul
        spec.loader.exec_module(modul)
    finally:
        for ad, eski in eski_moduller.items():
            if eski is None:
                sys.modules.pop(ad, None)
            else:
                sys.modules[ad] = eski
    return modul, wx, baslik_esitle, govde_esitle, onizleme_esitle, arka_plan


class BaslangicSenkronizasyonTestleri(unittest.TestCase):
    def test_son_uidler_ayar_sayisiyla_sinirlanir(self):
        modul, *_ = startup_sync_yukle()
        self.assertEqual(["5", "4", "3"], modul.son_uidleri_sinirla(["1", "2", "3", "4", "5"], 3))
        self.assertEqual(["2", "1"], modul.son_uidleri_sinirla(["1", "2"], 25))

    def test_basliklar_tam_govde_ve_onizleme_sinirli_esitlenir(self):
        modul, _wx, baslik, govde, onizleme, _arka_plan = startup_sync_yukle()
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)
        yonetici._baslat()

        self.assertEqual(["1", "2", "3", "4"], baslik.call_args.kwargs["sunucu_uidleri"])
        self.assertEqual(["4", "3"], govde.call_args.kwargs["sunucu_uidleri"])
        self.assertEqual(["4", "3"], onizleme.call_args.kwargs["sunucu_uidleri"])
        self.assertTrue(yonetici._tamamlandi)
        self.assertFalse(yonetici._calisiyor)

    def test_ag_hatasi_bir_dakika_sonraya_yeniden_planlanir(self):
        class HataliImap:
            def __enter__(self):
                raise OSError("ag yok")

            def __exit__(self, *_args):
                return False

        modul, wx, *_ = startup_sync_yukle(imap_sinifi=HataliImap)
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)
        yonetici._baslat()

        self.assertFalse(yonetici._tamamlandi)
        self.assertFalse(yonetici._calisiyor)
        self.assertEqual(modul.BASLANGIC_SENKRONIZASYON_AG_YENIDEN_DENEME_MS, wx.zamanlayicilar[-1].gecikme)
        self.assertTrue(wx.call_after_cagrilari)

    def test_silme_kilidi_bes_saniye_sonraya_yeniden_planlanir(self):
        modul, wx, *_ = startup_sync_yukle(silme_sonucu={"kilitli": True})
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)
        yonetici._baslat()

        self.assertFalse(yonetici._tamamlandi)
        self.assertEqual(modul.BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS, wx.zamanlayicilar[-1].gecikme)

    def test_onbellek_siniri_sonraki_klasorlerde_govde_indirmesini_durdurur(self):
        modul, _wx, _baslik, govde, onizleme, _arka_plan = startup_sync_yukle(
            klasor_haritasi={
                "Gelen Kutusu": "INBOX",
                "Gönderilen E-postalar": '"[Gmail]/Sent Mail"',
            }
        )
        govde.return_value = {"iptal_edildi": False, "sinira_ulasti": True}
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)
        yonetici._baslat()

        self.assertEqual(1, govde.call_count)
        self.assertEqual(2, onizleme.call_count)
        self.assertTrue(yonetici._tamamlandi)

    def test_esitleme_kilidi_mesgulken_islem_yeniden_planlanir(self):
        modul, wx, baslik, govde, _onizleme, _arka_plan = startup_sync_yukle()
        baslik.return_value = {"iptal_edildi": False, "atlandi": True}
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)
        yonetici._baslat()

        self.assertEqual(0, govde.call_count)
        self.assertFalse(yonetici._tamamlandi)
        self.assertEqual(
            modul.BASLANGIC_SENKRONIZASYON_KILIT_YENIDEN_DENEME_MS,
            wx.zamanlayicilar[-1].gecikme,
        )

    def test_ayni_anda_ikinci_isci_baslatilmaz(self):
        modul, _wx, _baslik, _govde, _onizleme, arka_plan = startup_sync_yukle()
        bekleyen = []
        arka_plan.side_effect = lambda hedef, *args: bekleyen.append((hedef, args))
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(0)

        yonetici._baslat()
        yonetici._baslat()
        self.assertEqual(1, arka_plan.call_count)
        self.assertTrue(yonetici._calisiyor)

        hedef, args = bekleyen.pop()
        hedef(*args)
        self.assertTrue(yonetici._tamamlandi)
        self.assertFalse(yonetici._calisiyor)

    def test_durdurma_bekleyen_zamanlayiciyi_iptal_eder(self):
        modul, wx, *_ = startup_sync_yukle()
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(15000)
        zamanlayici = wx.zamanlayicilar[-1]

        yonetici.durdur()
        self.assertTrue(zamanlayici.durduruldu)
        self.assertTrue(yonetici._iptal.is_set())


if __name__ == "__main__":
    unittest.main()
