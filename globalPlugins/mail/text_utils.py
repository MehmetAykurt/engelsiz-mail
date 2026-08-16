# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import html
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

HTML_TEMIZLE_KARAKTER_SINIRI = 120000
RE_HTML_STYLE_SCRIPT_HEAD = re.compile(r"<(style|script|head)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_HTML_BLOK_ETIKETLERI = re.compile(r"</?(br|p|div|table|thead|tbody|tfoot|tr|td|th|ul|ol|li|blockquote|section|article|header|footer|hr|h[1-6])[^>]*>", re.IGNORECASE)
RE_HTML_ETIKETLERI = re.compile(r"<[^>]+>")
RE_HTML_BAGLANTI = re.compile(
    r"<a\b(?P<ozellikler>[^>]*)>(?P<icerik>.*?)</a\s*>",
    re.IGNORECASE | re.DOTALL,
)
RE_HTML_HREF = re.compile(
    r"\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
    re.IGNORECASE,
)
RE_COKLU_BOSLUK = re.compile(r"[^\S\r\n]+")
RE_MARKDOWN_VURGU = re.compile(r"(?<!\*)\*{1,3}([^*\r\n]+?)\*{1,3}(?!\*)")
RE_MARKDOWN_BAGLANTI = re.compile(r"\[([^\]\r\n]+)\]\((https?://[^)\s]+)\)")
RE_MOJIBAKE_ISARETLERI = re.compile(r"(?:Ã|Â|Ä|Å|�)")
RE_EPOSTA_ALT_BILGI_AYRACI = re.compile(r"^\s*[-=]{4,}\s*$")
RE_URL_SONU_KOSELI_EPOSTA = re.compile(r"^(?P<url>https?://[^\s\[]+)\s+\[[^\]\r\n]+@[^]\r\n]+\]\s*$", re.IGNORECASE)
RE_HTTP_BAGLANTI_ADAYI = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
RE_YANIT_KONU_ONEKI = re.compile(r"^\s*(?:re|ynt)\s*:\s*(.+)$", re.IGNORECASE)
RE_ILETILMIS_KONU_ONEKI = re.compile(r"^\s*(?:fw|fwd)\s*:\s*(.+)$", re.IGNORECASE)
RE_ALINTI_ISARETI = re.compile(r"(?<!\S)>{1,8}(?=\s)")
RE_KOSELI_EPOSTA_ADRESI = re.compile(r"<([A-Z0-9._%+\-=]+@[A-Z0-9.-]+\.[A-Z]{2,})>", re.IGNORECASE)
RE_GROUPS_IO_DONUSTURULMUS_ADRES = re.compile(
    r"\b(?P<yerel>[A-Z0-9._%+\-]+)=(?P<alan>[A-Z0-9.-]+\.[A-Z]{2,})@groups\.io\b",
    re.IGNORECASE,
)
RE_ALINTI_YAZDI_SATIRI = re.compile(
    r"^(?P<kisi>.+?)\s+şunları yazdı\s*\((?P<tarih>[^)\r\n]+)\)\s*:\s*$",
    re.IGNORECASE,
)


def metin_cozum_kalitesini_puanla(metin):
    """Metin çözümleme adaylarını Türkçe okunabilirlik ve bozulma bakımından karşılaştırır."""
    metin = str(metin or "")
    bozukluk = len(RE_MOJIBAKE_ISARETLERI.findall(metin))
    degisim = metin.count("�")
    denetim = sum(
        1 for karakter in metin
        if ord(karakter) < 32 and karakter not in "\t\r\n"
    )
    turkce = sum(1 for karakter in metin if karakter in "çğıöşüÇĞİÖŞÜ")
    return (degisim * 100) + (bozukluk * 8) + (denetim * 4) - turkce


def eposta_baytlarini_metne_coz(veri, bildirilen_karakter_kumesi="utf-8"):
    """E-posta gövde baytlarını, yanlış charset bildirimlerine karşı Türkçe metni koruyarak çözer."""
    if isinstance(veri, str):
        return metin_kodlama_bozulmasini_duzelt(veri)
    if not isinstance(veri, (bytes, bytearray)):
        return ""

    kodlamalar = [bildirilen_karakter_kumesi, "utf-8", "windows-1254", "iso-8859-9", "windows-1252", "latin-1"]
    benzersiz = []
    gorulen = set()
    for kodlama in kodlamalar:
        kodlama = str(kodlama or "").strip()
        anahtar = kodlama.lower()
        if anahtar and anahtar not in gorulen:
            benzersiz.append(kodlama)
            gorulen.add(anahtar)

    adaylar = []
    for kodlama in benzersiz:
        try:
            adaylar.append(veri.decode(kodlama, errors="strict"))
        except (LookupError, UnicodeDecodeError):
            continue
    if adaylar:
        return metin_kodlama_bozulmasini_duzelt(min(adaylar, key=metin_cozum_kalitesini_puanla))

    yedekler = []
    for kodlama in benzersiz:
        try:
            yedekler.append(veri.decode(kodlama, errors="replace"))
        except LookupError:
            continue
    if yedekler:
        return metin_kodlama_bozulmasini_duzelt(min(yedekler, key=metin_cozum_kalitesini_puanla))
    return veri.decode("utf-8", errors="replace")


def metin_kodlama_bozulmasini_duzelt(metin):
    """UTF-8 metnin Latin-1/Windows kodlaması gibi okunmasından doğan bozulmaları onarır."""
    metin = str(metin or "")
    if not metin:
        return ""

    def puanla(deger):
        bozukluk = len(RE_MOJIBAKE_ISARETLERI.findall(deger))
        degisim = deger.count("�")
        turkce = sum(1 for karakter in deger if karakter in "çğıöşüÇĞİÖŞÜ")
        return (bozukluk * 4) + (degisim * 6) - turkce

    en_iyi = metin
    en_iyi_puan = puanla(metin)
    aday = metin
    for _ in range(3):
        if not RE_MOJIBAKE_ISARETLERI.search(aday):
            break
        sonraki_adaylar = []
        for kodlama in ("windows-1252", "latin-1"):
            try:
                sonraki_adaylar.append(aday.encode(kodlama).decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        if not sonraki_adaylar:
            break
        sonraki = min(sonraki_adaylar, key=puanla)
        sonraki_puan = puanla(sonraki)
        if sonraki_puan < en_iyi_puan:
            en_iyi = sonraki
            en_iyi_puan = sonraki_puan
            aday = sonraki
        else:
            break
    return en_iyi


def eposta_alt_bilgi_fazlaliklarini_temizle(metin):
    """Okumayı zorlaştıran ayraçları ve URL sonundaki köşeli e-posta bilgisini temizler."""
    satirlar = []
    for satir in str(metin or "").splitlines():
        if RE_EPOSTA_ALT_BILGI_AYRACI.match(satir):
            continue
        eslesme = RE_URL_SONU_KOSELI_EPOSTA.match(satir.strip())
        satirlar.append(eslesme.group("url") if eslesme else satir)
    return "\n".join(satirlar)


def _http_baglantisi_sonunu_temizle(adres):
    """Cümle noktalamasını URL'den ayırırken dengeli kapanış işaretlerini korur."""
    adres = str(adres or "")
    onceki = None
    while adres and adres != onceki:
        onceki = adres
        adres = adres.rstrip(".,;:!?")
        for acilis, kapanis in (("(", ")"), ("[", "]"), ("{", "}")):
            while adres.endswith(kapanis) and adres.count(kapanis) > adres.count(acilis):
                adres = adres[:-1]
    return adres


def http_baglantilarini_bul(metin):
    """Metindeki HTTP/HTTPS bağlantılarını başlangıç ve bitiş konumlarıyla döndürür."""
    metin = str(metin or "")
    baglantilar = []
    for eslesme in RE_HTTP_BAGLANTI_ADAYI.finditer(metin):
        adres = _http_baglantisi_sonunu_temizle(eslesme.group(0))
        if not adres:
            continue
        baglantilar.append((eslesme.start(), eslesme.start() + len(adres), adres))
    return baglantilar


def http_baglantilarini_yeni_satirdan_baslat(metin):
    """Satır içindeki HTTP/HTTPS bağlantılarının önüne gerektiğinde satır sonu ekler."""
    metin = str(metin or "")
    baglantilar = http_baglantilarini_bul(metin)
    if not baglantilar:
        return metin
    parcalar = []
    onceki_bitis = 0
    for baslangic, bitis, adres in baglantilar:
        parcalar.append(metin[onceki_bitis:baslangic])
        satir_basi = metin.rfind("\n", 0, baslangic) + 1
        if metin[satir_basi:baslangic].strip():
            parcalar.append("\n")
        parcalar.append(adres)
        onceki_bitis = bitis
    parcalar.append(metin[onceki_bitis:])
    return "".join(parcalar)


def alinti_isaretlerini_temizle(metin):
    """Yanıt/iletme alıntılarındaki > işaretlerini kaldırır ve sıkışan satırları açar."""
    metin = str(metin or "").replace("\ufeff", "")
    if not metin:
        return ""
    metin = RE_ALINTI_ISARETI.sub("\n\n", metin)
    satirlar = []
    for satir in metin.splitlines():
        temiz = re.sub(r"^\s*>+\s*", "", satir).strip()
        temiz = re.sub(r"\s+>+\s*$", "", temiz).strip()
        if not temiz or re.fullmatch(r">+", temiz):
            if satirlar and satirlar[-1]:
                satirlar.append("")
            continue
        satirlar.append(temiz)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(satirlar)).strip()


def alinti_basliklarini_duzenle(metin):
    """Alıntı başlangıçlarını ve köşeli e-posta adreslerini daha okunur hale getirir."""
    satirlar = []
    for satir in str(metin or "").splitlines():
        temiz = RE_KOSELI_EPOSTA_ADRESI.sub(r"\1", satir).strip()
        temiz = RE_GROUPS_IO_DONUSTURULMUS_ADRES.sub(r"\g<yerel>@\g<alan>", temiz)
        eslesme = RE_ALINTI_YAZDI_SATIRI.match(temiz)
        if eslesme:
            kisi = eslesme.group("kisi").strip()
            tarih = eslesme.group("tarih").strip()
            if kisi:
                satirlar.append(kisi)
            satirlar.append(f"({tarih}) tarih ve saatte şunları yazdı:")
        else:
            satirlar.append(temiz)
    return "\n".join(satirlar)


def konu_gosterimini_duzenle(konu):
    """Teknik yanıt/iletme konu öneklerini kullanıcıya daha doğal gösterir."""
    konu = str(konu or "").strip()
    if not konu:
        return ""
    etiketler = []
    kalan = konu
    # Zincirlenmiş "Fwd: Re:" başlıklarında yalnızca ilk önek çevrilmesin.
    # Kötü biçimli bir başlığın döngüyü uzatmaması için makul bir sınır kullanılır.
    for _ in range(20):
        eslesme = RE_YANIT_KONU_ONEKI.match(kalan)
        if eslesme:
            if "Yanıtlanmış" not in etiketler:
                etiketler.append("Yanıtlanmış")
            kalan = eslesme.group(1).strip()
            continue
        eslesme = RE_ILETILMIS_KONU_ONEKI.match(kalan)
        if eslesme:
            etiketler.append("İletilmiş")
            kalan = eslesme.group(1).strip()
            continue
        break
    if not etiketler:
        return konu
    return ": ".join(etiketler + [kalan])


def guvenli_coz(metin):
    if not metin:
        return ""
    try:
        sonuc = []
        for icerik, karakter_kumesi in decode_header(str(metin)):
            if isinstance(icerik, bytes):
                sonuc.append(icerik.decode(karakter_kumesi or "utf-8", errors="replace"))
            else:
                sonuc.append(str(icerik))
        return metin_kodlama_bozulmasini_duzelt("".join(sonuc).strip())
    except Exception:
        return metin_kodlama_bozulmasini_duzelt(str(metin).strip())


def html_icerik_gibi_gorunuyor_mu(metin):
    """Metnin HTML etiketi veya HTML e-posta kırpığı içerip içermediğini denetler."""
    metin = str(metin or "")
    if not metin or "<" not in metin or ">" not in metin:
        return False
    return bool(re.search(r"(?is)<\s*/?\s*(html|head|body|style|script|table|thead|tbody|tfoot|tr|td|th|div|span|p|br|a|img|meta|title|strong|em|b|i|u|ul|ol|li|blockquote|section|article|header|footer|hr)\b", metin))


def html_kirpilmamis_bloklari_temizle(html_metni):
    """Kırpılmış HTML ön izlemelerinde kapanmamış head/style/script bloklarını atar."""
    metin = str(html_metni or "")
    for etiket in ("style", "script"):
        desen_acilis = re.compile(r"(?is)<\s*" + etiket + r"\b[^>]*>")
        desen_kapanis = re.compile(r"(?is)</\s*" + etiket + r"\s*>")
        while True:
            acilis = desen_acilis.search(metin)
            if not acilis:
                break
            kapanis = desen_kapanis.search(metin, acilis.end())
            if kapanis:
                metin = metin[:acilis.start()] + " " + metin[kapanis.end():]
            else:
                # IMAP BODY.PEEK kırpığı style/script bloğunun ortasında bittiyse
                # kalan CSS/JS kullanıcıya ön izleme olarak okutulmamalıdır.
                metin = metin[:acilis.start()]
                break

    head_acilis = re.search(r"(?is)<\s*head\b[^>]*>", metin)
    if head_acilis:
        head_kapanis = re.search(r"(?is)</\s*head\s*>", metin, head_acilis.end())
        if head_kapanis:
            metin = metin[:head_acilis.start()] + " " + metin[head_kapanis.end():]
        else:
            body_acilis = re.search(r"(?is)<\s*body\b[^>]*>", metin, head_acilis.end())
            if body_acilis:
                metin = metin[:head_acilis.start()] + " " + metin[body_acilis.start():]
            else:
                metin = metin[:head_acilis.start()]
    return metin


def html_baglantilarini_koru(html_metni):
    """HTML bağlantı metnini ve HTTP adresini düz metne birlikte aktarır."""
    def baglantiyi_cevir(eslesme):
        href = RE_HTML_HREF.search(eslesme.group("ozellikler") or "")
        if not href:
            return eslesme.group("icerik") or ""
        adres = html.unescape(next((deger for deger in href.groups() if deger is not None), "")).strip()
        if not re.match(r"^https?://", adres, flags=re.IGNORECASE):
            return eslesme.group("icerik") or ""
        gorunen = RE_HTML_ETIKETLERI.sub(" ", eslesme.group("icerik") or "")
        gorunen = re.sub(r"\s+", " ", html.unescape(gorunen)).strip()
        if not gorunen or gorunen.casefold() == adres.casefold():
            return "\n" + adres + "\n"
        return f"{gorunen}\n{adres}\n"

    return RE_HTML_BAGLANTI.sub(baglantiyi_cevir, str(html_metni or ""))


def html_temizle(html_metni):
    if not html_metni:
        return ""
    html_metni = str(html_metni)
    if len(html_metni) > HTML_TEMIZLE_KARAKTER_SINIRI:
        html_metni = html_metni[:HTML_TEMIZLE_KARAKTER_SINIRI]
    metin = RE_HTML_STYLE_SCRIPT_HEAD.sub("", html_metni)
    metin = html_kirpilmamis_bloklari_temizle(metin)
    metin = html_baglantilarini_koru(metin)
    metin = RE_HTML_BLOK_ETIKETLERI.sub("\n", metin)
    metin = RE_HTML_ETIKETLERI.sub(" ", metin)
    # Kırpılmış MIME/HTML parçalarında meta charset etiketi veya yarım HTML etiketi
    # parçalanmış biçimde metne sızabilir: t=iso-8859-9">, <table width=...
    metin = re.sub(r"(?is)<\s*/?\s*[a-z][^<>\r\n]{0,300}$", " ", metin)
    metin = re.sub(r"(?i)\b(?:charse)?t\s*=\s*[\"']?(?:utf-8|iso-8859-9|windows-1254|latin-1)[\"']?\s*[\"']?\s*>?", " ", metin)
    metin = html.unescape(metin)
    metin = RE_COKLU_BOSLUK.sub(" ", metin)
    satirlar = [satir.strip() for satir in metin.splitlines()]
    return "\n".join(satir for satir in satirlar if satir).strip()


def duz_metni_ekran_okuyucu_icin_temizle(metin):
    """Düz metnin satır düzenini korurken temel Markdown işaretlerini temizler."""
    metin = metin_kodlama_bozulmasini_duzelt(str(metin or "")).replace("\r\n", "\n").replace("\r", "\n")
    metin = eposta_alt_bilgi_fazlaliklarini_temizle(metin)
    metin = alinti_isaretlerini_temizle(metin)
    metin = alinti_basliklarini_duzenle(metin)
    if not metin:
        return ""

    paragraflar = re.split(r"\n[ \t]*\n", metin)
    temiz_paragraflar = []
    for paragraf in paragraflar:
        satirlar = [satir.strip() for satir in paragraf.split("\n")]
        satirlar = [satir for satir in satirlar if satir]
        if not satirlar:
            continue

        # Düz metindeki Enter tuşları anlamlıdır. İmza, adres ve kullanıcının
        # bilinçli olarak alt alta yazdığı diğer satırlar boşlukla birleştirilmez.
        paragraf = "\n".join(satirlar)

        paragraf = RE_MARKDOWN_BAGLANTI.sub(r"\1: \2", paragraf)
        onceki = None
        while paragraf != onceki:
            onceki = paragraf
            paragraf = RE_MARKDOWN_VURGU.sub(r"\1", paragraf)
        paragraf = re.sub(r"(?m)^\s*#{1,6}\s+", "", paragraf)
        paragraf = paragraf.replace("`", "")
        paragraf = re.sub(r"(?m)^\s*\*{2,3}\s+", "", paragraf)
        paragraf = re.sub(r"(?m)^\s*\*\s+", "- ", paragraf)
        # Mailchimp gibi düz metin bültenleri kapanış işareti olmadan `** başlık`
        # üretebilir. Kalan çift/üçlü vurgu işaretlerini de konuşmadan çıkar.
        paragraf = re.sub(r"(?<!\*)\*{2,3}(?=\s)", "", paragraf)
        # Bağlantı başlığa, paranteze veya emojiye yapışmış olsa da her URL
        # ekran okuyucuda ayrı bir satırdan başlasın.
        paragraf = http_baglantilarini_yeni_satirdan_baslat(paragraf)
        paragraf = re.sub(r"\n{2,}", "\n", paragraf)
        paragraf = RE_COKLU_BOSLUK.sub(" ", paragraf)
        temiz_paragraflar.append(paragraf.strip())

    return "\n\n".join(paragraf for paragraf in temiz_paragraflar if paragraf).strip()


def turkce_tarih_yap(tarih_metni):
    if not tarih_metni:
        return _("Tarih yok")
    aylar = {
        1: _("Ocak"),
        2: _("Şubat"),
        3: _("Mart"),
        4: _("Nisan"),
        5: _("Mayıs"),
        6: _("Haziran"),
        7: _("Temmuz"),
        8: _("Ağustos"),
        9: _("Eylül"),
        10: _("Ekim"),
        11: _("Kasım"),
        12: _("Aralık"),
    }
    try:
        tarih = parsedate_to_datetime(tarih_metni)
        if tarih.tzinfo is not None:
            tarih = tarih.astimezone()
        return f"{tarih.day} {aylar[tarih.month]} {tarih.year} {tarih.hour:02d}:{tarih.minute:02d}"
    except Exception:
        return str(tarih_metni)


def guvenli_dosya_adi(metin, varsayilan="dosya", azami_uzunluk=90):
    metin = guvenli_coz(metin or varsayilan)
    metin = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", metin)
    metin = re.sub(r"\s+", " ", metin).strip(" ._")
    if not metin:
        metin = varsayilan
    return metin[:azami_uzunluk].strip(" ._") or varsayilan


def eposta_basligi_tek_satir_yap(deger):
    deger = str(deger or "").strip()
    deger = re.sub(r"[\r\n]+", " ", deger)
    deger = re.sub(r"\s+", " ", deger).strip()
    return deger
