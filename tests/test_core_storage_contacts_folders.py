# -*- coding: utf-8 -*-
"""Kaydetme, rehber, klasör, konuşma ve ek önbelleği testleri."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support import load_mail_module, module, temporary_workspace


class JSONDepolamaTestleri(unittest.TestCase):
    def _yukle(self, kayitlar=None):
        kayitlar = kayitlar if kayitlar is not None else []
        return load_mail_module(
            "storage",
            stubs={"mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: kayitlar.append(a))},
        )

    def test_turkce_json_atomik_yazilir_ve_okunur(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp, "ayarlar.json")
            veri = {"ad": "Mehmet Aykurt", "metin": "çğıöşü ÇĞİÖŞÜ"}
            with self._yukle() as storage:
                self.assertTrue(storage.guvenli_json_yaz(str(yol), veri))
                self.assertEqual(veri, storage.guvenli_json_oku(str(yol), {}))
            self.assertEqual([], list(Path(tmp).glob("engelsizmail_*.tmp")))

    def test_bozuk_json_yedeklenir_ve_varsayilan_doner(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp, "bozuk.json")
            yol.write_text("{bozuk", encoding="utf-8")
            with self._yukle() as storage:
                self.assertEqual([], storage.guvenli_json_oku(str(yol), []))
            self.assertFalse(yol.exists())
            self.assertTrue(Path(str(yol) + ".bozuk").exists())

    def test_yanlis_json_turu_varsayilana_doner_ama_dosya_korunur(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp, "liste.json")
            yol.write_text('{"anahtar": 1}', encoding="utf-8")
            with self._yukle() as storage:
                self.assertEqual([], storage.guvenli_json_oku(str(yol), []))
            self.assertTrue(yol.exists())

    def test_json_guncelle_tek_islemde_degisikligi_yazar(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp, "sayac.json")
            with self._yukle() as storage:
                storage.guvenli_json_yaz(str(yol), {"sayac": 1})
                self.assertTrue(
                    storage.guvenli_json_guncelle(
                        str(yol), {}, lambda veri: {**veri, "sayac": veri["sayac"] + 1}
                    )
                )
                self.assertEqual({"sayac": 2}, storage.guvenli_json_oku(str(yol), {}))

    def test_json_guncelleyici_yanlis_tur_dondururse_hata_verir(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self._yukle() as storage:
                with self.assertRaises(TypeError):
                    storage.guvenli_json_guncelle(str(Path(tmp, "x.json")), {}, lambda _v: [])
                with self.assertRaises(TypeError):
                    storage.guvenli_json_guncelle(str(Path(tmp, "x.json")), {}, "çağrılmaz")

    def test_yedekleyerek_yaz_eski_veriyi_korur(self):
        with tempfile.TemporaryDirectory() as tmp:
            asil = Path(tmp, "ayar.json")
            yedek = Path(tmp, "ayar.yedek.json")
            with self._yukle() as storage:
                storage.guvenli_json_yaz(str(asil), {"surum": 1})
                self.assertTrue(storage.guvenli_json_yedekleyerek_yaz(str(asil), {"surum": 2}, str(yedek)))
                self.assertEqual({"surum": 1}, storage.guvenli_json_oku(str(yedek), {}))
                self.assertEqual({"surum": 2}, storage.guvenli_json_oku(str(asil), {}))

    def test_serilestirilemeyen_veri_gecici_dosya_birakmaz(self):
        with tempfile.TemporaryDirectory() as tmp:
            yol = Path(tmp, "hata.json")
            with self._yukle() as storage:
                self.assertFalse(storage.guvenli_json_yaz(str(yol), {"veri": object()}))
            self.assertFalse(yol.exists())
            self.assertEqual([], list(Path(tmp).glob("engelsizmail_*.tmp")))


class RehberVeKisilerTestleri(unittest.TestCase):
    def _yukle(self, workspace):
        global_vars = module(
            "globalVars",
            appArgs=type("AppArgs", (), {"configPath": str(workspace.config_dir)})(),
        )
        return load_mail_module(
            "contacts",
            stubs={
                "globalVars": global_vars,
                "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            },
        )

    def test_rehber_yinelenen_adresleri_casefold_ile_temizler(self):
        with temporary_workspace() as workspace:
            yol = workspace.config_dir / "engelsiz-mail" / "adres.json"
            yol.parent.mkdir(parents=True, exist_ok=True)
            yol.write_text(json.dumps(["Mehmet@Example.com", " mehmet@example.com ", "çağrı@örnek.istanbul"]), encoding="utf-8")
            with self._yukle(workspace) as contacts:
                sonuc = contacts.rehberi_yukle()
        self.assertEqual(["Mehmet@Example.com", "çağrı@örnek.istanbul"], sonuc)

    def test_rehbere_eklenen_adres_basa_alinir_ve_yinelenmez(self):
        with temporary_workspace() as workspace:
            with self._yukle(workspace) as contacts:
                self.assertTrue(contacts.rehbere_ekle("bir@example.com"))
                self.assertTrue(contacts.rehbere_ekle("iki@example.com"))
                self.assertTrue(contacts.rehbere_ekle("BIR@example.com"))
                sonuc = contacts.rehberi_yukle()
        self.assertEqual(["BIR@example.com", "iki@example.com"], sonuc)

    def test_kisiler_gecersiz_ve_yinelenen_kayitlardan_arindirilir(self):
        with temporary_workspace() as workspace:
            with self._yukle(workspace) as contacts:
                self.assertTrue(
                    contacts.kisileri_kaydet(
                        [
                            {"ad": "Zeynep", "soyad": "Şahin", "eposta": "z@example.com"},
                            {"ad": "Aynı", "soyad": "Kişi", "eposta": "Z@example.com"},
                            {"ad": "Hatalı", "eposta": "hatalı"},
                            "bozuk",
                            {"ad": "Çağrı", "eposta": "çağrı@örnek.istanbul"},
                        ]
                    )
                )
                sonuc = contacts.kisileri_yukle()
        self.assertEqual(2, len(sonuc))
        self.assertEqual({"Çağrı", "Zeynep"}, {kisi["ad"] for kisi in sonuc})
        self.assertEqual({"çağrı@örnek.istanbul", "z@example.com"}, {kisi["eposta"].lower() for kisi in sonuc})

    def test_kisi_ekle_guncelle_ve_baslik_uretimi(self):
        with temporary_workspace() as workspace:
            with self._yukle(workspace) as contacts:
                contacts.kisi_ekle_veya_guncelle(
                    {"ad": "Mehmet", "soyad": "Aykurt", "eposta": "m@example.com"}
                )
                contacts.kisi_ekle_veya_guncelle(
                    {"ad": "Mehmet", "soyad": "Aykurt", "eposta": "yeni@example.com"},
                    eski_eposta="m@example.com",
                )
                kisiler = contacts.kisileri_yukle()
                baslik = contacts.kisi_eposta_basligi(kisiler[0])
                gorunum = contacts.kisi_gorunen_ad(kisiler[0])
        self.assertEqual(1, len(kisiler))
        self.assertIn("yeni@example.com", baslik)
        self.assertEqual("Mehmet Aykurt yeni@example.com", gorunum)

    def test_gecersiz_kisi_adresi_reddedilir(self):
        with temporary_workspace() as workspace:
            with self._yukle(workspace) as contacts:
                with self.assertRaisesRegex(contacts.MailHatasi, "geçerli"):
                    contacts.kisi_ekle_veya_guncelle({"ad": "Hatalı", "eposta": "yanlış"})


class KlasorVeKonusmaTestleri(unittest.TestCase):
    def test_modified_utf7_turkce_ve_ampersand_roundtrip(self):
        with load_mail_module("folders", stubs={"mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None)}) as folders:
            for metin in ("Arşiv/Şiir", "A&B", "İstanbul Çalışmaları", "INBOX"):
                with self.subTest(metin=metin):
                    kodlu = folders.encode_mutf7(metin)
                    self.assertEqual(metin, folders.decode_mutf7(kodlu))

    def test_imap_list_satiri_ve_klasor_haritasi(self):
        with load_mail_module("folders", stubs={"mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None)}) as folders:
            ozel_ad = "Şiirler"
            kodlu_ozel_ad = folders.encode_mutf7(ozel_ad)
            satirlar = [
                b'(\\HasNoChildren \\Inbox) "/" "INBOX"',
                b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
                f'(\\HasNoChildren) "/" "{kodlu_ozel_ad}"'.encode("ascii"),
                b'(\\Noselect) "/" "[Gmail]"',
            ]
            harita, ozeller = folders.imap_klasor_haritasi_olustur(satirlar)
        self.assertEqual("INBOX", harita["Gelen Kutusu"])
        self.assertEqual('"[Gmail]/Sent Mail"', harita["Gönderilen E-postalar"])
        self.assertIn(ozel_ad, ozeller)

    def test_arsiv_adi_guvenlik_kurallari(self):
        with load_mail_module("folders", stubs={"mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None)}) as folders:
            self.assertEqual("Şiirler 2026", folders.arsiv_klasor_adini_dogrula(" Şiirler 2026 "))
            for ad in ("", "INBOX", "[Gmail]/Yeni", "../kaçış", 'çift"tırnak', "\t"):
                with self.subTest(ad=ad):
                    with self.assertRaises(folders.MailHatasi):
                        folders.arsiv_klasor_adini_dogrula(ad)
            with self.assertRaisesRegex(folders.MailHatasi, "zaten var"):
                folders.arsiv_klasor_adini_dogrula("Şiirler", ["şiirler"])

    def test_konusmalar_gruplanir_okunmamis_ve_ek_bilgisi_birlesir(self):
        mailler = [
            {"id": "3", "thread_id": "t1", "liste_gosterim": "Mehmet", "is_seen": False, "ek_var": False},
            {"id": "2", "thread_id": "t1", "liste_gosterim": "Eski", "is_seen": True, "ek_var": True},
            {"id": "1", "thread_id": "", "liste_gosterim": "Tek", "is_seen": True},
        ]
        with load_mail_module("conversation") as conversation:
            gruplar = conversation.epostalari_konusmalara_grupla(mailler)
            uidler = conversation.secimleri_uidlere_genislet(gruplar, ["3"])
        self.assertEqual(2, len(gruplar))
        self.assertEqual(["3", "2"], gruplar[0]["ids"])
        self.assertEqual(1, gruplar[0]["okunmamis_sayisi"])
        self.assertTrue(gruplar[0]["ek_var"])
        self.assertIn("2 e-posta", gruplar[0]["liste_gosterim"])
        self.assertEqual(["3", "2"], uidler)

    def test_konusma_gosterimi_klasorler_arasi_toplam_sayiyi_kullanir(self):
        with load_mail_module("conversation") as conversation:
            gruplar = conversation.epostalari_konusmalara_grupla([
                {
                    "id": "2", "thread_id": "th1", "kimden": "Ahmet",
                    "liste_gosterim": "Ahmet", "is_seen": True,
                    "toplam_ileti_sayisi": 5,
                },
                {
                    "id": "1", "thread_id": "th1", "kimden": "Ahmet",
                    "liste_gosterim": "Ahmet", "is_seen": True,
                    "toplam_ileti_sayisi": 5,
                },
            ])
        self.assertEqual(5, gruplar[0]["ileti_sayisi"])
        self.assertEqual(["2", "1"], gruplar[0]["ids"])
        self.assertIn("5 e-posta", gruplar[0]["liste_gosterim"])

    def test_konusma_siniri_en_az_bir_grup_dondurur(self):
        with load_mail_module("conversation") as conversation:
            sonuc = conversation.epostalari_konusmalara_grupla(
                [{"id": "1"}, {"id": "2"}], sinir=0
            )
        self.assertEqual(1, len(sonuc))


class EkOnbellekTestleri(unittest.TestCase):
    def _yukle(self, workspace, *, kimlik=None, db_kayitlari=None, kaydet_hatasi=None):
        kaydedilen = []
        db_kayitlari = db_kayitlari if db_kayitlari is not None else []

        def kaydet(_mesaj_id, kayitlar, tamamlandi):
            kaydedilen.append((list(kayitlar), tamamlandi))
            if kaydet_hatasi:
                raise kaydet_hatasi

        stubs = {
            "mail.mail_store": module(
                "mail.mail_store",
                mesaj_onbellek_kimligini_al=lambda *a: kimlik,
                ek_kayitlarini_kaydet=kaydet,
                ek_kayitlarini_al=lambda _id: list(db_kayitlari),
            ),
            "mail.paths": module("mail.paths", EKLER_KLASORU=str(workspace.attachment_dir)),
            "mail.text_utils": module(
                "mail.text_utils",
                guvenli_dosya_adi=lambda ad, varsayilan="ek_dosya": os.path.basename(str(ad or varsayilan)).replace("..", "_"),
            ),
        }
        return load_mail_module("attachment_cache", stubs=stubs), kaydedilen

    def test_ekler_atomik_kaydedilir_ve_db_kaydi_uretilir(self):
        with temporary_workspace() as workspace:
            yonetici, kaydedilen = self._yukle(
                workspace, kimlik={"message_id": 7, "uidvalidity": 99}
            )
            with yonetici as cache:
                self.assertTrue(
                    cache.ekleri_onbellege_kaydet(
                        "Kullanici@Example.com", "INBOX", 12,
                        [("şiir.txt", b"icerik")], tamamlandi=True,
                    )
                )
            kayit = kaydedilen[0][0][0]
            dosya = workspace.attachment_dir / kayit["local_path"]
            self.assertTrue(dosya.is_file())
            self.assertEqual(b"icerik", dosya.read_bytes())
            self.assertEqual(hashlib.sha256(b"icerik").hexdigest(), kayit["sha256"])
            self.assertTrue(kaydedilen[0][1])

    def test_kimlik_yoksa_dosya_ve_db_kaydi_olusturulmaz(self):
        with temporary_workspace() as workspace:
            yonetici, kaydedilen = self._yukle(workspace, kimlik=None)
            with yonetici as cache:
                self.assertFalse(cache.ekleri_onbellege_kaydet("a@example.com", "INBOX", 1, [("a", b"x")]))
            self.assertEqual([], kaydedilen)
            self.assertEqual([], list(workspace.attachment_dir.rglob("*")))

    def test_db_kayit_hatasinda_yeni_dosya_temizlenir(self):
        with temporary_workspace() as workspace:
            yonetici, _ = self._yukle(
                workspace,
                kimlik={"message_id": 7, "uidvalidity": 99},
                kaydet_hatasi=RuntimeError("db hatası"),
            )
            with yonetici as cache:
                with self.assertRaises(RuntimeError):
                    cache.ekleri_onbellege_kaydet("a@example.com", "INBOX", 1, [("a.txt", b"x")])
            self.assertEqual([], [p for p in workspace.attachment_dir.rglob("*") if p.is_file()])

    def test_onbellek_dogrulanarak_okunur_boyut_ve_hash_bozulmasi_reddedilir(self):
        with temporary_workspace() as workspace:
            goreli = "hesap/klasor/1_1/a.txt"
            dosya = workspace.attachment_dir / goreli
            dosya.parent.mkdir(parents=True)
            dosya.write_bytes(b"dogru")
            kayit = {
                "file_name": "a.txt",
                "local_path": goreli,
                "size_bytes": 5,
                "sha256": hashlib.sha256(b"dogru").hexdigest(),
            }
            yonetici, _ = self._yukle(workspace, db_kayitlari=[kayit])
            with yonetici as cache:
                self.assertEqual([("a.txt", b"dogru")], cache.ekleri_onbellekten_al(1))
                dosya.write_bytes(b"yanlis")
                self.assertIsNone(cache.ekleri_onbellekten_al(1))

    def test_dizin_disina_cikma_reddedilir(self):
        with temporary_workspace() as workspace:
            yonetici, _ = self._yukle(workspace)
            with yonetici as cache:
                with self.assertRaisesRegex(ValueError, "güvenli dizinin dışına"):
                    cache._guvenli_tam_yol("../../kaçış.txt")


if __name__ == "__main__":
    unittest.main()
