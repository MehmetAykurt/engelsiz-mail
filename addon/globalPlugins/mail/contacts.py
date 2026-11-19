# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import email.utils
import os

import globalVars

from .errors import MailHatasi
from .storage import guvenli_json_oku, guvenli_json_yaz, json_islemi
from .validators import eposta_adresi_gecerli_mi

AZAMI_KISI_SAYISI = 1000
AZAMI_ADRES_GECMISI = 200
REHBER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "adres.json")
KISILER_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "kisiler.json")


def adres_anahtari(adres):
    """Adres geçmişini büyük/küçük harften bağımsız karşılaştırır."""
    return str(adres or "").strip().casefold()


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
        except UnicodeEncodeError:
            temiz_ad = tam_ad.replace("\r", " ").replace("\n", " ").strip()
            if any(karakter in temiz_ad for karakter in (",", ";", '"', "<", ">")):
                temiz_ad = '"' + temiz_ad.replace("\\", "\\\\").replace('"', '\\"') + '"'
            return f"{temiz_ad} <{eposta}>" if temiz_ad else eposta
        except Exception:
            return eposta
    return eposta


def rehberi_yukle(kesin=False):
    adresler = guvenli_json_oku(REHBER_DOSYASI, [], kesin=kesin)
    if not isinstance(adresler, list):
        return []
    temiz = []
    gorulen = set()
    for adres in adresler:
        adres = str(adres).strip()
        anahtar = adres_anahtari(adres)
        if not anahtar or anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        temiz.append(adres)
    return temiz[:AZAMI_ADRES_GECMISI]


@json_islemi
def rehbere_ekle(yeni_adres):
    yeni_adres = str(yeni_adres or "").strip()
    if not yeni_adres:
        return False
    yeni_anahtar = adres_anahtari(yeni_adres)
    try:
        mevcut_adresler = rehberi_yukle(kesin=True)
    except OSError:
        # Okunamayan adres geçmişinin üzerine eksik liste yazma.
        return False
    adresler = [
        adres for adres in mevcut_adresler
        if adres_anahtari(adres) != yeni_anahtar
    ]
    adresler.insert(0, yeni_adres)
    return guvenli_json_yaz(REHBER_DOSYASI, adresler[:AZAMI_ADRES_GECMISI])


def kisileri_yukle(kesin=False):
    """Manuel oluşturulan kişileri ad, soyad ve e-posta alanlarıyla yükler."""
    veriler = guvenli_json_oku(KISILER_DOSYASI, [], kesin=kesin)
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
    return kisiler[:AZAMI_KISI_SAYISI]


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
    return guvenli_json_yaz(KISILER_DOSYASI, temiz[:AZAMI_KISI_SAYISI])


@json_islemi
def kisi_ekle_veya_guncelle(kisi, eski_eposta=None):
    """Yeni kişiyi ekler veya eski e-posta adresine sahip kaydı günceller."""
    kisi = {
        "ad": str((kisi or {}).get("ad", "")).strip(),
        "soyad": str((kisi or {}).get("soyad", "")).strip(),
        "eposta": str((kisi or {}).get("eposta", "")).strip(),
    }
    if not eposta_adresi_gecerli_mi(kisi["eposta"]):
        raise MailHatasi(_("Lütfen geçerli bir e-posta adresi yazın."))
    try:
        kisiler = kisileri_yukle(kesin=True)
    except OSError:
        # Okunamayan kişi listesinin üzerine eksik liste yazma.
        return False
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
        if len(sonuc) >= AZAMI_KISI_SAYISI:
            # Sınırı aşan kayıtlar kaydederken sessizce atılırdı; bunun yerine reddet.
            raise MailHatasi(
                _('Kişi sayısı sınırına ({0}) ulaşıldı. Yeni kişi eklemek için önce bazı kişileri silin.').format(AZAMI_KISI_SAYISI)
            )
        sonuc.append(kisi)
    return kisileri_kaydet(sonuc)


@json_islemi
def kisi_sil(eposta):
    """Remove one identity from the latest list, preserving concurrent additions."""
    anahtar = str(eposta or "").strip().casefold()
    try:
        kisiler = kisileri_yukle(kesin=True)
    except OSError:
        return False
    return kisileri_kaydet([kisi for kisi in kisiler if kisi_anahtari(kisi) != anahtar])

