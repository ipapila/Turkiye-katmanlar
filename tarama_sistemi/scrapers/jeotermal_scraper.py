"""
scrapers/jeotermal_scraper.py

Kaynak : https://www.enerjiatlasi.com/jeotermal/
Hedef  : Türkiye'deki tüm işletmedeki / lisanslı JES'lerin listesi,
         kurulu güç (MW), il, firma, teknoloji bilgileriyle birlikte.

Koordinatlar Nominatim (OpenStreetMap) geocoder ile çözümlenir;
önceki çalıştırmadan cache dosyasından okunur (gereksiz istek yapmaz).
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

    # ── Cache yönetimi ──────────────────────────────────────────────────────
    def _load_cache(self) -> dict:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
        return {}

    def _save_cache(self):
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(self._geo_cache, ensure_ascii=False, indent=2))

    def _koordinat(self, il: str, ilce: str = "") -> tuple[Optional[float], Optional[float]]:
        """İl/ilçe → (lat, lon) — önce cache, sonra Nominatim."""
        key = f"{il}|{ilce}"
        if key in self._geo_cache:
            return tuple(self._geo_cache[key])

        sorgu = f"{ilce}, {il}, Türkiye" if ilce else f"{il}, Türkiye"
        try:
            loc = self._geocode(sorgu, language="tr")
            if loc:
                coords = [loc.latitude, loc.longitude]
                self._geo_cache[key] = coords
                self._save_cache()
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode hatası [{sorgu}]: {e}")
        return None, None

    # ── Ana tarama mantığı ──────────────────────────────────────────────────
    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")
        soup = self._soup(self.base_url)
        features = []

        # Tüm JES tablolarını işle (işletmedeki, inşaat, lisanslı vb.)
        for tablo in soup.select("table"):
            satirlar = tablo.select("tr")
            for satir in satirlar[1:]:  # başlık satırını atla
                hücreler = [td.get_text(strip=True) for td in satir.select("td")]
                if len(hücreler) < 4:
                    continue

                # Tablo yapısı: Sıra | Ad | İl | Firma | Kurulu Güç
                ad_link = satir.select_one("td:nth-child(2) a")
                ad = ad_link.get_text(strip=True) if ad_link else hücreler[1]
                detail_url = BASE + ad_link["href"] if ad_link and ad_link.get("href") else None

                il_raw = hücreler[2] if len(hücreler) > 2 else ""
                firma = hücreler[3] if len(hücreler) > 3 else ""
                guc_raw = hücreler[4] if len(hücreler) > 4 else ""

                # Güç: "165 MW" → 165.0
                guc_mw = self._guc_parse(guc_raw)
                il = il_raw.strip()

                # Durum: hangi tablodayız?
                durum = self._tablo_durumu(tablo)

                lat, lon = self._koordinat(il)

                features.append({
                    "ad": ad,
                    "il": il,
                    "firma": firma,
                    "kurulu_guc_mw": guc_mw,
                    "durum": durum,
                    "kaynak_url": detail_url,
                    "kategori": "JES",
                    "lat": lat,
                    "lon": lon,
                })

        logger.success(f"[{self.name}] {len(features)} santral bulundu.")
        return features

    @staticmethod
    def _guc_parse(metin: str) -> Optional[float]:
        m = re.search(r"[\d,\.]+", metin.replace(",", "."))
        try:
            return float(m.group()) if m else None
        except ValueError:
            return None

    @staticmethod
    def _tablo_durumu(tablo) -> str:
        """Tablonun üstündeki başlık h2/h3'ten durum bilgisi çıkar."""
        prev = tablo.find_previous(["h2", "h3", "h4"])
        if prev:
            t = prev.get_text(strip=True).lower()
            if "yapım" in t or "inşaat" in t:
                return "İnşaat Halinde"
            if "lisans" in t:
                return "Lisanslı"
            if "ön lisans" in t:
                return "Ön Lisans"
        return "İşletmede"
