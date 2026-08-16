# -*- coding: utf-8 -*-
"""İleti alma, MIME çözümleme, ön izleme ve ek işleme testleri."""

from __future__ import annotations

from email.message import EmailMessage
from email.policy import default
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support import load_mail_module, module


LOGGER = module(
    "mail.logger",
    hata_kaydet=lambda *a, **k: None,
    uyari_kaydet=lambda *a, **k: None,
)


class MesajAyrıştırmaTestleri(unittest.TestCase):
    def _yukle(self):
        return load_mail_module("message_parser", stubs={"mail.logger": LOGGER})

    def test_groups_io_gonderen_adi_ve_adresi_temizlenir(self):
        with self._yukle() as parser:
            self.assertEqual(
                "Mehmet Aykurt",
                parser.grup_araci_gonderen_bilgisini_temizle("Mehmet Aykurt via groups.io"),
            )
            self.assertEqual(
                "mehmet@example.com",
                parser.grup_araci_adresini_temizle("mehmet=example.com@groups.io"),
            )

    def test_gonderen_gosterimi_gorunen_adi_onceler(self):
        with self._yukle() as parser:
            sonuc = parser.gonderen_gosterimini_al(
                "=?utf-8?b?TWVobWV0IEF5a3VydA==?= <mehmet@example.com>"
            )
        self.assertEqual("Mehmet Aykurt", sonuc)

    def test_adres_basligi_duzenlenir_yinelenenler_atilir(self):
        with self._yukle() as parser:
            sonuc = parser.adres_basligini_duzenle(
                '"Aykurt, Mehmet" <mehmet@example.com>; MEHMET@example.com, çağrı@örnek.istanbul'
            )
        self.assertEqual(1, sonuc.lower().count("mehmet@example.com"))
        self.assertIn("çağrı@örnek.istanbul", sonuc)

    def test_yanit_adresi_reply_to_basligini_onceler(self):
        mesaj = EmailMessage()
        mesaj["From"] = "gonderen@example.com"
        mesaj["Reply-To"] = "yanit@example.com"
        with self._yukle() as parser:
            self.assertEqual("yanit@example.com", parser.yanit_adresini_bul(mesaj))

    def test_yanit_basliklari_references_zincirini_genisletir(self):
        with self._yukle() as parser:
            sonuc = parser.yanit_basliklari_hazirla(
                {"message_id": "<iki@example.com>", "references": "<bir@example.com>"}
            )
            tekrar = parser.yanit_basliklari_hazirla(
                {"message_id": "<iki@example.com>", "references": "<bir@example.com> <iki@example.com>"}
            )
        self.assertEqual("<iki@example.com>", sonuc["In-Reply-To"])
        self.assertEqual("<bir@example.com> <iki@example.com>", sonuc["References"])
        self.assertEqual("<bir@example.com> <iki@example.com>", tekrar["References"])

    def test_fetch_ham_verisi_birlestirilir_ek_ve_seen_bayragi_bulunur(self):
        fetch = [
            (b"1 (FLAGS (\\Seen) BODYSTRUCTURE (... FILENAME ...)", b"ilk"),
            b")",
            (b"2 BODY[]", b"ikinci"),
        ]
        with self._yukle() as parser:
            self.assertEqual(b"ilkikinci", parser.ham_mesaj_verisi_al(fetch))
            self.assertTrue(parser.fetch_sonucunda_ek_var_mi(fetch))
            self.assertTrue(parser.seen_bayragi_var_mi(fetch))

    def test_onizleme_kisaltma_tek_satir_ve_sinirli(self):
        with self._yukle() as parser:
            sonuc = parser.onizleme_metnini_kisalt("Birinci\n\tİkinci " + "x" * 30, sinir=20)
        self.assertNotIn("\n", sonuc)
        self.assertTrue(sonuc.endswith("..."))
        self.assertLessEqual(len(sonuc), 23)

    def test_quoted_printable_turkce_onizleme_cozulur(self):
        ham = (
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Content-Transfer-Encoding: quoted-printable\r\n\r\n"
            b"T=C3=BCrk=C3=A7e =C5=9Fiir ve =C4=B0stanbul"
        )
        with self._yukle() as parser:
            sonuc = parser.onizleme_email_paketiyle_coz(ham)
        self.assertIn("Türkçe şiir", sonuc)
        self.assertIn("İstanbul", sonuc)


class MIMEVeEkTestleri(unittest.TestCase):
    def _yukle(self):
        return load_mail_module("attachments", stubs={"mail.logger": LOGGER})

    @staticmethod
    def _karma_mesaj():
        mesaj = EmailMessage()
        mesaj["From"] = "g@example.com"
        mesaj["To"] = "a@example.com"
        mesaj["Subject"] = "Türkçe ileti"
        mesaj.set_content("Düz metin: çğıöşü")
        mesaj.add_alternative("<html><body><p>HTML metni</p></body></html>", subtype="html")
        mesaj.add_attachment(b"ek-icerigi", maintype="application", subtype="octet-stream", filename="belge.txt")
        return mesaj

    def test_multipart_mesajdan_duz_metin_ve_ek_cikarilir(self):
        mesaj = self._karma_mesaj()
        with self._yukle() as attachments:
            metin, ekler = attachments.mesaj_metni_ve_ekleri_cikar(mesaj)
        self.assertIn("Düz metin", metin)
        self.assertEqual([("belge.txt", b"ek-icerigi")], ekler)

    def test_yalniz_html_mesaj_duz_metne_donusur(self):
        mesaj = EmailMessage()
        mesaj.set_content("<html><body><h1>Başlık</h1><p>Türkçe içerik</p></body></html>", subtype="html")
        with self._yukle() as attachments:
            metin, ekler = attachments.mesaj_metni_ve_ekleri_cikar(mesaj)
        self.assertIn("Başlık", metin)
        self.assertIn("Türkçe içerik", metin)
        self.assertEqual([], ekler)

    def test_buyuk_ek_atlanir_ve_not_eklenir(self):
        mesaj = EmailMessage()
        mesaj.set_content("Ana metin")
        mesaj.add_attachment(b"123456", maintype="application", subtype="octet-stream", filename="buyuk.bin")
        with self._yukle() as attachments:
            with mock.patch.object(attachments, "AZAMI_EK_ONBELLEK_TEK_BOYUTU", 5):
                metin, ekler, atlanan = attachments.mesaj_metni_ve_ekleri_cikar(mesaj, ayrintili=True)
        self.assertEqual([], ekler)
        self.assertEqual(1, atlanan)
        self.assertIn("Atlanan ekler", metin)
        self.assertIn("buyuk.bin", metin)

    def test_benzersiz_yol_mevcut_dosyayi_ezmez(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "şiir.txt").write_text("ilk", encoding="utf-8")
            Path(tmp, "şiir_1.txt").write_text("ikinci", encoding="utf-8")
            with self._yukle() as attachments:
                sonuc = attachments.benzersiz_yol(tmp, "şiir.txt")
        self.assertTrue(sonuc.endswith("şiir_2.txt"))

    def test_icerik_turu_bilinmeyen_dosyaya_octet_stream_verilir(self):
        with self._yukle() as attachments:
            self.assertEqual(
                ["application", "octet-stream"],
                attachments.ek_icerik_turu_bul("dosya.bilinmeyenuzanti"),
            )
            self.assertEqual(["text", "plain"], attachments.ek_icerik_turu_bul("dosya.txt"))

    def test_eml_basliklari_varsa_gecerlidir(self):
        ham = (
            "From: Gönderen <g@example.com>\r\n"
            "To: a@example.com\r\n"
            "Subject: Türkçe\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "İçerik"
        ).encode("utf-8")
        with self._yukle() as attachments:
            mesaj = attachments.eml_verisini_dogrula(ham)
        self.assertEqual("Türkçe", str(mesaj["Subject"]))

    def test_basliksiz_ve_bos_eml_reddedilir(self):
        with self._yukle() as attachments:
            for ham in (b"", b"yalnizca govde"):
                with self.subTest(ham=ham):
                    with self.assertRaises(attachments.MailHatasi):
                        attachments.eml_verisini_dogrula(ham)

    def test_ham_eposta_boyutu_bos_ve_asiri_buyuk_veriyi_reddeder(self):
        with self._yukle() as attachments:
            with self.assertRaisesRegex(attachments.MailHatasi, "boş"):
                attachments.ham_eposta_boyutunu_denetle(b"")
            with mock.patch.object(attachments, "AZAMI_EPOSTA_ISLEME_BOYUTU", 3):
                with self.assertRaisesRegex(attachments.MailHatasi, "çok büyük"):
                    attachments.ham_eposta_boyutunu_denetle(b"1234")

    def test_eml_dosya_boyutu_normal_bos_ve_buyuk_durumlari(self):
        with tempfile.TemporaryDirectory() as tmp:
            normal = Path(tmp, "normal.eml")
            bos = Path(tmp, "bos.eml")
            normal.write_bytes(b"123")
            bos.write_bytes(b"")
            with self._yukle() as attachments:
                self.assertEqual(3, attachments.eml_dosya_boyutunu_denetle(normal))
                with self.assertRaisesRegex(attachments.MailHatasi, "boş"):
                    attachments.eml_dosya_boyutunu_denetle(bos)
                with mock.patch.object(attachments, "AZAMI_EML_DOSYA_BOYUTU", 2):
                    with self.assertRaisesRegex(attachments.MailHatasi, "çok büyük"):
                        attachments.eml_dosya_boyutunu_denetle(normal)

    def test_ek_boyutu_tek_ve_toplam_sinirlarini_denetler(self):
        with self._yukle() as attachments:
            with mock.patch.object(attachments, "AZAMI_TEK_EK_BOYUTU", 3), mock.patch.object(
                attachments, "AZAMI_TOPLAM_EK_BOYUTU", 5
            ):
                with self.assertRaisesRegex(attachments.MailHatasi, "Tek ek"):
                    attachments.ek_kayitlari_boyutunu_denetle(
                        [{"tur": "hazir", "ad": "a.bin", "veri": b"1234"}]
                    )
                with self.assertRaisesRegex(attachments.MailHatasi, "toplam boyutu"):
                    attachments.ek_kayitlari_boyutunu_denetle(
                        [
                            {"tur": "hazir", "ad": "a.bin", "veri": b"123"},
                            {"tur": "hazir", "ad": "b.bin", "veri": b"123"},
                        ]
                    )


class OnizlemeTestleri(unittest.TestCase):
    def test_multipart_alternative_turkce_onizleme(self):
        mesaj = EmailMessage()
        mesaj.set_content("Türkçe düz içerik: İstanbul")
        mesaj.add_alternative("<p>HTML içerik</p>", subtype="html")
        with load_mail_module("preview", stubs={"mail.logger": LOGGER}) as preview:
            sonuc = preview.onizleme_metni_olustur(mesaj.as_bytes(policy=default))
        self.assertIn("Türkçe düz içerik", sonuc)

    def test_bos_veri_bos_onizleme_dondurur(self):
        with load_mail_module("preview", stubs={"mail.logger": LOGGER}) as preview:
            self.assertEqual("", preview.onizleme_metni_olustur(b""))

    def test_basliksiz_utf8_turkce_metin_korunur(self):
        with load_mail_module("preview", stubs={"mail.logger": LOGGER}) as preview:
            sonuc = preview.onizleme_metni_olustur("Şehit Ali Örnek Ortaokulu".encode("utf-8"))
        self.assertIn("Şehit Ali Örnek", sonuc)


if __name__ == "__main__":
    unittest.main()
