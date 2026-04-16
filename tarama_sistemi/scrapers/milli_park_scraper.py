"""
scrapers/milli_park_scraper.py

Kaynak  : https://www.tarimorman.gov.tr/DKMP/Menu/27/Milli-Parklar
          https://cevreonline.com/milli-parklar-listesi/
          Wikipedia — Türkiye'deki millî parklar listesi

Tablo verisi + ilan tarihi + alan (ha) + koordinat bilgisi.
Selenium gerekmez; statik HTML ve basit regex yeterli.
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

BAKANLÍK_URL = "https://www.tarimorman.gov.tr/DKMP/Menu/27/Milli-Parklar"
CEVREONLINE_URL = "https://cevreonline.com/milli-parklar-listesi/"


class MilliParkScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="MilliParklar-DKMP",
            base_url=CEVREONLINE_URL,
            rate_limit_sn=2.5,
        )
        gc = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(gc.geocode, min_delay_seconds=1.1)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")
        features = []

        soup = self._soup(self.base_url)
        # CevreOnline sıralamalı liste içeriyor
        items = soup.select("li, td")
        seen = set()

        for item in items:
            text = item.get_text(" ", strip=True)
            # "Yozgat Çamlığı Milli Parkı (Yozgat) İlan Tarihi: 05.02.1958" formatı
            m = re.match(
                r"^(.+?Milli\s+Park[ıi])\s*\(([^)]+)\)\s+İlan\s+Tarihi:\s*([\d\.]+)",
                text,
                re.IGNORECASE,
            )
            if not m:
                continue

            ad = m.group(1).strip()
            il = m.group(2).strip()
            tarih = m.group(3).strip()

            key = ad
            if key in seen:
                continue
            seen.add(key)

            lat, lon = self._koord(il)
            features.append({
                "ad": ad,
                "il": il,
                "ilan_tarihi": tarih,
                "kategori": "Milli Park",
                "kaynak": BAKANLÍK_URL,
                "lat": lat,
                "lon": lon,
            })

        logger.success(f"[{self.name}] {len(features)} milli park bulundu.")
        return features

    def _koord(self, il_metin: str):
        """İl adından koordinat — birden fazla il varsa ilkini kullan."""
        il = il_metin.split("/")[0].split("-")[0].strip()
        try:
            loc = self._geocode(f"{il}, Türkiye", language="tr")
            if loc:
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode hatası [{il}]: {e}")
        return None, None
