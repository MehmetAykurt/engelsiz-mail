# -*- coding: utf-8 -*-
"""Gmail konuşmalarını ana listede tek satıra dönüştüren yardımcılar."""


def epostalari_konusmalara_grupla(mailler, sinir=None):
    """Aynı Gmail thread kimliğindeki iletileri, en yeni ileti temsilci olacak biçimde gruplar."""
    gruplar = []
    harita = {}
    for mesaj in mailler or []:
        thread_id = str(mesaj.get("thread_id") or "").strip()
        anahtar = "thread:" + thread_id if thread_id else "uid:" + str(mesaj.get("id") or "")
        grup = harita.get(anahtar)
        if grup is None:
            grup = dict(mesaj)
            grup["konusma_mi"] = bool(thread_id)
            grup["thread_id"] = thread_id
            grup["ids"] = []
            grup["okunmamis_sayisi"] = 0
            grup["ek_var"] = False
            harita[anahtar] = grup
            gruplar.append(grup)
        uid = str(mesaj.get("id") or "")
        if uid and uid not in grup["ids"]:
            grup["ids"].append(uid)
        if not bool(mesaj.get("is_seen", True)):
            grup["okunmamis_sayisi"] += 1
        grup["ek_var"] = bool(grup.get("ek_var")) or bool(mesaj.get("ek_var"))

    for grup in gruplar:
        adet = len(grup.get("ids") or [])
        grup["ileti_sayisi"] = adet
        if adet > 1:
            temel = str(grup.get("liste_gosterim") or grup.get("kimden") or "").strip()
            temel = temel.replace("[Okunmadı] ", "", 1)
            okunmamis = int(grup.get("okunmamis_sayisi") or 0)
            durum = f"{okunmamis} okunmamış, " if okunmamis else ""
            grup["liste_gosterim"] = f"{durum}{temel}, {adet} ileti"
            grup["kimden"] = grup["liste_gosterim"]
        grup["id"] = str((grup.get("ids") or [grup.get("id", "")])[0])
    if sinir is not None:
        return gruplar[:max(1, int(sinir))]
    return gruplar


def mesaj_uidlerini_al(mesaj):
    ids = [str(uid) for uid in (mesaj or {}).get("ids", []) if str(uid)]
    if ids:
        return ids
    uid = str((mesaj or {}).get("id") or "")
    return [uid] if uid else []


def secimleri_uidlere_genislet(mailler, secimler):
    """Ana listedeki konuşma temsilcilerini gerçek klasör UID listesine genişletir."""
    secim_kumesi = {str(uid) for uid in secimler or []}
    sonuc = []
    for mesaj in mailler or []:
        if str(mesaj.get("id") or "") not in secim_kumesi:
            continue
        for uid in mesaj_uidlerini_al(mesaj):
            if uid not in sonuc:
                sonuc.append(uid)
    for uid in secim_kumesi:
        if uid and uid not in sonuc:
            sonuc.append(uid)
    return sonuc
