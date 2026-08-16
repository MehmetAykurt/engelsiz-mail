# -*- coding: utf-8 -*-
"""Engelsiz Mail Python kaynaklarından yeniden üretilebilir gettext şablonu çıkarır."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

try:
    from babel.messages.catalog import Catalog
    from babel.messages.extract import extract_from_dir
    from babel.messages.pofile import write_po
except ImportError as exc:  # pragma: no cover - yalnız geliştirme ortamı denetimi
    raise SystemExit("Çeviri şablonunu üretmek için Babel paketi gereklidir.") from exc

SABIT_OLUSTURMA_ZAMANI = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _surumu_al(kaynak_kok: Path) -> str:
    yol = kaynak_kok / "globalPlugins" / "mail" / "version.py"
    if not yol.is_file():
        return ""
    eslesme = re.search(r'^EKLENTI_SURUMU\s*=\s*[\'\"]([^\'\"]+)', yol.read_text(encoding="utf-8"), re.M)
    return eslesme.group(1) if eslesme else ""


def ceviri_sablonunu_olustur(kaynak_kok: Path, hedef: Path) -> Path:
    kaynak_kok = Path(kaynak_kok).resolve()
    python_koku = kaynak_kok / "globalPlugins" / "mail"
    if not python_koku.is_dir():
        raise ValueError(f"Python kaynak klasörü bulunamadı: {python_koku}")

    katalog = Catalog(
        project="Engelsiz Mail",
        version=_surumu_al(kaynak_kok),
        copyright_holder="Mehmet Aykurt",
        msgid_bugs_address="m.aykurt38@gmail.com",
        charset="utf-8",
        creation_date=SABIT_OLUSTURMA_ZAMANI,
    )
    for dosya, satir, mesaj, yorumlar, baglam in extract_from_dir(
        str(python_koku),
        directory_filter=lambda yol: "vendor" not in Path(yol).parts and "__pycache__" not in Path(yol).parts,
    ):
        if not mesaj:
            continue
        katalog.add(
            mesaj,
            locations=[(f"globalPlugins/mail/{dosya}", satir)],
            auto_comments=yorumlar,
            context=baglam,
        )

    hedef = Path(hedef).resolve()
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with hedef.open("wb") as dosya:
        write_po(
            dosya,
            katalog,
            width=100,
            sort_by_file=True,
            include_previous=False,
            omit_header=False,
        )
    return hedef


def _komut_satiri():
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("kaynak", type=Path, help="Engelsiz Mail kaynak proje kökü")
    ayristirici.add_argument("hedef", type=Path, help="Oluşturulacak .pot dosyası")
    return ayristirici.parse_args()


def main():
    secenekler = _komut_satiri()
    print(ceviri_sablonunu_olustur(secenekler.kaynak, secenekler.hedef))


if __name__ == "__main__":
    main()
