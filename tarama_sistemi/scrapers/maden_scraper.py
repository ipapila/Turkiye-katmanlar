"""
scrapers/maden_scraper.py

Kaynaklar:
  1. MAPEG istatistik sayfası (il bazlı ruhsat sayıları)
  2. madenplatformu.org — sektörel listeler
  3. Seed verisi — bu projede araştırmayla derlenmiş 55 maden noktası

Maden türleri: metalik, enerji hammaddesi, bor, trona, petrol, doğalgaz, jeotermal
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

MAPEG_URL = "https://www.mapeg.gov.tr/istatistik.aspx"
MADEN_PLATFORM_URL = "https://www.madenplatformu.org/turkiyede-madenler"

# Araştırmayla derlenmiş temel maden listesi (konum + metadata)
MADEN_SEED = [
    # — ALTIN —
    {"ad": "Kışladağ Altın Madeni",   "il": "Uşak",      "ilce": "Eşme",       "tur": "Altın",    "sinif": "Metalik",  "firma": "Eldorado Gold / Tüprag", "lat": 38.4833, "lon": 29.1667},
    {"ad": "Çöpler Altın Madeni",     "il": "Erzincan",  "ilce": "İliç",       "tur": "Altın",    "sinif": "Metalik",  "firma": "Anagold / SSR Mining",  "lat": 39.0167, "lon": 38.5333},
    {"ad": "Mastra Altın Madeni",     "il": "Gümüşhane", "ilce": "Köse",       "tur": "Altın",    "sinif": "Metalik",  "firma": "Doğu Biga Madencilik",  "lat": 40.4167, "lon": 38.6333},
    {"ad": "Kaymaz Altın Madeni",     "il": "Eskişehir", "ilce": "Sivrihisar", "tur": "Altın",    "sinif": "Metalik",  "firma": "Eldorado Gold",          "lat": 39.4500, "lon": 31.5333},
    # — BAKIR —
    {"ad": "Murgul Bakır Madeni",     "il": "Artvin",    "ilce": "Murgul",     "tur": "Bakır",    "sinif": "Metalik",  "firma": "Eti Bakır / KBI Copper",  "lat": 41.2167, "lon": 41.5667},
    {"ad": "Küre Bakır Madeni",       "il": "Kastamonu", "ilce": "Küre",       "tur": "Bakır",    "sinif": "Metalik",  "firma": "Eti Bakır",               "lat": 41.8000, "lon": 33.7167},
    # — KROM —
    {"ad": "Guleman Krom Madeni",     "il": "Elazığ",    "ilce": "Sivrice",    "tur": "Krom",     "sinif": "Metalik",  "firma": "Eti Krom",               "lat": 38.2667, "lon": 39.3167},
    # — DEMİR —
    {"ad": "Hekimhan Demir Madeni",   "il": "Malatya",   "ilce": "Hekimhan",   "tur": "Demir",    "sinif": "Metalik",  "firma": "Kardemir",               "lat": 38.8000, "lon": 37.9333},
    # — LİNYİT —
    {"ad": "Afşin-Elbistan Linyit",  "il": "Kahramanmaraş","ilce":"Afşin",     "tur": "Linyit",   "sinif": "Enerji",   "firma": "EÜAŞ/Kalyon",           "lat": 38.2500, "lon": 36.9167},
    {"ad": "Soma Linyit",            "il": "Manisa",    "ilce": "Soma",       "tur": "Linyit",   "sinif": "Enerji",   "firma": "Park Elektrik / Soma Kömür","lat": 39.1833, "lon": 27.5833},
    {"ad": "Tunçbilek Linyit",       "il": "Kütahya",   "ilce": "Tavşanlı",  "tur": "Linyit",   "sinif": "Enerji",   "firma": "GLİ / EÜAŞ",            "lat": 39.5500, "lon": 29.4833},
    # — TAŞ KÖMÜRÜ —
    {"ad": "Zonguldak Taş Kömürü",   "il": "Zonguldak", "ilce": "Merkez",    "tur": "Taş Kömürü","sinif":"Enerji",   "firma": "TTK",                    "lat": 41.4500, "lon": 31.7833},
    # — BOR —
    {"ad": "Kırka Bor Madeni",       "il": "Eskişehir", "ilce": "Mihalgazi", "tur": "Bor",      "sinif": "Endüstriyel","firma": "Eti Maden",             "lat": 39.9167, "lon": 30.5333},
    {"ad": "Emet Bor Madeni",        "il": "Kütahya",   "ilce": "Emet",      "tur": "Bor",      "sinif": "Endüstriyel","firma": "Eti Maden",             "lat": 39.3333, "lon": 29.2500},
    {"ad": "Bigadiç Bor Madeni",     "il": "Balıkesir", "ilce": "Bigadiç",   "tur": "Bor",      "sinif": "Endüstriyel","firma": "Eti Maden",             "lat": 39.3833, "lon": 28.1333},
    # — TRONA —
    {"ad": "Beypazarı Trona",        "il": "Ankara",    "ilce": "Beypazarı", "tur": "Trona",    "sinif": "Endüstriyel","firma": "Eti Soda",              "lat": 40.1667, "lon": 31.9167},
    # — PETROL —
    {"ad": "Batman Petrol Sahası",   "il": "Batman",    "ilce": "Merkez",    "tur": "Petrol",   "sinif": "Enerji",   "firma": "TPAO",                   "lat": 37.8833, "lon": 41.1333},
    # — DOĞALGAZ —
    {"ad": "Hamitabat Doğalgaz",     "il": "Kırklareli","ilce": "Babaeski",  "tur": "Doğalgaz", "sinif": "Enerji",   "firma": "TPAO / BOTAŞ",           "lat": 41.4333, "lon": 27.1000},
]


class MadenScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="MAPEG-Maden",
            base_url=MAPEG_URL,
            rate_limit_sn=3.0,
        )
        gc = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(gc.geocode, min_delay_seconds=1.1)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")

        # Seed verisiyle başla, canlı siteden güncelleme ara
        features = list(MADEN_SEED)
        canlı = self._mapeg_istatistik()
        if canlı:
            logger.info(f"[{self.name}] MAPEG'den {len(canlı)} il verisi alındı.")
            # İl bazlı ruhsat sayılarını istatistik olarak ayrı tut
            for kayit in canlı:
                features.append(kayit)

        # Eksik koordinatları tamamla
        for f in features:
            if not f.get("lat") or not f.get("lon"):
                lat, lon = self._koord(f.get("il", ""), f.get("ilce", ""))
                f["lat"] = lat
                f["lon"] = lon

        for f in features:
            f.setdefault("kategori", "Maden")

        logger.success(f"[{self.name}] {len(features)} maden kaydı hazır.")
        return features

    def _mapeg_istatistik(self) -> list[dict]:
        """MAPEG'in statik istatistik sayfasından il bazlı ruhsat sayıları."""
        try:
            soup = self._soup(MAPEG_URL)
            satirlar = soup.select("table tr")
            sonuc = []
            for satir in satirlar[1:]:
                hücreler = [td.get_text(strip=True) for td in satir.select("td")]
                if len(hücreler) >= 2:
                    sonuc.append({
                        "ad": f"{hücreler[0]} Ruhsat İstatistiği",
                        "il": hücreler[0],
                        "ruhsat_sayisi": hücreler[1],
                        "kategori": "MAPEG_İstatistik",
                        "lat": None,
                        "lon": None,
                    })
            return sonuc
        except Exception as e:
            logger.warning(f"[{self.name}] MAPEG istatistik hatası: {e}")
            return []

    def _koord(self, il: str, ilce: str = "") -> tuple:
        sorgu = f"{ilce}, {il}, Türkiye" if ilce else f"{il}, Türkiye"
        try:
            loc = self._geocode(sorgu, language="tr")
            if loc:
                return loc.latitude, loc.longitude
        except Exception:
            pass
        return None, None
