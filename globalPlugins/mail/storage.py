# -*- coding: utf-8 -*-

import json
import os
import tempfile
import threading

from .logger import hata_kaydet


_JSON_KILIDI = threading.RLock()


def bozuk_json_dosyasini_yedekle(dosya_yolu):
    """Okunamayan JSON dosyasını silmek yerine .bozuk uzantılı yedeğe taşır."""
    with _JSON_KILIDI:
        try:
            if not dosya_yolu or not os.path.exists(dosya_yolu):
                return
            temel_yedek_yolu = dosya_yolu + ".bozuk"
            yedek_yolu = temel_yedek_yolu
            sayac = 1
            while os.path.exists(yedek_yolu):
                sayac += 1
                yedek_yolu = f"{temel_yedek_yolu}.{sayac}"
            os.replace(dosya_yolu, yedek_yolu)
            hata_kaydet(f"Bozuk JSON dosyası yedeklendi: {yedek_yolu}")
        except Exception as e:
            hata_kaydet("Bozuk JSON dosyası yedeklenemedi.", e)


def guvenli_json_oku(dosya_yolu, varsayilan):
    with _JSON_KILIDI:
        try:
            if not os.path.exists(dosya_yolu):
                return varsayilan
            with open(dosya_yolu, "r", encoding="utf-8") as dosya:
                veri = json.load(dosya)
            return veri if isinstance(veri, type(varsayilan)) else varsayilan
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            hata_kaydet(f"JSON dosyası okunamadı: {dosya_yolu}", e)
            bozuk_json_dosyasini_yedekle(dosya_yolu)
            return varsayilan


def guvenli_json_yaz(dosya_yolu, veri):
    with _JSON_KILIDI:
        klasor = os.path.dirname(dosya_yolu)
        gecici_yol = None
        try:
            os.makedirs(klasor, exist_ok=True)
            fd, gecici_yol = tempfile.mkstemp(prefix="engelsizmail_", suffix=".tmp", dir=klasor)
            with os.fdopen(fd, "w", encoding="utf-8") as dosya:
                json.dump(veri, dosya, ensure_ascii=False, indent=2)
                dosya.flush()
                try:
                    os.fsync(dosya.fileno())
                except OSError:
                    pass
            os.replace(gecici_yol, dosya_yolu)
            return True
        except (OSError, TypeError, ValueError) as e:
            hata_kaydet(f"JSON dosyası yazılamadı: {dosya_yolu}", e)
            if gecici_yol:
                try:
                    os.remove(gecici_yol)
                except OSError:
                    pass
            return False


def guvenli_json_guncelle(dosya_yolu, varsayilan, guncelleyici):
    """JSON verisini aynı kilit altında okuyup değiştirerek geri yazar."""
    if not callable(guncelleyici):
        raise TypeError("JSON güncelleyici çağrılabilir olmalıdır.")
    with _JSON_KILIDI:
        mevcut = guvenli_json_oku(dosya_yolu, varsayilan)
        yeni_veri = guncelleyici(mevcut)
        if not isinstance(yeni_veri, type(varsayilan)):
            raise TypeError("JSON güncelleyici beklenen veri türünü döndürmedi.")
        return guvenli_json_yaz(dosya_yolu, yeni_veri)


def guvenli_json_yedekleyerek_yaz(dosya_yolu, veri, yedek_yolu):
    """Mevcut JSON'u güvenlik kopyasına aldıktan sonra yeni veriyi atomik olarak yazar."""
    with _JSON_KILIDI:
        if os.path.exists(dosya_yolu):
            mevcut = guvenli_json_oku(dosya_yolu, {})
            if not isinstance(mevcut, dict):
                mevcut = {}
            if not guvenli_json_yaz(yedek_yolu, mevcut):
                return False
        return guvenli_json_yaz(dosya_yolu, veri)
