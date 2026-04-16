"""
scrapers/ockkb_scraper.py

Kaynak  : https://ockb.csb.gov.tr/
Mimari  : seed + canlı_kontrol (Ramsar/MilliPark ile aynı)
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

OCKB_BASE = "https://ockb.csb.gov.tr"

OCKKB_SEED = [
    {"id":"A-01","ad":"Gökova ÖÇKB",                       "il":"Muğla",         "alan_km2":576.9,   "tarih":"1988-07-05","kiyi_deniz":True,  "lat":37.0800,"lon":28.4500},
    {"id":"A-02","ad":"Köyceğiz-Dalyan ÖÇKB",               "il":"Muğla",         "alan_km2":461.46,  "tarih":"1988-07-05","kiyi_deniz":True,  "lat":36.8500,"lon":28.6700},
    {"id":"A-03","ad":"Fethiye-Göcek ÖÇKB",                 "il":"Muğla",         "alan_km2":816.02,  "tarih":"1988-07-05","kiyi_deniz":True,  "lat":36.7500,"lon":29.2000},
    {"id":"A-04","ad":"Patara ÖÇKB",                        "il":"Antalya",       "alan_km2":189.81,  "tarih":"1990-03-02","kiyi_deniz":True,  "lat":36.3200,"lon":29.3300},
    {"id":"A-05","ad":"Kaş-Kekova ÖÇKB",                    "il":"Antalya",       "alan_km2":258.3,   "tarih":"1990-03-02","kiyi_deniz":True,  "lat":36.2000,"lon":29.9100},
    {"id":"A-06","ad":"Göksu Deltası ÖÇKB",                 "il":"Mersin",        "alan_km2":226.31,  "tarih":"1990-03-02","kiyi_deniz":True,  "lat":36.2000,"lon":33.5000},
    {"id":"A-07","ad":"Gölbaşı ÖÇKB",                       "il":"Ankara",        "alan_km2":273.94,  "tarih":"1990-11-21","kiyi_deniz":False, "lat":39.8800,"lon":32.5000},
    {"id":"A-08","ad":"Datça-Bozburun ÖÇKB",                "il":"Muğla",         "alan_km2":1443.89, "tarih":"1990-01-18","kiyi_deniz":True,  "lat":36.7500,"lon":27.8200},
    {"id":"A-09","ad":"Belek ÖÇKB",                         "il":"Antalya",       "alan_km2":111.79,  "tarih":"1990-11-21","kiyi_deniz":True,  "lat":36.8700,"lon":31.0800},
    {"id":"A-10","ad":"Ihlara ÖÇKB",                        "il":"Aksaray",       "alan_km2":54.64,   "tarih":"1990-11-21","kiyi_deniz":False, "lat":38.3550,"lon":34.3600},
    {"id":"A-11","ad":"Foça ÖÇKB",                          "il":"İzmir",         "alan_km2":71.44,   "tarih":"1990-11-21","kiyi_deniz":True,  "lat":38.6700,"lon":26.7200},
    {"id":"A-12","ad":"Pamukkale ÖÇKB",                     "il":"Denizli",       "alan_km2":66.56,   "tarih":"1990-11-21","kiyi_deniz":False, "lat":37.9250,"lon":29.1120},
    {"id":"A-13","ad":"Uzungöl ÖÇKB",                       "il":"Trabzon",       "alan_km2":149.12,  "tarih":"2004-01-07","kiyi_deniz":False, "lat":40.5700,"lon":40.2800},
    {"id":"A-14","ad":"Tuz Gölü ÖÇKB",                      "il":"Konya",         "alan_km2":7414.40, "tarih":"2000-11-02","kiyi_deniz":False, "lat":38.7500,"lon":33.5000},
    {"id":"A-15","ad":"Saros Körfezi ÖÇKB",                 "il":"Çanakkale",     "alan_km2":730.21,  "tarih":"2010-12-22","kiyi_deniz":True,  "lat":40.6800,"lon":26.5500},
    {"id":"A-16","ad":"Finike Denizaltı Dağları ÖÇKB",      "il":"Antalya",       "alan_km2":11228.85,"tarih":"2013-08-16","kiyi_deniz":True,  "lat":36.4500,"lon":30.3500},
    {"id":"A-17","ad":"Salda Gölü ÖÇKB",                    "il":"Burdur",        "alan_km2":62.0,    "tarih":"2019-04-20","kiyi_deniz":False, "lat":37.5400,"lon":29.6800},
    {"id":"A-18","ad":"Karaburun-Ildır Körfezi ÖÇKB",       "il":"İzmir",         "alan_km2":760.0,   "tarih":"2019-03-14","kiyi_deniz":True,  "lat":38.4500,"lon":26.5500},
    {"id":"A-19","ad":"Marmara Denizi ve Adalar ÖÇKB",       "il":"İstanbul",      "alan_km2":12246.0, "tarih":"2021-11-04","kiyi_deniz":True,  "lat":40.7000,"lon":28.0000},
]


class OCKBScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="ÖÇKB-csb.gov.tr",
            base_url=OCKB_BASE,
            rate_limit_sn=3.0,
        )
        gc = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(gc.geocode, min_delay_seconds=1.1)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")

        # Canlı siteden yeni ÖÇKB eklenip eklenmediğini kontrol et
        self._canli_kontrol()

        features = []
        for s in OCKKB_SEED:
            features.append({
                **s,
                "kategori": "ÖÇKB",
                "kaynak_url": OCKB_BASE,
            })

        logger.success(f"[{self.name}] {len(features)} ÖÇKB hazır.")
        return features

    def _canli_kontrol(self):
        """Yeni ÖÇKB ilan edilip edilmediğini kontrol eder."""
        try:
            soup = self._soup(self.base_url)
            metin = soup.get_text(" ")
            m = re.search(r"(\d+)\s+(?:adet\s+)?özel\s+çevre\s+koruma", metin, re.IGNORECASE)
            if m:
                sayi = int(m.group(1))
                if sayi > len(OCKKB_SEED):
                    logger.warning(
                        f"[{self.name}] ÖÇKB sayısı {sayi}'e çıkmış! "
                        f"Seed güncellenmeli (şu an {len(OCKKB_SEED)})."
                    )
        except Exception as e:
            logger.warning(f"[{self.name}] Canlı kontrol hatası: {e} — seed verisi kullanılıyor.")
