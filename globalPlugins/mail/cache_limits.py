# -*- coding: utf-8 -*-
"""Gövde ve ek önbelleğinin diski sınırsız tüketmesini engeller."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import os
import shutil

from .database import veritabani_baglantisi
from .errors import MailHatasi
from .paths import AYARLAR_KLASORU


AZAMI_TOPLAM_ONBELLEK_BOYUTU = 5 * 1024 * 1024 * 1024
ASGARI_BOS_DISK_BOYUTU = 512 * 1024 * 1024


class OnbellekSiniriHatasi(MailHatasi):
    """Yeni gövde veya ek yazımının güvenli depolama sınırına takıldığını belirtir."""


def onbellek_kotasi_denetle(yeni_veri_boyutu=0):
    """Yaklaşık toplam önbellek ve boş disk sınırını yeni yazımdan önce denetler."""
    try:
        yeni_veri_boyutu = max(0, int(yeni_veri_boyutu or 0))
    except (TypeError, ValueError):
        yeni_veri_boyutu = 0
    with veritabani_baglantisi() as db:
        govdeler = int(db.execute(
            "SELECT COALESCE(SUM(raw_size_bytes), 0) FROM message_bodies"
        ).fetchone()[0] or 0)
        ekler = int(db.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM attachments WHERE download_state = 'downloaded'"
        ).fetchone()[0] or 0)
    if govdeler + ekler + yeni_veri_boyutu > AZAMI_TOPLAM_ONBELLEK_BOYUTU:
        raise OnbellekSiniriHatasi(
            _("E-posta önbelleği 5 GB güvenlik sınırına ulaştığı için yeni gövde kaydedilmedi.")
        )
    os.makedirs(AYARLAR_KLASORU, exist_ok=True)
    bos_alan = int(shutil.disk_usage(AYARLAR_KLASORU).free)
    if bos_alan - yeni_veri_boyutu < ASGARI_BOS_DISK_BOYUTU:
        raise OnbellekSiniriHatasi(
            _("Diskte 512 MB güvenli boş alan kalmayacağı için yeni e-posta önbelleğe alınmadı.")
        )
    return True
