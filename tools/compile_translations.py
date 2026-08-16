# -*- coding: utf-8 -*-
"""Engelsiz Mail gettext .po dosyasını NVDA'nın kullandığı .mo biçimine derler."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

try:
    from babel.messages import mofile, pofile
except ImportError as exc:  # pragma: no cover - geliştirme aracı
    raise SystemExit("Dil dosyasını derlemek için Babel paketi gereklidir.") from exc

_YER_TUTUCU_DESENI = re.compile(r"\{[^{}]+\}")


def _katalogu_dogrula(katalog) -> None:
    """Dağıtıma uygun olmayan çeviri kayıtlarında açıklayıcı hata üretir."""
    bos = []
    belirsiz = []
    yer_tutucu_hatalari = []
    for mesaj in katalog:
        if not mesaj.id:
            continue
        if not mesaj.string:
            bos.append(mesaj.id)
        if "fuzzy" in mesaj.flags:
            belirsiz.append(mesaj.id)
        kaynak = mesaj.id if isinstance(mesaj.id, str) else "\n".join(mesaj.id)
        ceviri = mesaj.string if isinstance(mesaj.string, str) else "\n".join(mesaj.string or ())
        if sorted(_YER_TUTUCU_DESENI.findall(kaynak)) != sorted(_YER_TUTUCU_DESENI.findall(ceviri)):
            yer_tutucu_hatalari.append(mesaj.id)

    eski = list(getattr(katalog, "obsolete", {}).keys())
    sorunlar = []
    if bos:
        sorunlar.append(f"çevrilmemiş metin: {len(bos)}")
    if belirsiz:
        sorunlar.append(f"belirsiz (fuzzy) çeviri: {len(belirsiz)}")
    if eski:
        sorunlar.append(f"eski (obsolete) çeviri: {len(eski)}")
    if yer_tutucu_hatalari:
        sorunlar.append(f"yer tutucu uyuşmazlığı: {len(yer_tutucu_hatalari)}")
    if sorunlar:
        raise ValueError("Dil dosyası doğrulanamadı: " + ", ".join(sorunlar))


def ceviriyi_derle(kaynak_po: Path, hedef_mo: Path) -> Path:
    kaynak_po = Path(kaynak_po).resolve()
    hedef_mo = Path(hedef_mo).resolve()
    if not kaynak_po.is_file():
        raise ValueError(f"PO dosyası bulunamadı: {kaynak_po}")
    with kaynak_po.open("r", encoding="utf-8") as dosya:
        katalog = pofile.read_po(dosya)
    _katalogu_dogrula(katalog)
    hedef_mo.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef_mo.with_name(hedef_mo.name + ".tmp")
    try:
        with gecici.open("wb") as dosya:
            mofile.write_mo(dosya, katalog)
        gecici.replace(hedef_mo)
    finally:
        try:
            gecici.unlink()
        except FileNotFoundError:
            pass
    return hedef_mo


def _komut_satiri():
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("kaynak_po", type=Path, help="Derlenecek .po dosyası")
    ayristirici.add_argument("hedef_mo", type=Path, help="Oluşturulacak .mo dosyası")
    return ayristirici.parse_args()


def main():
    secenekler = _komut_satiri()
    print(ceviriyi_derle(secenekler.kaynak_po, secenekler.hedef_mo))


if __name__ == "__main__":
    main()
