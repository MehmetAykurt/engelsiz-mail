# -*- coding: utf-8 -*-
"""Geliştiricinin diğer NVDA eklentilerini tanıtan ve indiren pencere."""

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
import winreg
from dataclasses import dataclass

import ui
import wx

from ..attachments import benzersiz_yol
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..ui_helpers import arka_planda_calistir, guvenli_call_after


JSON_ZAMAN_ASIMI_SANIYE = 15
INDIRME_ZAMAN_ASIMI_SANIYE = 30
AZAMI_JSON_BOYUTU = 128 * 1024
AZAMI_EKLENTI_BOYUTU = 100 * 1024 * 1024
INDIRME_PARCA_BOYUTU = 64 * 1024
INDIRILENLER_KAYIT_DEGERI = "{374DE290-123F-4565-9164-39C4925E467B}"
IZINLI_JSON_SUNUCULARI = {"raw.githubusercontent.com"}
IZINLI_INDIRME_SUNUCULARI = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


@dataclass(frozen=True)
class DigerEklenti:
    anahtar: str
    ad: str
    aciklama: str
    json_url: str


DIGER_EKLENTILER = (
    DigerEklenti(
        anahtar="engelsiz_nota",
        ad="Engelsiz Nota",
        aciklama=(
            "Engelsiz Nota e-katalog sisteminde eser aramanızı, eser "
            "ayrıntılarını incelemenizi ve favorilerinizi yönetmenizi sağlayan "
            "erişilebilir müzik kütüphanesi asistanıdır."
        ),
        json_url=(
            "https://raw.githubusercontent.com/MehmetAykurt/"
            "engelsiz-nota/main/update.json"
        ),
    ),
    DigerEklenti(
        anahtar="getem",
        ad="GETEM E-Kütüphane",
        aciklama=(
            "GETEM e-katalog sisteminde kitap aramanızı, kitap ayrıntılarını "
            "incelemenizi ve kişisel favori okuma listenizi yönetmenizi "
            "sağlayan erişilebilir kütüphane eklentisidir."
        ),
        json_url=(
            "https://raw.githubusercontent.com/MehmetAykurt/"
            "getem/main/update.json"
        ),
    ),
    DigerEklenti(
        anahtar="kurum_rehberi",
        ad="Kurum Rehberi",
        aciklama=(
            "Kurum ve personel iletişim bilgilerini kaydetme, arama, düzenleme, "
            "yedekleme, içe ve dışa aktarma özellikleri sunan erişilebilir ve "
            "özelleştirilebilir rehber eklentisidir."
        ),
        json_url=(
            "https://raw.githubusercontent.com/MehmetAykurt/"
            "kurum-rehberi/main/update.json"
        ),
    ),
    DigerEklenti(
        anahtar="suno",
        ad="Suno AI Prompt Oluşturucu",
        aciklama=(
            "Müzik türü, makam, tempo, duygu, enstrüman, vokal ve prodüksiyon "
            "seçenekleriyle Suno AI için erişilebilir biçimde İngilizce müzik "
            "promptları oluşturmanızı sağlar."
        ),
        json_url=(
            "https://raw.githubusercontent.com/MehmetAykurt/"
            "suno/main/update.json"
        ),
    ),
)


class DigerEklentiHatasi(Exception):
    """Kullanıcıya sade bir indirme hatası göstermek için kullanılır."""


def _https_adresini_dogrula(url, izinli_sunucular):
    try:
        parcalar = urllib.parse.urlsplit(str(url or ""))
    except (TypeError, ValueError) as hata:
        raise DigerEklentiHatasi("İndirme adresi geçersiz.") from hata
    sunucu = (parcalar.hostname or "").lower()
    if parcalar.scheme.lower() != "https" or sunucu not in izinli_sunucular:
        raise DigerEklentiHatasi("Güvenli bir indirme adresi alınamadı.")
    return str(url)


def _indirilenler_klasorunu_al():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as anahtar:
            deger, _ = winreg.QueryValueEx(anahtar, INDIRILENLER_KAYIT_DEGERI)
        yol = os.path.abspath(os.path.expandvars(str(deger)))
        if os.path.isdir(yol):
            return yol
    except (OSError, TypeError, ValueError):
        pass
    varsayilan = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(varsayilan):
        return varsayilan
    raise DigerEklentiHatasi("İndirilenler klasörü bulunamadı.")


def _json_katalogunu_al(json_url):
    _https_adresini_dogrula(json_url, IZINLI_JSON_SUNUCULARI)
    istek = urllib.request.Request(
        json_url,
        headers={"User-Agent": "Engelsiz-Mail-NVDA-Add-on"},
    )
    try:
        with urllib.request.urlopen(istek, timeout=JSON_ZAMAN_ASIMI_SANIYE) as yanit:
            _https_adresini_dogrula(yanit.geturl(), IZINLI_JSON_SUNUCULARI)
            veri = yanit.read(AZAMI_JSON_BOYUTU + 1)
    except DigerEklentiHatasi:
        raise
    except Exception as hata:
        raise DigerEklentiHatasi(
            "Eklenti bilgileri internetten alınamadı."
        ) from hata
    if len(veri) > AZAMI_JSON_BOYUTU:
        raise DigerEklentiHatasi("Eklenti bilgi dosyası beklenenden büyük.")
    try:
        katalog = json.loads(veri.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as hata:
        raise DigerEklentiHatasi("Eklenti bilgi dosyası okunamadı.") from hata
    if not isinstance(katalog, dict):
        raise DigerEklentiHatasi("Eklenti bilgi dosyasının biçimi geçersiz.")
    return katalog


def _dosya_adini_al(indirme_url):
    try:
        dosya_adi = os.path.basename(
            urllib.parse.unquote(urllib.parse.urlsplit(indirme_url).path)
        )
    except (TypeError, ValueError) as hata:
        raise DigerEklentiHatasi("İndirilecek dosyanın adı alınamadı.") from hata
    if not dosya_adi or not dosya_adi.lower().endswith(".nvda-addon"):
        raise DigerEklentiHatasi("Bağlantı bir NVDA eklenti dosyasına ait değil.")
    return dosya_adi


def _sha256_degerini_dogrula(deger):
    deger = str(deger or "").strip().lower()
    if len(deger) != 64 or any(karakter not in "0123456789abcdef" for karakter in deger):
        raise DigerEklentiHatasi("Eklentinin doğrulama bilgisi geçersiz.")
    return deger


def _eklentiyi_indir(eklenti):
    katalog = _json_katalogunu_al(eklenti.json_url)
    indirme_url = _https_adresini_dogrula(
        katalog.get("link"),
        IZINLI_INDIRME_SUNUCULARI,
    )
    beklenen_sha256 = _sha256_degerini_dogrula(katalog.get("sha256"))
    dosya_adi = _dosya_adini_al(indirme_url)
    indirilenler = _indirilenler_klasorunu_al()
    hedef_yol = benzersiz_yol(indirilenler, dosya_adi)
    gecici_yol = None
    istek = urllib.request.Request(
        indirme_url,
        headers={"User-Agent": "Engelsiz-Mail-NVDA-Add-on"},
    )
    try:
        with urllib.request.urlopen(istek, timeout=INDIRME_ZAMAN_ASIMI_SANIYE) as yanit:
            _https_adresini_dogrula(
                yanit.geturl(),
                IZINLI_INDIRME_SUNUCULARI,
            )
            try:
                bildirilen_boyut = int(yanit.headers.get("Content-Length", "0") or 0)
            except (TypeError, ValueError):
                bildirilen_boyut = 0
            if bildirilen_boyut > AZAMI_EKLENTI_BOYUTU:
                raise DigerEklentiHatasi("Eklenti dosyası beklenenden büyük.")

            ozet = hashlib.sha256()
            toplam = 0
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="engelsiz_mail_",
                suffix=".part",
                dir=indirilenler,
                delete=False,
            ) as gecici_dosya:
                gecici_yol = gecici_dosya.name
                while True:
                    parca = yanit.read(INDIRME_PARCA_BOYUTU)
                    if not parca:
                        break
                    toplam += len(parca)
                    if toplam > AZAMI_EKLENTI_BOYUTU:
                        raise DigerEklentiHatasi(
                            "Eklenti dosyası beklenenden büyük."
                        )
                    gecici_dosya.write(parca)
                    ozet.update(parca)
        if toplam <= 0:
            raise DigerEklentiHatasi("İndirilen eklenti dosyası boş.")
        if ozet.hexdigest().lower() != beklenen_sha256:
            raise DigerEklentiHatasi(
                "İndirilen dosyanın güvenlik doğrulaması başarısız oldu."
            )
        os.replace(gecici_yol, hedef_yol)
        gecici_yol = None
        return hedef_yol
    except DigerEklentiHatasi:
        raise
    except Exception as hata:
        raise DigerEklentiHatasi("Eklenti indirilemedi.") from hata
    finally:
        if gecici_yol and os.path.exists(gecici_yol):
            try:
                os.remove(gecici_yol)
            except OSError as hata:
                hata_kaydet("Yarım kalan eklenti indirmesi temizlenemedi.", hata)


def _indirilen_dosyayi_goster(dosya_yolu):
    try:
        subprocess.Popen(
            ["explorer.exe", "/select,", os.path.normpath(dosya_yolu)],
            close_fds=True,
        )
        return
    except Exception as hata:
        hata_kaydet("İndirilen eklenti dosyası Explorer'da seçilemedi.", hata)
    try:
        os.startfile(os.path.dirname(dosya_yolu))
    except Exception as hata:
        hata_kaydet("İndirilenler klasörü açılamadı.", hata)
        ui.message("İndirilenler klasörü açılamadı.")


def _indirme_threadi(ebeveyn, eklenti):
    try:
        dosya_yolu = _eklentiyi_indir(eklenti)
        sonuc = {"basarili": True, "dosya_yolu": dosya_yolu}
    except DigerEklentiHatasi as hata:
        hata_kaydet(f"{eklenti.ad} indirilemedi.", hata)
        sonuc = {"basarili": False, "mesaj": str(hata)}
    except Exception as hata:
        hata_kaydet(f"{eklenti.ad} indirilirken beklenmeyen hata.", hata)
        sonuc = {"basarili": False, "mesaj": "Eklenti indirilemedi."}
    guvenli_call_after(ebeveyn, _indirme_bitti, sonuc)


def _indirme_bitti(sonuc):
    if not sonuc.get("basarili"):
        ui.message(sonuc.get("mesaj") or "Eklenti indirilemedi.")
        return
    _indirilen_dosyayi_goster(sonuc["dosya_yolu"])


def _indirmeyi_arka_planda_baslat(ebeveyn, eklenti):
    arka_planda_calistir(_indirme_threadi, ebeveyn, eklenti)


class DigerEklentiPenceresi(wx.Dialog):
    def __init__(self, parent, eklenti):
        super().__init__(
            parent,
            title=eklenti.ad,
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.eklenti = eklenti

        ana_duzen = wx.BoxSizer(wx.VERTICAL)
        baslik = wx.StaticText(self, label=eklenti.ad)
        baslik.SetFont(baslik.GetFont().Bold())
        ana_duzen.Add(baslik, 0, wx.ALL, 10)

        ana_duzen.Add(
            wx.StaticText(self, label="Açıklama:"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )
        self.txt_aciklama = wx.TextCtrl(
            self,
            value=eklenti.aciklama,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        self.txt_aciklama.SetName("Açıklama")
        ana_duzen.Add(self.txt_aciklama, 1, wx.ALL | wx.EXPAND, 10)

        dugme_duzeni = wx.BoxSizer(wx.HORIZONTAL)
        self.indir_btn = wx.Button(self, label="&İndir")
        self.kapat_btn = wx.Button(self, wx.ID_CANCEL, label="&Kapat")
        self.indir_btn.Bind(wx.EVT_BUTTON, self.indir_basildi)
        dugme_duzeni.Add(self.indir_btn, 0, wx.ALL, 5)
        dugme_duzeni.Add(self.kapat_btn, 0, wx.ALL, 5)
        ana_duzen.Add(dugme_duzeni, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

        self.SetSizer(ana_duzen)
        self.SetSize((610, 330))
        self.CenterOnParent()
        wx.CallAfter(self.txt_aciklama.SetFocus)

    def indir_basildi(self, event):
        ebeveyn = self.GetParent()
        eklenti = self.eklenti
        mesaj_soyle_ve_sonra_calistir(
            f"{eklenti.ad} indiriliyor.",
            lambda: _indirmeyi_arka_planda_baslat(ebeveyn, eklenti),
            ad=f"{eklenti.ad} indirmesini başlat",
        )
        self.EndModal(wx.ID_OK)
