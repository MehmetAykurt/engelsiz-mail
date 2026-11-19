# -*- coding: utf-8 -*-

import os

import globalVars

try:
    import languageHandler
except Exception:
    languageHandler = None

EKLENTI_KOK_DIZINI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AYARLAR_KLASORU = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail")
AYARLAR_DOSYASI = os.path.join(AYARLAR_KLASORU, "ayarlar.json")
VERITABANI_DOSYASI = os.path.join(AYARLAR_KLASORU, "engelsiz_mail.db")
EKLER_KLASORU = os.path.join(AYARLAR_KLASORU, "attachments")


def belge_dili_klasoru():
    """Yalnız desteklenen belge dillerinden birini döndürür."""
    try:
        dil = languageHandler.getLanguage() if languageHandler is not None else ""
    except Exception:
        dil = ""
    dil = str(dil or "").replace("_", "-").lower()
    if dil == "en" or dil.startswith("en-"):
        return "en"
    return "tr"


def yerellestirilmis_belge_yolu(dosya_adi):
    """NVDA diline uygun belgeyi, gerekirse Türkçe geri dönüşle bulur."""
    dosya_adi = str(dosya_adi or "").strip()
    if not dosya_adi:
        return ""
    aday_diller = [belge_dili_klasoru()]
    if "tr" not in aday_diller:
        aday_diller.append("tr")
    for dil in aday_diller:
        yol = os.path.join(EKLENTI_KOK_DIZINI, "doc", dil, dosya_adi)
        if os.path.isfile(yol):
            return yol
    return os.path.join(EKLENTI_KOK_DIZINI, "doc", aday_diller[0], dosya_adi)
