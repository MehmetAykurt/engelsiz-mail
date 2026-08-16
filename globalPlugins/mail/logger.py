# -*- coding: utf-8 -*-

from logHandler import log


EKLENTI_ADI = "Engelsiz Mail"


def _hata_bilgisi(hata):
    """Bir hata nesnesini etkin ``except`` bloğından bağımsız kayda hazırlar."""
    if hata is None:
        return None, ""
    hata_turu = type(hata).__name__
    hata_metni = str(hata or "").strip()
    ozet = hata_turu if not hata_metni else f"{hata_turu}: {hata_metni}"
    return (type(hata), hata, hata.__traceback__), ozet


def hata_kaydet(baslik, hata=None):
    """Teknik ayrıntıları NVDA günlüğüne yazar; kullanıcıya ham hata göstermez."""
    try:
        if hata is None:
            log.debug(f"{EKLENTI_ADI}: {baslik}")
            return
        exc_info, hata_ozeti = _hata_bilgisi(hata)
        log.error(
            f"{EKLENTI_ADI}: {baslik} ({hata_ozeti})",
            exc_info=exc_info,
        )
    except Exception:
        pass


def uyari_kaydet(baslik, hata=None):
    """Beklenen kurtarma durumlarını traceback üretmeden warning düzeyinde yazar."""
    try:
        if hata is None:
            log.warning(f"{EKLENTI_ADI}: {baslik}")
            return
        _exc_info, hata_ozeti = _hata_bilgisi(hata)
        log.warning(f"{EKLENTI_ADI}: {baslik} ({hata_ozeti})")
    except Exception:
        pass
