# -*- coding: utf-8 -*-

import email.utils
import re
import unicodedata


_ASCII_YEREL_KARAKTERLER = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.!#$%&'*+/=?^_`{|}~-"
)


def bildirim_ses_dosyasi_duzenle(dosya_yolu):
    """Kullanıcı tanımlı bildirim sesi dosya yolunu temizler."""
    dosya_yolu = str(dosya_yolu or "").strip()
    if not dosya_yolu:
        return ""
    return dosya_yolu


def alici_basligini_cozumle(kime):
    """Alıcı alanını geçerli adresler ve geçersiz girdiler olarak ayırır.

    Gönderim güvenliği için bir alandaki hatalı girdiler sessizce atılmaz.
    Boş ayraçlar yok sayılır; yinelenen geçerli adresler tekilleştirilir.
    """
    adresler = []
    gecersizler = []
    gorulen = set()
    kaynak = str(kime or "").replace(";", ",").strip()
    kaynak = kaynak.rstrip(" ,")
    if not kaynak:
        return adresler, gecersizler

    for ad, adres in email.utils.getaddresses([kaynak]):
        ad = str(ad or "").strip()
        adres = str(adres or "").strip()
        if not ad and not adres:
            continue
        if not eposta_adresi_gecerli_mi(adres):
            gecersiz = adres or ad
            if gecersiz and gecersiz not in gecersizler:
                gecersizler.append(gecersiz)
            continue
        anahtar = adres.casefold()
        if anahtar not in gorulen:
            adresler.append(adres)
            gorulen.add(anahtar)

    # Ayrıştırıcı tamamen boş sonuç ürettiyse kaynak metin yine de hatalıdır.
    if not adresler and not gecersizler:
        gecersizler.append(kaynak)
    return adresler, gecersizler


def alici_listesi_yap(kime):
    """Alıcı alanından geçerli ve tekrarsız e-posta adresleri çıkarır."""
    adresler, _gecersizler = alici_basligini_cozumle(kime)
    return adresler


def _yerel_bolum_karakteri_gecerli_mi(karakter):
    """SMTPUTF8 dot-atom yerel bölümünde kabul edilen karakteri denetler."""
    if karakter in _ASCII_YEREL_KARAKTERLER:
        return True
    if ord(karakter) < 128:
        return False
    # Uluslararası adreslerde harf, sayı ve birleştirme işaretlerini kabul et.
    # Denetim karakterleri, ayırıcılar ve adres ayrıştırmasını bozabilecek
    # Unicode noktalama/simge karakterleri bilinçli olarak reddedilir.
    return unicodedata.category(karakter)[:1] in {"L", "N", "M"}


def _alan_adi_gecerli_mi(alan):
    """Unicode alan adını IDNA karşılığı üzerinden güvenli biçimde denetler."""
    if alan.startswith(".") or alan.endswith(".") or ".." in alan:
        return False
    etiketler = alan.split(".")
    if len(etiketler) < 2:
        return False

    ascii_etiketler = []
    for etiket in etiketler:
        if not etiket:
            return False
        if etiket.startswith("-") or etiket.endswith("-"):
            return False
        try:
            ascii_etiket = etiket.encode("idna").decode("ascii")
        except (UnicodeError, ValueError):
            return False
        if not ascii_etiket or len(ascii_etiket.encode("ascii")) > 63:
            return False
        if ascii_etiket.startswith("-") or ascii_etiket.endswith("-"):
            return False
        if not re.fullmatch(r"[A-Za-z0-9-]+", ascii_etiket):
            return False
        ascii_etiketler.append(ascii_etiket)

    ascii_alan = ".".join(ascii_etiketler)
    return len(ascii_alan.encode("ascii")) <= 253


def eposta_adresi_gecerli_mi(eposta):
    """ASCII ve SMTPUTF8 e-posta adreslerini güvenli dot-atom kurallarıyla denetler."""
    eposta = str(eposta or "").strip()
    if not eposta:
        return False
    try:
        if len(eposta.encode("utf-8")) > 254:
            return False
    except UnicodeEncodeError:
        return False
    if any(karakter in eposta for karakter in (" ", "\t", "\r", "\n")):
        return False
    if eposta.count("@") != 1:
        return False

    yerel, alan = eposta.rsplit("@", 1)
    if not yerel or not alan:
        return False
    try:
        if len(yerel.encode("utf-8")) > 64:
            return False
    except UnicodeEncodeError:
        return False
    if yerel.startswith(".") or yerel.endswith(".") or ".." in yerel:
        return False
    if not all(_yerel_bolum_karakteri_gecerli_mi(karakter) for karakter in yerel):
        return False

    return _alan_adi_gecerli_mi(alan)
