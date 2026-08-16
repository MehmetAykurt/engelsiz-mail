# -*- coding: utf-8 -*-
"""SQLite kayıt, listeleme, gövde kaydetme ve arama bütünleşme testleri."""

from __future__ import annotations

import importlib
import time
import unittest

from support import temporary_database


class _VeritabaniSenaryosu:
    eposta = "kullanici@example.com"
    klasor = "INBOX"
    uidvalidity = 777

    @staticmethod
    def modulleri_yukle():
        return (
            importlib.import_module("mail.mail_store"),
            importlib.import_module("mail.search"),
        )

    @classmethod
    def temel_veriyi_ekle(cls, store):
        hesap_id, klasor_id, degisti = store.hesap_ve_klasor_hazirla(
            cls.eposta, cls.klasor, "Gelen Kutusu", cls.uidvalidity
        )
        assert not degisti
        store.baslik_paketini_kaydet(
            hesap_id,
            klasor_id,
            cls.uidvalidity,
            [
                {
                    "uid": 10,
                    "gmail_message_id": "gm10",
                    "gmail_thread_id": "th1",
                    "rfc_message_id": "<10@example.com>",
                    "subject": "İstanbul şiir gecesi",
                    "sender": "Mehmet Aykurt <mehmet@example.com>",
                    "recipients_to": "kullanici@example.com",
                    "recipients_cc": "",
                    "reply_to": "yanit@example.com",
                    "internal_date": 1000,
                    "date_header": "Thu, 6 Aug 2026 10:00:00 +0300",
                    "preview": "Birinci ön izleme",
                    "has_attachments": True,
                    "flags": [],
                },
                {
                    "uid": 11,
                    "gmail_message_id": "gm11",
                    "gmail_thread_id": "th1",
                    "rfc_message_id": "<11@example.com>",
                    "subject": "İstanbul şiir gecesi yanıtı",
                    "sender": "Asya <asya@example.com>",
                    "recipients_to": "kullanici@example.com",
                    "internal_date": 2000,
                    "preview": "İkinci ön izleme",
                    "has_attachments": False,
                    "flags": ["\\Seen", "\\Answered"],
                },
                {
                    "uid": 12,
                    "gmail_message_id": "gm12",
                    "gmail_thread_id": "th2",
                    "rfc_message_id": "<12@example.com>",
                    "subject": "Kayseri toplantısı %100",
                    "sender": "Gülsüm <gulsum@example.com>",
                    "recipients_to": "kullanici@example.com",
                    "internal_date": 3000,
                    "preview": "Üçüncü ön izleme",
                    "has_attachments": False,
                    "flags": [],
                },
            ],
        )
        store.klasor_senkronizasyonunu_tamamla(klasor_id, cls.uidvalidity, [10, 11, 12])
        return hesap_id, klasor_id


class MailStoreTestleri(unittest.TestCase, _VeritabaniSenaryosu):
    def test_basliklar_en_yeni_uid_once_listelenir_ve_sinirlanir(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            liste = store.klasor_basliklarini_listele(self.eposta, self.klasor, 2)
        self.assertEqual([12, 11], [satir["uid"] for satir in liste])
        self.assertEqual("Kayseri toplantısı %100", liste[0]["subject"])

    def test_konusmalar_en_yeni_temsilciyle_gruplanir(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            liste = store.klasor_konusma_basliklarini_listele(self.eposta, self.klasor, 10)
        self.assertEqual(3, len(liste))
        self.assertEqual(12, liste[0]["uid"])
        thread1 = [s for s in liste if s["gmail_thread_id"] == "th1"]
        self.assertEqual([11, 10], [s["uid"] for s in thread1])

    def test_konusma_toplami_acik_klasor_disindaki_iletileri_de_sayar(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            hesap_id, _gelen_id = self.temel_veriyi_ekle(store)
            _hesap_id, gonderilen_id, _degisti = store.hesap_ve_klasor_hazirla(
                self.eposta, "[Gmail]/Sent Mail", "Gönderilen E-postalar", 888
            )
            store.baslik_paketini_kaydet(
                hesap_id,
                gonderilen_id,
                888,
                [{
                    "uid": 20,
                    "gmail_message_id": "gm20",
                    "gmail_thread_id": "th1",
                    "subject": "Re: İstanbul şiir gecesi",
                    "sender": self.eposta,
                    "recipients_to": "yanit@example.com",
                    "internal_date": 2500,
                    "flags": ["\\Seen"],
                }],
            )
            store.klasor_senkronizasyonunu_tamamla(gonderilen_id, 888, [20])
            liste = store.klasor_konusma_basliklarini_listele(
                self.eposta, self.klasor, 10
            )
        thread1 = [s for s in liste if s["gmail_thread_id"] == "th1"]
        self.assertEqual({3}, {s["toplam_ileti_sayisi"] for s in thread1})

    def test_konusma_mesajlari_tarih_sirasiyla_doner(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            liste = store.konusma_mesajlarini_listele(self.eposta, self.klasor, "th1")
        self.assertEqual([11, 10], [s["uid"] for s in liste])
        self.assertEqual("<10@example.com>", liste[1]["rfc_message_id"])

    def test_govde_eksigi_kaydetme_okuma_ve_onizleme_guncelleme(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            self.assertEqual(["10", "11"], store.govdesi_eksik_uidleri_al(self.eposta, self.klasor, [10, 11]))
            self.assertTrue(
                store.mesaj_govdesini_kaydet(
                    self.eposta, self.klasor, 10,
                    "Türkçe gövde metni\nİkinci satır", 1234,
                    "Thu, 6 Aug 2026 11:00:00 +0300",
                )
            )
            govde = store.mesaj_govdesini_al(self.eposta, self.klasor, 10)
            self.assertEqual("Türkçe gövde metni\nİkinci satır", govde["plain_text"])
            self.assertEqual(1234, govde["raw_size_bytes"])
            self.assertEqual([], store.govdesi_eksik_uidleri_al(self.eposta, self.klasor, [10]))
            self.assertTrue(store.mesaj_onizlemesini_kaydet(self.eposta, self.klasor, 10, "Yeni ön izleme"))
            liste = store.klasor_basliklarini_listele(self.eposta, self.klasor, 10)
        uid10 = next(s for s in liste if s["uid"] == 10)
        self.assertEqual("Yeni ön izleme", uid10["preview"])

    def test_bilinmeyen_uid_icin_govde_ve_onizleme_kaydedilmez(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            self.assertFalse(store.mesaj_govdesini_kaydet(self.eposta, self.klasor, 999, "x", 1))
            self.assertFalse(store.mesaj_onizlemesini_kaydet(self.eposta, self.klasor, 999, "x"))
            self.assertIsNone(store.mesaj_govdesini_al(self.eposta, self.klasor, 999))

    def test_ek_kayitlari_govdeden_sonra_kaydedilir(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            kimlik = store.mesaj_onbellek_kimligini_al(self.eposta, self.klasor, 10)
            with self.assertRaisesRegex(ValueError, "govdesi kaydedilmelidir"):
                store.ek_kayitlarini_kaydet(kimlik["message_id"], [], True)
            store.mesaj_govdesini_kaydet(self.eposta, self.klasor, 10, "gövde", 5)
            store.ek_kayitlarini_kaydet(
                kimlik["message_id"],
                [{
                    "part_path": "1.2",
                    "file_name": "şiir.txt",
                    "content_type": "text/plain",
                    "size_bytes": 6,
                    "sha256": "abc",
                    "local_path": "x/şiir.txt",
                }],
                True,
            )
            kayitlar = store.ek_kayitlarini_al(kimlik["message_id"])
            govde = store.mesaj_govdesini_al(self.eposta, self.klasor, 10)
        self.assertEqual("şiir.txt", kayitlar[0]["file_name"])
        self.assertEqual(1, govde["attachments_cached"])

    def test_okundu_isareti_ayni_mesajin_butun_klasor_uyeliklerine_yansir(self):
        with temporary_database() as (database, _workspace):
            store, _search = self.modulleri_yukle()
            hesap_id, _inbox_id = self.temel_veriyi_ekle(store)
            _h, arsiv_id, _d = store.hesap_ve_klasor_hazirla(self.eposta, '"Arşiv"', "Arşiv", 888)
            store.baslik_paketini_kaydet(
                hesap_id, arsiv_id, 888,
                [{
                    "uid": 55,
                    "gmail_message_id": "gm10",
                    "gmail_thread_id": "th1",
                    "subject": "İstanbul şiir gecesi",
                    "sender": "Mehmet <mehmet@example.com>",
                    "internal_date": 1000,
                    "flags": [],
                }],
            )
            store.klasor_senkronizasyonunu_tamamla(arsiv_id, 888, [55])
            self.assertTrue(store.mesaji_yerelde_okundu_yap(self.eposta, self.klasor, 10))
            with database.veritabani_baglantisi() as db:
                durumlar = [int(s[0]) for s in db.execute(
                    "SELECT is_seen FROM folder_messages fm JOIN messages m ON m.id=fm.message_id WHERE m.gmail_message_id='gm10'"
                ).fetchall()]
        self.assertEqual([1, 1], sorted(durumlar))

    def test_uidvalidity_degisiminde_eski_uyelikler_temizlenir(self):
        with temporary_database():
            store, _search = self.modulleri_yukle()
            self.temel_veriyi_ekle(store)
            _hesap, _klasor, degisti = store.hesap_ve_klasor_hazirla(
                self.eposta, self.klasor, "Gelen Kutusu", 999
            )
            liste = store.klasor_basliklarini_listele(self.eposta, self.klasor, 20)
        self.assertTrue(degisti)
        self.assertEqual([], liste)


class AramaTestleri(unittest.TestCase, _VeritabaniSenaryosu):
    def _hazirla(self, store):
        hesap_id, klasor_id = self.temel_veriyi_ekle(store)
        store.mesaj_govdesini_kaydet(
            self.eposta, self.klasor, 10,
            "Yüreğimdeki fısıltı ve bağlama ezgisi", 100,
        )
        store.mesaj_govdesini_kaydet(
            self.eposta, self.klasor, 11,
            "Yanıt gövdesi", 50,
        )
        return hesap_id, klasor_id

    def test_gonderen_konu_ve_icerik_sql_aramasi(self):
        with temporary_database():
            store, search = self.modulleri_yukle()
            self._hazirla(store)
            gonderen = search.epostalarda_ara(self.eposta, "Mehmet", "gonderen", fts_kullan=False)
            konu = search.epostalarda_ara(self.eposta, "İstanbul", "konu", fts_kullan=False)
            icerik = search.epostalarda_ara(self.eposta, "bağlama", "icerik", fts_kullan=False)
        self.assertEqual([10], [s["uid"] for s in gonderen])
        self.assertEqual([11, 10], [s["uid"] for s in konu])
        self.assertEqual([10], [s["uid"] for s in icerik])
        self.assertIn("Yüreğimdeki", icerik[0]["excerpt"])

    def test_okunmus_ve_okunmamis_aramasi(self):
        with temporary_database():
            store, search = self.modulleri_yukle()
            self._hazirla(store)
            okunmamis = search.epostalarda_ara(self.eposta, "", "okunmamis")
            okunmus = search.epostalarda_ara(self.eposta, "", "okunmus")
        self.assertEqual([12, 10], [s["uid"] for s in okunmamis])
        self.assertEqual([11], [s["uid"] for s in okunmus])

    def test_yuzde_ve_alt_cizgi_sql_jokeri_olarak_yorumlanmaz(self):
        with temporary_database():
            store, search = self.modulleri_yukle()
            self._hazirla(store)
            yuzde = search.epostalarda_ara(self.eposta, "%100", "konu", fts_kullan=False)
            alt = search.epostalarda_ara(self.eposta, "_", "konu", fts_kullan=False)
        self.assertEqual([12], [s["uid"] for s in yuzde])
        self.assertEqual([], alt)

    def test_fts5_varsa_turkce_konu_aramasi_sonuclanir(self):
        with temporary_database():
            store, search = self.modulleri_yukle()
            self._hazirla(store)
            fts_var = search.fts5_hazirla()
            sonuc = search.epostalarda_ara(self.eposta, "İstanbul şiir", "konu", fts_kullan=True)
        self.assertIsInstance(fts_var, bool)
        self.assertEqual([11, 10], [s["uid"] for s in sonuc])

    def test_bos_metin_ve_gecersiz_tur(self):
        with temporary_database():
            store, search = self.modulleri_yukle()
            self._hazirla(store)
            self.assertEqual([], search.epostalarda_ara(self.eposta, "  ", "konu"))
            with self.assertRaisesRegex(ValueError, "Geçersiz"):
                search.epostalarda_ara(self.eposta, "x", "yanlis")

    def test_bekleyen_silme_kaydindaki_ileti_aramadan_gizlenir(self):
        with temporary_database() as (database, _workspace):
            store, search = self.modulleri_yukle()
            hesap_id, _klasor_id = self._hazirla(store)
            simdi = int(time.time())
            with database.veritabani_baglantisi(yazma=True) as db:
                db.execute(
                    """INSERT INTO pending_deletions(
                        account_id, operation_type, source_folder, source_category,
                        source_uid, gmail_message_id, trash_folder, source_label,
                        remove_source_label, source_uidvalidity, request_token,
                        created_at, updated_at
                    ) VALUES (?, 'trash', 'INBOX', 'Gelen Kutusu', 10, 'gm10',
                              'Trash', '', 0, ?, 'token-10', ?, ?)""",
                    (hesap_id, self.uidvalidity, simdi, simdi),
                )
            sonuc = search.epostalarda_ara(self.eposta, "Mehmet", "gonderen", fts_kullan=False)
            liste = store.klasor_basliklarini_listele(self.eposta, self.klasor, 10)
        self.assertEqual([], sonuc)
        self.assertNotIn(10, [s["uid"] for s in liste])


if __name__ == "__main__":
    unittest.main()
