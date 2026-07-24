# -*- coding: utf-8 -*-

import email.utils
import re


def bildirim_ses_dosyasi_duzenle(dosya_yolu):
    """Kullanıcı tanımlı bildirim sesi dosya yolunu temizler."""
    dosya_yolu = str(dosya_yolu or "").strip()
    if not dosya_yolu:
        return ""
    return dosya_yolu


def alici_listesi_yap(kime):
    """Alıcı alanından geçerli ve tekrarsız e-posta adresleri çıkarır."""
    adresler = []
    gorulen = set()
    kaynak = str(kime or "").replace(";", ",")
    for _ad, adres in email.utils.getaddresses([kaynak]):
        adres = str(adres or "").strip()
        anahtar = adres.lower()
        if eposta_adresi_gecerli_mi(adres) and anahtar not in gorulen:
            adresler.append(adres)
            gorulen.add(anahtar)
    for adres in re.findall(r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}", kaynak):
        adres = str(adres or "").strip()
        anahtar = adres.lower()
        if eposta_adresi_gecerli_mi(adres) and anahtar not in gorulen:
            adresler.append(adres)
            gorulen.add(anahtar)
    return adresler


def eposta_adresi_gecerli_mi(eposta):
    """E-posta adresini temel ve güvenli biçim kurallarına göre denetler."""
    eposta = str(eposta or "").strip()
    if not eposta or len(eposta) > 254:
        return False
    if any(karakter in eposta for karakter in (" ", "\t", "\r", "\n")):
        return False
    if eposta.count("@") != 1:
        return False

    yerel, alan = eposta.rsplit("@", 1)
    if not yerel or not alan or len(yerel) > 64 or len(alan) > 253:
        return False
    if yerel.startswith(".") or yerel.endswith(".") or ".." in yerel:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", yerel):
        return False
    if alan.startswith(".") or alan.endswith(".") or ".." in alan:
        return False

    etiketler = alan.split(".")
    if len(etiketler) < 2:
        return False
    for etiket in etiketler:
        if not etiket or len(etiket) > 63:
            return False
        if etiket.startswith("-") or etiket.endswith("-"):
            return False
        if not re.fullmatch(r"[A-Za-z0-9-]+", etiket):
            return False

    return True
