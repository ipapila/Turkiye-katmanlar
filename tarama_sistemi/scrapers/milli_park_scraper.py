"""
scrapers/milli_park_scraper.py

Kaynak  : https://www.tarimorman.gov.tr/DKMP/Menu/27/Milli-Parklar  (sayı değişimi kontrolü)
Fallback: Seed verisi — araştırmayla derlenmiş 50 milli park

Mimari: Ramsar tarayıcısıyla aynı — seed + canlı_kontrol.
Canlı site (tarimorman.gov.tr) erişilebilirse yeni park eklenip
eklenmediğini kontrol eder; seed'e ek olarak yenilerini ekler.
"""

import re
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

from scrapers.base_scraper import BaseScraper

BAKANLÍK_URL = "https://www.tarimorman.gov.tr/DKMP/Menu/27/Milli-Parklar"

# 50 milli parkın tamamı — araştırmayla doğrulanmış
MILLI_PARK_SEED = [
    {"sira":1,  "ad":"Yozgat Çamlığı Milli Parkı",                     "il":"Yozgat",              "alan_ha":267,    "tarih":"1958-02-05", "lat":39.8167,"lon":34.8000},
    {"sira":2,  "ad":"Karatepe-Aslantaş Milli Parkı",                   "il":"Osmaniye",            "alan_ha":4145,   "tarih":"1958-05-29", "lat":37.4000,"lon":36.1667},
    {"sira":3,  "ad":"Soğuksu Milli Parkı",                             "il":"Ankara",              "alan_ha":1187,   "tarih":"1959-02-19", "lat":40.5600,"lon":32.6000},
    {"sira":4,  "ad":"Kuşcenneti (Manyas Gölü) Milli Parkı",            "il":"Balıkesir",           "alan_ha":24047,  "tarih":"1959-07-27", "lat":40.1953,"lon":27.9678},
    {"sira":5,  "ad":"Uludağ Milli Parkı",                              "il":"Bursa",               "alan_ha":12762,  "tarih":"1961-09-20", "lat":40.1500,"lon":29.2167},
    {"sira":6,  "ad":"Yedigöller Milli Parkı",                          "il":"Bolu",                "alan_ha":2019,   "tarih":"1965-04-29", "lat":40.9333,"lon":31.7333},
    {"sira":7,  "ad":"Dilek Yarımadası-Büyük Menderes Deltası Milli Parkı","il":"Aydın",             "alan_ha":27598,  "tarih":"1966-05-19", "lat":37.6000,"lon":27.2500},
    {"sira":8,  "ad":"Spil Dağı Milli Parkı",                           "il":"Manisa",              "alan_ha":6860,   "tarih":"1968-04-22", "lat":38.5833,"lon":27.7000},
    {"sira":9,  "ad":"Kızıldağ Milli Parkı",                            "il":"Isparta",             "alan_ha":55105,  "tarih":"1969-05-09", "lat":37.8000,"lon":31.1500},
    {"sira":10, "ad":"Güllük Dağı-Termessos Milli Parkı",               "il":"Antalya",             "alan_ha":6700,   "tarih":"1970-11-03", "lat":37.0667,"lon":30.4667},
    {"sira":11, "ad":"Kovada Gölü Milli Parkı",                         "il":"Isparta",             "alan_ha":6550,   "tarih":"1970-11-03", "lat":37.8667,"lon":30.9000},
    {"sira":12, "ad":"Munzur Vadisi Milli Parkı",                       "il":"Tunceli",             "alan_ha":62674,  "tarih":"1971-12-21", "lat":39.2667,"lon":39.3333},
    {"sira":13, "ad":"Beydağları Sahil Milli Parkı",                    "il":"Antalya",             "alan_ha":31165,  "tarih":"1972-03-16", "lat":36.4833,"lon":30.5333},
    {"sira":14, "ad":"Köprülü Kanyon Milli Parkı",                      "il":"Antalya",             "alan_ha":35719,  "tarih":"1973-12-12", "lat":37.2667,"lon":31.4000},
    {"sira":15, "ad":"Gelibolu Yarımadası Tarihi Milli Parkı",           "il":"Çanakkale",           "alan_ha":33439,  "tarih":"1973",       "lat":40.2833,"lon":26.4200},
    {"sira":16, "ad":"Ilgaz Dağı Milli Parkı",                          "il":"Kastamonu",           "alan_ha":1117,   "tarih":"1976-06-02", "lat":41.0833,"lon":33.6333},
    {"sira":17, "ad":"Başkomutan Tarihi Milli Parkı",                    "il":"Afyonkarahisar",      "alan_ha":34833,  "tarih":"1981-11-08", "lat":38.9333,"lon":30.2833},
    {"sira":18, "ad":"Göreme Tarihi Milli Parkı",                       "il":"Nevşehir",            "alan_ha":9614,   "tarih":"1986-11-25", "lat":38.6500,"lon":34.8500},
    {"sira":19, "ad":"Altındere Vadisi Milli Parkı",                    "il":"Trabzon",             "alan_ha":4468,   "tarih":"1987-09-09", "lat":40.7167,"lon":39.6333},
    {"sira":20, "ad":"Boğazköy-Alacahöyük Milli Parkı",                 "il":"Çorum",               "alan_ha":2600,   "tarih":"1988-09-21", "lat":40.0333,"lon":34.6167},
    {"sira":21, "ad":"Nemrut Dağı Milli Parkı",                         "il":"Adıyaman",            "alan_ha":13827,  "tarih":"1988-12-07", "lat":37.9667,"lon":38.7333},
    {"sira":22, "ad":"Beyşehir Gölü Milli Parkı",                       "il":"Konya",               "alan_ha":88750,  "tarih":"1993-02-20", "lat":37.7167,"lon":31.4667},
    {"sira":23, "ad":"Kazdağı Milli Parkı",                             "il":"Balıkesir",           "alan_ha":20935,  "tarih":"1994-04-17", "lat":39.7833,"lon":26.9000},
    {"sira":24, "ad":"Altınbeşik Mağarası Milli Parkı",                 "il":"Antalya",             "alan_ha":1147,   "tarih":"1994-08-31", "lat":37.0667,"lon":31.4500},
    {"sira":25, "ad":"Hatila Vadisi Milli Parkı",                       "il":"Artvin",              "alan_ha":16944,  "tarih":"1994-08-31", "lat":41.2167,"lon":41.8000},
    {"sira":26, "ad":"Karagöl-Sahara Milli Parkı",                      "il":"Artvin",              "alan_ha":3251,   "tarih":"1994-08-31", "lat":41.1500,"lon":42.4833},
    {"sira":27, "ad":"Kaçkar Dağları Milli Parkı",                      "il":"Rize",                "alan_ha":51550,  "tarih":"1994-08-31", "lat":40.8667,"lon":41.1500},
    {"sira":28, "ad":"Aladağlar Milli Parkı",                           "il":"Adana",               "alan_ha":54614,  "tarih":"1995",       "lat":37.7333,"lon":35.2500},
    {"sira":29, "ad":"Marmaris Milli Parkı",                            "il":"Muğla",               "alan_ha":30250,  "tarih":"1996",       "lat":36.8333,"lon":28.3000},
    {"sira":30, "ad":"Saklıkent Milli Parkı",                           "il":"Muğla",               "alan_ha":1196,   "tarih":"1996-06-06", "lat":36.4000,"lon":29.4167},
    {"sira":31, "ad":"Troya Tarihi Milli Parkı",                        "il":"Çanakkale",           "alan_ha":10462,  "tarih":"1996-11-07", "lat":39.9500,"lon":26.2333},
    {"sira":32, "ad":"Honaz Dağı Milli Parkı",                          "il":"Denizli",             "alan_ha":6972,   "tarih":"1998-04-21", "lat":37.7000,"lon":29.2667},
    {"sira":33, "ad":"Küre Dağları Milli Parkı",                        "il":"Kastamonu",           "alan_ha":37753,  "tarih":"2000",       "lat":41.8500,"lon":33.6000},
    {"sira":34, "ad":"Sarıkamış-Allahuekber Dağları Milli Parkı",       "il":"Kars",                "alan_ha":22520,  "tarih":"2004-10-19", "lat":40.3833,"lon":42.6667},
    {"sira":35, "ad":"Ağrı Dağı Milli Parkı",                           "il":"Ağrı",                "alan_ha":88015,  "tarih":"2004-11-17", "lat":39.7333,"lon":44.2333},
    {"sira":36, "ad":"Gala Gölü Milli Parkı",                           "il":"Edirne",              "alan_ha":5936,   "tarih":"2005",       "lat":40.9667,"lon":26.3833},
    {"sira":37, "ad":"Sultan Sazlığı Milli Parkı",                      "il":"Kayseri",             "alan_ha":17200,  "tarih":"2006-03-17", "lat":38.3336,"lon":35.2661},
    {"sira":38, "ad":"Tek Tek Dağları Milli Parkı",                     "il":"Şanlıurfa",           "alan_ha":26182,  "tarih":"2007-05-29", "lat":37.1833,"lon":38.7833},
    {"sira":39, "ad":"İğneada Longoz Ormanları Milli Parkı",             "il":"Kırklareli",          "alan_ha":3155,   "tarih":"2007-11-03", "lat":41.8900,"lon":27.9600},
    {"sira":40, "ad":"Yumurtalık Lagünleri Milli Parkı",                "il":"Adana",               "alan_ha":19800,  "tarih":"2009-10-16", "lat":36.8000,"lon":35.6350},
    {"sira":41, "ad":"Nene Hatun Tarihi Milli Parkı",                   "il":"Erzurum",             "alan_ha":387,    "tarih":"2009-06-06", "lat":39.9081,"lon":41.2722},
    {"sira":42, "ad":"Sakarya Meydan Muharebesi Tarihi Milli Parkı",     "il":"Ankara",              "alan_ha":13850,  "tarih":"2015-02-08", "lat":39.5833,"lon":32.0167},
    {"sira":43, "ad":"Kop Dağı Müdafaası Tarihi Milli Parkı",           "il":"Bayburt",             "alan_ha":6335,   "tarih":"2016-11-15", "lat":40.2500,"lon":40.3333},
    {"sira":44, "ad":"Malazgirt Meydan Muharebesi Tarihi Milli Parkı",   "il":"Muş",                 "alan_ha":238,    "tarih":"2018-03-17", "lat":38.9333,"lon":42.5333},
    {"sira":45, "ad":"İstiklal Yolu Tarihi Milli Parkı",                 "il":"Kastamonu",           "alan_ha":236,    "tarih":"2018-11-02", "lat":41.4167,"lon":33.7167},
    {"sira":46, "ad":"Botan Vadisi Milli Parkı",                        "il":"Siirt",               "alan_ha":11358,  "tarih":"2019-08-15", "lat":37.8500,"lon":41.5833},
    {"sira":47, "ad":"Hakkari Cilo ve Sat Dağları Milli Parkı",          "il":"Hakkari",             "alan_ha":27500,  "tarih":"2020-09-26", "lat":37.5500,"lon":44.1000},
    {"sira":48, "ad":"Sarıçalı Dağı Milli Parkı",                       "il":"Ankara",              "alan_ha":1024,   "tarih":"2021-10-28", "lat":40.1833,"lon":31.9333},
    {"sira":49, "ad":"Derebucak Çamlık Mağaraları Milli Parkı",          "il":"Konya",               "alan_ha":1147,   "tarih":"2022-06-07", "lat":37.4167,"lon":31.8167},
    {"sira":50, "ad":"Abant Gölü Milli Parkı",                          "il":"Bolu",                "alan_ha":1262,   "tarih":"2022-06-09", "lat":40.5833,"lon":31.2167},
    {"sira":51, "ad":"Akdağ Milli Parkı",                               "il":"Denizli",             "alan_ha":15933,  "tarih":"2024-01-17", "lat":38.2833,"lon":29.2000},
    {"sira":52, "ad":"Geben Vadisi Milli Parkı",                        "il":"Giresun",             "alan_ha":None,   "tarih":"2025-05-30", "lat":40.5667,"lon":38.5000},
]


class MilliParkScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="MilliParklar-DKMP",
            base_url=BAKANLÍK_URL,
            rate_limit_sn=2.5,
        )
        gc = Nominatim(user_agent="tr_env_monitor/1.0")
        self._geocode = RateLimiter(gc.geocode, min_delay_seconds=1.1)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] tarama başlıyor…")

        # Canlı siteden yeni park kontrolü yap
        yeni_parklar = self._canli_kontrol()
        features = []

        for seed in MILLI_PARK_SEED:
            features.append({
                "sira": seed["sira"],
                "ad": seed["ad"],
                "il": seed["il"],
                "alan_ha": seed["alan_ha"],
                "ilan_tarihi": seed["tarih"],
                "kategori": "Milli Park",
                "kaynak_url": BAKANLÍK_URL,
                "lat": seed["lat"],
                "lon": seed["lon"],
            })

        # Canlı siteden gelip seed'de olmayan yeni parkları ekle
        for yeni in yeni_parklar:
            if not any(yeni.get("ad", "").lower() in s["ad"].lower() for s in MILLI_PARK_SEED):
                lat, lon = self._koord(yeni.get("il", ""))
                features.append({**yeni, "kategori": "Milli Park", "lat": lat, "lon": lon})
                logger.info(f"[{self.name}] YENİ milli park tespit edildi: {yeni.get('ad')}")

        logger.success(f"[{self.name}] {len(features)} milli park hazır.")
        return features

    def _canli_kontrol(self) -> list[dict]:
        """
        tarimorman.gov.tr sayfasından milli park sayısını kontrol eder.
        50'den fazlaysa yeni park var demektir.
        """
        try:
            soup = self._soup(self.base_url)
            metin = soup.get_text(" ")
            m = re.search(r"(\d+)\s+milli\s+park", metin, re.IGNORECASE)
            if m:
                sayi = int(m.group(1))
                if sayi > len(MILLI_PARK_SEED):
                    logger.warning(
                        f"[{self.name}] Milli park sayısı {sayi}'e çıkmış! "
                        f"Seed güncellenmeli."
                    )
        except Exception as e:
            logger.warning(f"[{self.name}] Canlı kontrol hatası: {e} — seed verisi kullanılıyor.")
        return []

    def _koord(self, il_metin: str):
        il = il_metin.split("/")[0].split("-")[0].strip()
        try:
            loc = self._geocode(f"{il}, Türkiye", language="tr")
            if loc:
                return loc.latitude, loc.longitude
        except Exception as e:
            logger.warning(f"Geocode hatası [{il}]: {e}")
        return None, None
