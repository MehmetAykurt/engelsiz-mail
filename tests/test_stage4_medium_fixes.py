# -*- coding: utf-8 -*-
"""Dördüncü aşamadaki orta düzey düzeltmelerin davranış testleri."""

from __future__ import annotations

import pathlib
import threading
import unittest
from unittest import mock

from support import FakeIMAP, load_mail_module, module, temporary_workspace


class _FakeLog:
    def exception(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None


LOG_HANDLER = module("logHandler", log=_FakeLog())


class AliciDogrulamaTestleri(unittest.TestCase):
    def test_gecerli_adresler_ve_gorunen_adlar_korunur(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            mesaj = smtp_client.eposta_mesaji_olustur(
                "gonderen@example.com",
                '"Aykurt, Mehmet" <mehmet@example.com>, ikinci@example.com,',
                "Türkçe konu",
                "İçerik",
                [],
            )
        self.assertIn("mehmet@example.com", str(mesaj["To"]))
        self.assertIn("ikinci@example.com", str(mesaj["To"]))

    def test_kime_bilgi_ve_gizli_alanlarinda_hata_sessizce_atilmaz(self):
        with load_mail_module("smtp_client", stubs={"logHandler": LOG_HANDLER}) as smtp_client:
            senaryolar = (
                {"kime_basligi": "a@example.com, hatali"},
                {"kime_basligi": "a@example.com", "bilgi_basligi": "b@example.com, hatali"},
                {"kime_basligi": "a@example.com", "gizli_basligi": "c@example.com, hatali"},
            )
            for alanlar in senaryolar:
                with self.subTest(alanlar=alanlar):
                    alanlar = dict(alanlar)
                    kime_basligi = alanlar.pop("kime_basligi")
                    with self.assertRaises(smtp_client.MailHatasi):
                        smtp_client.eposta_mesaji_olustur(
                            "gonderen@example.com",
                            kime_basligi,
                            konu="Deneme",
                            icerik="İçerik",
                            ek_kayitlari=[],
                            **alanlar,
                        )


class ImapKapanisTestleri(unittest.TestCase):
    def test_imap_baglanti_yoneticisi_shutdown_ile_oturumu_keser(self):
        ham_imap = FakeIMAP("imap.example.com")

        class FakeIMAP4:
            error = RuntimeError

        vendor_imaplib = module(
            "mail.vendor.imaplib",
            IMAP4_SSL=lambda *a, **k: ham_imap,
            IMAP4=FakeIMAP4,
        )
        stubs = {
            "mail.errors": module("mail.errors", MailHatasi=RuntimeError),
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.vendor": module("mail.vendor", imaplib=vendor_imaplib),
        }
        with load_mail_module("imap_client", stubs=stubs) as imap_client:
            baglanti = imap_client.ImapBaglantisi(
                {"eposta": "kullanici@example.com", "sifre": "sifre"}
            )
            self.assertIs(ham_imap, baglanti.__enter__())
            self.assertTrue(baglanti.shutdown())
            self.assertTrue(ham_imap.shutdown_called)
            self.assertIsNone(baglanti.imap)
            baglanti.__exit__(None, None, None)
            self.assertFalse(ham_imap.logout_called)

    def test_baslangic_yoneticisi_etkin_baglantiyi_kapatir(self):
        from test_startup_sync import startup_sync_yukle

        modul, _wx, *_ = startup_sync_yukle()
        yonetici = modul.BaslangicSenkronizasyonYoneticisi(15000)
        aktif = mock.Mock()
        with yonetici._baglanti_kilidi:
            yonetici._aktif_baglanti = aktif
        yonetici.durdur()
        aktif.shutdown.assert_called_once_with()
        self.assertTrue(yonetici._iptal.is_set())

    def test_bekleyen_silme_yoneticisi_etkin_baglantiyi_kapatir(self):
        class Timer:
            def Stop(self):
                return None

        wx = module("wx", CallLater=lambda *a, **k: Timer(), CallAfter=lambda f, *a: f(*a))
        stubs = {
            "wx": wx,
            "mail.attachment_cache": module(
                "mail.attachment_cache", EK_ONBELLEK_KILIDI=threading.RLock(), _guvenli_tam_yol=lambda p: p
            ),
            "mail.config": module("mail.config", ayarlari_yukle=lambda: {}),
            "mail.database": module(
                "mail.database", veritabani_baglantisi=lambda *a, **k: None, veritabani_hazirla=lambda: None
            ),
            "mail.errors": module("mail.errors", MailHatasi=RuntimeError),
            "mail.imap_client": module(
                "mail.imap_client",
                ImapBaglantisi=object,
                imap_gmail_etiket_destegini_dogrula=lambda *a, **k: True,
                imap_gmail_etiket_store=lambda *a, **k: True,
                imap_gmail_msgidleri_kalici_sil=lambda *a, **k: True,
                imap_uidvalidity_al=lambda *a, **k: 1,
                imap_ok_mu=lambda *a, **k: True,
                imap_uid_search_sonucu_uidleri_al=lambda *a, **k: [],
                imap_x_gm_msgid_haritasi_al=lambda *a, **k: {},
                uid_kumesi_hazirla=lambda *a, **k: "1",
            ),
            "mail.logger": module(
                "mail.logger", hata_kaydet=lambda *a, **k: None, uyari_kaydet=lambda *a, **k: None
            ),
            "mail.mailbox_state": module("mail.mailbox_state", POSTA_DURUM_KILIDI=threading.Lock()),
            "mail.ui_helpers": module("mail.ui_helpers", arka_planda_calistir=lambda *a, **k: None),
        }
        with load_mail_module("pending_deletions", stubs=stubs) as pending:
            yonetici = pending.BekleyenSilmeYoneticisi(15000)
            aktif = mock.Mock()
            yonetici._aktif_baglantiyi_ayarla(aktif)
            yonetici.durdur()
            aktif.shutdown.assert_called_once_with()
            self.assertTrue(yonetici._iptal.is_set())


class AyarYedegiGuvenlikTestleri(unittest.TestCase):
    @staticmethod
    def _stublar(workspace, MailHatasi):
        return {
            "mail.errors": module("mail.errors", MailHatasi=MailHatasi),
            "mail.paths": module("mail.paths", AYARLAR_DOSYASI=str(workspace.settings_path)),
            "mail.security": module(
                "mail.security",
                uygulama_sifresini_coz=lambda _v: "abcd efgh ijkl mnop",
                uygulama_sifresini_sifrele=lambda v: f"DPAPI:{v}",
            ),
            "mail.storage": module(
                "mail.storage",
                guvenli_json_oku=lambda *a, **k: {
                    "eposta": "kullanici@example.com",
                    "sifre_dpapi": "sifreli",
                },
                guvenli_json_yedekleyerek_yaz=lambda *a, **k: True,
            ),
            "mail.version": module("mail.version", EKLENTI_SURUMU="1.7.0"),
        }

    def test_basarili_yedek_tercih_edilen_sifreyi_tasir_ve_gecici_dosya_birakmaz(self):
        import json
        import zipfile

        class MailHatasi(Exception):
            pass

        with temporary_workspace() as workspace:
            workspace.settings_path.write_text("{}", encoding="utf-8")
            hedef = workspace.root / "ayar_yedegi.zip"
            with load_mail_module(
                "settings_backup", stubs=self._stublar(workspace, MailHatasi)
            ) as settings_backup:
                sonuc = settings_backup.ayarlari_disa_aktar(str(hedef))
            self.assertEqual(str(hedef), sonuc)
            with zipfile.ZipFile(hedef, "r") as arsiv:
                veri = json.loads(arsiv.read("ayarlar.json").decode("utf-8"))
            self.assertEqual("abcdefghijklmnop", veri["ayarlar"]["sifre"].replace(" ", ""))
            self.assertEqual([], list(workspace.root.glob("engelsiz_mail_*.tmp")))

    def test_disa_aktarma_hatasi_gecici_zip_birakmaz(self):
        class MailHatasi(Exception):
            pass

        with temporary_workspace() as workspace:
            workspace.settings_path.write_text("{}", encoding="utf-8")
            hedef = workspace.root / "ayar_yedegi.zip"
            with load_mail_module(
                "settings_backup", stubs=self._stublar(workspace, MailHatasi)
            ) as settings_backup:
                with mock.patch.object(settings_backup.os, "replace", side_effect=OSError("disk hatası")):
                    with self.assertRaises(MailHatasi):
                        settings_backup.ayarlari_disa_aktar(str(hedef))
            kalanlar = list(workspace.root.glob("engelsiz_mail_*.tmp"))
            self.assertEqual([], kalanlar)
            self.assertFalse(hedef.exists())


class KaynakBildirimiTestleri(unittest.TestCase):
    def test_imaplib_degistirildigi_acikca_belgelenir(self):
        source_path = pathlib.Path(__file__).resolve().parents[1] / "globalPlugins" / "mail" / "vendor" / "SOURCE.txt"
        metin = source_path.read_text(encoding="utf-8")
        self.assertIn("değiştirilmiş bir paket kopyasıdır", metin)
        self.assertIn("IMAP4.idle()", metin)
        self.assertIn("1b73aee9080c178bb72caa94631eed20649ad91fe7242c2657acd0f9a4781e16", metin)


if __name__ == "__main__":
    unittest.main()
