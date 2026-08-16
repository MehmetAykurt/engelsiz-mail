# -*- coding: utf-8 -*-
"""Temiz ve yeniden üretilebilir NVDA eklenti paketi oluşturur."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import zipfile


EKLENTI_KOK_DOSYALARI = frozenset({"manifest.ini", "LICENSE"})
EKLENTI_KOK_KLASORLERI = frozenset({"globalPlugins", "doc", "locale"})
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
HARIC_TUTULAN_UZANTILAR = frozenset({".pyc", ".pyo", ".po", ".pot"})
SABIT_ZIP_TARIHI = (2026, 1, 1, 0, 0, 0)


def _pakete_eklenebilir_mi(goreli_yol: Path) -> bool:
    if not goreli_yol.parts:
        return False
    if goreli_yol.parts[0] not in EKLENTI_KOK_KLASORLERI:
        return goreli_yol.as_posix() in EKLENTI_KOK_DOSYALARI
    if any(parca in HARIC_TUTULAN_KLASORLER for parca in goreli_yol.parts):
        return False
    if goreli_yol.name in HARIC_TUTULAN_DOSYALAR:
        return False
    if goreli_yol.suffix.lower() in HARIC_TUTULAN_UZANTILAR:
        return False
    return True


def eklenti_dosyalarini_listele(kaynak_kok: Path):
    """NVDA eklenti paketine girecek gerçek dosyaları sıralı olarak üretir."""
    kaynak_kok = Path(kaynak_kok).resolve()
    for yol in sorted(
        kaynak_kok.rglob("*"),
        key=lambda oge: (oge.as_posix().casefold(), oge.as_posix()),
    ):
        if yol.is_symlink() or not yol.is_file():
            continue
        goreli = yol.relative_to(kaynak_kok)
        if _pakete_eklenebilir_mi(goreli):
            yield yol, goreli


def _gerekli_dosyalari_dogrula(kaynak_kok: Path) -> None:
    eksikler = [ad for ad in sorted(EKLENTI_KOK_DOSYALARI) if not (kaynak_kok / ad).is_file()]
    if not (kaynak_kok / "globalPlugins").is_dir():
        eksikler.append("globalPlugins/")
    if not (kaynak_kok / "doc").is_dir():
        eksikler.append("doc/")
    if eksikler:
        raise ValueError("Eklenti paketi için gerekli öğeler eksik: " + ", ".join(eksikler))


def eklenti_paketi_olustur(kaynak_kok, hedef_paket):
    """Kaynak ağacından kökünde manifest bulunan temiz `.nvda-addon` üretir."""
    kaynak_kok = Path(kaynak_kok).resolve()
    hedef_paket = Path(hedef_paket).resolve()
    if not kaynak_kok.is_dir():
        raise ValueError(f"Kaynak klasör bulunamadı: {kaynak_kok}")
    if hedef_paket.suffix.lower() != ".nvda-addon":
        raise ValueError("Hedef dosyanın uzantısı .nvda-addon olmalıdır.")
    _gerekli_dosyalari_dogrula(kaynak_kok)

    hedef_paket.parent.mkdir(parents=True, exist_ok=True)
    gecici_paket = hedef_paket.with_name(hedef_paket.name + ".tmp")
    try:
        with zipfile.ZipFile(
            gecici_paket,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as arsiv:
            for yol, goreli in eklenti_dosyalarini_listele(kaynak_kok):
                if yol.resolve() in {hedef_paket, gecici_paket}:
                    continue
                arsiv_adi = PurePosixPath(*goreli.parts).as_posix()
                bilgi = zipfile.ZipInfo(arsiv_adi, date_time=SABIT_ZIP_TARIHI)
                bilgi.compress_type = zipfile.ZIP_DEFLATED
                bilgi.external_attr = (os.stat(yol).st_mode & 0xFFFF) << 16
                with yol.open("rb") as kaynak:
                    arsiv.writestr(
                        bilgi,
                        kaynak.read(),
                        compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=9,
                    )
        os.replace(gecici_paket, hedef_paket)
    finally:
        try:
            gecici_paket.unlink()
        except FileNotFoundError:
            pass
    return hedef_paket


def _komut_satiri():
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("kaynak", type=Path, help="Kaynak proje klasörü")
    ayristirici.add_argument("hedef", type=Path, help="Oluşturulacak .nvda-addon dosyası")
    return ayristirici.parse_args()


def main():
    secenekler = _komut_satiri()
    sonuc = eklenti_paketi_olustur(secenekler.kaynak, secenekler.hedef)
    print(sonuc)


if __name__ == "__main__":
    main()
