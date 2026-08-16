# -*- coding: utf-8 -*-
"""Gönderme ve taslak kaydetme çekirdeğinin bütünleşik davranış testleri."""

from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path

from support import FakeSMTPFactory, FakeSMTPSession, load_mail_module, module


LOGGER = module(
    "mail.logger",
    hata_kaydet=lambda *a, **k: None,
    uyari_kaydet=lambda *a, **k: None,
)


class SMTPMesajOlusturmaTestleri(unittest.TestCase):
    def _yukle(self):
        return load_mail_module("smtp_client", stubs={"mail.logger": LOGGER})

    def test_turkce_gorunen_ad_konu_ve_govde_korunur(self):
        with self._yukle() as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "mehmet@example.com",
                '"Aykurt, Mehmet" <alici@example.com>',
                "Şiir: Çağrı ve İstanbul\r\nGizli satır",
                "Türkçe gövde: çğıöşü ÇĞİÖŞÜ",
                [],
                gorunen_ad="Mehmet Aykurt",
            )
        self.assertIn("mehmet@example.com", str(mesaj["From"]))
        self.assertIn("alici@example.com", str(mesaj["To"]))
        self.assertNotIn("\r", str(mesaj["Subject"]))
        self.assertNotIn("\n", str(mesaj["Subject"]))
        self.assertIn("Türkçe gövde", mesaj.get_content())

    def test_bos_konu_konusuz_olur(self):
        with self._yukle() as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "", "İçerik", []
            )
        self.assertEqual("Konusuz", str(mesaj["Subject"]))

    def test_bcc_gonderim_mesajinda_yok_taslakta_var(self):
        with self._yukle() as smtp:
            gonderim = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "K", "I", [],
                gizli_basligi="gizli@example.com", taslak=False,
            )
            taslak = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "K", "I", [],
                gizli_basligi="gizli@example.com", taslak=True,
            )
        self.assertIsNone(gonderim["Bcc"])
        self.assertIn("gizli@example.com", str(taslak["Bcc"]))
        self.assertEqual("1", str(taslak["X-Unsent"]))
        self.assertTrue(taslak["Date"])
        self.assertTrue(taslak["Message-ID"])

    def test_yanit_basliklari_eklenir_mevcut_baslik_ezilmez(self):
        with self._yukle() as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "K", "I", [],
                ek_basliklar={
                    "In-Reply-To": "<onceki@example.com>",
                    "References": "<ilk@example.com> <onceki@example.com>",
                    "Subject": "Ezilmemeli",
                },
            )
        self.assertEqual("<onceki@example.com>", str(mesaj["In-Reply-To"]))
        self.assertIn("<ilk@example.com>", str(mesaj["References"]))
        self.assertEqual("K", str(mesaj["Subject"]))

    def test_hazir_ve_dosya_eki_mime_olarak_eklenir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp) / "Türkçe belge.txt"
            yol.write_text("dosya içeriği", encoding="utf-8")
            with self._yukle() as smtp:
                mesaj = smtp.eposta_mesaji_olustur(
                    "g@example.com", "a@example.com", "K", "I",
                    [
                        {"tur": "hazir", "ad": "hazır.pdf", "veri": b"%PDF-test"},
                        {"tur": "dosya", "yol": str(yol)},
                    ],
                )
        ekler = list(mesaj.iter_attachments())
        self.assertEqual(2, len(ekler))
        self.assertEqual("hazır.pdf", ekler[0].get_filename())
        self.assertEqual("Türkçe belge.txt", ekler[1].get_filename())
        self.assertEqual(b"%PDF-test", ekler[0].get_payload(decode=True))

    def test_bulunamayan_ek_anlasilir_hata_verir(self):
        with self._yukle() as smtp:
            with self.assertRaisesRegex(smtp.MailHatasi, "Ek dosya bulunamadı"):
                smtp.eposta_mesaji_olustur(
                    "g@example.com", "a@example.com", "K", "I",
                    [{"tur": "dosya", "yol": "/olmayan/ek.txt"}],
                )

    def test_bos_kime_alani_taslak_icin_desteklenir(self):
        with self._yukle() as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "g@example.com", "", "Taslak", "Henüz alıcı yok", [], taslak=True
            )
        self.assertIsNone(mesaj["To"])
        self.assertEqual("1", str(mesaj["X-Unsent"]))


class SMTPBaglantiVeGonderimTestleri(unittest.TestCase):
    def _yukle(self, factory):
        smtplib_mod = factory.as_module()
        return load_mail_module(
            "smtp_client",
            stubs={
                "mail.logger": LOGGER,
                "mail.vendor": module("mail.vendor", smtplib=smtplib_mod),
                "mail.vendor.smtplib": smtplib_mod,
            },
        )

    def test_465_ssl_ile_gonderir_ve_oturumu_kapatir(self):
        factory = FakeSMTPFactory()
        with self._yukle(factory) as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "K", "I", []
            )
            smtp.smtp_ssl_ile_gonder("g@example.com", "sifre", ["a@example.com"], mesaj)
        self.assertEqual(1, len(factory.ssl_sessions))
        oturum = factory.ssl_sessions[0]
        self.assertEqual(("g@example.com", "sifre"), oturum.logged_in_as)
        self.assertEqual(["a@example.com"], oturum.sent_messages[0]["to_addrs"])
        self.assertTrue(oturum.quit_called)

    def test_465_basarisizsa_587_starttls_kullanilir(self):
        factory = FakeSMTPFactory()
        factory.ssl_constructor_results.append(OSError("465 kapalı"))
        with self._yukle(factory) as smtp:
            yontem = smtp.smtp_baglanti_denetle("g@example.com", "sifre")
        self.assertEqual("587 STARTTLS", yontem)
        self.assertEqual(1, len(factory.starttls_sessions))
        oturum = factory.starttls_sessions[0]
        self.assertTrue(oturum.tls_started)
        self.assertEqual(2, sum(1 for ad, _a, _k in oturum.calls if ad == "ehlo"))
        self.assertTrue(oturum.quit_called)

    def test_iki_baglanti_yontemi_de_basarisizsa_birlesik_hata_verilir(self):
        factory = FakeSMTPFactory()
        factory.ssl_constructor_results.append(socket.timeout("zaman aşımı"))
        factory.starttls_constructor_results.append(ConnectionRefusedError("reddedildi"))
        with self._yukle(factory) as smtp:
            with self.assertRaisesRegex(smtp.MailHatasi, "465 SSL sonucu") as yakalanan:
                smtp.smtp_baglanti_denetle("g@example.com", "sifre")
        self.assertIn("587 STARTTLS sonucu", str(yakalanan.exception))

    def test_gonderim_sirasinda_baglanti_koparsa_sonuc_belirsiz_hatasi_verilir(self):
        factory = FakeSMTPFactory()
        oturum = FakeSMTPSession()
        smtplib_mod = factory.as_module()
        oturum.script("send_message", smtplib_mod.SMTPServerDisconnected("koptu"))
        factory.ssl_constructor_results.append(oturum)
        with self._yukle(factory) as smtp:
            mesaj = smtp.eposta_mesaji_olustur(
                "g@example.com", "a@example.com", "K", "I", []
            )
            with self.assertRaisesRegex(smtp.MailHatasi, "Gönderim sonucu doğrulanamadı"):
                smtp.smtp_ssl_ile_gonder("g@example.com", "sifre", ["a@example.com"], mesaj)
        self.assertTrue(oturum.quit_called)

    def test_quit_hatasi_close_ile_yedeklenir(self):
        factory = FakeSMTPFactory()
        oturum = FakeSMTPSession()
        oturum.script("quit", OSError("quit olmadı"))
        factory.ssl_constructor_results.append(oturum)
        with self._yukle(factory) as smtp:
            smtp.smtp_baglanti_denetle("g@example.com", "sifre")
        self.assertTrue(oturum.closed)
        self.assertTrue(any(ad == "close" for ad, _a, _k in oturum.calls))


class TaslakHizmetiTestleri(unittest.TestCase):
    class _ImapHatasi(Exception):
        pass

    def _yukle(self, baglanti_sinifi, klasorler=None, mesaj=None):
        imaplib_mod = module(
            "mail.vendor.imaplib",
            IMAP4=type("IMAP4", (), {"error": self._ImapHatasi}),
        )
        return load_mail_module(
            "draft_service",
            stubs={
                "mail.errors": module("mail.errors", MailHatasi=RuntimeError),
                "mail.folders": module(
                    "mail.folders",
                    taslak_klasor_adaylarini_temizle=lambda _a: list(
                        klasorler or ['"[Gmail]/Drafts"']
                    ),
                ),
                "mail.imap_client": module("mail.imap_client", ImapBaglantisi=baglanti_sinifi),
                "mail.logger": LOGGER,
                "mail.smtp_client": module(
                    "mail.smtp_client",
                    eposta_mesaji_olustur=lambda *a, **k: mesaj or self._mesaj(),
                ),
                "mail.vendor": module("mail.vendor", imaplib=imaplib_mod),
                "mail.vendor.imaplib": imaplib_mod,
            },
        )

    @staticmethod
    def _mesaj():
        from email.message import EmailMessage
        ileti = EmailMessage()
        ileti["From"] = "g@example.com"
        ileti.set_content("Taslak")
        return ileti

    def test_hesap_bilgisi_eksikse_imap_acilmaz(self):
        class Baglanti:
            def __init__(self, _ayarlar):
                raise AssertionError("Bağlantı açılmamalı")
        with self._yukle(Baglanti) as draft:
            with self.assertRaisesRegex(RuntimeError, "Hesap bilgileri eksik"):
                draft.taslagi_sunucuya_kaydet("", "", "", "K", "I", [], ayarlar={})

    def test_ilk_klasor_reddederse_ikinci_adaya_append_yapar(self):
        append_cagrilari = []

        class Baglanti:
            def __init__(self, ayarlar):
                self.ayarlar = ayarlar
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def append(self, klasor, bayrak, tarih, veri):
                append_cagrilari.append((klasor, bayrak, tarih, veri))
                return ("NO", [b"red"]) if len(append_cagrilari) == 1 else ("OK", [b"kaydedildi"])

        with self._yukle(Baglanti, klasorler=["ilk", "ikinci"]) as draft:
            sonuc = draft.taslagi_sunucuya_kaydet(
                "a@example.com", "", "", "K", "I", [],
                ayarlar={"eposta": "g@example.com", "sifre": "sifre"},
            )
        self.assertTrue(sonuc)
        self.assertEqual(["ilk", "ikinci"], [c[0] for c in append_cagrilari])
        self.assertEqual("(\\Draft)", append_cagrilari[1][1])
        self.assertIn(b"Taslak", append_cagrilari[1][3])

    def test_butun_klasorler_basarisizsa_anlasilir_hata_verir(self):
        class Baglanti:
            def __init__(self, _ayarlar):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def append(self, *_args):
                return "NO", [b"red"]

        with self._yukle(Baglanti, klasorler=["bir", "iki"]) as draft:
            with self.assertRaisesRegex(RuntimeError, "Taslak.*kaydedilemedi"):
                draft.taslagi_sunucuya_kaydet(
                    "a@example.com", "", "", "K", "I", [],
                    ayarlar={"eposta": "g@example.com", "sifre": "sifre"},
                )


if __name__ == "__main__":
    unittest.main()
