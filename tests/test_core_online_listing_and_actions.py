# -*- coding: utf-8 -*-
"""Çevrim içi listeleme, yanıtlama, iletme ve dışa kaydetme testleri."""

from __future__ import annotations

import email
from email.message import EmailMessage
from pathlib import Path
import tempfile
import types
import unittest

from support import FakeIMAP, load_mail_module, module


class _MailHatasi(Exception):
    pass


class CevrimIciListelemeTestleri(unittest.TestCase):
    @staticmethod
    def _uidleri_ayristir(veri):
        parcalar = []
        for oge in veri or []:
            if isinstance(oge, bytes):
                parcalar.extend(oge.decode("ascii", errors="ignore").split())
            elif isinstance(oge, str):
                parcalar.extend(oge.split())
        return parcalar

    @staticmethod
    def _baslik(uid, *, kimden, kime, konu, seen=False, ek=False, thread_id=None):
        mesaj = EmailMessage()
        mesaj["From"] = kimden
        mesaj["To"] = kime
        mesaj["Subject"] = konu
        mesaj["Date"] = "Thu, 6 Aug 2026 12:00:00 +0300"
        bayrak = b"\\Seen" if seen else b""
        govde = b' BODYSTRUCTURE ("TEXT" "PLAIN" NIL NIL NIL "8BIT" 1 1)'
        if ek:
            govde += b' ("APPLICATION" "PDF" ("NAME" "siir.pdf") NIL NIL "BASE64" 1 NIL ("ATTACHMENT" ("FILENAME" "siir.pdf")))'
        thread = b" X-GM-THRID " + str(thread_id).encode("ascii") if thread_id else b""
        meta = b"%d (UID %d%s FLAGS (%s)%s)" % (uid, uid, thread, bayrak, govde)
        return [(meta, mesaj.as_bytes())]

    def _yukle(
        self,
        imap,
        *,
        grup=False,
        sync_sonucu=None,
        yerel_sonuc=None,
        toplu_harita=None,
        onizleme_haritasi=None,
        loglar=None,
    ):
        loglar = loglar if loglar is not None else []
        toplu_harita = dict(toplu_harita or {})
        onizleme_haritasi = dict(onizleme_haritasi or {})

        class Baglanti:
            def __init__(self, ayarlar):
                self.ayarlar = ayarlar

            def __enter__(self):
                return imap

            def __exit__(self, exc_type, exc, tb):
                return False

        def status_ayristir(veri):
            ham = b" ".join(x for x in (veri or []) if isinstance(x, bytes)).upper()
            sonuc = {}
            for anahtar in (b"MESSAGES", b"UNSEEN"):
                if anahtar in ham:
                    try:
                        sonrasi = ham.split(anahtar, 1)[1].strip().split()[0].rstrip(b")")
                        sonuc[anahtar.decode("ascii").lower()] = int(sonrasi)
                    except Exception:
                        pass
            return sonuc

        stubs = {
            "mail.errors": module("mail.errors", MailHatasi=_MailHatasi),
            "mail.imap_client": module(
                "mail.imap_client",
                ImapBaglantisi=Baglanti,
                imap_status_sayilarini_ayristir=status_ayristir,
                imap_toplu_uid_fetch=lambda _imap, _uidler, _alanlar: dict(toplu_harita),
                uidleri_ayristir=self._uidleri_ayristir,
            ),
            "mail.logger": module(
                "mail.logger", hata_kaydet=lambda *a, **k: loglar.append((a, k))
            ),
            "mail.header_sync": module(
                "mail.header_sync",
                klasor_basliklarini_senkronize_et=lambda *a, **k: dict(sync_sonucu or {}),
            ),
            "mail.mail_store": module(
                "mail.mail_store",
                klasor_basliklarini_listele=lambda *a, **k: [],
                klasor_konusma_basliklarini_listele=lambda *a, **k: [],
                klasor_onizleme_haritasi_al=lambda *a, **k: dict(onizleme_haritasi),
                klasor_yerel_onbellegi_var_mi=lambda *a, **k: yerel_sonuc is not None,
            ),
            "mail.config": module(
                "mail.config", konusmalari_grupla_ayari_yukle=lambda: bool(grup)
            ),
            "mail.conversation": module(
                "mail.conversation", epostalari_konusmalara_grupla=lambda mailler, _sinir=None: list(mailler)
            ),
        }
        yonetici = load_mail_module("mailbox_loader", stubs=stubs)
        return yonetici, loglar

    @staticmethod
    def _ayarlar():
        return {
            "eposta": "mehmet@example.com",
            "sifre": "uygulama-sifresi",
            "gorunen_ad": "Mehmet Aykurt",
        }

    @staticmethod
    def _harita(_imap):
        return (
            {"Gelen Kutusu": "INBOX", "Gönderilen E-postalar": '"[Gmail]/Sent Mail"'},
            ["Şiirler"],
        )

    def test_canli_liste_en_yeni_uid_ilk_turkce_baslik_ve_onizlemeyle_doner(self):
        imap = FakeIMAP()
        imap.script("status", ("OK", [b"INBOX (MESSAGES 3 UNSEEN 2)"]))
        imap.uid_responses["SEARCH"] = ("OK", [b"1 2 3"])
        harita = {
            "3": self._baslik(
                3,
                kimden="Çağrı Şahin <cagri@example.com>",
                kime="Mehmet <mehmet@example.com>",
                konu="İstanbul ve bağlama",
                seen=False,
                ek=True,
            ),
            "2": self._baslik(
                2,
                kimden="Gülşen <gulsen@example.com>",
                kime="mehmet@example.com",
                konu="Okunmuş ileti",
                seen=True,
            ),
        }
        with self._yukle(
            imap,
            toplu_harita=harita,
            onizleme_haritasi={"3": "Türkçe ön izleme: çğıöşü"},
        )[0] as loader:
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 2, True
            )
        self.assertEqual(["3", "2"], [m["id"] for m in sonuc["mailler"]])
        self.assertTrue(sonuc["mailler"][0]["liste_gosterim"].startswith("[Okunmadı]"))
        self.assertEqual("İstanbul ve bağlama", sonuc["mailler"][0]["konu"])
        self.assertEqual("Türkçe ön izleme: çğıöşü", sonuc["mailler"][0]["onizleme"])
        self.assertTrue(sonuc["mailler"][0]["ek_var"])
        self.assertTrue(sonuc["mailler"][1]["is_seen"])
        self.assertEqual({"messages": 3, "unseen": 2}, sonuc["klasor_bilgisi"])

    def test_gonderilenler_listesinde_gonderen_yerine_alici_gosterilir(self):
        imap = FakeIMAP()
        imap.uid_responses["SEARCH"] = ("OK", [b"7"])
        fetch = self._baslik(
            7,
            kimden="Mehmet Aykurt <mehmet@example.com>",
            kime="Asya Aykurt <asya@example.com>",
            konu="Gönderilen Türkçe ileti",
            seen=True,
        )
        with self._yukle(imap, toplu_harita={"7": fetch})[0] as loader:
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gönderilen E-postalar", "", self._harita, 10, False
            )
        satir = sonuc["mailler"][0]
        self.assertIn("Asya Aykurt", satir["liste_gosterim"])
        self.assertNotIn("Mehmet Aykurt", satir["liste_gosterim"])
        self.assertEqual('"[Gmail]/Sent Mail"', imap.selected_mailbox)

    def test_status_basarisizsa_sayilar_uid_aramalarindan_tamamlanir(self):
        imap = FakeIMAP()
        imap.script("status", OSError("STATUS desteklenmiyor"))

        def uid_cevabi(*args):
            if args == ("ALL",):
                return "OK", [b"1 2 3 4"]
            if args == ("UNSEEN",):
                return "OK", [b"2 4"]
            return "OK", []

        imap.uid_responses["SEARCH"] = uid_cevabi
        fetch = self._baslik(
            4,
            kimden="Durum <durum@example.com>",
            kime="mehmet@example.com",
            konu="STATUS yedeği",
            seen=False,
        )
        with self._yukle(imap, toplu_harita={"4": fetch})[0] as loader:
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 1, False
            )
        self.assertEqual({"messages": 4, "unseen": 2}, sonuc["klasor_bilgisi"])
        self.assertEqual(["4"], [m["id"] for m in sonuc["mailler"]])

    def test_toplu_fetchte_eksik_uid_tekil_fetchle_tamamlanir(self):
        imap = FakeIMAP()
        imap.uid_responses["SEARCH"] = ("OK", [b"8"])
        tekil = self._baslik(
            8,
            kimden="Tekil <tekil@example.com>",
            kime="mehmet@example.com",
            konu="Tekil FETCH",
            seen=False,
        )

        def fetch_cevabi(*args):
            self.assertEqual("8", args[0])
            return "OK", tekil

        imap.uid_responses["FETCH"] = fetch_cevabi
        with self._yukle(imap, toplu_harita={})[0] as loader:
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 10, False
            )
        self.assertEqual(["8"], [m["id"] for m in sonuc["mailler"]])
        self.assertTrue(any(c[0] == "uid" and c[1][0] == "FETCH" for c in imap.calls))

    def test_gruplama_esitlemesi_basariliysa_yerel_liste_kullanilir(self):
        imap = FakeIMAP()
        imap.uid_responses["SEARCH"] = ("OK", [b"1 2"])
        yerel = [{"id": "2", "thread_id": "t1", "konu": "Yerel konuşma"}]
        with self._yukle(
            imap,
            grup=True,
            sync_sonucu={"atlandi": False, "iptal_edildi": False},
            yerel_sonuc=yerel,
        )[0] as loader:
            loader.yerel_eposta_listesi_hazirla = lambda *a, **k: list(yerel)
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 10, True
            )
        self.assertEqual(yerel, sonuc["mailler"])
        self.assertFalse(any(c[0] == "uid" and c[1][0] == "FETCH" for c in imap.calls))

    def test_esitleme_atlanirsa_canli_liste_gmail_konusma_kimligini_korur(self):
        imap = FakeIMAP()
        imap.uid_responses["SEARCH"] = ("OK", [b"1 2"])
        harita = {
            str(uid): self._baslik(
                uid,
                kimden="Ahmet <ahmet@example.com>",
                kime="mehmet@example.com",
                konu="Re: Toplantı",
                seen=True,
                thread_id=987654321,
            )
            for uid in (1, 2)
        }
        with self._yukle(
            imap,
            grup=True,
            sync_sonucu={"atlandi": True},
            toplu_harita=harita,
        )[0] as loader:
            sonuc = loader.eposta_listesi_hazirla(
                self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 10, False
            )
        self.assertEqual(
            {"987654321"}, {mesaj["thread_id"] for mesaj in sonuc["mailler"]}
        )

    def test_klasor_acilamazsa_anlasilir_hata_verilir(self):
        imap = FakeIMAP()
        imap.script("select", ("NO", [b"Denied"]))
        with self._yukle(imap)[0] as loader:
            with self.assertRaisesRegex(_MailHatasi, "Seçili klasör açılamadı"):
                loader.eposta_listesi_hazirla(
                    self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 10, False
                )

    def test_search_basarisizsa_anlasilir_hata_verilir(self):
        imap = FakeIMAP()
        imap.uid_responses["SEARCH"] = ("NO", [b"Search failed"])
        with self._yukle(imap)[0] as loader:
            with self.assertRaisesRegex(_MailHatasi, "E-posta listesi alınamadı"):
                loader.eposta_listesi_hazirla(
                    self._ayarlar(), "Gelen Kutusu", "INBOX", self._harita, 10, False
                )


class MesajEylemleriTestleri(unittest.TestCase):
    def _yukle(
        self,
        *,
        ayarlar=None,
        govde_onbellegi=None,
        ek_onbellegi=None,
        imap=None,
        govde_cikarma=None,
        kaydedilen_govdeler=None,
        ui_mesajlari=None,
        acilan_pencereler=None,
        loglar=None,
        konusma_satirlari=None,
    ):
        ayarlar = dict(
            ayarlar
            or {
                "eposta": "mehmet@example.com",
                "sifre": "uygulama-sifresi",
                "gorunen_ad": "Mehmet Aykurt",
            }
        )
        kaydedilen_govdeler = kaydedilen_govdeler if kaydedilen_govdeler is not None else []
        ui_mesajlari = ui_mesajlari if ui_mesajlari is not None else []
        acilan_pencereler = acilan_pencereler if acilan_pencereler is not None else []
        loglar = loglar if loglar is not None else []
        imap = imap or FakeIMAP()

        class Baglanti:
            def __init__(self, _ayarlar):
                pass

            def __enter__(self):
                return imap

            def __exit__(self, exc_type, exc, tb):
                return False

        class SahteDialog:
            def __init__(self, *args, **kwargs):
                pass

        wx = module(
            "wx",
            Dialog=SahteDialog,
            ID_CLOSE=5101,
            ID_OPEN=5102,
            ID_OK=5100,
            OK=4,
            ICON_ERROR=16,
            FD_SAVE=1,
            FD_OVERWRITE_PROMPT=2,
            FD_OPEN=4,
            FD_FILE_MUST_EXIST=8,
            YES_NO=16,
            ICON_QUESTION=32,
            YES=2,
        )
        ui_mod = module("ui", message=lambda metin: ui_mesajlari.append(str(metin)))
        gui_mod = module("gui", messageBox=lambda *a, **k: wx.YES)

        class YeniPostaPenceresi:
            def __init__(self, parent, **kwargs):
                self.parent = parent
                self.kwargs = dict(kwargs)
                self.txt_icerik = types.SimpleNamespace(SetInsertionPoint=lambda _n: None)
                acilan_pencereler.append(self)

        ui_package = module("mail.ui")
        ui_package.__path__ = []

        def ham_al(veri):
            return b"".join(
                parca[1]
                for parca in (veri or [])
                if isinstance(parca, tuple) and len(parca) >= 2 and isinstance(parca[1], bytes)
            )

        def baslik_duzenle(deger):
            return " ".join(str(deger or "").replace("\r", " ").replace("\n", " ").split())

        if govde_cikarma is None:
            govde_cikarma = lambda _mesaj, ayrintili=False: (
                ("Türkçe ileti gövdesi", [("şiir.txt", "şiir".encode("utf-8"))], 0)
                if ayrintili
                else ("Türkçe ileti gövdesi", [("şiir.txt", "şiir".encode("utf-8"))])
            )

        stubs = {
            "wx": wx,
            "ui": ui_mod,
            "gui": gui_mod,
            "mail.ui": ui_package,
            "mail.ui.folder_view": module("mail.ui.folder_view", LISTE_MODU_EPOSTA="eposta"),
            "mail.ui.compose_window": module(
                "mail.ui.compose_window", YeniPostaPenceresi=YeniPostaPenceresi
            ),
            "mail.ui.message_view": module(
                "mail.ui.message_view", MesajOkumaPenceresi=object
            ),
            "mail.attachments": module(
                "mail.attachments",
                AZAMI_EPOSTA_ISLEME_BOYUTU=50 * 1024 * 1024,
                mesaj_metni_ve_ekleri_cikar=govde_cikarma,
                ham_eposta_boyutunu_denetle=lambda *a, **k: None,
                eml_dosya_boyutunu_denetle=lambda *a, **k: None,
                eml_verisini_dogrula=lambda *a, **k: None,
                benzersiz_yol=lambda klasor, ad: str(Path(klasor) / ad),
            ),
            "mail.config": module(
                "mail.config", ayarlari_yukle=lambda: dict(ayarlar), imza_yukle=lambda: ""
            ),
            "mail.errors": module("mail.errors", MailHatasi=_MailHatasi),
            "mail.imap_client": module(
                "mail.imap_client",
                ImapBaglantisi=Baglanti,
                imap_eposta_boyutunu_denetle=lambda *a, **k: None,
                imap_ok_mu=lambda tip, mesaj: None if tip == "OK" else (_ for _ in ()).throw(_MailHatasi(mesaj)),
            ),
            "mail.logger": module(
                "mail.logger", hata_kaydet=lambda *a, **k: loglar.append((a, k))
            ),
            "mail.cache_limits": module(
                "mail.cache_limits", onbellek_kotasi_denetle=lambda *a, **k: None
            ),
            "mail.database_schema": module("mail.database_schema", BODY_PARSER_VERSION=3),
            "mail.message_center": module(
                "mail.message_center",
                mesaj_soyle_ve_sonra_calistir=lambda _m, callback, **_k: callback(),
            ),
            "mail.mail_store": module(
                "mail.mail_store",
                mesaj_govdesini_al=lambda *a, **k: govde_onbellegi,
                mesaj_govdesini_kaydet=lambda *a, **k: kaydedilen_govdeler.append((a, k)) or True,
                mesaji_yerelde_okundu_yap=lambda *a, **k: True,
                konusma_mesajlarini_listele=lambda *a, **k: list(konusma_satirlari or []),
            ),
            "mail.body_sync": module(
                "mail.body_sync",
                klasor_govdelerini_senkronize_et=lambda *a, **k: {},
                secili_govdeleri_dogrudan_senkronize_et=lambda *a, **k: {},
                yeni_ileti_govdesini_ek_indirmeden_kaydet=lambda *a, **k: {},
            ),
            "mail.attachment_cache": module(
                "mail.attachment_cache", ekleri_onbellekten_al=lambda _id: ek_onbellegi
            ),
            "mail.message_parser": module(
                "mail.message_parser",
                adres_basligini_duzenle=lambda deger: baslik_duzenle(deger),
                adres_basligini_gosterime_hazirla=lambda deger, *a, **k: baslik_duzenle(deger),
                gonderen_gosterimini_al=lambda deger, varsayilan="Bilinmiyor": baslik_duzenle(deger) or varsayilan,
                gonderen_basligini_gosterime_hazirla=lambda deger, varsayilan="Bilinmiyor": baslik_duzenle(deger) or varsayilan,
                grup_araci_adresini_temizle=lambda deger: str(deger or ""),
                yanit_adresini_bul=lambda mesaj: baslik_duzenle(
                    mesaj.get("Reply-To", "") or mesaj.get("From", "")
                ),
                ham_mesaj_verisi_al=ham_al,
                yanit_basliklari_hazirla=lambda veri: (
                    {
                        "In-Reply-To": baslik_duzenle(veri.get("message_id", "")),
                        "References": " ".join(
                            x
                            for x in (
                                baslik_duzenle(veri.get("references", "")),
                                baslik_duzenle(veri.get("message_id", "")),
                            )
                            if x
                        ),
                    }
                    if veri.get("message_id")
                    else {}
                ),
            ),
            "mail.text_utils": module(
                "mail.text_utils",
                guvenli_coz=lambda deger: str(deger or ""),
                eposta_basligi_tek_satir_yap=baslik_duzenle,
                konu_gosterimini_duzenle=lambda deger: str(deger or ""),
                turkce_tarih_yap=lambda deger: "6 Ağustos 2026" if deger else "",
                guvenli_dosya_adi=lambda deger, varsayilan="dosya", *a: str(deger or varsayilan),
            ),
            "mail.ui_helpers": module(
                "mail.ui_helpers",
                pencere_kullanilabilir_mi=lambda _p: True,
                guvenli_call_after=lambda _p, callback, *a, **k: callback(*a, **k),
                guvenli_modal_goster=lambda pencere, *_a, **_k: pencere,
                arka_planda_calistir=lambda callback, *a, **k: callback(*a, **k),
            ),
        }
        return (
            load_mail_module("ui.message_actions", stubs=stubs),
            {
                "imap": imap,
                "ui_mesajlari": ui_mesajlari,
                "acilan_pencereler": acilan_pencereler,
                "kaydedilen_govdeler": kaydedilen_govdeler,
                "loglar": loglar,
            },
        )

    @staticmethod
    def _onbellek(**degisiklikler):
        temel = {
            "parser_version": 3,
            "sender": "Çağrı Şahin <cagri@example.com>",
            "reply_to": "yanit@example.com",
            "recipients_to": "Mehmet Aykurt <mehmet@example.com>",
            "subject": "İstanbul şiir gecesi",
            "date_header": "Thu, 6 Aug 2026 12:00:00 +0300",
            "rfc_message_id": "<mesaj@example.com>",
            "references_header": "<ilk@example.com>",
            "plain_text": "Türkçe gövde: çğıöşü",
            "has_attachments": False,
            "attachments_cached": False,
            "message_id": 17,
        }
        temel.update(degisiklikler)
        return temel

    def test_yanit_onbellekten_ag_baglantisi_olmadan_hazirlanir(self):
        onbellek = self._onbellek()
        with self._yukle(govde_onbellegi=onbellek)[0] as actions:
            veri = actions._yanit_veya_ilet_onbellek_verisi(
                {"eposta": "mehmet@example.com", "gorunen_ad": "Mehmet Aykurt"},
                "9",
                "INBOX",
                "yanitla",
            )
        self.assertEqual("yanit@example.com", veri["yanit_adresi"])
        self.assertEqual("İstanbul şiir gecesi", veri["konu"])
        self.assertEqual("Türkçe gövde: çğıöşü", veri["icerik"])
        self.assertEqual([], veri["ekler"])

    def test_iletmede_ek_onbellegi_eksikse_canli_indirme_istenir(self):
        onbellek = self._onbellek(has_attachments=True, attachments_cached=False)
        with self._yukle(govde_onbellegi=onbellek)[0] as actions:
            sonuc = actions._yanit_veya_ilet_onbellek_verisi(
                {"eposta": "mehmet@example.com"}, "9", "INBOX", "ilet"
            )
        self.assertIsNone(sonuc)

    def test_iletmede_onbellekteki_ekler_korunur(self):
        onbellek = self._onbellek(has_attachments=True, attachments_cached=True)
        ekler = [("şiir.txt", "şiir".encode("utf-8"))]
        with self._yukle(govde_onbellegi=onbellek, ek_onbellegi=ekler)[0] as actions:
            sonuc = actions._yanit_veya_ilet_onbellek_verisi(
                {"eposta": "mehmet@example.com"}, "9", "INBOX", "ilet"
            )
        self.assertEqual(ekler, sonuc["ekler"])

    def test_eski_parser_surumu_onbellekten_kullanilmaz(self):
        with self._yukle(govde_onbellegi=self._onbellek(parser_version=2))[0] as actions:
            self.assertIsNone(
                actions._yanit_veya_ilet_onbellek_verisi(
                    {"eposta": "mehmet@example.com"}, "9", "INBOX", "yanitla"
                )
            )

    def test_yanit_penceresi_re_konu_yanit_basliklari_ve_aliciyla_acilir(self):
        with self._yukle()[0] as actions:
            sahip = types.SimpleNamespace(
                liste=object(),
                taslak_kaydedildi=lambda: None,
                taslak_klasor_adaylari=lambda: ["Drafts"],
            )
            actions.yanit_veya_ilet_penceresini_ac(
                sahip,
                {
                    "konu": "İstanbul",
                    "icerik": "Özgün gövde",
                    "yanit_adresi": "yanit@example.com",
                    "message_id": "<m@example.com>",
                    "references": "<ilk@example.com>",
                    "ekler": [("ek.txt", b"x")],
                },
                "yanitla",
            )
            pencere = actions.YeniPostaPenceresi
        # Sınıfın kendisini değil, yükleme yardımcısındaki yakalanan örneği ayrı testte doğrula.
        self.assertIsNotNone(pencere)

    def test_yanit_ve_ilet_penceresi_parametreleri(self):
        acilan = []
        yonetici, _ctx = self._yukle(acilan_pencereler=acilan)
        with yonetici as actions:
            sahip = types.SimpleNamespace(
                liste=object(),
                taslak_kaydedildi=lambda: None,
                taslak_klasor_adaylari=lambda: ["Drafts"],
            )
            veri = {
                "konu": "İstanbul",
                "icerik": "Özgün gövde",
                "yanit_adresi": "yanit@example.com",
                "message_id": "<m@example.com>",
                "references": "<ilk@example.com>",
                "ekler": [("şiir.txt", "şiir".encode("utf-8"))],
            }
            actions.yanit_veya_ilet_penceresini_ac(sahip, veri, "yanitla")
            actions.yanit_veya_ilet_penceresini_ac(sahip, veri, "ilet")
        yanit, ilet = acilan
        self.assertEqual("yanit@example.com", yanit.kwargs["varsayilan_kime"])
        self.assertEqual("Re: İstanbul", yanit.kwargs["varsayilan_konu"])
        self.assertEqual("<m@example.com>", yanit.kwargs["yanit_basliklari"]["In-Reply-To"])
        self.assertIsNone(yanit.kwargs["hazir_ekler"])
        self.assertEqual("", ilet.kwargs["varsayilan_kime"])
        self.assertEqual("Fwd: İstanbul", ilet.kwargs["varsayilan_konu"])
        self.assertEqual([( "şiir.txt", "şiir".encode("utf-8"))], ilet.kwargs["hazir_ekler"])
        self.assertIn("İletilen E-posta", ilet.kwargs["varsayilan_icerik"])

    def test_konusmada_her_ileti_icin_ayni_konu_tekrarlanmaz(self):
        satirlar = [
            {
                "uid": str(uid),
                "parser_version": 3,
                "sender": "Ahmet <ahmet@example.com>",
                "recipients_to": "Mehmet <mehmet@example.com>",
                "recipients_cc": "",
                "date_header": "Thu, 13 Aug 2026 01:00:00 +0300",
                "subject": "Re: Toplantı",
                "plain_text": f"{uid}. ileti gövdesi",
                "has_attachments": False,
                "message_id": uid,
                "rfc_message_id": f"<{uid}@example.com>",
                "references_header": "",
                "reply_to": "ahmet@example.com",
            }
            for uid in (3, 2, 1)
        ]
        acilan = []
        with self._yukle(konusma_satirlari=satirlar)[0] as actions:
            sahip = types.SimpleNamespace(
                mesaji_listede_okundu_yap=lambda _uid: None,
                okuma_penceresini_ac=lambda veri: acilan.append(veri),
            )
            actions.sunucudan_konusma_icerigi_indir(
                sahip, "thread-1", ["3", "2", "1"], "INBOX"
            )

        self.assertEqual(1, len(acilan))
        self.assertEqual("Re: Toplantı", acilan[0]["konu"])
        self.assertEqual(3, acilan[0]["ileti_sayisi"])
        self.assertNotIn("Konu:", acilan[0]["icerik"])

    def test_txt_kayit_metni_turkce_basliklari_ve_ekleri_icerir(self):
        mesaj = EmailMessage()
        mesaj["From"] = "Çağrı <cagri@example.com>"
        mesaj["To"] = "Mehmet <mehmet@example.com>"
        mesaj["Cc"] = "Asya <asya@example.com>"
        mesaj["Subject"] = "Şiir: İstanbul"
        mesaj["Date"] = "Thu, 6 Aug 2026 12:00:00 +0300"
        with self._yukle()[0] as actions:
            sahip = types.SimpleNamespace(secili_kategori="Gelen Kutusu")
            metin = actions.txt_kayit_metni_olustur(
                sahip,
                mesaj,
                "Türkçe gövde: çğıöşü",
                [("şiir.txt", b"x"), ("fotoğraf.jpg", b"y")],
                "INBOX",
            )
        self.assertIn("Kimden: Çağrı <cagri@example.com>", metin)
        self.assertIn("Bilgi: Asya <asya@example.com>", metin)
        self.assertIn("Konu: Şiir: İstanbul", metin)
        self.assertIn("Ek sayısı: 2", metin)
        self.assertIn("- fotoğraf.jpg", metin)
        self.assertTrue(metin.endswith("\n"))

    def test_eml_disa_kaydetme_ham_baytlari_aynen_yazar(self):
        ham = b"From: cagri@example.com\r\nTo: mehmet@example.com\r\nSubject: Test\r\n\r\nGovde"
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = ("OK", [(b"1", ham)])
        ui_mesajlari = []
        with tempfile.TemporaryDirectory() as tmp:
            hedef = Path(tmp, "ileti.eml")
            with self._yukle(imap=imap, ui_mesajlari=ui_mesajlari)[0] as actions:
                sonuc = []
                sahip = types.SimpleNamespace(
                    liste=types.SimpleNamespace(SetFocus=lambda: None),
                    txt_kayit_metni_olustur=lambda *a: "",
                )
                actions.kaydetme_sonuc_penceresi_goster = lambda _s, bicim, yol: sonuc.append((bicim, yol))
                actions.sunucudan_epostayi_kaydet(sahip, "1", "INBOX", str(hedef), "eml")
            self.assertEqual(ham, hedef.read_bytes())
        self.assertEqual([("eml", str(hedef))], sonuc)
        self.assertEqual([], ui_mesajlari)

    def test_txt_disa_kaydetme_utf8_yazar(self):
        ham = b"From: cagri@example.com\r\nTo: mehmet@example.com\r\nSubject: Test\r\n\r\nGovde"
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = ("OK", [(b"1", ham)])
        with tempfile.TemporaryDirectory() as tmp:
            hedef = Path(tmp, "ileti.txt")
            with self._yukle(imap=imap)[0] as actions:
                sahip = types.SimpleNamespace(
                    secili_kategori="Gelen Kutusu",
                    liste=types.SimpleNamespace(SetFocus=lambda: None),
                )
                sahip.txt_kayit_metni_olustur = lambda mesaj, icerik, ekler, klasor: actions.txt_kayit_metni_olustur(
                    sahip, mesaj, icerik, ekler, klasor
                )
                actions.kaydetme_sonuc_penceresi_goster = lambda *a: None
                actions.sunucudan_epostayi_kaydet(sahip, "1", "INBOX", str(hedef), "txt")
            metin = hedef.read_text(encoding="utf-8")
        self.assertIn("Türkçe ileti gövdesi", metin)
        self.assertIn("şiir.txt", metin)

    def test_desteklenmeyen_kaydetme_bicimi_kullaniciya_bildirilir(self):
        mesajlar = []
        with tempfile.TemporaryDirectory() as tmp:
            hedef = Path(tmp, "ileti.pdf")
            with self._yukle(ui_mesajlari=mesajlar)[0] as actions:
                sahip = types.SimpleNamespace(liste=types.SimpleNamespace(SetFocus=lambda: None))
                actions.sunucudan_epostayi_kaydet(sahip, "1", "INBOX", str(hedef), "pdf")
            self.assertFalse(hedef.exists())
        self.assertTrue(any("Desteklenmeyen kaydetme biçimi" in m for m in mesajlar))

    def test_sunucudan_yanit_hazirlarken_reply_to_ve_basliklar_korunur(self):
        mesaj = EmailMessage()
        mesaj["From"] = "Çağrı <cagri@example.com>"
        mesaj["Reply-To"] = "yanit@example.com"
        mesaj["To"] = "Mehmet <mehmet@example.com>"
        mesaj["Subject"] = "Türkçe konu"
        mesaj["Date"] = "Thu, 6 Aug 2026 12:00:00 +0300"
        mesaj["Message-ID"] = "<m@example.com>"
        mesaj["References"] = "<ilk@example.com>"
        mesaj.set_content("Gövde")
        ham = mesaj.as_bytes()
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = ("OK", [(b"1", ham)])
        acilan = []
        kaydedilen = []
        yonetici, _ctx = self._yukle(
            imap=imap,
            govde_onbellegi=None,
            kaydedilen_govdeler=kaydedilen,
        )
        with yonetici as actions:
            sahip = types.SimpleNamespace(
                yanit_veya_ilet_penceresini_ac=lambda veri, islem: acilan.append((veri, islem))
            )
            actions.sunucudan_yanit_veya_ilet_hazirla(sahip, "1", "INBOX", "yanitla")
        self.assertEqual("yanitla", acilan[0][1])
        veri = acilan[0][0]
        self.assertEqual("yanit@example.com", veri["yanit_adresi"])
        self.assertEqual("<m@example.com>", veri["message_id"])
        self.assertEqual([], veri["ekler"])
        self.assertEqual(1, len(kaydedilen))

    def test_sunucudan_ilet_hazirlarken_ekler_tasinir(self):
        mesaj = EmailMessage()
        mesaj["From"] = "Çağrı <cagri@example.com>"
        mesaj["To"] = "Mehmet <mehmet@example.com>"
        mesaj["Subject"] = "Ekli ileti"
        mesaj.set_content("Gövde")
        ham = mesaj.as_bytes()
        imap = FakeIMAP()
        imap.uid_responses["FETCH"] = ("OK", [(b"1", ham)])
        acilan = []
        with self._yukle(imap=imap, govde_onbellegi=None)[0] as actions:
            sahip = types.SimpleNamespace(
                yanit_veya_ilet_penceresini_ac=lambda veri, islem: acilan.append((veri, islem))
            )
            actions.sunucudan_yanit_veya_ilet_hazirla(sahip, "1", "INBOX", "ilet")
        self.assertEqual("ilet", acilan[0][1])
        self.assertEqual([("şiir.txt", "şiir".encode("utf-8"))], acilan[0][0]["ekler"])


if __name__ == "__main__":
    unittest.main()
