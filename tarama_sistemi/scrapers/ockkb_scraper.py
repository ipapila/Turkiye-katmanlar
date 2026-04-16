"""
scrapers/ockkb_scraper.py

Kaynak  : https://ockb.csb.gov.tr/
          https://tvk.csb.gov.tr/

19 Özel Çevre Koruma Bölgesi'nin ad, il, alan, ilan tarihi bilgilerini
çeker. ÖÇKB sayısı değişirse (yeni ilan) otomatik algılar.
Selenium değil, statik HTML + navigasyon menüsü.
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

OCKB_BASE = "https://ockb.csb.gov.tr"
BOLGE_LIST_URL = f"{OCKB_BASE}/"

# Bilinen ÖÇKB'lerin slug listesi (site navigasyonundan dinamik alınır;
# bu liste fallback olarak kullanılır)
BILINEN_SLUGLAR = [
    "gokova-ozel-cevre-koruma-bolgesi-i-2748",
    "koyceğiz-dalyan-ozel-cevre-koruma-bolgesi-i-2749",
    "fethiye-gocek-ozel-cevre-koruma-bolgesi-i-2750",
    "patara-ozel-cevre-koruma-bolgesi-i-2751",
    "kas-kekova-ozel-cevre-koruma-bolgesi-i-2752",
    "goksu-deltasi-ozel-cevre-koruma-bolgesi-i-2753",
    "golbasi-ozel-cevre-koruma-bolgesi-i-2754",
    "datca-bozburun-ozel-cevre-koruma-bolgesi-i-2755",
    "belek-ozel-cevre-koruma-bolgesi-i-2756",
    "ihlara-ozel-cevre-koruma-bolgesi-i-2757",
    "foca-ozel-cevre-koruma-bolgesi-i-2758",
    "pamukkale-ozel-cevre-koruma-bolgesi-i-2759",
    "uzungol-ozel-cevre-koruma-bolgesi-i-2760",
    "tuzgolu-ozel-cevre-koruma-bolgesi-i-2761",
    "saros-korfezi-ozel-cevre-koruma-bolgesi-i-2762",
    "finike-denizalti-daglari-ozel-cevre-koruma-bolgesi-i-3716",
    "salda-golu-ozel-cevre-koruma-bolgesi-i-91579",
    "karaburun-ildir-korfezi-ozel-cevre-koruma-bolgesi-i-91580",
    "marmara-denizi-ve-adalar-ozel-cevre-koruma-bolgesi-i-106827",
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
        sluglar = self._sluglari_bul()
        features = []

        for slug in sluglar:
            url = f"{OCKB_BASE}/{slug}"
            try:
                f = self._bolge_detay(url)
                if f:
                    features.append(f)
            except Exception as e:
                logger.warning(f"[{self.name}] Hata ({slug}): {e}")

        logger.success(f"[{self.name}] {len(features)} ÖÇKB bulundu.")
        return features

    def _sluglari_bul(self) -> list[str]:
        """Ana sayfadaki navigasyon menüsünden slug listesi çıkar."""
        try:
            soup = self._soup(BOLGE_LIST_URL)
            linkler = soup.select("a[href*='ozel-cevre-koruma-bolgesi']")
            sluglar = []
            for link in linkler:
                href = link.get("href", "")
                # /slug-i-1234 formatı
                m = re.search(r"/([\w-]+-i-\d+)", href)
                if m:
                    sluglar.append(m.group(1))
            if sluglar:
                logger.info(f"[{self.name}] Menüden {len(set(sluglar))} slug alındı.")
                return list(set(sluglar))
        except Exception as e:
            logger.warning(f"[{self.name}] Menü parse hatası: {e} — fallback kullanılıyor.")
        return BILINEN_SLUGLAR

    def _bolge_detay(self, url: str) -> dict | None:
        """Tek bir ÖÇKB detay sayfasını parse eder."""
        soup = self._soup(url)

        # Başlık
        h1 = soup.find("h1")
        ad = h1.get_text(strip=True) if h1 else url.split("/")[-1]

        # İl bilgisi — metin içinden çıkar
        metin = soup.get_text(" ")
        il = self._il_bul(metin, ad)

        # Alan (km² veya ha) — "576.9" gibi sayıları ara
        alan_m = re.search(
            r"(\d[\d\.,]+)\s*(?:km[²2]|hektar|ha)",
            metin[:3000],
            re.IGNORECASE,
        )
        alan = None
        alan_birim = None
        if alan_m:
            alan = float(alan_m.group(1).replace(",", "."))
            alan_birim = "km2" if "km" in alan_m.group(0).lower() else "ha"

        # İlan tarihi
        tarih_m = re.search(
            r"(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{4}|\d{4})",
            metin[:2000],
        )
        ilan_tarihi = tarih_m.group(1) if tarih_m else None

        lat, lon = self._koord(il)
        return {
            "ad": ad,
            "il": il,
            "alan": alan,
            "alan_birim": alan_birim,
            "ilan_tarihi": ilan_tarihi,
            "kategori": "ÖÇKB",
            "kaynak_url": url,
            "lat": lat,
            "lon": lon,
        }

    @staticmethod
    def _il_bul(metin: str, ad: str) -> str:
        """Metinden veya ad'dan il bilgisi çıkar."""
        # "Muğla ili" veya "Antalya İli" gibi ifadeler
        m = re.search(
            r"([A-ZÇĞİÖŞÜa-zçğışöüI][a-zçğışöüI]+)\s+[Ii]li",
            metin[:1500],
        )
        if m:
            return m.group(1)
        # Ad içinden il tahmini (örn: "Gökova" → "Muğla")
        _ad_il_map = {
            "gökova": "Muğla", "köyceğiz": "Muğla", "fethiye": "Muğla",
            "datça": "Muğla", "marmaris": "Muğla",
            "patara": "Antalya", "kaş": "Antalya", "belek": "Antalya",
            "göksu": "Mersin", "foça": "İzmir", "karaburun": "İzmir",
            "pamukkale": "Denizli", "saros": "Çanakkale",
            "gölbaşı": "Ankara", "tuz gölü": "Konya",
            "uzungöl": "Trabzon", "ihlara": "Aksaray", "salda": "Burdur",
            "marmara denizi": "İstanbul",
        }
        ad_lower = ad.lower()
        for anahtar, il in _ad_il_map.items():
            if anahtar in ad_lower:
                return il
        return "Bilinmiyor"

    def _koord(self, il: str):
        if not il or il == "Bilinmiyor":
            return None, None
        try:
            loc = self._geocode(f"{il}, Türkiye", language="tr")
            if loc:
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode [{il}]: {e}")
        return None, None
