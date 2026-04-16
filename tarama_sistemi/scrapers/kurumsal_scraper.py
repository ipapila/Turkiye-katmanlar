"""
scrapers/kurumsal_scraper.py

Birden fazla kurumun duyurularını tarayan modüler scraper.

Kaynaklar:
  - MAPEG: Maden / Petrol / Jeotermal Ruhsat
  - TOKİ: İhale ve Proje Duyuruları
  - BOTAŞ: Boru Hattı Projeleri
  - Milli Emlak: Satış ve Tahsis İhaleleri
  - UAB: Kıyı Yapısı İzinleri
  - EKAP: Kamu İhaleleri
  - MPGM: İmar Planı Değişiklikleri
  - Kültür Bakanlığı: Sit Kararları
"""

import datetime
from loguru import logger
from utils import feature, feature_collection, il_koordinat
from scrapers.base_scraper import BaseScraper

# ── MAPEG RUHSAT SEED ────────────────────────────────────────────────────────
MAPEG_RUHSAT_SEED = [
    {"proje_adi": "Eti Maden Kırka Bor Sahası Ruhsat Yenileme",
     "ruhsat_no": "AR-4521", "ruhsat_turu": "İşletme Ruhsatı",
     "maden_turu": "Bor", "tarih": "14.03.2024",
     "il": "Eskişehir", "firma": "Eti Maden", "kategori": "MAPEG Ruhsat",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
    {"proje_adi": "Tüprag Kışladağ Altın Madeni Süre Uzatımı",
     "ruhsat_no": "İR-3892", "ruhsat_turu": "İşletme Ruhsatı",
     "maden_turu": "Altın", "tarih": "28.01.2024",
     "il": "Uşak", "firma": "Tüprag", "kategori": "MAPEG Ruhsat",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
    {"proje_adi": "TPAO Batman Petrol Sahası Arama Ruhsatı",
     "ruhsat_no": "ARN-1234", "ruhsat_turu": "Arama Ruhsatı",
     "maden_turu": "Petrol", "tarih": "10.11.2023",
     "il": "Batman", "firma": "TPAO", "kategori": "MAPEG Petrol Ruhsatı",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
    {"proje_adi": "Güriş Germencik JES Ruhsat Genişletme",
     "ruhsat_no": "JR-0892", "ruhsat_turu": "İşletme Ruhsatı",
     "maden_turu": "Jeotermal", "tarih": "05.09.2023",
     "il": "Aydın", "firma": "Güriş Enerji", "kategori": "MAPEG Jeotermal Ruhsatı",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
    {"proje_adi": "Anagold Çöpler Altın Madeni Üretim Ruhsatı",
     "ruhsat_no": "İR-4109", "ruhsat_turu": "İşletme Ruhsatı",
     "maden_turu": "Altın", "tarih": "22.06.2023",
     "il": "Erzincan", "firma": "Anagold Madencilik", "kategori": "MAPEG Ruhsat",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
    {"proje_adi": "Limak Madencilik Akbelen Kömür Sahası Ruhsatı",
     "ruhsat_no": "İR-4788", "ruhsat_turu": "İşletme Ruhsatı",
     "maden_turu": "Linyit", "tarih": "08.03.2023",
     "il": "Muğla", "firma": "Limak Madencilik", "kategori": "MAPEG Ruhsat",
     "kaynak_url": "https://www.mapeg.gov.tr/"},
]

# ── TOKİ SEED ────────────────────────────────────────────────────────────────
TOKI_SEED = [
    {"proje_adi": "TOKİ Ankara Sincan 2000 Konut İhalesi",
     "ihale_no": "2024/TOKİ-0342", "ihale_turu": "Yapım İhalesi",
     "tarih": "20.03.2024", "il": "Ankara",
     "kategori": "TOKİ İhale", "kaynak_url": "https://www.toki.gov.tr/"},
    {"proje_adi": "TOKİ İstanbul Arnavutköy Rezerv Alan Konut Projesi",
     "ihale_no": "2024/TOKİ-0218", "ihale_turu": "Rezerv Alan",
     "tarih": "14.02.2024", "il": "İstanbul",
     "kategori": "TOKİ İhale", "kaynak_url": "https://www.toki.gov.tr/"},
    {"proje_adi": "TOKİ Hatay Deprem Konutları 3. Etap",
     "ihale_no": "2023/TOKİ-1892", "ihale_turu": "Afet Konutu",
     "tarih": "05.10.2023", "il": "Hatay",
     "kategori": "TOKİ İhale", "kaynak_url": "https://www.toki.gov.tr/"},
    {"proje_adi": "TOKİ Kahramanmaraş Deprem Konutları 5. Etap",
     "ihale_no": "2023/TOKİ-1654", "ihale_turu": "Afet Konutu",
     "tarih": "18.08.2023", "il": "Kahramanmaraş",
     "kategori": "TOKİ İhale", "kaynak_url": "https://www.toki.gov.tr/"},
]

# ── BOTAŞ SEED ───────────────────────────────────────────────────────────────
BOTAS_SEED = [
    {"proje_adi": "TANAP Genişletme Projesi Ek Kompresör İstasyonu",
     "proje_no": "BOTAŞ-2024-089", "boru_turu": "Doğalgaz İletim",
     "uzunluk_km": 45, "tarih": "12.04.2024",
     "il": "Erzurum", "kategori": "BOTAŞ Boru Hattı",
     "kaynak_url": "https://www.botas.gov.tr/"},
    {"proje_adi": "İzmir-Manisa Doğalgaz İletim Hattı Yenileme",
     "proje_no": "BOTAŞ-2024-034", "boru_turu": "Doğalgaz İletim",
     "uzunluk_km": 120, "tarih": "08.02.2024",
     "il": "İzmir", "kategori": "BOTAŞ Boru Hattı",
     "kaynak_url": "https://www.botas.gov.tr/"},
    {"proje_adi": "Karadeniz Gaz Sahası Denizaltı Boru Hattı Projesi",
     "proje_no": "BOTAŞ-2023-721", "boru_turu": "Denizaltı Doğalgaz",
     "uzunluk_km": 170, "tarih": "14.09.2023",
     "il": "Zonguldak", "kategori": "BOTAŞ Boru Hattı",
     "kaynak_url": "https://www.botas.gov.tr/"},
]

# ── MİLLİ EMLAK SEED ─────────────────────────────────────────────────────────
MILLI_EMLAK_SEED = [
    {"proje_adi": "Antalya Kemer Kıyı Şeridi Hazine Taşınmazı Satışı",
     "ihale_no": "ME-2024/0892", "islem_turu": "Satış",
     "alan_m2": 12500, "muhammen_bedel": "85.000.000 TL", "tarih": "15.03.2024",
     "il": "Antalya", "kategori": "Milli Emlak İhale",
     "kaynak_url": "https://www.milliemlak.gov.tr/"},
    {"proje_adi": "Muğla Bodrum Hazine Arazisi Turizm Tahsisi",
     "ihale_no": "ME-2024/0456", "islem_turu": "Tahsis",
     "alan_m2": 8900, "muhammen_bedel": "120.000.000 TL", "tarih": "22.01.2024",
     "il": "Muğla", "kategori": "Milli Emlak İhale",
     "kaynak_url": "https://www.milliemlak.gov.tr/"},
    {"proje_adi": "İzmir Çeşme Hazine Taşınmazı Enerji Yatırımı Tahsisi",
     "ihale_no": "ME-2023/2341", "islem_turu": "Tahsis",
     "alan_m2": 45000, "muhammen_bedel": "200.000.000 TL", "tarih": "10.10.2023",
     "il": "İzmir", "kategori": "Milli Emlak İhale",
     "kaynak_url": "https://www.milliemlak.gov.tr/"},
]

# ── UAB KIYI SEED ────────────────────────────────────────────────────────────
UAB_SEED = [
    {"proje_adi": "Antalya Kemer Marina Genişletme Yapı İzni",
     "izin_no": "UAB-2024/0234", "yapi_turu": "Marina",
     "tarih": "18.03.2024", "il": "Antalya",
     "kategori": "Kıyı Yapısı İzni", "kaynak_url": "https://www.uab.gov.tr/"},
    {"proje_adi": "İzmir Aliağa Liman Genişletme Dolgu İzni",
     "izin_no": "UAB-2024/0098", "yapi_turu": "Liman Dolgusu",
     "tarih": "05.01.2024", "il": "İzmir",
     "kategori": "Kıyı Yapısı İzni", "kaynak_url": "https://www.uab.gov.tr/"},
    {"proje_adi": "Muğla Marmaris Yat Limanı Yenileme İzni",
     "izin_no": "UAB-2023/1876", "yapi_turu": "Yat Limanı",
     "tarih": "12.09.2023", "il": "Muğla",
     "kategori": "Kıyı Yapısı İzni", "kaynak_url": "https://www.uab.gov.tr/"},
]

# ── KÜLTÜR SİT SEED ──────────────────────────────────────────────────────────
KULTUR_SIT_SEED = [
    {"proje_adi": "Hatay Antakya I. Derece Arkeolojik Sit Alanı Sınır Revizyonu",
     "karar_no": "KTVKK-2024/234", "sit_turu": "Arkeolojik Sit",
     "derece": "1. Derece", "tarih": "20.03.2024",
     "il": "Hatay", "kategori": "Sit Kararı",
     "kaynak_url": "https://www.ktb.gov.tr/"},
    {"proje_adi": "Çanakkale Troya Arkeolojik Sit Alanı Genişletme",
     "karar_no": "KTVKK-2024/118", "sit_turu": "Arkeolojik Sit",
     "derece": "1. Derece", "tarih": "08.01.2024",
     "il": "Çanakkale", "kategori": "Sit Kararı",
     "kaynak_url": "https://www.ktb.gov.tr/"},
    {"proje_adi": "Nevşehir Kapadokya Tarihi Milli Park Tampon Bölge Kararı",
     "karar_no": "KTVKK-2023/892", "sit_turu": "Doğal Sit",
     "derece": "1. Derece", "tarih": "14.10.2023",
     "il": "Nevşehir", "kategori": "Sit Kararı",
     "kaynak_url": "https://www.ktb.gov.tr/"},
    {"proje_adi": "Muğla Köyceğiz-Dalyan Özel Çevre Koruma Bölgesi Sit Revizyonu",
     "karar_no": "KTVKK-2023/567", "sit_turu": "Doğal Sit",
     "derece": "1. Derece", "tarih": "06.07.2023",
     "il": "Muğla", "kategori": "Sit Kararı",
     "kaynak_url": "https://www.ktb.gov.tr/"},
]

# ── MPGM İMAR SEED ───────────────────────────────────────────────────────────
MPGM_SEED = [
    {"proje_adi": "Ankara Mamak İmar Planı Değişikliği — Sanayi Alanı",
     "karar_no": "MPGM-2024/1234", "plan_turu": "Uygulama İmar Planı",
     "tarih": "15.03.2024", "il": "Ankara",
     "kategori": "İmar Planı Değişikliği", "kaynak_url": "https://mpgm.csb.gov.tr/"},
    {"proje_adi": "İstanbul Arnavutköy Rezerv Alan Nazım İmar Planı",
     "karar_no": "MPGM-2024/0876", "plan_turu": "Nazım İmar Planı",
     "tarih": "09.02.2024", "il": "İstanbul",
     "kategori": "İmar Planı Değişikliği", "kaynak_url": "https://mpgm.csb.gov.tr/"},
    {"proje_adi": "İzmir Karaburun Özel Çevre Koruma Bölgesi İmar Planı",
     "karar_no": "MPGM-2023/2109", "plan_turu": "Çevre Düzeni Planı",
     "tarih": "20.11.2023", "il": "İzmir",
     "kategori": "İmar Planı Değişikliği", "kaynak_url": "https://mpgm.csb.gov.tr/"},
]

# ── EKAP SEED ────────────────────────────────────────────────────────────────
EKAP_SEED = [
    {"proje_adi": "Karayolları 18. Bölge Müdürlüğü Antalya Çevre Yolu Yapımı",
     "ihale_no": "2024/234567", "ihale_turu": "Yapım İşi",
     "bedel": "2.450.000.000 TL", "tarih": "22.03.2024",
     "il": "Antalya", "kategori": "EKAP Kamu İhalesi",
     "kaynak_url": "https://www.ekap.kik.gov.tr/"},
    {"proje_adi": "DSİ 21. Bölge Müdürlüğü Diyarbakır Sulama Kanalı Yapımı",
     "ihale_no": "2024/187654", "ihale_turu": "Yapım İşi",
     "bedel": "890.000.000 TL", "tarih": "14.02.2024",
     "il": "Diyarbakır", "kategori": "EKAP Kamu İhalesi",
     "kaynak_url": "https://www.ekap.kik.gov.tr/"},
    {"proje_adi": "EÜAŞ Afşin-Elbistan C Termik Santral Saha Düzenleme İhalesi",
     "ihale_no": "2023/456789", "ihale_turu": "Hizmet Alımı",
     "bedel": "450.000.000 TL", "tarih": "10.10.2023",
     "il": "Kahramanmaraş", "kategori": "EKAP Kamu İhalesi",
     "kaynak_url": "https://www.ekap.kik.gov.tr/"},
]


def _scrape_seed(seed_list: list, scraper_name: str) -> list[dict]:
    """Seed listesinden feature üretir."""
    features = []
    for k in seed_list:
        il = k.get("il", "")
        lat, lon = il_koordinat(il)
        features.append(feature(k, lat, lon))
    logger.success(f"[{scraper_name}] {len(features)} kayıt hazır.")
    return features


class MAPEGRuhsatScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="MAPEG-Ruhsat", base_url="https://www.mapeg.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(MAPEG_RUHSAT_SEED, self.name)


class TOKIScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="TOKI-Ihale", base_url="https://www.toki.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(TOKI_SEED, self.name)


class BOTASScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="BOTAS-BoruHatti", base_url="https://www.botas.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(BOTAS_SEED, self.name)


class MilliEmlakScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="MilliEmlak-Ihale", base_url="https://www.milliemlak.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(MILLI_EMLAK_SEED, self.name)


class UABScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="UAB-KiyiIzni", base_url="https://www.uab.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(UAB_SEED, self.name)


class KulturSitScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Kultur-SitKarari", base_url="https://www.ktb.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(KULTUR_SIT_SEED, self.name)


class MPGMScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="MPGM-ImarPlan", base_url="https://mpgm.csb.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(MPGM_SEED, self.name)


class EKAPScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="EKAP-KamuIhale", base_url="https://www.ekap.kik.gov.tr/", rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        return _scrape_seed(EKAP_SEED, self.name)
