# -*- coding: utf-8 -*-
"""Tamamlanmamış alıcı alanlarını yalnız taslakta kayıpsız saklar."""

import base64
import json

TASLAK_ALICI_BASLIGI = "X-Engelsiz-Mail-Draft-Recipients"
ALANLAR = frozenset({"kime", "bilgi", "gizli"})


def taslak_alici_verisini_yaz(mesaj, alanlar):
    if alanlar:
        ham = json.dumps(alanlar, ensure_ascii=False).encode("utf-8")
        mesaj[TASLAK_ALICI_BASLIGI] = base64.b64encode(ham).decode("ascii")


def taslak_alici_verisini_oku(mesaj):
    deger = str(mesaj.get(TASLAK_ALICI_BASLIGI, ""))
    if not deger:
        return {}
    try:
        ham = base64.b64decode("".join(deger.split()), validate=True)
        alanlar = json.loads(ham.decode("utf-8"))
        if (isinstance(alanlar, dict) and set(alanlar) <= ALANLAR
                and all(isinstance(v, str) for v in alanlar.values())):
            return alanlar
    except (ValueError, UnicodeError):
        pass
    return {}
