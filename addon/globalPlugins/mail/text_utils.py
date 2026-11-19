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
from html.parser import HTMLParser
from urllib.parse import urlsplit
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
RE_ILETILMIS_KONU_ONEKI = re.compile(r"^\s*(?:fw|fwd|ilt)\s*:\s*(.+)$", re.IGNORECASE)
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
    for _sira in range(20):
        eslesme = RE_YANIT_KONU_ONEKI.match(kalan)
        if eslesme:
            if _("Yanıtlanmış") not in etiketler:
                etiketler.append(_("Yanıtlanmış"))
            kalan = eslesme.group(1).strip()
            continue
        eslesme = RE_ILETILMIS_KONU_ONEKI.match(kalan)
        if eslesme:
            if _("İletilmiş") not in etiketler:
                etiketler.append(_("İletilmiş"))
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


IZINLI_BAGLANTI_SEMALARI = ("http", "https", "mailto")
_BAGLANTI_KONTROL_KARAKTERLERI = re.compile(r"[\x00-\x20\x7f-\x9f​-‏  ﻿]")


def guvenli_baglanti_mi(adres):
    """Yalnızca http, https ve mailto adreslerinin dış uygulamada açılmasına izin verir.

    Tarayıcıların yok saydığı boşluk ve denetim karakterleri önce atılır; böylece
    ``java\\tscript:`` gibi gizlenmiş şemalar da reddedilir.
    """
    if not isinstance(adres, str):
        return False
    temiz = _BAGLANTI_KONTROL_KARAKTERLERI.sub("", adres)
    # İçinde boşluk veya denetim karakteri bulunan adres şüphelidir; reddedilir.
    if not temiz or temiz != adres.strip():
        return False
    try:
        parcalar = urlsplit(temiz)
    except ValueError:
        return False
    sema = parcalar.scheme.lower()
    if sema not in IZINLI_BAGLANTI_SEMALARI:
        return False
    if sema == "mailto":
        return bool(parcalar.path)
    return bool(parcalar.netloc and parcalar.hostname)


_HTML_IZINLI_ETIKETLER = frozenset({
    "a", "b", "strong", "i", "em", "u", "s", "strike", "p", "br", "hr", "div", "span",
    "blockquote", "pre", "code", "ul", "ol", "li", "dl", "dt", "dd",
    "h1", "h2", "h3", "h4", "h5", "h6", "sub", "sup", "small", "center",
    "table", "caption", "thead", "tbody", "tfoot", "tr", "td", "th",
})
_HTML_BOS_ETIKETLER = frozenset({"br", "hr"})
_HTML_ICERIGIYLE_ATILAN_ETIKETLER = frozenset({
    "script", "style", "head", "title", "noscript", "template", "iframe",
    "frameset", "noframes", "object", "applet", "svg", "math", "audio",
    "video", "canvas", "select", "textarea", "button", "xmp",
})
# Kapanış etiketi olmayan tehlikeli öğeler yalnızca atılır; içerik atlama kipine girilmez.
_HTML_BOS_ATILAN_ETIKETLER = frozenset({
    "embed", "frame", "input", "meta", "link", "base", "source", "track", "param",
})
_HTML_SAYISAL_OZNITELIKLER = {"td": ("colspan", "rowspan"), "th": ("colspan", "rowspan")}

# "E-posta içeriğini olduğu gibi göster" seçeneğinde ek olarak izin verilenler.
# Betik, çerçeve, form, nesne, meta yönlendirme ve olay öznitelikleri bu kipte de atılır.
_UZAK_EK_ETIKETLER = frozenset({"font", "big", "tt", "cite", "address", "abbr"})
_UZAK_GENEL_OZNITELIKLER = frozenset({
    "style", "class", "align", "valign", "width", "height", "bgcolor", "color", "face",
    "size", "border", "cellpadding", "cellspacing", "dir", "lang", "title", "nowrap",
})
_RESIM_VERI_ADRESI = re.compile(r"^data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=]+$", re.IGNORECASE)
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
_OZNITELIK_KONTROL_KARAKTERLERI = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _resim_adresi_guvenli_mi(adres):
    """Yalnızca http(s) adresleri ve gömülü png/jpeg/gif/webp resimleri güvenlidir."""
    adres = str(adres or "").strip()
    if not adres or _OZNITELIK_KONTROL_KARAKTERLERI.search(adres) or any(k in adres for k in (" ", "\t", "\r", "\n")):
        return False
    if _RESIM_VERI_ADRESI.match(adres):
        return True
    try:
        parcalar = urlsplit(adres)
    except ValueError:
        return False
    return parcalar.scheme.lower() in ("http", "https") and bool(parcalar.netloc and parcalar.hostname)


def _css_guvenli_mi(css):
    """Betik çalıştırabilecek veya güvensiz adrese bağlanan CSS'i reddeder."""
    css = str(css or "")
    # Ters eğik çizgi (CSS kaçışı) gizlenmiş anahtar sözcükleri saklayabilir; reddedilir.
    if "\\" in css or "<" in css or "\x00" in css:
        return False
    sade = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    kucuk = re.sub(r"\s+", "", sade).lower()
    for yasak in ("expression(", "javascript:", "vbscript:", "behavior:", "-moz-binding", "@import"):
        if yasak in kucuk:
            return False
    for eslesme in _CSS_URL.finditer(sade):
        if not _resim_adresi_guvenli_mi(eslesme.group(2)):
            return False
    return True


class _HtmlTemizleyici(HTMLParser):
    """İzin listesine dayalı, betiksiz HTML üretir.

    Varsayılan kipte uzak içerik (resim, stil) da atılır. ``uzak_icerik`` doğruysa
    http(s) resimleri ve güvenli biçim öznitelikleri korunur; betikler yine atılır.
    """

    def __init__(self, uzak_icerik=False):
        super().__init__(convert_charrefs=True)
        self.cikti = []
        self._acik = []
        self._atlanan = None
        self._atlanan_derinlik = 0
        self.uzak = bool(uzak_icerik)
        self._izinli = _HTML_IZINLI_ETIKETLER | (_UZAK_EK_ETIKETLER if self.uzak else frozenset())
        # Uzak kipte <head> içindeki <style> bloklarının da korunabilmesi için head atlanmaz;
        # title, meta, link gibi öğeler yine tek tek atılır.
        self._atilan = _HTML_ICERIGIYLE_ATILAN_ETIKETLER - ({"style", "head"} if self.uzak else frozenset())
        self._stil_icinde = False
        self._stil_tamponu = []

    def _stili_kapat(self):
        css = "".join(self._stil_tamponu)
        self._stil_icinde = False
        self._stil_tamponu = []
        if css.strip() and _css_guvenli_mi(css):
            self.cikti.append("<style>%s</style>" % css)

    def _atlama_durumu(self, etiket, baslangic):
        if self._atlanan is None:
            if baslangic:
                self._atlanan = etiket
                self._atlanan_derinlik = 1
            return
        if etiket == self._atlanan:
            self._atlanan_derinlik += 1 if baslangic else -1
            if self._atlanan_derinlik <= 0:
                self._atlanan = None
                self._atlanan_derinlik = 0

    def handle_starttag(self, etiket, ozellikler):
        etiket = etiket.lower()
        if self._atlanan is not None:
            self._atlama_durumu(etiket, True)
            return
        if etiket in _HTML_BOS_ATILAN_ETIKETLER:
            return
        if etiket == "style" and self.uzak:
            self._stil_icinde = True
            self._stil_tamponu = []
            return
        if etiket in self._atilan:
            self._atlama_durumu(etiket, True)
            return
        if etiket == "img":
            ozel = {}
            for ad, deger in ozellikler:
                ozel[ad.lower()] = str(deger or "").strip()
            alt = ozel.get("alt", "")
            kaynak = ozel.get("src", "")
            if self.uzak and _resim_adresi_guvenli_mi(kaynak):
                nitelik = ' src="%s"' % html.escape(kaynak, quote=True)
                if alt:
                    nitelik += ' alt="%s"' % html.escape(alt, quote=True)
                for ad in ("width", "height", "title", "align", "border"):
                    deger = ozel.get(ad, "")
                    if deger and len(deger) <= 200 and not _OZNITELIK_KONTROL_KARAKTERLERI.search(deger):
                        nitelik += ' %s="%s"' % (ad, html.escape(deger, quote=True))
                if ozel.get("style") and _css_guvenli_mi(ozel["style"]):
                    nitelik += ' style="%s"' % html.escape(ozel["style"], quote=True)
                self.cikti.append("<img%s>" % nitelik)
                return
            if alt:
                self.cikti.append(html.escape("[%s]" % alt, quote=False))
            return
        if etiket not in self._izinli:
            return
        nitelikler = ""
        if etiket == "a":
            for ad, deger in ozellikler:
                if ad.lower() == "href" and guvenli_baglanti_mi(deger):
                    nitelikler = ' href="%s" rel="noopener noreferrer"' % html.escape(
                        str(deger).strip(), quote=True
                    )
                    break
        elif etiket in _HTML_SAYISAL_OZNITELIKLER:
            for ad, deger in ozellikler:
                if ad.lower() in _HTML_SAYISAL_OZNITELIKLER[etiket] and str(deger or "").strip().isdigit():
                    sayi = str(deger).strip()
                    if len(sayi) <= 3:
                        nitelikler += ' %s="%s"' % (ad.lower(), sayi)
        if self.uzak:
            for ad, deger in ozellikler:
                ad = ad.lower()
                deger = str(deger or "").strip()
                if ad not in _UZAK_GENEL_OZNITELIKLER or not deger or len(deger) > 1000:
                    continue
                if _OZNITELIK_KONTROL_KARAKTERLERI.search(deger):
                    continue
                if ad == "style" and not _css_guvenli_mi(deger):
                    continue
                nitelikler += ' %s="%s"' % (ad, html.escape(deger, quote=True))
        self.cikti.append("<%s%s>" % (etiket, nitelikler))
        if etiket not in _HTML_BOS_ETIKETLER:
            self._acik.append(etiket)

    def handle_startendtag(self, etiket, ozellikler):
        self.handle_starttag(etiket, ozellikler)
        etiket = etiket.lower()
        if etiket not in _HTML_BOS_ETIKETLER and etiket in _HTML_IZINLI_ETIKETLER:
            self.handle_endtag(etiket)
        elif etiket in _HTML_ICERIGIYLE_ATILAN_ETIKETLER and self._atlanan == etiket:
            self.handle_endtag(etiket)

    def handle_endtag(self, etiket):
        etiket = etiket.lower()
        if etiket == "style" and self._stil_icinde:
            self._stili_kapat()
            return
        if self._atlanan is not None:
            self._atlama_durumu(etiket, False)
            return
        if etiket in self._acik:
            while self._acik:
                son = self._acik.pop()
                self.cikti.append("</%s>" % son)
                if son == etiket:
                    break

    def handle_data(self, veri):
        if self._stil_icinde:
            self._stil_tamponu.append(veri)
            return
        if self._atlanan is None:
            self.cikti.append(html.escape(veri, quote=False))

    # Yorumlar, bildirimler ve işleme yönergeleri hiçbir zaman çıktıya alınmaz.
    def handle_comment(self, veri):
        pass

    def handle_decl(self, bildirim):
        pass

    def handle_pi(self, veri):
        pass

    def unknown_decl(self, veri):
        pass

    def sonuc(self):
        if self._stil_icinde:
            self._stili_kapat()
        while self._acik:
            self.cikti.append("</%s>" % self._acik.pop())
        return "".join(self.cikti)


def html_guvenli_hale_getir(html_metni, uzak_icerik=False):
    """E-posta HTML'ini WebView'a verilmeden önce izin listesiyle temizler.

    Varsayılan olarak betik, stil, çerçeve, form, uzak resim, meta yönlendirme ve
    olay öznitelikleri atılır; yalnızca http, https ve mailto bağlantıları korunur.
    ``uzak_icerik`` doğruysa ("olduğu gibi göster") http(s) resimleri ve güvenli
    stil/biçim öznitelikleri de korunur; betikler ve çerçeveler yine atılır.
    """
    if not html_metni:
        return ""
    html_metni = str(html_metni)
    temizleyici = _HtmlTemizleyici(uzak_icerik=uzak_icerik)
    try:
        temizleyici.feed(html_metni)
        temizleyici.close()
    except Exception:
        # Bozuk HTML'de güvenli yedek: yalnızca kaçışlı düz metin.
        return html.escape(html_temizle(html_metni), quote=False).replace("\n", "<br>\n")
    return temizleyici.sonuc()


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


_WINDOWS_AYRILMIS_ADLAR = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def guvenli_dosya_adi(metin, varsayilan="dosya", azami_uzunluk=90):
    """Dosya adını güvenli hale getirir; Windows aygıt adlarını (CON, NUL...) önekler."""
    ad = _guvenli_dosya_adi_temel(metin, varsayilan, azami_uzunluk)
    if ad.split(".", 1)[0].strip().upper() in _WINDOWS_AYRILMIS_ADLAR:
        ad = "_" + ad
    return ad


def _guvenli_dosya_adi_temel(metin, varsayilan, azami_uzunluk):
    metin = guvenli_coz(metin or varsayilan)
    metin = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", metin)
    metin = re.sub(r"\s+", " ", metin).strip(" ._")
    if not metin:
        metin = varsayilan
    if len(metin) <= azami_uzunluk:
        return metin.strip(" ._") or varsayilan
    # Uzun adlarda dosya türü bozulmasın diye uzantı korunur.
    nokta = metin.rfind(".")
    uzanti = metin[nokta:] if 0 < nokta else ""
    if uzanti and (len(uzanti) > 16 or " " in uzanti):
        uzanti = ""
    govde = metin[:nokta] if uzanti else metin
    govde = govde[:azami_uzunluk - len(uzanti)].strip(" ._")
    return (govde + uzanti) if govde else (metin[:azami_uzunluk].strip(" ._") or varsayilan)


def eposta_basligi_tek_satir_yap(deger):
    deger = str(deger or "").strip()
    deger = re.sub(r"[\r\n]+", " ", deger)
    deger = re.sub(r"\s+", " ", deger).strip()
    return deger
