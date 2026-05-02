#!/usr/bin/env python3
"""
Türkiye Ekoloji Haritası — Otomatik Günlük Tarama
Kaynaklar: Resmî Gazete, Cumhuriyet, BirGün, Bianet, Ekoloji Birliği
Çıktı: data/tarama_YYYY-MM-DD.json + data/son_tarama.json
"""

import json, re, time, hashlib, random, string
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import feedparser

# ─── Yapılandırma ────────────────────────────────────────────────────────────

BUGUN = date.today().isoformat()
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (TurkiyeEkolojiHaritasi/1.0)"}

# Anahtar kelimeler → kategori eşlemesi
KELIMELER = {
    "Maden Ocağı":        ["maden ruhsat", "maden işletme", "altın maden", "gümüş maden",
                            "bakır maden", "linyit", "kömür ocağı", "taş ocağı", "kireç taşı",
                            "MAPEG", "maden arama ruhsatı", "maden işletme ruhsatı"],
    "Taş-Mermer Ocağı":   ["mermer ocağı", "granit ocağı", "kum ocağı", "agrega ocağı",
                            "taşocağı", "kil ocağı", "kuvars ocağı"],
    "Rüzgar Santrali":    ["rüzgar enerji santrali", "RES ", "rüzgar türbini",
                            "enerji santrali lisansı", "rüzgar santrali"],
    "Güneş Santrali":     ["güneş enerji santrali", "GES ", "fotovoltaik",
                            "güneş paneli santrali"],
    "Hidroelektrik":      ["hidroelektrik", "HES ", "baraj inşaat", "regülatör"],
    "Jeotermal":          ["jeotermal", "jeotermal kaynak", "jeotermal enerji"],
    "Termik Santral":     ["termik santral", "ısı merkezi", "doğalgaz santrali",
                            "kömür termik"],
    "Kıyı İhlalleri":     ["kıyı yapılaşma", "deniz dolgu", "marina", "yat limanı",
                            "iskele inşaat", "kıyı koruma", "özel çevre koruma",
                            "sit alanı imar", "kıyı kenar çizgisi"],
    "Ekolojik İhlal":     ["orman yangını", "yasadışı kesim", "kaçak kesim",
                            "ağaç kesiimi", "orman tahribat", "erozyon"],
    "ÇED":                ["ÇED olumlu", "ÇED olumsuz", "ÇED muafiyeti",
                            "çevresel etki değerlendirmesi", "ÇED kararı"],
    "Acele Kamulaştırma": ["acele kamulaştırma", "2942 sayılı", "acele el koyma"],
    "Nükleer":            ["nükleer", "Akkuyu", "reaktör"],
    "Sulak Alan":         ["sulak alan", "Ramsar", "tabiatı koruma alanı", "bataklık"],
}

# RSS feed'leri
RSS_FEEDS = [
    ("Cumhuriyet Çevre",   "https://www.cumhuriyet.com.tr/rss/cevre.xml"),
    ("BirGün",             "https://www.birgun.net/rss"),
    ("Bianet",             "https://bianet.org/biamag/feed.rss"),
    ("Ekoloji Birliği",    "https://ekolojibirligi.org/feed/"),
    ("Greenpeace TR",      "https://www.greenpeace.org/turkey/feed/"),
]

# İl → koordinat merkezi (yaklaşık)
IL_KOORD = {
    "Adana":(37.0000,35.3213),"Adıyaman":(37.7648,38.2786),"Afyonkarahisar":(38.7507,30.5567),
    "Ağrı":(39.7191,43.0503),"Amasya":(40.6499,35.8353),"Ankara":(39.9208,32.8541),
    "Antalya":(36.8969,30.7133),"Artvin":(41.1828,41.8183),"Aydın":(37.8560,27.8416),
    "Balıkesir":(39.6484,27.8826),"Bilecik":(40.1506,29.9792),"Bingöl":(38.8855,40.4983),
    "Bitlis":(38.4006,42.1076),"Bolu":(40.7360,31.6069),"Burdur":(37.7265,30.2908),
    "Bursa":(40.1826,29.0665),"Çanakkale":(40.1553,26.4142),"Çankırı":(40.6013,33.6134),
    "Çorum":(40.5506,34.9556),"Denizli":(37.7765,29.0864),"Diyarbakır":(37.9144,40.2306),
    "Edirne":(41.6818,26.5623),"Elazığ":(38.6810,39.2264),"Erzincan":(39.7500,39.5000),
    "Erzurum":(39.9055,41.2658),"Eskişehir":(39.7767,30.5206),"Gaziantep":(37.0662,37.3833),
    "Giresun":(40.9128,38.3895),"Gümüşhane":(40.4386,39.4814),"Hakkari":(37.5744,43.7408),
    "Hatay":(36.4018,36.3498),"Isparta":(37.7648,30.5566),"İçel":(36.8000,34.6333),
    "İstanbul":(41.0082,28.9784),"İzmir":(38.4189,27.1287),"Kars":(40.6013,43.0975),
    "Kastamonu":(41.3887,33.7827),"Kayseri":(38.7312,35.4787),"Kırklareli":(41.7333,27.2167),
    "Kırşehir":(39.1458,34.1614),"Kocaeli":(40.8533,29.8815),"Konya":(37.8667,32.4833),
    "Kütahya":(39.4167,29.9833),"Malatya":(38.3552,38.3095),"Manisa":(38.6191,27.4289),
    "Kahramanmaraş":(37.5858,36.9371),"Mardin":(37.3212,40.7245),"Muğla":(37.2153,28.3636),
    "Muş":(38.9462,41.7539),"Nevşehir":(38.6939,34.6857),"Niğde":(37.9667,34.6833),
    "Ordu":(40.9862,37.8797),"Rize":(41.0201,40.5234),"Sakarya":(40.6940,30.4358),
    "Samsun":(41.2867,36.3300),"Siirt":(37.9333,41.9500),"Sinop":(42.0231,35.1531),
    "Sivas":(39.7477,37.0179),"Tekirdağ":(40.9833,27.5167),"Tokat":(40.3167,36.5500),
    "Trabzon":(41.0015,39.7178),"Tunceli":(39.1079,39.5480),"Şanlıurfa":(37.1591,38.7969),
    "Uşak":(38.6823,29.4082),"Van":(38.4891,43.4089),"Yozgat":(39.8181,34.8147),
    "Zonguldak":(41.4564,31.7987),"Aksaray":(38.3687,34.0370),"Bayburt":(40.2552,40.2249),
    "Karaman":(37.1759,33.2287),"Kırıkkale":(39.8468,33.5153),"Batman":(37.8812,41.1351),
    "Şırnak":(37.5164,42.4611),"Bartın":(41.6344,32.3375),"Ardahan":(41.1105,42.7022),
    "Iğdır":(39.9167,44.0333),"Yalova":(40.6500,29.2667),"Karabük":(41.2061,32.6204),
    "Kilis":(36.7184,37.1212),"Osmaniye":(37.0742,36.2464),"Düzce":(40.8438,31.1565),
}

def uid(text: str) -> str:
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"auto_{h}_{date.today().strftime('%Y%m%d')}"

def kategori_bul(metin: str) -> str:
    metin_lower = metin.lower()
    for kat, kelimeler in KELIMELER.items():
        for k in kelimeler:
            if k.lower() in metin_lower:
                return kat
    return "Ekolojik İhlal"

def il_bul(metin: str) -> tuple[str, tuple]:
    for il, koord in IL_KOORD.items():
        if il.lower() in metin.lower():
            return il, koord
    return "", (39.0, 35.0)  # Türkiye merkezi varsayılan

def koord_jitter(lat, lng):
    return round(lat + random.uniform(-0.05, 0.05), 5), \
           round(lng + random.uniform(-0.05, 0.05), 5)

def kayit_olustur(baslik, aciklama, url, kaynak_adi, eklenme=None):
    tam_metin = f"{baslik} {aciklama}"
    kat = kategori_bul(tam_metin)
    il, (lat, lng) = il_bul(tam_metin)
    lat, lng = koord_jitter(lat, lng)
    return {
        "id": uid(url or baslik),
        "tip": kat,
        "ad": baslik[:120],
        "il": il,
        "ilce": "",
        "koordinatlar": {"lat": lat, "lng": lng},
        "alan_ha": 0,
        "durum": "Aktif",
        "belge_no": "",
        "eklenme": eklenme or BUGUN,
        "kaynak": kaynak_adi,
        "kaynak_link": url or "",
        "aciklama": aciklama[:500],
        "alt_kategori": "",
        "sabit": False,
        "_auto": True,
        "_tarih": BUGUN,
    }

def rss_tara(feed_url: str, kaynak_adi: str) -> list:
    print(f"  RSS: {kaynak_adi}")
    bulunanlar = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:30]:
            baslik = entry.get("title", "")
            ozet   = entry.get("summary", "")
            url    = entry.get("link", "")
            tam    = f"{baslik} {ozet}"
            ilgili = any(
                k.lower() in tam.lower()
                for kelimeler in KELIMELER.values()
                for k in kelimeler
            )
            if ilgili:
                bulunanlar.append(kayit_olustur(baslik, ozet, url, kaynak_adi))
                print(f"    ✓ {baslik[:60]}")
    except Exception as e:
        print(f"    ✗ Hata: {e}")
    return bulunanlar

def resmi_gazete_tara() -> list:
    """Bugünkü Resmî Gazete'yi tara."""
    print("  Resmî Gazete taranıyor...")
    url = f"https://www.resmigazete.gov.tr/eskiler/{BUGUN[:4]}/{BUGUN[5:7]}/{BUGUN.replace('-','')}.htm"
    bulunanlar = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    ✗ HTTP {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        linkler = soup.find_all("a")
        for a in linkler:
            baslik = a.get_text(strip=True)
            href   = a.get("href", "")
            if len(baslik) < 10:
                continue
            ilgili = any(
                k.lower() in baslik.lower()
                for kelimeler in KELIMELER.values()
                for k in kelimeler
            )
            if ilgili:
                tam_url = f"https://www.resmigazete.gov.tr{href}" if href.startswith("/") else href
                bulunanlar.append(kayit_olustur(baslik, f"Resmî Gazete kararı: {baslik}", tam_url, "Resmî Gazete"))
                print(f"    ✓ {baslik[:60]}")
    except Exception as e:
        print(f"    ✗ Hata: {e}")
    return bulunanlar

def bianet_ara() -> list:
    """Bianet'te çevre haberleri ara."""
    print("  Bianet çevre haberleri...")
    bulunanlar = []
    try:
        r = requests.get("https://bianet.org/bianet/cevre", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        haberler = soup.select("h3 a, h2 a")[:20]
        for a in haberler:
            baslik = a.get_text(strip=True)
            href   = a.get("href", "")
            url    = f"https://bianet.org{href}" if href.startswith("/") else href
            ilgili = any(
                k.lower() in baslik.lower()
                for kelimeler in KELIMELER.values()
                for k in kelimeler
            )
            if ilgili:
                bulunanlar.append(kayit_olustur(baslik, baslik, url, "Bianet"))
                print(f"    ✓ {baslik[:60]}")
    except Exception as e:
        print(f"    ✗ Hata: {e}")
    return bulunanlar

def mevcut_id_ler() -> set:
    """Daha önce eklenen ID'leri topla (tekrar eklemeyi önler)."""
    ids = set()
    for dosya in DATA_DIR.glob("tarama_*.json"):
        try:
            with open(dosya, encoding="utf-8") as f:
                for r in json.load(f):
                    ids.add(r.get("id", ""))
        except:
            pass
    return ids

# ─── ANA AKIŞ ────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"🌿 Türkiye Ekoloji Taraması — {BUGUN}")
    print(f"{'='*60}\n")

    mevcut = mevcut_id_ler()
    tum_kayitlar = []

    # Resmî Gazete
    tum_kayitlar += resmi_gazete_tara()
    time.sleep(2)

    # RSS feed'leri
    for kaynak_adi, feed_url in RSS_FEEDS:
        tum_kayitlar += rss_tara(feed_url, kaynak_adi)
        time.sleep(1)

    # Bianet web scrape
    tum_kayitlar += bianet_ara()

    # Tekrar önleme
    yeni = [r for r in tum_kayitlar if r["id"] not in mevcut]

    print(f"\n{'─'*40}")
    print(f"Toplam bulunan : {len(tum_kayitlar)}")
    print(f"Yeni kayıt     : {len(yeni)}")

    if not yeni:
        print("Yeni kayıt yok, dosya yazılmıyor.")
        return

    # Günlük dosya
    cikti = DATA_DIR / f"tarama_{BUGUN}.json"
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, indent=2)
    print(f"Yazıldı → {cikti}")

    # son_tarama.json (haritaya yükleme için)
    son = DATA_DIR / "son_tarama.json"
    with open(son, "w", encoding="utf-8") as f:
        json.dump(yeni, f, ensure_ascii=False, indent=2)
    print(f"Yazıldı → {son}")

    # Özet
    from collections import Counter
    cats = Counter(r["tip"] for r in yeni)
    print("\nKategori dağılımı:")
    for c, n in cats.items():
        print(f"  {c}: {n}")

if __name__ == "__main__":
    main()
