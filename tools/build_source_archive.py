# -*- coding: utf-8 -*-
"""Önbellek ve geçici dosya taşımayan kaynak ZIP paketi oluşturur."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import zipfile


HARIC_TUTULAN_KLASORLER = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
    }
)
HARIC_TUTULAN_DOSYALAR = frozenset({".coverage", "coverage.xml"})
HARIC_TUTULAN_UZANTILAR = frozenset({".pyc", ".pyo"})
SABIT_ZIP_TARIHI = (2026, 1, 1, 0, 0, 0)


def arsive_eklenebilir_mi(goreli_yol: Path) -> bool:
    """Bir kaynak yolunun dağıtım arşivine eklenip eklenmeyeceğini döndürür."""
    if any(parca in HARIC_TUTULAN_KLASORLER for parca in goreli_yol.parts):
        return False
    if goreli_yol.name in HARIC_TUTULAN_DOSYALAR:
        return False
    if goreli_yol.suffix.lower() in HARIC_TUTULAN_UZANTILAR:
        return False
    return True


def kaynak_dosyalarini_listele(kaynak_kok: Path):
    """Arşive girecek gerçek dosyaları sıralı olarak üretir."""
    kaynak_kok = Path(kaynak_kok).resolve()
    for yol in sorted(
        kaynak_kok.rglob("*"),
        key=lambda oge: (oge.as_posix().casefold(), oge.as_posix()),
    ):
        if yol.is_symlink() or not yol.is_file():
            continue
        goreli = yol.relative_to(kaynak_kok)
        if arsive_eklenebilir_mi(goreli):
            yield yol, goreli


def kaynak_arsivi_olustur(kaynak_kok, hedef_zip, kok_adi=None):
    """Kaynak ağacını temiz ve yeniden üretilebilir bir ZIP arşivine yazar."""
    kaynak_kok = Path(kaynak_kok).resolve()
    hedef_zip = Path(hedef_zip).resolve()
    if not kaynak_kok.is_dir():
        raise ValueError(f"Kaynak klasör bulunamadı: {kaynak_kok}")

    kok_adi = str(kok_adi or kaynak_kok.name).strip().strip("/\\")
    if not kok_adi or kok_adi in {".", ".."}:
        raise ValueError("Geçerli bir ZIP kök klasör adı belirtilmelidir.")

    hedef_zip.parent.mkdir(parents=True, exist_ok=True)
    gecici_zip = hedef_zip.with_name(hedef_zip.name + ".tmp")
    try:
        with zipfile.ZipFile(
            gecici_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as arsiv:
            for yol, goreli in kaynak_dosyalarini_listele(kaynak_kok):
                if yol.resolve() in {hedef_zip, gecici_zip}:
                    continue
                arsiv_adi = f"{kok_adi}/{goreli.as_posix()}"
                bilgi = zipfile.ZipInfo(arsiv_adi, date_time=SABIT_ZIP_TARIHI)
                bilgi.compress_type = zipfile.ZIP_DEFLATED
                bilgi.external_attr = (os.stat(yol).st_mode & 0xFFFF) << 16
                with yol.open("rb") as kaynak:
                    arsiv.writestr(bilgi, kaynak.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(gecici_zip, hedef_zip)
    finally:
        try:
            gecici_zip.unlink()
        except FileNotFoundError:
            pass
    return hedef_zip


def _komut_satiri():
    ayrıştırıcı = argparse.ArgumentParser(description=__doc__)
    ayrıştırıcı.add_argument("kaynak", type=Path, help="Kaynak proje klasörü")
    ayrıştırıcı.add_argument("hedef", type=Path, help="Oluşturulacak ZIP dosyası")
    ayrıştırıcı.add_argument("--kok-adi", default=None, help="ZIP içindeki kök klasör adı")
    return ayrıştırıcı.parse_args()


def main():
    secenekler = _komut_satiri()
    sonuc = kaynak_arsivi_olustur(secenekler.kaynak, secenekler.hedef, secenekler.kok_adi)
    print(sonuc)


if __name__ == "__main__":
    main()
