# -*- coding: utf-8 -*-

from logHandler import log


EKLENTI_ADI = "Engelsiz Mail"


def hata_kaydet(baslik, hata=None):
    """Teknik ayrıntıları NVDA günlüğüne yazar; kullanıcıya ham hata göstermez."""
    try:
        if hata:
            log.exception(f"{EKLENTI_ADI}: {baslik}")
        else:
            log.debug(f"{EKLENTI_ADI}: {baslik}")
    except Exception:
        pass


def uyari_kaydet(baslik, hata=None):
    """Beklenen kurtarma durumlarını traceback üretmeden warning düzeyinde yazar."""
    try:
        if hata is None:
            log.warning(f"{EKLENTI_ADI}: {baslik}")
            return
        hata_turu = type(hata).__name__
        log.warning(f"{EKLENTI_ADI}: {baslik} ({hata_turu})")
    except Exception:
        pass
