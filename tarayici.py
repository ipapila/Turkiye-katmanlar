
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
    # Harita uygulamanız localStorage ile çalışıyorsa bu URL'leri kendi
    # sunucunuzun JSON export endpoint'iyle değiştirin.
    "https://ekoloji-izleme.com/harita/data.json",
    "https://ekoloji-izleme.com/harita/ihlaller.json",
    "https://ipapila.github.io/Turkiye-katmanlar/data/ihlaller.json",
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
            # Farklı JSON yapılarını dene
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = (
                    data.get("features") or      # GeoJSON
                    data.get("ihlaller") or
                    data.get("data") or
                    data.get("items") or
                    list(data.values())[0] if data else []
                )
            else:
                continue

            for item in items:
                # GeoJSON Feature → düzleştir
                if item.get("type") == "Feature":
                    props = item.get("properties", {})
                    coords = item.get("geometry", {}).get("coordinates", [])
                    item = {**props}
                    if coords and len(coords) >= 2:
                        item["lng"] = coords[0]
                        item["lat"] = coords[1]

                kayit = {
                    "id": item.get("id") or haber_id(url, item.get("baslik", "")),
                    "baslik": item.get("baslik") or item.get("name") or item.get("title", ""),
                    "konum": item.get("konum") or item.get("il") or item.get("location", ""),
                    "kategori": item.get("kategori") or item.get("alan_turu") or item.get("type", ""),
                    "siddet": item.get("siddet") or item.get("durum") or "takipte",
                    "tarih": tarih_normalize(item.get("tarih") or item.get("date")),
                    "url": item.get("url") or item.get("kaynak_url") or "",
                    "ozet": item.get("aciklama") or item.get("ozet") or item.get("description", ""),
                    "lat": item.get("lat") or item.get("enlem"),
                    "lng": item.get("lng") or item.get("boylam"),
                    "kaynak": "harita",
                    "kaynak_url": url,
                }
                if kayit["baslik"]:
                    kayitlar.append(kayit)
            log.info(f"  → {len(items)} kayıt okundu")
        except Exception as e:
            log.warning(f"  JSON parse hatası: {e}")

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

    # 2. Harita verisi (birincil kaynak)
    log.info("\n── Harita Verisi ──")
    harita_kayitlari = harita_verisi_cek(harita_urls or HARITA_URLS)
    log.info(f"Toplam harita kaydı: {len(harita_kayitlari)}")

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

    # 6. Sonucu yaz
    cikti = {
        "meta": {
            "guncelleme": datetime.now(timezone.utc).isoformat(),
            "toplam": len(birlesik),
            "harita_kayit_sayisi": len(harita_kayitlari),
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
            harita_urls=harita_urls,
            ozet_cek_aktif=args.ozet_cek,
        )


if __name__ == "__main__":
    main()
