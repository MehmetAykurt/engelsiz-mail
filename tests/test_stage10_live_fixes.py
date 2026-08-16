# -*- coding: utf-8 -*-
"""Canlı NVDA testinde belirlenen erişilebilirlik ve sayaç düzeltmeleri."""

from __future__ import annotations

import ast
import unittest

from support import MAIL_ROOT, load_mail_module, module


class Stage10LiveFixTests(unittest.TestCase):
    @staticmethod
    def _compose_stubs(message_center):
        class Dialog:
            pass

        return {
            "wx": module("wx", Dialog=Dialog, ID_OK=5100),
            "gui": module("gui"),
            "ui": module("ui", message=lambda _metin: None),
            "mail.config": module(
                "mail.config",
                ayarlari_yukle=lambda: {},
                adres_otomatik_kaydet_ayari_yukle=lambda: False,
            ),
            "mail.contacts": module(
                "mail.contacts",
                adres_anahtari=lambda adres: str(adres or "").casefold(),
                kisileri_yukle=lambda: [],
                rehbere_ekle=lambda _adres: None,
                rehberi_yukle=lambda: [],
            ),
            "mail.errors": module("mail.errors", MailHatasi=Exception),
            "mail.folders": module(
                "mail.folders",
                taslak_klasor_adaylarini_temizle=lambda _deger: [],
            ),
            "mail.draft_service": module(
                "mail.draft_service",
                taslagi_sunucuya_kaydet=lambda *a, **k: None,
            ),
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.message_center": module(
                "mail.message_center",
                mesaj_soyle_ve_sonra_calistir=message_center,
            ),
            "mail.message_parser": module(
                "mail.message_parser",
                adres_basligini_duzenle=lambda deger: str(deger or ""),
            ),
            "mail.smtp_client": module(
                "mail.smtp_client",
                eposta_mesaji_olustur=lambda *a, **k: None,
                smtp_ssl_ile_gonder=lambda *a, **k: None,
            ),
            "mail.text_utils": module(
                "mail.text_utils",
                guvenli_coz=lambda deger: str(deger or ""),
            ),
            "mail.ui_helpers": module(
                "mail.ui_helpers",
                arka_plan_gorev_jetonu_olustur=lambda *a, **k: None,
                arka_plan_gorevlerini_gecersiz_kil=lambda *a, **k: None,
                arka_planda_calistir=lambda *a, **k: None,
                gorev_icin_guvenli_call_after=lambda *a, **k: None,
                gorunum_denetimlerine_uygula=lambda *a, **k: None,
                pencere_kullanilabilir_mi=lambda *a, **k: True,
            ),
            "mail.validators": module(
                "mail.validators",
                alici_basligini_cozumle=lambda _deger: ([], []),
            ),
            "mail.ui.contacts_window": module(
                "mail.ui.contacts_window",
                KisiSecPenceresi=object,
            ),
        }

    def test_send_success_is_spoken_before_callback_and_window_close(self):
        events = []
        pending_callbacks = []

        def message_center(text, callback, **kwargs):
            events.append(("message", text, kwargs.get("ad")))
            pending_callbacks.append(callback)

        stubs = self._compose_stubs(message_center)
        with load_mail_module("ui.compose_window", stubs=stubs) as compose_window:
            window = compose_window.YeniPostaPenceresi.__new__(
                compose_window.YeniPostaPenceresi
            )
            window.gonderildi_callback = lambda: events.append(("post_send",))
            window.EndModal = lambda code: events.append(("close", code))

            window.gonderim_basarili(("kullanici@example.com",))

            self.assertEqual(
                [("message", "E-posta başarıyla gönderildi.", "E-posta gönderim sonucu")],
                events,
            )
            self.assertEqual(1, len(pending_callbacks))

            pending_callbacks[0]()

        self.assertEqual(
            [
                ("message", "E-posta başarıyla gönderildi.", "E-posta gönderim sonucu"),
                ("post_send",),
                ("close", 5100),
            ],
            events,
        )

    def test_folder_view_displays_pending_delete_adjustment_without_mutating_cache(self):
        class FakeList:
            def __init__(self):
                self.rows = []
                self.enabled = True

            def IsEnabled(self):
                return self.enabled

            def Enable(self):
                self.enabled = True

            def DeleteAllItems(self):
                self.rows = []

            def InsertItem(self, index, text):
                self.rows.insert(index, [text, ""])

            def SetItem(self, index, column, text):
                self.rows[index][column] = text

            def SetFocus(self):
                pass

        def count_message(_category, info):
            total = info.get("messages") if isinstance(info, dict) else None
            return f"Toplam {total} ileti." if isinstance(total, int) else ""

        stubs = {
            "wx": module("wx", CallAfter=lambda callback, *args: callback(*args)),
            "mail.folder_counts": module(
                "mail.folder_counts",
                klasor_secimi_sayisi_mesaji=count_message,
            ),
            "mail.logger": module("mail.logger", hata_kaydet=lambda *a, **k: None),
            "mail.ui_helpers": module(
                "mail.ui_helpers", pencere_kullanilabilir_mi=lambda _obj: True
            ),
        }
        with load_mail_module("ui.folder_view", stubs=stubs) as folder_view:
            class Window:
                liste_modu = folder_view.LISTE_MODU_KLASOR
                secili_kategori = "Gelen Kutusu"
                kategori_isimleri = ["Gelen Kutusu"]
                ozel_klasorler = []
                liste = FakeList()
                _klasor_sayisi_cache = {
                    "Gelen Kutusu": {"messages": 9, "unseen": 2}
                }

                def klasor_modunu_hazirla(self):
                    self.liste_modu = folder_view.LISTE_MODU_KLASOR

                def klasor_liste_ogeleri(self):
                    return ["Gelen Kutusu"]

                def tum_kategoriler(self):
                    return ["Gelen Kutusu"]

                def liste_secim_ver(self, _index, odak_ver=True):
                    self.focus_requested = odak_ver

                def _bekleyen_toplu_islem_sayilarini_uygula(self, values):
                    self.adjustment_input = values
                    return {"Gelen Kutusu": {"messages": 8, "unseen": 1}}

            window = Window()
            folder_view.klasor_gorunumunu_goster(window)

        self.assertEqual("Toplam 8 ileti", window.liste.rows[0][1])
        self.assertEqual(9, window._klasor_sayisi_cache["Gelen Kutusu"]["messages"])
        self.assertIs(window.adjustment_input, window._klasor_sayisi_cache)

    def test_server_count_cache_remains_raw_and_adjustment_is_display_only(self):
        discovery_source = (MAIL_ROOT / "ui" / "folder_discovery.py").read_text(
            encoding="utf-8"
        )
        view_source = (MAIL_ROOT / "ui" / "folder_view.py").read_text(
            encoding="utf-8"
        )
        discovery_tree = ast.parse(discovery_source)
        view_tree = ast.parse(view_source)

        forbidden_methods = {
            "_klasor_sayisi_onbellegi_yukle",
            "klasorleri_kesfet_sonuc",
            "gonderim_sonrasi_esitle_sonuc",
            "sistem_klasor_sayilarini_guncelle_sonuc",
        }
        for node in discovery_tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in forbidden_methods:
                continue
            calls_adjustment = any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "_bekleyen_toplu_islem_sayilarini_uygula"
                for child in ast.walk(node)
            )
            self.assertFalse(
                calls_adjustment,
                f"{node.name} ham sunucu sayısını kalıcı önbelleğe yazmadan önce değiştirmemelidir.",
            )

        view_methods = {
            "klasor_gorunumunu_goster",
            "klasor_sayilarini_gorunumde_guncelle",
        }
        adjusted_methods = set()
        for node in view_tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in view_methods:
                continue
            if any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "_bekleyen_toplu_islem_sayilarini_uygula"
                for child in ast.walk(node)
            ):
                adjusted_methods.add(node.name)
        self.assertEqual(view_methods, adjusted_methods)


if __name__ == "__main__":
    unittest.main()
