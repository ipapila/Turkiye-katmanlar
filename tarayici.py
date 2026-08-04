#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ekoloji-izleme.com — Haber Tarayıcı
====================================
Harita verisini birincil kaynak olarak kullanır,
RSS beslemelerinden ve web sitelerinden çevre haberlerini çeker.
Çıktı: haberler.json  (sitenin kök dizinine koyun)

Kurulum:
    pip install requests beautifulsoup4 feedparser lxml

Kullanım:
    python tarayici.py                   # tek seferlik
    python tarayici.py --surekli         # her 3 saatte bir döngü
    python tarayici.py --harita-url URL  # harita JSON endpoint'i
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# ─── YAPILANDIRMA ──────────────────────────────────────────────────────────────

HARITA_URLS = [
    # index.html'in kullandığı gerçek veri kaynağıyla birebir aynı
    # (bkz. index.html: repoOwner='ipapila', repoName='Turkiye-katmanlar',
    # repoPath='data.json' → raw.githubusercontent.com/.../main/data.json).
    "https://raw.githubusercontent.com/ipapila/Turkiye-katmanlar/main/data.json",
    # Harita uygulamanız localStorage ile çalışıyorsa bu URL'leri kendi
    # sunucunuzun JSON export endpoint'iyle değiştirin.
    "https://ekoloji-izleme.com/harita/data.json",
]

RSS_KAYNAKLARI = [
    # Google News — Çevre konuları
    {
        "url": "https://news.google.com/rss/search?q=çevre+ihlali+Türkiye&hl=tr&gl=TR&ceid=TR:tr",
        "kaynak": "Google News",
        "kategori": "Çevre İhlali",
    },
    {
        "url": "https://news.google.com/rss/search?q=orman+yangını+maden+Türkiye&hl=tr&gl=TR&ceid=TR:tr",
        "kaynak": "Google News",
        "kategori": "Orman / Maden",
    },
    {
        "url": "https://news.google.com/rss/search?q=HES+RES+baraj+çevre+Türkiye&hl=tr&gl=TR&ceid=TR:tr",
        "kaynak": "Google News",
        "kategori": "HES / RES / Baraj",
    },
    {
        "url": "https://news.google.com/rss/search?q=acele+kamulaştırma+çevre+Türkiye&hl=tr&gl=TR&ceid=TR:tr",
        "kaynak": "Google News",
        "kategori": "Kamulaştırma",
    },
    {
        "url": "https://news.google.com/rss/search?q=ÇED+maden+Türkiye+2025&hl=tr&gl=TR&ceid=TR:tr",
        "kaynak": "Google News",
        "kategori": "ÇED Kararları",
    },
    # Uzman çevre medyası
    {
        "url": "https://iklimhaber.org/feed/",
        "kaynak": "İklim Haber",
        "kategori": "İklim",
    },
    {
        "url": "https://www.sozcu.com.tr/rss/cevre.xml",
        "kaynak": "Sözcü",
        "kategori": "Haber",
    },
    {
        "url": "https://www.cumhuriyet.com.tr/rss/cevre.rss",
        "kaynak": "Cumhuriyet",
        "kategori": "Haber",
    },
    {
        "url": "https://www.tema.org.tr/duyurular?format=feed",
        "kaynak": "TEMA",
        "kategori": "STK",
    },
]

WEB_KAYNAKLARI = [
    {
        "url": "https://yesilgazete.org",
        "kaynak": "Yeşil Gazete",
        "kategori": "Çevre Medyası",
        "secici": "article h2 a, .entry-title a, h2.post-title a",
        "ozet_secici": "article .entry-content p, .post-excerpt",
    },
    {
        "url": "https://iklimhaber.org",
        "kaynak": "İklim Haber",
        "kategori": "İklim",
        "secici": "article h2 a, .entry-title a",
        "ozet_secici": "article p",
    },
    {
        "url": "https://www.greenpeace.org/turkey/blog/",
        "kaynak": "Greenpeace TR",
        "kategori": "STK",
        "secici": ".post-title a, h2 a",
        "ozet_secici": ".post-excerpt p",
    },
    {
        "url": "https://www.wwf.org.tr/basin_bultenleri/",
        "kaynak": "WWF Türkiye",
        "kategori": "STK",
        "secici": ".press-release-title a, h3 a, h2 a",
        "ozet_secici": ".press-release-excerpt",
    },
    {
        "url": "https://tr.euronews.com/tag/cevre",
        "kaynak": "Euronews TR",
        "kategori": "Haber",
        "secici": ".article__title a, h3.article__title a",
        "ozet_secici": ".article__summary",
    },
    {
        "url": "https://www.csb.gov.tr/duyurular",
        "kaynak": "Çevre Bakanlığı",
        "kategori": "Resmi",
        "secici": ".duyuru-item a, .news-item a, h3 a",
        "ozet_secici": ".duyuru-ozet",
    },
]

# İlgisiz haberleri dışarıda bırakmak için negatif filtre
NEGATIF_ANAHTAR = [
    "spor", "futbol", "taraftar", "ekonomi faiz", "kur dolar",
    "moda", "magazin", "dizi film", "müzik", "oyun video",
]

CEVRE_ANAHTAR = [
    "çevre", "ekoloji", "orman", "maden", "HES", "RES", "GES", "baraj",
    "kamulaştırma", "ÇED", "doğa", "habitat", "kirlilik", "atık",
    "iklim", "yangın", "sel", "taşkın", "heyelan", "kıyı", "deniz",
    "su hakkı", "tarım", "biyoçeşitlilik", "nesli", "koruma alanı",
    "taş ocağı", "termik", "jeotermal", "nükleer", "bor", "altın maden",
    "ihlal", "kaçak yapı", "ruhsatsız", "izinsiz", "yıkım", "ağaç kesim",
    "sulak alan", "milli park", "MAPEG", "EPDK", "Resmî Gazete",
]

# 81 il merkezi için yaklaşık koordinat (il tespit edilince haritaya
# yerleştirmek için kullanılır; ilçe bilgisi yoksa bu, en iyi tahmindir).
IL_KOORDINATLARI = {
    "Adana": (37.00, 35.32), "Adıyaman": (37.76, 38.28), "Afyonkarahisar": (38.76, 30.54),
    "Ağrı": (39.72, 43.05), "Amasya": (40.65, 35.83), "Ankara": (39.93, 32.86),
    "Antalya": (36.90, 30.71), "Artvin": (41.18, 41.82), "Aydın": (37.85, 27.85),
    "Balıkesir": (39.65, 27.89), "Bilecik": (40.15, 29.98), "Bingöl": (38.88, 40.50),
    "Bitlis": (38.40, 42.11), "Bolu": (40.74, 31.60), "Burdur": (37.72, 30.29),
    "Bursa": (40.18, 29.06), "Çanakkale": (40.15, 26.41), "Çankırı": (40.60, 33.62),
    "Çorum": (40.55, 34.95), "Denizli": (37.78, 29.09), "Diyarbakır": (37.91, 40.24),
    "Edirne": (41.68, 26.56), "Elazığ": (38.68, 39.22), "Erzincan": (39.75, 39.49),
    "Erzurum": (39.90, 41.27), "Eskişehir": (39.78, 30.52), "Gaziantep": (37.07, 37.38),
    "Giresun": (40.91, 38.39), "Gümüşhane": (40.46, 39.48), "Hakkari": (37.58, 43.74),
    "Hatay": (36.20, 36.16), "Isparta": (37.76, 30.55), "Mersin": (36.81, 34.64),
    "İstanbul": (41.01, 28.98), "İzmir": (38.42, 27.14), "Kars": (40.61, 43.10),
    "Kastamonu": (41.38, 33.78), "Kayseri": (38.73, 35.49), "Kırklareli": (41.73, 27.22),
    "Kırşehir": (39.15, 34.16), "Kocaeli": (40.85, 29.88), "Konya": (37.87, 32.48),
    "Kütahya": (39.42, 29.98), "Malatya": (38.35, 38.31), "Manisa": (38.61, 27.43),
    "Kahramanmaraş": (37.57, 36.94), "Mardin": (37.31, 40.74), "Muğla": (37.22, 28.36),
    "Muş": (38.73, 41.49), "Nevşehir": (38.62, 34.72), "Niğde": (37.97, 34.68),
    "Ordu": (40.98, 37.88), "Rize": (41.02, 40.52), "Sakarya": (40.78, 30.40),
    "Samsun": (41.29, 36.33), "Siirt": (37.93, 41.94), "Sinop": (42.03, 35.15),
    "Sivas": (39.75, 37.02), "Tekirdağ": (40.98, 27.51), "Tokat": (40.31, 36.55),
    "Trabzon": (41.00, 39.72), "Tunceli": (39.11, 39.55), "Şanlıurfa": (37.16, 38.79),
    "Uşak": (38.68, 29.41), "Van": (38.49, 43.38), "Yozgat": (39.82, 34.81),
    "Zonguldak": (41.46, 31.79), "Aksaray": (38.37, 34.03), "Bayburt": (40.26, 40.22),
    "Karaman": (37.18, 33.22), "Kırıkkale": (39.85, 33.52), "Batman": (37.88, 41.13),
    "Şırnak": (37.52, 42.46), "Bartın": (41.63, 32.34), "Ardahan": (41.11, 42.70),
    "Iğdır": (39.92, 44.05), "Yalova": (40.65, 29.28), "Karabük": (41.20, 32.63),
    "Kilis": (36.72, 37.12), "Osmaniye": (37.07, 36.25), "Düzce": (40.84, 31.16),
}

# Metindeki anahtar kelimeye göre data.json'daki mevcut "tip" değerleriyle
# birebir uyumlu bir kategori üret. Sıra önemli: daha spesifik olanlar önce
# denenir, hiçbiri eşleşmezse "Ekolojik İhlal" genel kategorisi kullanılır.
KATEGORI_ANAHTAR_KELIMELER = [
    ("RES", ["res projesi", "rüzgar enerji", "rüzgar santral", " res "]),
    ("HES", ["hes projesi", "hidroelektrik", "akarsu tipi santral", " hes "]),
    ("GES", ["güneş enerjisi santral", "ges projesi", " ges "]),
    ("Jeotermal", ["jeotermal"]),
    ("Termik Reaktör", ["termik santral", "kömür santral"]),
    ("Nükleer Enerji", ["nükleer santral", "nükleer enerji"]),
    ("Taş-Mermer Ocağı", ["mermer ocağı", "taş ocağı", "taş-mermer"]),
    ("Maden Ocağı", ["maden ocağı", "maden sahası", "maden ruhsat", "altın maden", "bor maden"]),
    ("Acele Kamulaştırma", ["acele kamulaştırma", "kamulaştırma"]),
    ("Kültür Varlığı", ["kültür varlığı", "sit alanı", "tarihi eser", "sit alan"]),
    ("İklim Olayları", ["orman yangını", "sel felaketi", "taşkın", "heyelan", "hortum", "dolu yağış", "kuraklık"]),
    ("Milli Park", ["milli park"]),
    ("Sulak Alan", ["sulak alan"]),
    ("Özel Çevre Koruma Alanı", ["özel çevre koruma", "koruma alanı"]),
    ("Kıyı İhlalleri", ["kıyı dolgu", "kıyı ihlal", "kıyı işgal", "kaçak dolgu"]),
    ("Orman Alanı", ["ağaç kesim", "kaçak kesim", "orman arazisi", "orman alanı"]),
]


# ─── YARDIMCI FONKSİYONLAR ─────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tarayici")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EkolojiIzleme/1.0; "
        "+https://ekoloji-izleme.com)"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def haber_id(url: str, baslik: str) -> str:
    """Haber için tekrar girmesini önleyecek benzersiz ID üret."""
    hammadde = f"{url}|{baslik}"
    return hashlib.md5(hammadde.encode("utf-8")).hexdigest()[:12]


def cevre_ile_ilgili(metin: str) -> bool:
    """Metinde çevreyle ilgili anahtar kelime ara."""
    m = metin.lower()
    if any(k in m for k in NEGATIF_ANAHTAR):
        return False
    return any(k.lower() in m for k in CEVRE_ANAHTAR)


def tarih_normalize(tarih_str: Optional[str]) -> Optional[str]:
    """Farklı tarih formatlarını ISO 8601'e çevir."""
    if not tarih_str:
        return None
    try:
        # feedparser struct_time
        if hasattr(tarih_str, "tm_year"):
            dt = datetime(*tarih_str[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        # string
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(str(tarih_str))
        return dt.isoformat()
    except Exception:
        return str(tarih_str)


def fetch(url: str, timeout: int = 12) -> Optional[requests.Response]:
    """URL'yi çek, hata varsa None döndür."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r
    except Exception as e:
        log.warning(f"Fetch başarısız [{url[:60]}]: {e}")
        return None


# ─── HABERİ HARİTA KAYDINA DÖNÜŞTÜRME ──────────────────────────────────────────
# NOT: Bu bölüm, taranan haberleri data.json'un ŞEMASIYLA birebir uyumlu yeni
# kayıtlara çevirir ve otomatik olarak haritaya (data.json) ekler.

# İl adlarını uzundan kısaya sırala ki "Kahramanmaraş" ararken yanlışlıkla
# başka bir alt-string eşleşmesin.
_IL_ADLARI_SIRALI = sorted(IL_KOORDINATLARI.keys(), key=len, reverse=True)


def il_tespit_et(metin: str) -> Optional[str]:
    """Metinde geçen bir il adını (kelime sınırlarıyla) bul."""
    for il in _IL_ADLARI_SIRALI:
        # Türkçe büyük/küçük harf sorunlarından (İ/i, I/ı) kaçınmak için
        # basit bir "casefold" karşılaştırması + kelime sınırı kontrolü.
        desen = r"\b" + re.escape(il) + r"\b"
        if re.search(desen, metin, flags=re.IGNORECASE):
            return il
    return None


def kategori_tespit_et(metin: str) -> str:
    """Metindeki anahtar kelimelere göre data.json uyumlu bir 'tip' üret."""
    m = metin.lower()
    for kategori, kelimeler in KATEGORI_ANAHTAR_KELIMELER:
        if any(k in m for k in kelimeler):
            return kategori
    return "Ekolojik İhlal"


def il_koordinat_tahmini(il: str, tuz: str) -> tuple[float, float]:
    """
    İl merkezine, kayda özgü ama tekrar üretilebilir (deterministik) küçük
    bir sapma ekler. Böylece aynı ildeki farklı haberler tam olarak aynı
    noktaya üst üste binmez; aynı haber tekrar taranırsa da hep aynı
    koordinatı üretir (idempotent).
    """
    lat0, lng0 = IL_KOORDINATLARI[il]
    h = int(hashlib.md5(tuz.encode("utf-8")).hexdigest()[:8], 16)
    # ±0.12 derece (~10-13 km) aralığında sapma
    dlat = ((h % 2401) / 2400 - 0.5) * 0.24
    dlng = (((h // 2401) % 2401) / 2400 - 0.5) * 0.24
    return round(lat0 + dlat, 5), round(lng0 + dlng, 5)


def _baslik_normalize(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-zçğıöşü0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def kayit_mukerrer_mi(yeni: dict, mevcut_liste: list[dict]) -> bool:
    """Aynı haber linkine ya da aynı il+başlığa sahip kayıt zaten var mı?"""
    yeni_link = (yeni.get("kaynak_link") or "").strip()
    yeni_ad = _baslik_normalize(yeni.get("ad", ""))
    for r in mevcut_liste:
        if yeni_link and (r.get("kaynak_link") or "").strip() == yeni_link:
            return True
        if (
            yeni_ad
            and r.get("il") == yeni.get("il")
            and _baslik_normalize(r.get("ad", "")) == yeni_ad
        ):
            return True
    return False


def haberden_harita_kaydi_uret(haber: dict) -> Optional[dict]:
    """
    Taranan bir haberi data.json şemasına uygun bir harita kaydına çevirir.
    İl tespit edilemezse None döner (konumsuz kayıt haritaya eklenmez —
    yanlış yere işaretlemektense hiç eklememek tercih edilir).
    """
    metin = f"{haber.get('baslik','')} {haber.get('ozet','')}"
    il = il_tespit_et(metin)
    if not il:
        return None
    kategori = kategori_tespit_et(metin)
    lat, lng = il_koordinat_tahmini(il, haber.get("id", haber.get("url", "")))
    return {
        "id": f"tarayici-{haber.get('id')}",
        "tip": kategori,
        "ad": (haber.get("baslik") or "")[:200],
        "il": il,
        "ilce": "",
        "aciklama": (haber.get("ozet") or "")[:400],
        "koordinatlar": {"lat": lat, "lng": lng},
        "alan_ha": 0,
        "durum": "Takip Ediliyor",
        "belge_no": "",
        "eklenme": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "kaynak": haber.get("kaynak", ""),
        "alt_kategori": "Otomatik Tarama",
        "kaynak_link": haber.get("url", ""),
    }


def harita_verisini_yukle(yol_veya_url: str) -> list[dict]:
    """data.json'u yerel dosyadan (repo içi) ya da URL'den yükle."""
    if yol_veya_url.startswith("http://") or yol_veya_url.startswith("https://"):
        r = fetch(yol_veya_url)
        if not r:
            return []
        try:
            data = r.json()
        except Exception as e:
            log.warning(f"data.json parse hatası: {e}")
            return []
    else:
        p = Path(yol_veya_url)
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"data.json okunamadı: {e}")
            return []
    return data if isinstance(data, list) else []


def harita_verisini_kaydet(yol: str, kayitlar: list[dict]) -> None:
    Path(yol).write_text(
        json.dumps(kayitlar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── HARITA VERİSİ ─────────────────────────────────────────────────────────────

def harita_verisi_cek(urls: list[str]) -> list[dict]:
    """
    Harita JSON verilerini çek ve normalize et.
    Haritanın localStorage ile çalıştığı durumlarda bu URL'ler
    boş döner; Firebase/GitHub Pages JSON export kullanılmalıdır.
    """
    kayitlar = []
    for url in urls:
        log.info(f"Harita verisi: {url}")
        r = fetch(url)
        if not r:
            continue
        try:
            data = r.json()
        except Exception as e:
            log.warning(f"  JSON parse hatası: {e}")
            continue
        items = _harita_json_ogelerini_ayikla(data)
        kayitlar.extend(_harita_kayitlarini_normallestir(items, url))
        log.info(f"  → {len(items)} kayıt okundu")

    return kayitlar


def _harita_json_ogelerini_ayikla(data) -> list:
    """Ham JSON'dan (liste / GeoJSON / sarmalanmış dict) öge listesini çıkar."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return (
            data.get("features") or      # GeoJSON
            data.get("ihlaller") or
            data.get("data") or
            data.get("items") or
            (list(data.values())[0] if data else [])
        )
    return []


def _harita_kayitlarini_normallestir(items: list, kaynak_etiketi: str) -> list[dict]:
    """
    Ham harita ögelerini (GeoJSON Feature, data.json şeması, vb.) ortak,
    düz bir gösterim şemasına çevirir. haber referans listesi
    (haberler.json → harita_kayitlari) için kullanılır.
    """
    kayitlar = []
    for item in items:
        # GeoJSON Feature → düzleştir
        if item.get("type") == "Feature":
            props = item.get("properties", {})
            coords = item.get("geometry", {}).get("coordinates", [])
            item = {**props}
            if coords and len(coords) >= 2:
                item["lng"] = coords[0]
                item["lat"] = coords[1]

        # data.json şemasında koordinatlar iç içe:
        # {"koordinatlar": {"lat": ..., "lng": ...}}
        koord = item.get("koordinatlar") or {}
        if not isinstance(koord, dict):
            koord = {}

        il = item.get("il") or item.get("location", "")
        ilce = item.get("ilce") or ""
        konum = item.get("konum") or (f"{il} / {ilce}" if il and ilce else il)

        kayit = {
            "id": item.get("id") or haber_id(kaynak_etiketi, item.get("baslik") or item.get("ad", "")),
            "baslik": (
                item.get("baslik") or item.get("ad")
                or item.get("name") or item.get("title", "")
            ),
            "konum": konum,
            "kategori": (
                item.get("kategori") or item.get("tip")
                or item.get("alan_turu") or item.get("type", "")
            ),
            "siddet": item.get("siddet") or item.get("durum") or "takipte",
            "tarih": tarih_normalize(
                item.get("tarih") or item.get("eklenme") or item.get("date")
            ),
            "url": (
                item.get("url") or item.get("kaynak_link")
                or item.get("kaynak_url") or ""
            ),
            "ozet": item.get("aciklama") or item.get("ozet") or item.get("description", ""),
            "lat": item.get("lat") or item.get("enlem") or koord.get("lat"),
            "lng": item.get("lng") or item.get("boylam") or koord.get("lng"),
            "kaynak": "harita",
            "kaynak_url": kaynak_etiketi,
        }
        if kayit["baslik"]:
            kayitlar.append(kayit)
    return kayitlar


# ─── RSS TARAMA ────────────────────────────────────────────────────────────────

def rss_tara(kaynaklar: list[dict]) -> list[dict]:
    haberler = []
    for kaynak in kaynaklar:
        url = kaynak["url"]
        log.info(f"RSS: {kaynak['kaynak']} [{kaynak['kategori']}]")
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                log.warning(f"  RSS parse sorunu: {feed.bozo_exception}")
                continue
            adet = 0
            for entry in feed.entries[:20]:
                baslik = entry.get("title", "").strip()
                link   = entry.get("link", "")
                ozet   = BeautifulSoup(
                    entry.get("summary", ""), "lxml"
                ).get_text(" ", strip=True)
                tarih  = tarih_normalize(entry.get("published_parsed") or entry.get("updated_parsed"))

                metin = f"{baslik} {ozet}"
                if not cevre_ile_ilgili(metin):
                    continue

                haberler.append({
                    "id": haber_id(link, baslik),
                    "baslik": baslik,
                    "ozet": ozet[:280] if ozet else "",
                    "url": link,
                    "tarih": tarih,
                    "kaynak": kaynak["kaynak"],
                    "kategori": kaynak["kategori"],
                    "kaynak_turu": "rss",
                })
                adet += 1
            log.info(f"  → {adet} haber")
            time.sleep(0.8)
        except Exception as e:
            log.warning(f"  RSS hatası: {e}")
    return haberler


# ─── WEB SCRAPING ──────────────────────────────────────────────────────────────

def web_tara(kaynaklar: list[dict]) -> list[dict]:
    haberler = []
    for kaynak in kaynaklar:
        log.info(f"Web: {kaynak['kaynak']}")
        r = fetch(kaynak["url"])
        if not r:
            continue
        try:
            soup = BeautifulSoup(r.text, "lxml")
            linkler = soup.select(kaynak["secici"])
            adet = 0
            for a in linkler[:15]:
                baslik = a.get_text(" ", strip=True)
                if not baslik or len(baslik) < 10:
                    continue
                href = a.get("href", "")
                if not href:
                    continue
                link = urljoin(kaynak["url"], href)

                # Özet bulmaya çalış
                ozet = ""
                if kaynak.get("ozet_secici"):
                    parent = a.find_parent(["article", "div", "li"])
                    if parent:
                        ozet_el = parent.select_one(kaynak["ozet_secici"])
                        if ozet_el:
                            ozet = ozet_el.get_text(" ", strip=True)[:280]

                metin = f"{baslik} {ozet}"
                if not cevre_ile_ilgili(metin):
                    continue

                haberler.append({
                    "id": haber_id(link, baslik),
                    "baslik": baslik,
                    "ozet": ozet,
                    "url": link,
                    "tarih": datetime.now(timezone.utc).isoformat(),
                    "kaynak": kaynak["kaynak"],
                    "kategori": kaynak["kategori"],
                    "kaynak_turu": "web",
                })
                adet += 1
            log.info(f"  → {adet} haber")
        except Exception as e:
            log.warning(f"  Scrape hatası: {e}")
        time.sleep(1.2)
    return haberler


# ─── TEKİL HABER DETAYI ────────────────────────────────────────────────────────

def ozet_cek(url: str, max_karakter: int = 400) -> str:
    """Haber sayfasından ilk anlamlı paragrafı çek."""
    r = fetch(url, timeout=8)
    if not r:
        return ""
    try:
        soup = BeautifulSoup(r.text, "lxml")
        # Meta description
        meta = soup.find("meta", attrs={"name": "description"}) or \
               soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):
            return meta["content"][:max_karakter]
        # İlk anlamlı paragraf
        for p in soup.select("article p, .content p, .entry-content p"):
            metin = p.get_text(" ", strip=True)
            if len(metin) > 60:
                return metin[:max_karakter]
    except Exception:
        pass
    return ""


# ─── ANA FONKSİYON ─────────────────────────────────────────────────────────────

def tara(
    cikti_dosyasi: str = "haberler.json",
    harita_urls: list[str] = None,
    ozet_cek_aktif: bool = False,
    max_haber: int = 200,
    data_dosyasi: str = "data.json",
    haritaya_otomatik_ekle: bool = True,
) -> dict:
    """Tüm kaynakları tara, çıktıyı JSON dosyasına yaz."""
    log.info("═" * 55)
    log.info("  ekoloji-izleme.com — Haber Tarayıcı başlatılıyor")
    log.info("═" * 55)

    tum_haberler: list[dict] = []
    gorulen_idler: set[str] = set()

    # 1. Mevcut haberler.json varsa yükle (artımlı güncelleme)
    p = Path(cikti_dosyasi)
    if p.exists():
        try:
            eski = json.loads(p.read_text(encoding="utf-8"))
            for h in eski.get("haberler", []):
                gorulen_idler.add(h.get("id", ""))
            log.info(f"Mevcut dosyada {len(gorulen_idler)} haber var.")
        except Exception as e:
            log.warning(f"Mevcut JSON okunamadı: {e}")
            eski = {"haberler": [], "harita_kayitlari": []}
    else:
        eski = {"haberler": [], "harita_kayitlari": []}

    # 2. Harita verisi (birincil kaynak) — önce repo içindeki yerel
    #    data.json'u dene (GitHub Actions bunu doğrudan commit edebilir),
    #    yoksa uzak URL'lere düş.
    log.info("\n── Harita Verisi ──")
    harita_kaynagi = data_dosyasi
    harita_ham = harita_verisini_yukle(data_dosyasi)
    if not harita_ham:
        for url in (harita_urls or HARITA_URLS):
            harita_ham = harita_verisini_yukle(url)
            if harita_ham:
                harita_kaynagi = url
                break
    log.info(f"Mevcut harita kaydı: {len(harita_ham)}  (kaynak: {harita_kaynagi})")
    harita_kayitlari = _harita_kayitlarini_normallestir(harita_ham, harita_kaynagi)

    # 3. RSS tarama
    log.info("\n── RSS Kaynakları ──")
    rss_haberler = rss_tara(RSS_KAYNAKLARI)

    # 4. Web scraping
    log.info("\n── Web Scraping ──")
    web_haberler = web_tara(WEB_KAYNAKLARI)

    # 5. Birleştir ve tekilleştir
    tum_yeni = rss_haberler + web_haberler
    log.info(f"\nYeni haber adayı: {len(tum_yeni)}")

    for h in tum_yeni:
        if h["id"] not in gorulen_idler:
            # İsteğe bağlı: özet çek
            if ozet_cek_aktif and not h.get("ozet") and h.get("url"):
                h["ozet"] = ozet_cek(h["url"])
                time.sleep(0.5)
            tum_haberler.append(h)
            gorulen_idler.add(h["id"])

    # Eski haberlerle birleştir (en yeni başta)
    birlesik = tum_haberler + eski.get("haberler", [])
    birlesik.sort(
        key=lambda x: x.get("tarih") or "1970-01-01",
        reverse=True
    )
    birlesik = birlesik[:max_haber]

    # 5b. Yeni haberleri haritaya (data.json) otomatik kayıt olarak ekle.
    #     Sadece BU turda yeni görülen haberler denenir (tum_haberler),
    #     geçmiş turlarda zaten işlenmiş olanlar tekrar denenmez.
    eklenen_harita_kayitlari: list[dict] = []
    if haritaya_otomatik_ekle and tum_haberler:
        log.info("\n── Haritaya Otomatik Ekleme ──")
        for h in tum_haberler:
            aday = haberden_harita_kaydi_uret(h)
            if not aday:
                continue  # il tespit edilemedi → güvenli tarafta kal, ekleme
            if kayit_mukerrer_mi(aday, harita_ham):
                continue
            harita_ham.append(aday)
            eklenen_harita_kayitlari.append(aday)
        if eklenen_harita_kayitlari:
            harita_verisini_kaydet(data_dosyasi, harita_ham)
            harita_kayitlari = _harita_kayitlarini_normallestir(harita_ham, data_dosyasi)
            log.info(
                f"  → {len(eklenen_harita_kayitlari)} yeni kayıt {data_dosyasi}'a eklendi "
                f"(toplam artık {len(harita_ham)})"
            )
            for k in eklenen_harita_kayitlari:
                log.info(f"    + [{k['tip']}] {k['ad']}  ({k['il']})")
        else:
            log.info("  → Haritaya eklenecek yeni/uygun kayıt bulunamadı.")

    # 6. Sonucu yaz
    cikti = {
        "meta": {
            "guncelleme": datetime.now(timezone.utc).isoformat(),
            "toplam": len(birlesik),
            "harita_kayit_sayisi": len(harita_kayitlari),
            "haritaya_eklenen_yeni_kayit": len(eklenen_harita_kayitlari),
            "kaynaklar": {
                "rss": len(RSS_KAYNAKLARI),
                "web": len(WEB_KAYNAKLARI),
                "harita_url_sayisi": len(HARITA_URLS),
            },
        },
        "haberler": birlesik,
        "harita_kayitlari": harita_kayitlari,
    }

    Path(cikti_dosyasi).write_text(
        json.dumps(cikti, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log.info("\n" + "═" * 55)
    log.info(f"  Tamamlandı → {cikti_dosyasi}")
    log.info(f"  Toplam haber: {len(birlesik)}")
    log.info(f"  Harita kaydı: {len(harita_kayitlari)}")
    log.info(f"  Haritaya yeni eklenen: {len(eklenen_harita_kayitlari)}  ({data_dosyasi})")
    log.info("═" * 55)
    return cikti


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ekoloji-izleme.com Haber Tarayıcı"
    )
    parser.add_argument(
        "--cikti", default="haberler.json",
        help="Çıktı JSON dosyası (varsayılan: haberler.json)"
    )
    parser.add_argument(
        "--harita-url", action="append", dest="harita_urls",
        help="Harita JSON URL'si (birden fazla kez kullanılabilir)"
    )
    parser.add_argument(
        "--ozet-cek", action="store_true",
        help="Her haber için ayrıca sayfa açıp özet çek (yavaş)"
    )
    parser.add_argument(
        "--surekli", action="store_true",
        help="Her 3 saatte bir döngü hâlinde çalış"
    )
    parser.add_argument(
        "--aralik", type=int, default=180,
        help="--surekli modunda yenileme aralığı (dakika, varsayılan 180)"
    )
    parser.add_argument(
        "--data-dosyasi", default="data.json",
        help="Haritanın veri dosyası — bulunursa buradan okunur ve yeni "
             "kayıtlar buraya yazılır (varsayılan: data.json)"
    )
    parser.add_argument(
        "--haritaya-eklemeyi-kapat", action="store_true",
        help="Yeni haberleri data.json'a otomatik kayıt olarak eklemeyi devre dışı bırak"
    )
    args = parser.parse_args()

    harita_urls = args.harita_urls or HARITA_URLS

    if args.surekli:
        log.info(f"Sürekli mod — her {args.aralik} dakikada bir tarama")
        while True:
            try:
                tara(
                    cikti_dosyasi=args.cikti,
                    harita_urls=harita_urls,
                    ozet_cek_aktif=args.ozet_cek,
                    data_dosyasi=args.data_dosyasi,
                    haritaya_otomatik_ekle=not args.haritaya_eklemeyi_kapat,
                )
            except KeyboardInterrupt:
                log.info("Durduruldu.")
                sys.exit(0)
            except Exception as e:
                log.error(f"Tarama hatası: {e}")
            log.info(f"Bir sonraki tarama {args.aralik} dakika sonra…")
            time.sleep(args.aralik * 60)
    else:
        tara(
            cikti_dosyasi=args.cikti,
            data_dosyasi=args.data_dosyasi,
            haritaya_otomatik_ekle=not args.haritaya_eklemeyi_kapat,
            harita_urls=harita_urls,
            ozet_cek_aktif=args.ozet_cek,
        )


if __name__ == "__main__":
    main()
