# -*- coding: utf-8 -*-

import hashlib
import os
import time

import globalVars

from .logger import hata_kaydet
from .storage import guvenli_json_oku, guvenli_json_yaz

KLASOR_SAYISI_ONBELLEK_DOSYASI = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail", "klasor_sayilari.json")


def klasor_sayisi_mesaji(kategori_adi, klasor_bilgisi=None, listelenen_sayi=None):
    """Klasör toplamı ve okunmamış sayısı için kısa NVDA bildirimi üretir."""
    kategori_adi = str(kategori_adi or "Klasör").strip() or "Klasör"
    bilgi = klasor_bilgisi if isinstance(klasor_bilgisi, dict) else {}
    toplam = bilgi.get("messages")
    okunmamis = bilgi.get("unseen")

    parcalar = [f"{kategori_adi} klasörü hazır."]
    if isinstance(toplam, int) and toplam >= 0:
        if isinstance(okunmamis, int) and okunmamis > 0:
            parcalar.append(f"Toplam {toplam} ileti, {okunmamis} okunmamış.")
        elif isinstance(okunmamis, int):
            parcalar.append(f"Toplam {toplam} ileti. Okunmamış ileti yok.")
        else:
            parcalar.append(f"Toplam {toplam} ileti.")
    elif isinstance(okunmamis, int) and okunmamis > 0:
        parcalar.append(f"{okunmamis} okunmamış ileti var.")

    if isinstance(listelenen_sayi, int):
        if listelenen_sayi > 0:
            parcalar.append(f"{listelenen_sayi} e-posta listelendi.")
        else:
            parcalar.append("Gösterilecek e-posta yok.")
    return " ".join(parcalar)


def klasor_secimi_sayisi_mesaji(kategori_adi=None, klasor_bilgisi=None):
    """Klasör listesi satırında gösterilecek kısa toplam/okunmamış bilgisini üretir.

    Tek liste modelinde klasör adı birinci sütunda, sayı bilgisi ikinci sütunda gösterilir.
    Sıfır iletili klasörlerde de gereksiz "Toplam 0" ifadesi yerine kısa bir mesaj döndürürüz.
    """
    bilgi = klasor_bilgisi if isinstance(klasor_bilgisi, dict) else {}
    toplam = bilgi.get("messages")
    okunmamis = bilgi.get("unseen")

    if isinstance(toplam, int) and toplam == 0:
        return "İleti yok."
    if isinstance(toplam, int) and toplam > 0:
        if isinstance(okunmamis, int) and okunmamis > 0:
            return f"Toplam {toplam} ileti, {okunmamis} okunmamış."
        return f"Toplam {toplam} ileti."
    if isinstance(okunmamis, int) and okunmamis > 0:
        return f"{okunmamis} okunmamış ileti var."
    return ""


def klasor_sayisi_onbellek_hesap_anahtari(eposta):
    """Klasör sayı önbelleğini hesaba bağlamak için açık e-posta yerine kısa hesap anahtarı üretir."""
    eposta = str(eposta or "").strip().lower()
    if not eposta:
        return ""
    try:
        return hashlib.sha256(eposta.encode("utf-8")).hexdigest()[:24]
    except Exception:
        return ""


def klasor_sayisi_bilgisini_duzenle(bilgi):
    """Klasör toplam/okunmamış bilgisini güvenli JSON biçimine çeker."""
    if not isinstance(bilgi, dict):
        return {}
    sonuc = {}
    for anahtar in ("messages", "unseen"):
        try:
            deger = bilgi.get(anahtar)
            if deger is None:
                continue
            sayi = int(str(deger).strip())
            if sayi < 0:
                continue
            sonuc[anahtar] = sayi
        except Exception:
            continue
    try:
        zaman = bilgi.get("zaman") or bilgi.get("time") or bilgi.get("timestamp")
        if zaman is not None:
            sonuc["zaman"] = int(float(str(zaman).strip()))
    except Exception:
        pass
    if sonuc and "zaman" not in sonuc:
        sonuc["zaman"] = int(time.time())
    return sonuc


def eski_bicim_klasor_sayilarini_al(veri):
    """Hesap anahtarı olmayan eski önbellek biçiminden klasör sayılarını çıkarır."""
    if not isinstance(veri, dict) or veri.get("hesap_anahtari"):
        return {}
    eski_klasorler = {}
    kaynak = veri.get("klasorler") if isinstance(veri.get("klasorler"), dict) else veri
    if not isinstance(kaynak, dict):
        return {}
    atlanacak_anahtarlar = {
        "surum",
        "guncelleme_zamani",
        "klasor_haritasi",
        "sistem_klasorler",
        "ozel_klasorler",
    }
    for ad, bilgi in kaynak.items():
        ad = str(ad or "").strip()
        if not ad or ad in atlanacak_anahtarlar:
            continue
        temiz = klasor_sayisi_bilgisini_duzenle(bilgi)
        if temiz:
            eski_klasorler[ad] = temiz
    return eski_klasorler




def klasor_adlarini_duzenle(deger):
    """Klasör adı listesini güvenli ve tekrarsız JSON listesine çeker."""
    sonuc = []
    if not isinstance(deger, (list, tuple)):
        return sonuc
    for ad in deger:
        ad = str(ad or "").strip()
        if ad and ad not in sonuc:
            sonuc.append(ad)
    return sonuc


def klasor_haritasini_duzenle(deger):
    """Görünen klasör adı -> IMAP klasör adı haritasını güvenli JSON biçimine çeker."""
    sonuc = {}
    if not isinstance(deger, dict):
        return sonuc
    for ad, imap_adi in deger.items():
        ad = str(ad or "").strip()
        imap_adi = str(imap_adi or "").strip()
        if ad and imap_adi:
            sonuc[ad] = imap_adi
    return sonuc


def klasor_adlari_onbellegi_yukle(eposta):
    """Son bilinen sistem/özel klasör adlarını ve IMAP haritasını JSON önbellekten yükler."""
    hesap_anahtari = klasor_sayisi_onbellek_hesap_anahtari(eposta)
    if not hesap_anahtari:
        return {}
    veri = guvenli_json_oku(KLASOR_SAYISI_ONBELLEK_DOSYASI, {})
    if not isinstance(veri, dict):
        return {}
    if str(veri.get("hesap_anahtari", "")) != hesap_anahtari:
        if not veri.get("hesap_anahtari"):
            return {}
        return {}
    harita = klasor_haritasini_duzenle(veri.get("klasor_haritasi", {}))
    sistem = klasor_adlarini_duzenle(veri.get("sistem_klasorler", []))
    ozeller = klasor_adlarini_duzenle(veri.get("ozel_klasorler", []))
    sonuc = {}
    if harita:
        sonuc["klasor_haritasi"] = harita
    if sistem:
        sonuc["sistem_klasorler"] = sistem
    if ozeller:
        sonuc["ozel_klasorler"] = ozeller
    return sonuc

def klasor_sayisi_onbellegi_yukle(eposta):
    """Son bilinen klasör toplam/okunmamış sayılarını JSON önbellekten yükler."""
    hesap_anahtari = klasor_sayisi_onbellek_hesap_anahtari(eposta)
    if not hesap_anahtari:
        return {}
    veri = guvenli_json_oku(KLASOR_SAYISI_ONBELLEK_DOSYASI, {})
    if not isinstance(veri, dict):
        return {}
    if str(veri.get("hesap_anahtari", "")) == hesap_anahtari:
        klasorler = veri.get("klasorler", {})
    elif not veri.get("hesap_anahtari"):
        klasorler = eski_bicim_klasor_sayilarini_al(veri)
    else:
        return {}
    if not isinstance(klasorler, dict):
        return {}
    sonuc = {}
    for ad, bilgi in klasorler.items():
        ad = str(ad or "").strip()
        temiz = klasor_sayisi_bilgisini_duzenle(bilgi)
        if ad and temiz:
            sonuc[ad] = temiz
    return sonuc


def klasor_sayisi_onbellegi_kaydet(
    eposta,
    cache,
    klasor_haritasi=None,
    ozel_klasorler=None,
    sistem_klasorler=None,
):
    """Klasör sayılarını ve son bilinen klasör adlarını küçük JSON önbelleğine yazar."""
    hesap_anahtari = klasor_sayisi_onbellek_hesap_anahtari(eposta)
    if not hesap_anahtari or not isinstance(cache, dict):
        return False
    temiz_klasorler = {}
    for ad, bilgi in cache.items():
        ad = str(ad or "").strip()
        temiz = klasor_sayisi_bilgisini_duzenle(bilgi)
        if ad and temiz:
            temiz_klasorler[ad] = temiz

    eski_veri = guvenli_json_oku(KLASOR_SAYISI_ONBELLEK_DOSYASI, {})
    if not isinstance(eski_veri, dict):
        eski_veri = {}
    elif str(eski_veri.get("hesap_anahtari", "")) != hesap_anahtari:
        if not eski_veri.get("hesap_anahtari"):
            eski_veri = {"klasorler": eski_bicim_klasor_sayilarini_al(eski_veri)}
        else:
            eski_veri = {}

    temiz_harita = klasor_haritasini_duzenle(klasor_haritasi)
    if not temiz_harita:
        temiz_harita = klasor_haritasini_duzenle(eski_veri.get("klasor_haritasi", {}))

    temiz_ozeller = klasor_adlarini_duzenle(ozel_klasorler)
    if not temiz_ozeller:
        temiz_ozeller = klasor_adlarini_duzenle(eski_veri.get("ozel_klasorler", []))

    temiz_sistem = klasor_adlarini_duzenle(sistem_klasorler)
    if not temiz_sistem:
        temiz_sistem = klasor_adlarini_duzenle(eski_veri.get("sistem_klasorler", []))

    veri = {
        "surum": 2,
        "hesap_anahtari": hesap_anahtari,
        "guncelleme_zamani": int(time.time()),
        "klasorler": temiz_klasorler,
    }
    if temiz_sistem:
        veri["sistem_klasorler"] = temiz_sistem
    if temiz_harita:
        veri["klasor_haritasi"] = temiz_harita
    if temiz_ozeller:
        veri["ozel_klasorler"] = temiz_ozeller
    return guvenli_json_yaz(KLASOR_SAYISI_ONBELLEK_DOSYASI, veri)


def klasor_sayisi_onbellegi_temizle():
    """Hesap silindiğinde kalıcı klasör sayı önbelleğini kaldırır."""
    try:
        if os.path.exists(KLASOR_SAYISI_ONBELLEK_DOSYASI):
            os.remove(KLASOR_SAYISI_ONBELLEK_DOSYASI)
            return True
    except Exception as e:
        hata_kaydet("Klasör sayı önbelleği temizlenemedi.", e)
    return False
