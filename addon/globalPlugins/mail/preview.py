# -*- coding: utf-8 -*-
"""IMAP ön izleme verisini güvenli ve okunabilir metne dönüştürür."""

import email
from email import policy as email_policy
import quopri

from .attachments import mesaj_metni_ve_ekleri_cikar
from .message_parser import (
    onizleme_karakter_kumesi_bul,
    onizleme_verisini_metin_yap,
    onizleme_metnini_temizle,
    onizleme_metin_guvenli_mi,
    onizleme_kodlamasini_coz,
    onizleme_email_paketiyle_coz,
    onizleme_multipart_govde_coz,
)


def onizleme_metni_olustur(ham_veri):
    """IMAP üzerinden alınan kısa içerikten kullanıcıya okunabilir ön izleme üretir."""
    if not ham_veri:
        return ""

    # Öncelik Python'un email paketindedir. Bu yol Content-Type, charset,
    # Content-Transfer-Encoding, multipart/alternative ve iç içe MIME parçalarını
    # standart kurallara göre çözer. BODY.PEEK[TEXT] dış başlık getirmediğinde
    # geçici Content-Type başlığı eklenerek yine email paketi denenir.
    try:
        onizleme = onizleme_email_paketiyle_coz(ham_veri)
        if onizleme:
            return onizleme
    except Exception:
        pass

    # Standart e-posta çözümlemesi sonuç vermezse elle çözme yedeği kullanılır.
    try:
        onizleme = onizleme_multipart_govde_coz(ham_veri)
        if onizleme:
            return onizleme
    except Exception:
        pass

    karakter_kumesi = onizleme_karakter_kumesi_bul(ham_veri)

    try:
        ham_metin = onizleme_verisini_metin_yap(ham_veri, karakter_kumesi)
        ham_metin = onizleme_kodlamasini_coz(ham_metin, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(ham_metin)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
    except Exception:
        pass

    try:
        cozulmus_veri = quopri.decodestring(ham_veri)
        cozulmus_metin = onizleme_verisini_metin_yap(cozulmus_veri, karakter_kumesi)
        cozulmus_metin = onizleme_kodlamasini_coz(cozulmus_metin, karakter_kumesi)
        cozulmus_metin = onizleme_metnini_temizle(cozulmus_metin)
        if onizleme_metin_guvenli_mi(cozulmus_metin):
            return cozulmus_metin
    except Exception:
        pass

    try:
        mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
        icerik, _ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
        icerik = onizleme_kodlamasini_coz(icerik, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(icerik)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
    except Exception:
        pass

    try:
        ham_metin = onizleme_verisini_metin_yap(ham_veri, karakter_kumesi)
        ham_metin = onizleme_kodlamasini_coz(ham_metin, karakter_kumesi)
        onizleme = onizleme_metnini_temizle(ham_metin)
        if onizleme_metin_guvenli_mi(onizleme):
            return onizleme
        return ""
    except Exception:
        return ""
