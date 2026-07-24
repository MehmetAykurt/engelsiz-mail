# -*- coding: utf-8 -*-

import email.utils
import os

import globalVars

from .errors import MailHatasi
from .storage import guvenli_json_oku, guvenli_json_yaz
from .validators import eposta_adresi_gecerli_mi

REHBER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "adres.json")
KISILER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "kisiler.json")


def kisi_anahtari(kisi):
    """Kişi kaydını karşılaştırmak için e-posta adresini küçük harfe çevirir."""
    return str((kisi or {}).get("eposta", "")).strip().lower()


def kisi_gorunen_ad(kisi):
    """Kişinin listelerde okunacak sade adını döndürür."""
    ad = str((kisi or {}).get("ad", "")).strip()
    soyad = str((kisi or {}).get("soyad", "")).strip()
    eposta = str((kisi or {}).get("eposta", "")).strip()
    tam_ad = " ".join(parca for parca in [ad, soyad] if parca).strip()
    parcalar = [parca for parca in (tam_ad, eposta) if parca]
    return " ".join(parcalar)


def kisi_eposta_basligi(kisi):
    """Kişiyi e-posta başlığına güvenli biçimde eklenebilir biçime getirir."""
    ad = str((kisi or {}).get("ad", "")).strip()
    soyad = str((kisi or {}).get("soyad", "")).strip()
    eposta = str((kisi or {}).get("eposta", "")).strip()
    tam_ad = " ".join(parca for parca in [ad, soyad] if parca).strip()
    if not eposta_adresi_gecerli_mi(eposta):
        return ""
    if tam_ad:
        try:
            return email.utils.formataddr((tam_ad, eposta))
        except Exception:
            return eposta
    return eposta


def rehberi_yukle():
    adresler = guvenli_json_oku(REHBER_DOSYASI, [])
    if not isinstance(adresler, list):
        return []
    temiz = []
    for adres in adresler:
        adres = str(adres).strip()
        if adres and adres not in temiz:
            temiz.append(adres)
    return temiz[:200]


def rehbere_ekle(yeni_adres):
    yeni_adres = str(yeni_adres or "").strip()
    if not yeni_adres:
        return False
    adresler = rehberi_yukle()
    if yeni_adres in adresler:
        adresler.remove(yeni_adres)
    adresler.insert(0, yeni_adres)
    return guvenli_json_yaz(REHBER_DOSYASI, adresler[:200])


def kisileri_yukle():
    """Manuel oluşturulan kişileri ad, soyad ve e-posta alanlarıyla yükler."""
    veriler = guvenli_json_oku(KISILER_DOSYASI, [])
    if not isinstance(veriler, list):
        return []
    kisiler = []
    gorulen = set()
    for kayit in veriler:
        if not isinstance(kayit, dict):
            continue
        kisi = {
            "ad": str(kayit.get("ad", "")).strip(),
            "soyad": str(kayit.get("soyad", "")).strip(),
            "eposta": str(kayit.get("eposta", "")).strip(),
        }
        anahtar = kisi_anahtari(kisi)
        if not anahtar or anahtar in gorulen:
            continue
        if not eposta_adresi_gecerli_mi(kisi["eposta"]):
            continue
        gorulen.add(anahtar)
        kisiler.append(kisi)
    kisiler.sort(key=lambda k: (str(k.get("ad", "")).lower(), str(k.get("soyad", "")).lower(), str(k.get("eposta", "")).lower()))
    return kisiler[:1000]


def kisileri_kaydet(kisiler):
    """Kişileri temizleyip JSON dosyasına yazar."""
    temiz = []
    gorulen = set()
    for kayit in kisiler or []:
        if not isinstance(kayit, dict):
            continue
        kisi = {
            "ad": str(kayit.get("ad", "")).strip(),
            "soyad": str(kayit.get("soyad", "")).strip(),
            "eposta": str(kayit.get("eposta", "")).strip(),
        }
        anahtar = kisi_anahtari(kisi)
        if not anahtar or anahtar in gorulen:
            continue
        if not eposta_adresi_gecerli_mi(kisi["eposta"]):
            continue
        gorulen.add(anahtar)
        temiz.append(kisi)
    temiz.sort(key=lambda k: (str(k.get("ad", "")).lower(), str(k.get("soyad", "")).lower(), str(k.get("eposta", "")).lower()))
    return guvenli_json_yaz(KISILER_DOSYASI, temiz[:1000])


def kisi_ekle_veya_guncelle(kisi, eski_eposta=None):
    """Yeni kişiyi ekler veya eski e-posta adresine sahip kaydı günceller."""
    kisi = {
        "ad": str((kisi or {}).get("ad", "")).strip(),
        "soyad": str((kisi or {}).get("soyad", "")).strip(),
        "eposta": str((kisi or {}).get("eposta", "")).strip(),
    }
    if not eposta_adresi_gecerli_mi(kisi["eposta"]):
        raise MailHatasi("Lütfen geçerli bir e-posta adresi yazın.")
    kisiler = kisileri_yukle()
    eski_anahtar = str(eski_eposta or "").strip().lower()
    yeni_anahtar = kisi_anahtari(kisi)
    sonuc = []
    eklendi = False
    for mevcut in kisiler:
        mevcut_anahtar = kisi_anahtari(mevcut)
        if eski_anahtar and mevcut_anahtar == eski_anahtar:
            if not eklendi:
                sonuc.append(kisi)
                eklendi = True
            continue
        if mevcut_anahtar == yeni_anahtar:
            if not eklendi:
                sonuc.append(kisi)
                eklendi = True
            continue
        sonuc.append(mevcut)
    if not eklendi:
        sonuc.append(kisi)
    return kisileri_kaydet(sonuc)
