# -*- coding: utf-8 -*-
"""Üçüncü aşamadaki MIME, klasör listesi ve adres geçmişi düzeltmeleri."""

import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock


MAIL_KOKU = pathlib.Path(__file__).resolve().parents[1] / "globalPlugins" / "mail"


def _modul(ad, **uyeler):
    sonuc = types.ModuleType(ad)
    for uye_adi, deger in uyeler.items():
        setattr(sonuc, uye_adi, deger)
    return sonuc


def _modulu_yukle(ad, yol, sahteler):
    paket = _modul("mail")
    paket.__path__ = [str(MAIL_KOKU)]
    tum_sahteler = {"mail": paket, **sahteler}
    eskiler = {modul_adi: sys.modules.get(modul_adi) for modul_adi in tum_sahteler}
    eski_hedef = sys.modules.get(ad)
    sys.modules.update(tum_sahteler)
    try:
        sys.modules.pop(ad, None)
        spec = importlib.util.spec_from_file_location(ad, yol)
        modul = importlib.util.module_from_spec(spec)
        sys.modules[ad] = modul
        spec.loader.exec_module(modul)
        return modul
    finally:
        if eski_hedef is None:
            sys.modules.pop(ad, None)
        else:
            sys.modules[ad] = eski_hedef
        for modul_adi, eski in eskiler.items():
            if eski is None:
                sys.modules.pop(modul_adi, None)
            else:
                sys.modules[modul_adi] = eski


class _Imap:
    def __init__(self, bodystructure, yanitlar=None):
        self.bodystructure = bodystructure
        self.yanitlar = dict(yanitlar or {})

    def uid(self, _komut, _uid, sorgu):
        if sorgu == "(BODYSTRUCTURE)":
            return "OK", [(b"1 (BODYSTRUCTURE " + self.bodystructure + b")", b"")]
        return self.yanitlar.get(sorgu, ("NO", []))


class MimeGovdeTestleri(unittest.TestCase):
    def setUp(self):
        class MailHatasi(Exception):
            pass

        class OnbellekSiniriHatasi(MailHatasi):
            pass

        self.MailHatasi = MailHatasi
        self.kaydet = Mock(return_value=True)
        self.modul = _modulu_yukle(
            "mail.body_sync",
            MAIL_KOKU / "body_sync.py",
            {
                "mail.attachments": _modul(
                    "mail.attachments",
                    mesaj_metni_ve_ekleri_cikar=lambda _mesaj, ayrintili=False: ("okunan metin", [], []),
                ),
                "mail.errors": _modul("mail.errors", MailHatasi=MailHatasi),
                "mail.imap_client": _modul("mail.imap_client", uid_listesini_parcala=Mock()),
                "mail.logger": _modul("mail.logger", hata_kaydet=Mock(), uyari_kaydet=Mock()),
                "mail.mail_store": _modul(
                    "mail.mail_store",
                    govdesi_eksik_uidleri_al=Mock(),
                    mesaj_govdesini_kaydet=self.kaydet,
                ),
                "mail.message_parser": _modul(
                    "mail.message_parser",
                    ham_mesaj_verisi_al=lambda veri: b"".join(
                        oge[1] for oge in (veri or [])
                        if isinstance(oge, tuple) and len(oge) > 1 and isinstance(oge[1], bytes)
                    ),
                ),
                "mail.cache_limits": _modul(
                    "mail.cache_limits",
                    OnbellekSiniriHatasi=OnbellekSiniriHatasi,
                    onbellek_kotasi_denetle=Mock(),
                ),
            },
        )

    def test_gecerli_metin_parcasi_kaydedilir(self):
        imap = _Imap(
            b'(\"TEXT\" \"PLAIN\" (\"CHARSET\" \"UTF-8\") NIL NIL \"7BIT\" 12 1)',
            {
                "(BODY.PEEK[HEADER])": ("OK", [(b"x", b"Content-Type: text/plain; charset=utf-8\r\n")]),
                "(BODY.PEEK[TEXT])": ("OK", [(b"x", b"Merhaba")]),
            },
        )
        self.assertTrue(self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(imap, "a@b.com", "1"))
        self.assertEqual("okunan metin", self.kaydet.call_args.args[3])

    def test_bozuk_yapi_bos_govde_olarak_kaydedilmez(self):
        with self.assertRaises(self.MailHatasi):
            self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(
                _Imap(b"NIL"), "a@b.com", "2"
            )
        self.kaydet.assert_not_called()

    def test_iletilmis_mesaj_yapisi_bos_govde_olarak_kaydedilmez(self):
        with self.assertRaises(self.MailHatasi):
            self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(
                _Imap(b'(\"MESSAGE\" \"RFC822\" NIL NIL NIL \"7BIT\" 10)'),
                "a@b.com",
                "3",
            )
        self.kaydet.assert_not_called()

    def test_yalniz_ek_olan_ileti_bos_govdeyle_acilabilir(self):
        sonuc = self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(
            _Imap(b'(\"APPLICATION\" \"PDF\" NIL NIL NIL \"BASE64\" 100 NIL (\"ATTACHMENT\" (\"FILENAME\" \"x.pdf\")))'),
            "a@b.com",
            "4",
        )
        self.assertTrue(sonuc)
        self.assertEqual("", self.kaydet.call_args.args[3])

    def test_iletilmis_mesaj_eki_ana_metnin_okunmasini_engellemez(self):
        imap = _Imap(
            b'((\"TEXT\" \"PLAIN\" NIL NIL NIL \"7BIT\" 12 1) '
            b'(\"MESSAGE\" \"RFC822\" NIL NIL NIL \"7BIT\" 10 NIL '
            b'(\"ATTACHMENT\" (\"FILENAME\" \"ileti.eml\"))) \"MIXED\")',
            {
                "(BODY.PEEK[1.MIME])": ("OK", [(b"x", b"Content-Type: text/plain; charset=utf-8\r\n")]),
                "(BODY.PEEK[1])": ("OK", [(b"x", b"Merhaba")]),
            },
        )
        self.assertTrue(self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(imap, "a@b.com", "6"))
        self.assertEqual("okunan metin", self.kaydet.call_args.args[3])

    def test_duz_metin_yanindaki_takvim_parcasi_ana_govdeyi_engellemez(self):
        imap = _Imap(
            b'(("TEXT" "PLAIN" NIL NIL NIL "7BIT" 12 1) '
            b'("TEXT" "CALENDAR" NIL NIL NIL "7BIT" 30 3) "ALTERNATIVE")',
            {
                "(BODY.PEEK[1.MIME])": ("OK", [(b"x", b"Content-Type: text/plain; charset=utf-8\r\n")]),
                "(BODY.PEEK[1])": ("OK", [(b"x", b"Merhaba")]),
            },
        )
        self.assertTrue(self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(imap, "a@b.com", "7"))
        self.assertEqual("okunan metin", self.kaydet.call_args.args[3])

    def test_duz_metin_yanindaki_inline_ileti_ana_govdeyi_engellemez(self):
        imap = _Imap(
            b'(("TEXT" "PLAIN" NIL NIL NIL "7BIT" 12 1) '
            b'("MESSAGE" "RFC822" NIL NIL NIL "7BIT" 50) "MIXED")',
            {
                "(BODY.PEEK[1.MIME])": ("OK", [(b"x", b"Content-Type: text/plain; charset=utf-8\r\n")]),
                "(BODY.PEEK[1])": ("OK", [(b"x", b"Merhaba")]),
            },
        )
        self.assertTrue(self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(imap, "a@b.com", "8"))
        self.assertEqual("okunan metin", self.kaydet.call_args.args[3])

    def test_metin_fetch_hatasi_bos_govde_olarak_kaydedilmez(self):
        with self.assertRaises(self.MailHatasi):
            self.modul.yeni_ileti_govdesini_ek_indirmeden_kaydet(
                _Imap(b'(\"TEXT\" \"PLAIN\" NIL NIL NIL \"7BIT\" 12 1)'),
                "a@b.com",
                "5",
            )
        self.kaydet.assert_not_called()


class AdresGecmisiTestleri(unittest.TestCase):
    def _yukle(self, kayitlar):
        self.yaz = Mock(return_value=True)
        global_vars = _modul("globalVars")
        global_vars.appArgs = types.SimpleNamespace(configPath="C:\\NVDA")
        return _modulu_yukle(
            "mail.contacts",
            MAIL_KOKU / "contacts.py",
            {
                "globalVars": global_vars,
                "mail.errors": _modul("mail.errors", MailHatasi=Exception),
                "mail.storage": _modul(
                    "mail.storage",
                    guvenli_json_oku=lambda _yol, _varsayilan: list(kayitlar),
                    guvenli_json_yaz=self.yaz,
                ),
                "mail.validators": _modul("mail.validators", eposta_adresi_gecerli_mi=lambda _adres: True),
            },
        )

    def test_yuklemede_buyuk_kucuk_harf_tekrari_tek_kayit_olur(self):
        modul = self._yukle(["NVDA@groups.io", "nvda@groups.io", "b@example.com"])
        self.assertEqual(["NVDA@groups.io", "b@example.com"], modul.rehberi_yukle())

    def test_eklemede_eski_harf_varyanti_yenisiyle_degistirilir(self):
        modul = self._yukle(["NVDA@groups.io", "b@example.com"])
        self.assertTrue(modul.rehbere_ekle("nvda@groups.io"))
        self.assertEqual(
            ["nvda@groups.io", "b@example.com"],
            self.yaz.call_args.args[1],
        )


class KlasorListesiTestleri(unittest.TestCase):
    def test_tum_satirlar_acilabilir_klasordur(self):
        wx = _modul("wx", ListItem=object(), CallAfter=Mock())
        modul = _modulu_yukle(
            "mail.ui.folder_view",
            MAIL_KOKU / "ui" / "folder_view.py",
            {
                "wx": wx,
                "mail.ui": _modul("mail.ui"),
                "mail.folder_counts": _modul("mail.folder_counts", klasor_secimi_sayisi_mesaji=Mock()),
                "mail.logger": _modul("mail.logger", hata_kaydet=Mock()),
                "mail.ui_helpers": _modul("mail.ui_helpers", pencere_kullanilabilir_mi=Mock()),
            },
        )
        pencere = types.SimpleNamespace(
            kategori_isimleri=["Gelen Kutusu", "Gönderilmiş"],
            ozel_klasorler=["Projeler", "Gelen Kutusu", "Projeler"],
        )
        self.assertEqual(
            ["Gelen Kutusu", "Gönderilmiş", "Projeler"],
            modul.klasor_liste_ogeleri(pencere),
        )
        self.assertNotIn("Kullanıcı Klasörleri", modul.klasor_liste_ogeleri(pencere))


if __name__ == "__main__":
    unittest.main()
