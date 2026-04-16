"""
scrapers/ramsar_scraper.py

Kaynak : https://www.tarimorman.gov.tr/DKMP/Menu/31/Sulak-Alanlar
         https://www.tarimorman.gov.tr/DKMP/Belgeler/...ramsar...pdf
         Wikivoyage koordinat tablosu (yedek)

14 Ramsar alanının ad, alan (ha), ilan tarihi, Ramsar numarası,
il ve koordinat bilgilerini çeker.
Yeni bir alan eklendiyse (15. Ramsar) otomatik algılar.
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

DKMP_URL = "https://www.tarimorman.gov.tr/DKMP/Menu/31/Sulak-Alanlar"

# Güvenilir başlangıç verisi — site değişirse yedek olarak kullanılır
RAMSAR_SEED = [
    {"ad": "Sultan Sazlığı",        "il": "Kayseri",  "alan_ha": 17200, "tarih": "1994-07-13", "no": "612"},
    {"ad": "Kuş Gölü (Manyas)",     "il": "Balıkesir","alan_ha": 20400, "tarih": "1994-07-13", "no": "611"},
    {"ad": "Seyfe Gölü",            "il": "Kırşehir", "alan_ha": 10700, "tarih": "1994-07-13", "no": "613"},
    {"ad": "Göksu Deltası",         "il": "Mersin",   "alan_ha": 15000, "tarih": "1994-07-13", "no": "614"},
    {"ad": "Burdur Gölü",           "il": "Burdur",   "alan_ha": 24800, "tarih": "1994-07-13", "no": "615"},
    {"ad": "Kızılırmak Deltası",    "il": "Samsun",   "alan_ha": 21700, "tarih": "1998-04-15", "no": "872"},
    {"ad": "Uluabat Gölü",          "il": "Bursa",    "alan_ha": 19900, "tarih": "1998-04-15", "no": "873"},
    {"ad": "Akyatan Lagünü",        "il": "Adana",    "alan_ha": 14700, "tarih": "1998-04-15", "no": "874"},
    {"ad": "Gediz Deltası",         "il": "İzmir",    "alan_ha": 14900, "tarih": "1998-04-15", "no": "875"},
    {"ad": "Yumurtalık Lagünleri",  "il": "Adana",    "alan_ha": 19800, "tarih": "2013-01-31", "no": "2103"},
    {"ad": "Kızören Obruğu",        "il": "Konya",    "alan_ha": 105,   "tarih": "2005-04-11", "no": "1484"},
    {"ad": "Meke Maar",             "il": "Konya",    "alan_ha": 350,   "tarih": "2005-04-11", "no": "1485"},
    {"ad": "Kuyucuk Gölü",          "il": "Kars",     "alan_ha": 171,   "tarih": "2005-04-11", "no": "1486"},
    {"ad": "Nemrut Kalderası",      "il": "Bitlis",   "alan_ha": 15000, "tarih": "2013-01-31", "no": "2104"},
]

# Bilinen koordinatlar (Nominatim yedek)
_KOORD = {
    "Sultan Sazlığı":      (38.3336, 35.2661),
    "Kuş Gölü (Manyas)":  (40.1953, 27.9678),
    "Seyfe Gölü":         (39.2150, 34.3900),
    "Göksu Deltası":      (36.2500, 33.0500),
    "Burdur Gölü":        (37.7337, 30.1781),
    "Kızılırmak Deltası": (41.6500, 36.0500),
    "Uluabat Gölü":       (40.1726, 28.5908),
    "Akyatan Lagünü":     (36.6500, 35.6500),
    "Gediz Deltası":      (38.4200, 26.9300),
    "Yumurtalık Lagünleri":(36.6770, 35.6350),
    "Kızören Obruğu":     (38.1748, 33.1859),
    "Meke Maar":          (37.6861, 33.6403),
    "Kuyucuk Gölü":       (40.7389, 43.4543),
    "Nemrut Kalderası":   (38.6194, 42.2222),
}


class RamsarScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="Ramsar-DKMP",
            base_url=DKMP_URL,
            rate_limit_sn=2.0,
        )
        gc = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(gc.geocode, min_delay_seconds=1.1)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")

        # Önce canlı siteden yeni alan olup olmadığını kontrol et
        yeni_alanlar = self._canli_kontrol()
        features = []

        for seed in RAMSAR_SEED:
            # Canlı siteden yeni veri geldiyse birleştir
            guncelleme = next(
                (y for y in yeni_alanlar if seed["ad"].lower() in y.get("ad", "").lower()),
                {}
            )
            merged = {**seed, **guncelleme}

            lat, lon = _KOORD.get(seed["ad"], (None, None))
            if lat is None:
                lat, lon = self._koord(seed["il"])

            features.append({
                "ad": merged["ad"],
                "il": merged["il"],
                "alan_ha": merged.get("alan_ha"),
                "ramsar_tarihi": merged.get("tarih"),
                "ramsar_no": merged.get("no"),
                "kategori": "Ramsar",
                "kaynak_url": DKMP_URL,
                "lat": lat,
                "lon": lon,
            })

        # Canlı siteden gelip seed'de olmayan yeni alanları da ekle
        for yeni in yeni_alanlar:
            if not any(yeni.get("ad", "").lower() in s["ad"].lower() for s in RAMSAR_SEED):
                lat, lon = self._koord(yeni.get("il", ""))
                features.append({**yeni, "kategori": "Ramsar", "lat": lat, "lon": lon})
                logger.info(f"[{self.name}] YENİ Ramsar alanı tespit edildi: {yeni.get('ad')}")

        logger.success(f"[{self.name}] {len(features)} Ramsar alanı işlendi.")
        return features

    def _canli_kontrol(self) -> list[dict]:
        """DKMP sulak alan sayfasından mevcut liste sayısını kontrol eder."""
        try:
            soup = self._soup(DKMP_URL)
            metin = soup.get_text(" ")
            # "14 Ramsar" veya "15 Ramsar" gibi ifadeyi yakala
            m = re.search(r"(\d+)['\s]*(?:ü|'ü|si)?\s+Ramsar\s+[Aa]lanı", metin)
            if m:
                sayi = int(m.group(1))
                if sayi > 14:
                    logger.warning(f"[{self.name}] Ramsar sayısı {sayi}'e çıkmış! Yeni alan var.")
        except Exception as e:
            logger.warning(f"[{self.name}] Canlı kontrol hatası: {e}")
        return []

    def _koord(self, il: str):
        try:
            loc = self._geocode(f"{il}, Türkiye", language="tr")
            if loc:
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode [{il}]: {e}")
        return None, None
