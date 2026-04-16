"""
scrapers/jeotermal_scraper.py

Kaynak : https://www.enerjiatlasi.com/jeotermal/
Hedef  : Türkiye'deki tüm işletmedeki / lisanslı JES'lerin listesi.
Mimari : Ramsar/MilliPark ile aynı — canlı site erişilebilirse parse eder,
         403/timeout alırsa seed verisiyle devam eder.
"""

import re
import json
import time
from pathlib import Path
from typing import Optional
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

CACHE_FILE = Path("data/geocode_cache.json")
BASE = "https://www.enerjiatlasi.com"

# Araştırmayla derlenmiş JES seed verisi — site erişilemezse fallback
JES_SEED = [
    {"ad":"Germencik-Ömerbeyli JES",    "il":"Aydın",         "kurulu_guc_mw":232.0, "durum":"İşletmede", "firma":"Güriş/Zorlu",      "lat":37.8833,"lon":28.0167},
    {"ad":"Kızıldere JES",              "il":"Denizli",       "kurulu_guc_mw":165.0, "durum":"İşletmede", "firma":"Zorlu Enerji",      "lat":37.9333,"lon":28.8833},
    {"ad":"Alaşehir Efeler JES",        "il":"Manisa",        "kurulu_guc_mw":165.0, "durum":"İşletmede", "firma":"Güriş",             "lat":38.3500,"lon":28.5167},
    {"ad":"Gölemezli JES",              "il":"Denizli",       "kurulu_guc_mw":47.4,  "durum":"İşletmede", "firma":"Çelikler",          "lat":37.9000,"lon":29.0833},
    {"ad":"Salihli JES",                "il":"Manisa",        "kurulu_guc_mw":62.0,  "durum":"İşletmede", "firma":"BM Elektrik",       "lat":38.4833,"lon":28.1167},
    {"ad":"Tuzla JES",                  "il":"Çanakkale",     "kurulu_guc_mw":7.5,   "durum":"İşletmede", "firma":"Tuzla Jeotermal",   "lat":39.7167,"lon":26.3333},
    {"ad":"Seferihisar JES",            "il":"İzmir",         "kurulu_guc_mw":7.5,   "durum":"İşletmede", "firma":"Greeneco",          "lat":38.1000,"lon":26.8333},
    {"ad":"Afyon Ömer-Gecek JES",       "il":"Afyonkarahisar","kurulu_guc_mw":55.0,  "durum":"İşletmede", "firma":"Afyon JES",         "lat":38.5500,"lon":30.6167},
    {"ad":"Pamukkale JES",              "il":"Denizli",       "kurulu_guc_mw":20.4,  "durum":"İşletmede", "firma":"Zorlu Enerji",      "lat":37.9167,"lon":29.1167},
    {"ad":"Buharkent JES",              "il":"Aydın",         "kurulu_guc_mw":55.0,  "durum":"İşletmede", "firma":"Menderes JES",      "lat":37.9667,"lon":28.7000},
    {"ad":"Sultanhisar JES",            "il":"Aydın",         "kurulu_guc_mw":24.0,  "durum":"İşletmede", "firma":"Bereket Enerji",    "lat":37.8833,"lon":28.1667},
    {"ad":"Dinar JES",                  "il":"Afyonkarahisar","kurulu_guc_mw":6.8,   "durum":"İşletmede", "firma":"Batı Anadolu JES",  "lat":38.0600,"lon":30.1700},
    {"ad":"Kuyucak JES",                "il":"Aydın",         "kurulu_guc_mw":30.0,  "durum":"İşletmede", "firma":"Zorlu Enerji",      "lat":37.9000,"lon":28.4833},
    {"ad":"Pamukören JES",              "il":"Aydın",         "kurulu_guc_mw":45.0,  "durum":"İşletmede", "firma":"Zorlu Enerji",      "lat":37.8500,"lon":28.0833},
    {"ad":"Hidayet JES",                "il":"Aydın",         "kurulu_guc_mw":24.0,  "durum":"İşletmede", "firma":"Güriş",             "lat":37.9167,"lon":28.1500},
    {"ad":"İzmir Doğanbey JES",         "il":"İzmir",         "kurulu_guc_mw":9.5,   "durum":"İşletmede", "firma":"Pilot Enerji",      "lat":37.8500,"lon":27.1833},
    {"ad":"Tekke JES",                  "il":"Denizli",       "kurulu_guc_mw":33.0,  "durum":"İşletmede", "firma":"Zorlu Enerji",      "lat":37.9000,"lon":28.9500},
    {"ad":"Salavatlı JES",              "il":"Aydın",         "kurulu_guc_mw":7.9,   "durum":"İşletmede", "firma":"Tüprag Enerji",     "lat":37.9333,"lon":28.2333},
    {"ad":"Çallı JES",                  "il":"Manisa",        "kurulu_guc_mw":15.0,  "durum":"İşletmede", "firma":"BM Elektrik",       "lat":38.4167,"lon":28.0833},
    {"ad":"Ihlara JES",                 "il":"Aksaray",       "kurulu_guc_mw":16.0,  "durum":"İşletmede", "firma":"Kalyon Enerji",     "lat":38.2833,"lon":34.2167},
]


class JeotermalScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="EnerjiAtlasi-JES",
            base_url=f"{BASE}/jeotermal/",
            rate_limit_sn=3.0,
        )
        self._geocoder = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(self._geocoder.geocode, min_delay_seconds=1.1)
        self._geo_cache = self._load_cache()

    def _load_cache(self) -> dict:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
        return {}

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(self._geo_cache, ensure_ascii=False, indent=2))

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")

        # Önce canlı siteden dene
        canli = self._canli_scrape()
        if canli:
            logger.success(f"[{self.name}] Canlı siteden {len(canli)} JES alındı.")
            return canli

        # Canlı site erişilemezse seed kullan
        logger.warning(f"[{self.name}] Canlı site erişilemedi — seed verisi kullanılıyor.")
        features = []
        for s in JES_SEED:
            s["kategori"] = "JES"
            features.append(s)
        logger.success(f"[{self.name}] Seed'den {len(features)} JES hazır.")
        return features

    def _canli_scrape(self) -> list[dict]:
        """enerjiatlasi.com'dan canlı JES listesini çeker."""
        try:
            soup = self._soup(self.base_url)
            features = []
            for tablo in soup.select("table"):
                satirlar = tablo.select("tr")
                for satir in satirlar[1:]:
                    hücreler = [td.get_text(strip=True) for td in satir.select("td")]
                    if len(hücreler) < 4:
                        continue
                    ad_link = satir.select_one("td:nth-child(2) a")
                    ad = ad_link.get_text(strip=True) if ad_link else hücreler[1]
                    il = hücreler[2].strip() if len(hücreler) > 2 else ""
                    firma = hücreler[3].strip() if len(hücreler) > 3 else ""
                    guc_raw = hücreler[4] if len(hücreler) > 4 else ""
                    guc_mw = self._guc_parse(guc_raw)
                    durum = self._tablo_durumu(tablo)
                    lat, lon = self._koordinat(il)
                    features.append({
                        "ad": ad, "il": il, "firma": firma,
                        "kurulu_guc_mw": guc_mw, "durum": durum,
                        "kategori": "JES", "lat": lat, "lon": lon,
                    })
            return features
        except Exception as e:
            logger.warning(f"[{self.name}] Canlı scrape hatası: {e}")
            return []

    def _koordinat(self, il: str) -> tuple:
        key = il
        if key in self._geo_cache:
            return tuple(self._geo_cache[key])
        try:
            loc = self._geocode(f"{il}, Türkiye", language="tr")
            if loc:
                self._geo_cache[key] = [loc.latitude, loc.longitude]
                self._save_cache()
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode [{il}]: {e}")
        return None, None

    @staticmethod
    def _guc_parse(metin: str) -> Optional[float]:
        m = re.search(r"[\d,\.]+", metin.replace(",", "."))
        try:
            return float(m.group()) if m else None
        except ValueError:
            return None

    @staticmethod
    def _tablo_durumu(tablo) -> str:
        prev = tablo.find_previous(["h2", "h3", "h4"])
        if prev:
            t = prev.get_text(strip=True).lower()
            if "yapım" in t or "inşaat" in t:
                return "İnşaat Halinde"
            if "ön lisans" in t:
                return "Ön Lisans"
            if "lisans" in t:
                return "Lisanslı"
        return "İşletmede"
