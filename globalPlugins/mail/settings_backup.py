# -*- coding: utf-8 -*-
"""Engelsiz Mail ayarlarını taşınabilir ZIP yedeğine aktarma ve geri yükleme."""

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone

from .errors import MailHatasi
from .paths import AYARLAR_DOSYASI
from .security import uygulama_sifresini_coz, uygulama_sifresini_sifrele
from .storage import guvenli_json_oku, guvenli_json_yedekleyerek_yaz
from .version import EKLENTI_SURUMU


YEDEK_BICIMI = "engelsiz-mail-ayarlari"
YEDEK_SURUMU = 1
AYAR_GIRDI_ADI = "ayarlar.json"
AZAMI_ZIP_BOYUTU = 2 * 1024 * 1024
AZAMI_AYAR_BOYUTU = 1024 * 1024
SIFRE_DPAPI_ALANI = "sifre_dpapi"
SIFRE_DUZ_METIN_ALANI = "sifre"
AYAR_SEMA_SURUMU_ALANI = "sema_surumu"
GUNCEL_AYAR_SEMA_SURUMU = 1

GECICI_DURUM_ALANLARI = {
    "bildirim_son_uid",
    "bildirim_son_uid_hesap",
    "bildirim_uidvalidity",
    "bildirim_baslatildi",
}


def _hassas_ayar_kopyasi(ham_ayarlar):
    """DPAPI şifresini çözüp başka bilgisayara taşınabilir ayar kopyası üretir."""
    if not isinstance(ham_ayarlar, dict):
        raise MailHatasi("Ayar dosyasının içeriği geçerli değil.")
    ayarlar = dict(ham_ayarlar)
    sifreli = str(ayarlar.pop(SIFRE_DPAPI_ALANI, "") or "").strip()
    eski_sifre = str(ayarlar.pop(SIFRE_DUZ_METIN_ALANI, "") or "").strip().replace(" ", "")
    if sifreli:
        try:
            sifre = uygulama_sifresini_coz(sifreli)
        except Exception as e:
            raise MailHatasi("Kayıtlı uygulama şifresi yedekleme için çözülemedi.") from e
    else:
        sifre = eski_sifre
    ayarlar[SIFRE_DUZ_METIN_ALANI] = sifre
    for alan in GECICI_DURUM_ALANLARI:
        ayarlar.pop(alan, None)
    ayarlar[AYAR_SEMA_SURUMU_ALANI] = GUNCEL_AYAR_SEMA_SURUMU
    return ayarlar


def _yedek_verisini_olustur():
    if not os.path.isfile(AYARLAR_DOSYASI):
        raise MailHatasi("Dışa aktarılacak bir Engelsiz Mail ayar dosyası bulunamadı.")
    ham_ayarlar = guvenli_json_oku(AYARLAR_DOSYASI, {})
    if not ham_ayarlar:
        raise MailHatasi("Dışa aktarılacak geçerli ayar bulunamadı.")
    return {
        "yedek_bicimi": YEDEK_BICIMI,
        "yedek_surumu": YEDEK_SURUMU,
        "eklenti_surumu": EKLENTI_SURUMU,
        "olusturulma_zamani": datetime.now(timezone.utc).isoformat(),
        "ayarlar": _hassas_ayar_kopyasi(ham_ayarlar),
    }


def ayarlari_disa_aktar(hedef_yol):
    """Ayarları ve çözülebilir uygulama şifresini tek girdili ZIP dosyasına yazar."""
    hedef_yol = str(hedef_yol or "").strip()
    if not hedef_yol:
        raise MailHatasi("Yedek dosyası için geçerli bir konum seçilmedi.")
    hedef_yol = os.path.abspath(hedef_yol)
    if not hedef_yol.lower().endswith(".zip"):
        hedef_yol += ".zip"
    hedef_klasor = os.path.dirname(hedef_yol)
    if not hedef_klasor or not os.path.isdir(hedef_klasor):
        raise MailHatasi("Yedek dosyasının kaydedileceği klasör bulunamadı.")

    veri = json.dumps(_yedek_verisini_olustur(), ensure_ascii=False, indent=2).encode("utf-8")
    if len(veri) > AZAMI_AYAR_BOYUTU:
        raise MailHatasi("Ayar yedeği güvenli boyut sınırını aşıyor.")

    gecici_yol = None
    try:
        fd, gecici_yol = tempfile.mkstemp(prefix="engelsiz_mail_", suffix=".tmp", dir=hedef_klasor)
        os.close(fd)
        with zipfile.ZipFile(gecici_yol, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as arsiv:
            arsiv.writestr(AYAR_GIRDI_ADI, veri)
        os.replace(gecici_yol, hedef_yol)
        gecici_yol = None
        return hedef_yol
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        raise MailHatasi("Ayar yedeği oluşturulamadı.") from e
    finally:
        if gecici_yol:
            try:
                os.remove(gecici_yol)
            except OSError:
                pass


def _zipten_yedek_oku(kaynak_yol):
    kaynak_yol = str(kaynak_yol or "").strip()
    if not kaynak_yol:
        raise MailHatasi("Bir ayar yedeği seçilmedi.")
    kaynak_yol = os.path.abspath(kaynak_yol)
    if not os.path.isfile(kaynak_yol):
        raise MailHatasi("Seçilen yedek dosyası bulunamadı.")
    try:
        if os.path.getsize(kaynak_yol) > AZAMI_ZIP_BOYUTU:
            raise MailHatasi("Seçilen yedek dosyası güvenli boyut sınırını aşıyor.")
        with zipfile.ZipFile(kaynak_yol, "r") as arsiv:
            dosyalar = [bilgi for bilgi in arsiv.infolist() if not bilgi.is_dir()]
            if len(dosyalar) != 1 or dosyalar[0].filename != AYAR_GIRDI_ADI:
                raise MailHatasi("Bu dosya geçerli bir Engelsiz Mail ayar yedeği değil.")
            bilgi = dosyalar[0]
            if bilgi.file_size > AZAMI_AYAR_BOYUTU:
                raise MailHatasi("Yedekteki ayar dosyası güvenli boyut sınırını aşıyor.")
            ham_veri = arsiv.read(bilgi)
    except MailHatasi:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        raise MailHatasi("Seçilen ZIP yedeği okunamadı veya bozuk.") from e

    try:
        veri = json.loads(ham_veri.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as e:
        raise MailHatasi("Yedekteki ayar dosyası okunamadı veya bozuk.") from e
    return veri


def _ice_aktarilacak_ayarlari_hazirla(yedek):
    if not isinstance(yedek, dict):
        raise MailHatasi("Yedek içeriği geçerli değil.")
    if yedek.get("yedek_bicimi") != YEDEK_BICIMI:
        raise MailHatasi("Bu ZIP dosyası Engelsiz Mail ayar yedeği değil.")
    try:
        yedek_surumu = int(yedek.get("yedek_surumu", 0))
    except Exception as e:
        raise MailHatasi("Yedek sürümü okunamadı.") from e
    if yedek_surumu != YEDEK_SURUMU:
        raise MailHatasi("Bu ayar yedeğinin sürümü desteklenmiyor.")

    ayarlar = yedek.get("ayarlar")
    if not isinstance(ayarlar, dict):
        raise MailHatasi("Yedekte geçerli bir ayar bölümü bulunamadı.")
    try:
        sema_surumu = int(ayarlar.get(AYAR_SEMA_SURUMU_ALANI, 1))
    except Exception as e:
        raise MailHatasi("Ayar şema sürümü okunamadı.") from e
    if sema_surumu > GUNCEL_AYAR_SEMA_SURUMU:
        raise MailHatasi("Yedek, bu Engelsiz Mail sürümünden daha yeni ayarlar içeriyor.")

    ayarlar = dict(ayarlar)
    eposta = str(ayarlar.get("eposta", "") or "").strip()
    sifre = str(ayarlar.pop(SIFRE_DUZ_METIN_ALANI, "") or "").strip().replace(" ", "")
    ayarlar.pop(SIFRE_DPAPI_ALANI, None)
    if len(eposta) > 254 or (eposta and ("@" not in eposta or any(ch in eposta for ch in "\r\n\x00"))):
        raise MailHatasi("Yedekteki e-posta adresi geçerli değil.")
    if len(sifre) > 256 or any(ch in sifre for ch in "\r\n\x00"):
        raise MailHatasi("Yedekteki uygulama şifresi geçerli değil.")
    if sifre:
        try:
            ayarlar[SIFRE_DPAPI_ALANI] = uygulama_sifresini_sifrele(sifre)
        except Exception as e:
            raise MailHatasi("Uygulama şifresi bu bilgisayar için şifrelenemedi.") from e
    for alan in GECICI_DURUM_ALANLARI:
        ayarlar.pop(alan, None)
    ayarlar[AYAR_SEMA_SURUMU_ALANI] = GUNCEL_AYAR_SEMA_SURUMU
    return ayarlar


def ayarlari_ice_aktar(kaynak_yol):
    """Doğrulanmış ZIP ayarlarını hedef bilgisayarın DPAPI anahtarıyla kaydeder."""
    ayarlar = _ice_aktarilacak_ayarlari_hazirla(_zipten_yedek_oku(kaynak_yol))
    yedek_yolu = AYARLAR_DOSYASI + ".ice_aktarim_oncesi"
    if not guvenli_json_yedekleyerek_yaz(AYARLAR_DOSYASI, ayarlar, yedek_yolu):
        raise MailHatasi("İçe aktarılan ayarlar kaydedilemedi.")
    return True
