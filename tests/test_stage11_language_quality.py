# -*- coding: utf-8 -*-
"""11. çalışma / 6. aşama: İngilizce dil ve erişilebilirlik kalite sözleşmeleri."""

from __future__ import annotations

from pathlib import Path
import gettext
import re
import unittest

from babel.messages import pofile

from support.module_loader import PROJECT_ROOT


PO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.po"
MO = PROJECT_ROOT / "locale" / "en" / "LC_MESSAGES" / "nvda.mo"
README_EN = PROJECT_ROOT / "doc" / "en" / "readme.html"
WHATS_NEW_EN = PROJECT_ROOT / "doc" / "en" / "ne-yeni.html"


def _katalog():
    with PO.open("r", encoding="utf-8") as f:
        return pofile.read_po(f)


def _ceviri(katalog, msgid):
    mesaj = katalog.get(msgid)
    if mesaj is None:
        raise AssertionError(f"Çeviri girdisi bulunamadı: {msgid}")
    return mesaj.string


def _erisim_harfi(metin):
    metin = (metin or "").split("\t", 1)[0]
    i = 0
    while i < len(metin) - 1:
        if metin[i] == "&":
            if metin[i + 1] == "&":
                i += 2
                continue
            return metin[i + 1].casefold()
        i += 1
    return None


class IngilizceDilKalitesiTestleri(unittest.TestCase):
    def test_ingilizce_cevirilerde_turkce_ozel_harf_kalmadi(self):
        katalog = _katalog()
        turkce_harfler = set("çğıöşüÇĞİÖŞÜ")
        sorunlar = []
        for mesaj in katalog:
            if not mesaj.id:
                continue
            ceviri = mesaj.string or ""
            if any(harf in ceviri for harf in turkce_harfler):
                sorunlar.append((mesaj.id, ceviri))
        self.assertEqual([], sorunlar)

    def test_ingilizce_belgelerde_turkce_ozel_harf_kalmadi(self):
        turkce_harfler = set("çğıöşüÇĞİÖŞÜ")
        sorunlar = []
        # User guide should be fully English. What's New intentionally names
        # Turkish search characters (I/İ/ı/i, ç, ğ, ö, ş, ü), so it is excluded
        # from this character-level check.
        for yol in (README_EN,):
            metin = yol.read_text(encoding="utf-8")
            kalan = sorted({h for h in turkce_harfler if h in metin})
            if kalan:
                sorunlar.append((yol.name, kalan))
        self.assertEqual([], sorunlar)

    def test_ingilizce_erisim_harfleri_ana_arayuz_gruplarinda_cakismiyor(self):
        katalog = _katalog()
        gruplar = {
            "ust_menuler": ["&Dosya", "&Hesap", "&E-posta", "&Görünüm", "&Ayarlar", "&Yardım"],
            "dosya": ["&Yeni e-posta yaz\tCtrl+N", "&Aç...\tCtrl+O", "&Kaydet...\tCtrl+S", "&Çıkış\tAlt+F4"],
            "hesap": ["&Bağlan...\tAlt+B", "Bağlantıyı &denetle...\tF9", "Hesap bilgilerini &sil"],
            "eposta": ["&Ara...\tCtrl+F", "&Tümünü işaretle\tCtrl+A", "İşaretleri &kaldır\tCtrl+Shift+A", "A&rşiv", "Kişil&er...\tAlt+K", "İm&za...\tAlt+I", "&Sil", "&Yenile\tF5"],
            "arsiv_alt": ["A&rşive gönder\tAlt+R", "Arşiv klasörlerini &yönet...\tAlt+Shift+R"],
            "sil_alt": ["&Sil\tAlt+S", "&Kalıcı olarak sil\tShift+Delete"],
            "gorunum": ["&Yazı tipi...", "Yazı &boyutu...", "Yazı &stili...", "&Metin rengi...", "&Arka plan rengi...", "Sistem &renklerini kullan", "&Varsayılan görünüme dön"],
            "ayarlar": ["&E-posta sayısı...", "&Bildirimler...", "Ön i&zleme", "&Konuşmaları grupla", "&Sil", "Gönderilen e-posta adreslerini oto&matik kaydet", "Escape tuşuyla eklentiyi kapa&t", "İçe/&dışa aktar...", "&Yerel veritabanını sıfırla..."],
            "yardim": ["&Yardım kılavuzu\tF1", "Ye&nilikler", "Geliştiricinin diğer &eklentileri", "&Hakkında", "Öneri ve &görüş bildir..."],
            "yazma": ["&Kime (e-posta adresi):", "Kişilerden &seç", "&Bilgi (e-posta adresi):", "&Gizli (e-posta adresi):", "K&onu:", "&E-posta metni:", "&Ekler:", "Dosya e&kle", "Eki k&aldır", "Taslaklara &kaydet", "Taslağı &sil"],
            "kisiler": ["&Ad:", "&Soyad:", "&E-posta adresi:", "&Kaydet", "&Kişiler:", "&Ekle", "&Düzenle", "&Sil", "&Kapat"],
            "geri_bildirim": ["&Ad:", "&Soyad:", "Yanıt için &e-posta adresiniz:", "&Konu:", "&Bildirim metni:", "&Gönder"],
            "arama": ["Arama &türünü seçin:", "&Aranacak metin:", "&Ara", "E-postayı &aç", "&Klasöre git"],
            "bildirim": ["&Yeni e-posta geldiğinde bildir", "&Sesle bildir", "&Mesajla bildir", "&Varsayılan sistem sesini kullan", "&Kullanıcı tanımlı WAV dosyası kullan", "G&öz at...", "&Dinle", "Gönderen e-posta &adresini bildir", "&Konuyu bildir", "&Tamam", "İ&ptal"],
            "arsiv_yonetimi": ["&Arşiv klasörleri:", "&Yeni oluştur", "Yeniden &adlandır", "&Sil", "&Kapat"],
            "imza": ["&İmza metni:", "&Kaydet", "&Sil", "İ&ptal"],
            "okuma": ["&Ekleri kaydet", "&Yanıtla", "İ&let", "A&rşivle", "&Sil", "&Kapat"],
        }
        sorunlar = []
        for grup, msgidler in gruplar.items():
            gorulen = {}
            for msgid in msgidler:
                ceviri = _ceviri(katalog, msgid)
                harf = _erisim_harfi(ceviri)
                if not harf:
                    sorunlar.append(f"{grup}: erişim harfi yok: {ceviri}")
                    continue
                if harf in gorulen:
                    sorunlar.append(f"{grup}: {harf}: {gorulen[harf]} / {ceviri}")
                else:
                    gorulen[harf] = ceviri
        self.assertEqual([], sorunlar)

    def test_ingilizce_yardim_kisayollari_ingilizce_arayuzle_uyumlu(self):
        readme = README_EN.read_text(encoding="utf-8")
        self.assertIn("<strong>File — Alt+F:</strong>", readme)
        self.assertNotIn("<strong>File — Alt+D:</strong>", readme)
        self.assertIn("<strong>View — Alt+V:</strong>", readme)
        self.assertIn("<strong>Settings — Alt+S:</strong>", readme)
        self.assertIn("<strong>Help — Alt+H:</strong>", readme)
        self.assertIn("<kbd>Alt</kbd> + <kbd>C</kbd> to move to Cc", readme)
        self.assertIn("<kbd>Alt</kbd> + <kbd>B</kbd> to move to Bcc", readme)
        self.assertIn("<strong>Opens the Engelsiz Mail window.</strong>", readme)
        readme_tr = (PROJECT_ROOT / "doc" / "tr" / "readme.html").read_text(encoding="utf-8")
        self.assertIn("<strong>Engelsiz Mail penceresini açar.</strong>", readme_tr)

    def test_ingilizce_yardimda_bilinen_bozuk_ceviri_kaliplari_yok(self):
        readme = README_EN.read_text(encoding="utf-8")
        bozuklar = [
            "Press the key to open the link",
            "When opened with <kbd>N</kbd> to move to the next link",
            "<kbd>F10</kbd>Open the context menu",
            "Empty Spam folder...</strong> can be selected",
            "<kbd>Ctrl</kbd> + <kbd>F</kbd> The shortcut or",
            "<strong>Close</strong> The button or",
            "<strong>To</strong> The field is used",
            "Automatically save recipient addresses</strong> When this option is enabled",
            "Manage archive folders...</strong> lets you manage archive folders",
            "<strong>Open...</strong> Use the option",
            "<strong>Preview</strong> When this option is enabled",
            "<strong>Notifications...</strong> Use this option",
            "Email <strong>Send</strong> button or",
        ]
        self.assertEqual([], [kalip for kalip in bozuklar if kalip in readme])

    def test_mo_katalogu_duzeltilmis_erisim_harflerini_iceriyor(self):
        with MO.open("rb") as f:
            tr = gettext.GNUTranslations(f)
        self.assertEqual("C&heck connection...\tF9", tr.gettext("Bağlantıyı &denetle...\tF9"))
        self.assertEqual("Font s&tyle...", tr.gettext("Yazı &stili..."))
        self.assertEqual("Feedback &message:", tr.gettext("&Bildirim metni:"))
        self.assertEqual("Archi&ve", tr.gettext("A&rşivle"))

    def test_ingilizce_cevirilerde_basit_noktalama_kusuru_yok(self):
        katalog = _katalog()
        sorunlar = []
        for mesaj in katalog:
            if not mesaj.id:
                continue
            ceviri = mesaj.string or ""
            if re.search(r"\s+[,.!?;:](?:\s|$)", ceviri):
                sorunlar.append((mesaj.id, ceviri))
            if "  " in ceviri and "\n" not in ceviri:
                sorunlar.append((mesaj.id, ceviri))
        self.assertEqual([], sorunlar)


if __name__ == "__main__":
    unittest.main()
