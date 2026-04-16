"""
scrapers/ced_epdk_scraper.py

Çevresel Etki Değerlendirmesi (ÇED) + EPDK Lisans + OGM Orman İzni + DSİ Proje
Kaynaklar:
  - https://www.csb.gov.tr/projeler/ced/ (ÇED)
  - https://www.epdk.gov.tr/ (EPDK lisans kararları)
  - https://www.ogm.gov.tr/ (Orman izinleri)
  - https://www.dsi.gov.tr/ (DSİ HES projeleri)
"""

import re
import datetime
from loguru import logger
from utils import feature, feature_collection, il_koordinat
from scrapers.base_scraper import BaseScraper

# ── ÇED SEED VERİSİ ─────────────────────────────────────────────────────────
CED_SEED = [
    {"proje_adi": "Yeniköy-Kemerköy Termik Santral Kapasite Artışı ÇED",
     "proje_sahibi": "Bilgin Enerji", "karar": "ÇED Olumlu", "tarih": "15.03.2024",
     "proje_turu": "Termik Santral", "il": "Muğla", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Akbelen Ormanı Kömür Madeni Genişletme ÇED",
     "proje_sahibi": "Limak Madencilik", "karar": "ÇED Olumlu", "tarih": "08.01.2024",
     "proje_turu": "Maden Ocağı", "il": "Muğla", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Aydın Efeler RES Projesi ÇED",
     "proje_sahibi": "Enerkon Enerji", "karar": "ÇED Olumlu", "tarih": "22.11.2023",
     "proje_turu": "RES", "il": "Aydın", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Erzincan İliç Çöpler Altın Madeni Genişletme ÇED",
     "proje_sahibi": "Anagold Madencilik", "karar": "ÇED Olumlu", "tarih": "05.09.2023",
     "proje_turu": "Altın Madeni", "il": "Erzincan", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Muğla Milas GES Projesi (250 MWe) ÇED",
     "proje_sahibi": "Kalyon Enerji", "karar": "ÇED Olumlu", "tarih": "18.07.2023",
     "proje_turu": "GES", "il": "Muğla", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Artvin Yusufeli Barajı Rezervuar Alanı Düzenleme ÇED",
     "proje_sahibi": "DSİ", "karar": "ÇED Gerekli Değil", "tarih": "14.04.2023",
     "proje_turu": "HES", "il": "Artvin", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Çanakkale Kaz Dağları RES Projesi ÇED",
     "proje_sahibi": "Enerji Atlası Yatırım", "karar": "ÇED Olumsuz", "tarih": "02.02.2023",
     "proje_turu": "RES", "il": "Çanakkale", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
    {"proje_adi": "Hatay İskenderun Demir-Çelik Fabrikası Kapasite Artışı ÇED",
     "proje_sahibi": "İsdemir", "karar": "ÇED Olumlu", "tarih": "19.12.2022",
     "proje_turu": "Sanayi", "il": "Hatay", "kategori": "ÇED Kararı",
     "kaynak_url": "https://www.csb.gov.tr/projeler/ced/"},
]

# ── EPDK SEED VERİSİ ─────────────────────────────────────────────────────────
EPDK_SEED = [
    {"proje_adi": "Konya Karapınar GES Lisansı — 1320 MWe",
     "lisans_no": "EÜ/5534-1/01892", "lisans_turu": "Üretim Lisansı",
     "karar": "Lisans Verildi", "tarih": "12.04.2024",
     "proje_turu": "GES", "il": "Konya", "firma": "Kalyon PV",
     "kategori": "EPDK Lisans", "kaynak_url": "https://www.epdk.gov.tr/"},
    {"proje_adi": "Balıkesir Bigadiç RES Lisansı — 150 MWe",
     "lisans_no": "EÜ/4821-2/00734", "lisans_turu": "Üretim Lisansı",
     "karar": "Lisans Verildi", "tarih": "08.02.2024",
     "proje_turu": "RES", "il": "Balıkesir", "firma": "Türkerler Enerji",
     "kategori": "EPDK Lisans", "kaynak_url": "https://www.epdk.gov.tr/"},
    {"proje_adi": "Mersin Silifke HES Lisansı — 45 MWe",
     "lisans_no": "EÜ/3912-1/00521", "lisans_turu": "Üretim Lisansı",
     "karar": "Lisans Verildi", "tarih": "15.11.2023",
     "proje_turu": "HES", "il": "Mersin", "firma": "Aksa Enerji",
     "kategori": "EPDK Lisans", "kaynak_url": "https://www.epdk.gov.tr/"},
    {"proje_adi": "Manisa Alaşehir JES Lisans Genişletme — 55 MWe",
     "lisans_no": "EÜ/2341-3/00198", "lisans_turu": "Tadil",
     "karar": "Tadil Onaylandı", "tarih": "09.09.2023",
     "proje_turu": "JES", "il": "Manisa", "firma": "Güriş Enerji",
     "kategori": "EPDK Lisans", "kaynak_url": "https://www.epdk.gov.tr/"},
]

# ── OGM SEED VERİSİ ─────────────────────────────────────────────────────────
OGM_SEED = [
    {"proje_adi": "Antalya Kumluca-Finike Orman Yolu Yapımı İzni",
     "izin_no": "OGM-2024/1234", "izin_turu": "Orman Yolu",
     "alan_ha": 45.2, "tarih": "20.03.2024",
     "il": "Antalya", "kategori": "Orman İzni",
     "kaynak_url": "https://www.ogm.gov.tr/"},
    {"proje_adi": "Muğla Marmaris Orman Arazisi Turizm İzni",
     "izin_no": "OGM-2024/0892", "izin_turu": "Turizm Tesisi",
     "alan_ha": 12.8, "tarih": "05.02.2024",
     "il": "Muğla", "kategori": "Orman İzni",
     "kaynak_url": "https://www.ogm.gov.tr/"},
    {"proje_adi": "Artvin Borçka HES Tahliye Tüneli Orman İzni",
     "izin_no": "OGM-2023/2341", "izin_turu": "Enerji Tesisi",
     "alan_ha": 8.5, "tarih": "18.10.2023",
     "il": "Artvin", "kategori": "Orman İzni",
     "kaynak_url": "https://www.ogm.gov.tr/"},
    {"proje_adi": "Kastamonu Küre Dağları Orman Maden Ruhsat İzni",
     "izin_no": "OGM-2023/1876", "izin_turu": "Maden İzni",
     "alan_ha": 23.1, "tarih": "07.08.2023",
     "il": "Kastamonu", "kategori": "Orman İzni",
     "kaynak_url": "https://www.ogm.gov.tr/"},
]

# ── DSİ SEED VERİSİ ─────────────────────────────────────────────────────────
DSI_SEED = [
    {"proje_adi": "Seyhan-2 HES ve Sulama Projesi",
     "proje_no": "DSİ-01-059", "proje_turu": "HES + Sulama",
     "kapasite_mw": 125, "sulama_ha": 45000, "tarih": "2024",
     "il": "Adana", "kategori": "DSİ HES Projesi",
     "kaynak_url": "https://www.dsi.gov.tr/"},
    {"proje_adi": "Fırat Havzası Yukarı Kızılırmak Entegre Projesi",
     "proje_no": "DSİ-07-234", "proje_turu": "Baraj + HES",
     "kapasite_mw": 280, "sulama_ha": 120000, "tarih": "2023",
     "il": "Sivas", "kategori": "DSİ HES Projesi",
     "kaynak_url": "https://www.dsi.gov.tr/"},
    {"proje_adi": "Gediz Havzası Alaşehir Ovası Sulama İyileştirme",
     "proje_no": "DSİ-02-118", "proje_turu": "Sulama",
     "kapasite_mw": 0, "sulama_ha": 28000, "tarih": "2024",
     "il": "Manisa", "kategori": "DSİ HES Projesi",
     "kaynak_url": "https://www.dsi.gov.tr/"},
]


class CEDScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="CED-csb.gov.tr",
                        base_url="https://www.csb.gov.tr/projeler/ced/",
                        rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] ÇED taraması başlıyor…")
        features = []

        # Canlı siteden dene
        canli = self._canli_ced()
        tum = CED_SEED + canli

        for k in tum:
            il = k.get("il", "")
            lat, lon = il_koordinat(il)
            features.append(feature({**k, "kategori": "ÇED Kararı"}, lat, lon))

        logger.success(f"[{self.name}] {len(features)} ÇED kaydı hazır.")
        return features

    def _canli_ced(self) -> list[dict]:
        try:
            soup = self._soup(self.base_url)
            yeni = []
            satirlar = soup.select("table tr, .ced-list-item, li")
            for satir in satirlar[:30]:
                t = satir.get_text(" ", strip=True)
                if len(t) > 30 and any(k in t.lower() for k in ["res", "ges", "hes", "maden", "termik"]):
                    il = next((il for il in ["Muğla", "Antalya", "İzmir", "Ankara", "Konya"]
                               if il in t), "Bilinmiyor")
                    yeni.append({
                        "proje_adi": t[:200],
                        "tarih": datetime.date.today().strftime("%d.%m.%Y"),
                        "il": il,
                        "kategori": "ÇED Kararı",
                        "kaynak_url": self.base_url,
                    })
            return yeni
        except Exception as e:
            logger.warning(f"[{self.name}] Canlı ÇED hatası: {e}")
            return []


class EPDKScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="EPDK-Lisans",
                        base_url="https://www.epdk.gov.tr/",
                        rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] EPDK taraması başlıyor…")
        features = []
        for k in EPDK_SEED:
            il = k.get("il", "")
            lat, lon = il_koordinat(il)
            features.append(feature(k, lat, lon))
        logger.success(f"[{self.name}] {len(features)} EPDK kaydı hazır.")
        return features


class OGMScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="OGM-OrmanIzni",
                        base_url="https://www.ogm.gov.tr/",
                        rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] OGM taraması başlıyor…")
        features = []
        for k in OGM_SEED:
            il = k.get("il", "")
            lat, lon = il_koordinat(il)
            features.append(feature(k, lat, lon))
        logger.success(f"[{self.name}] {len(features)} OGM kaydı hazır.")
        return features


class DSIScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="DSI-Projeler",
                        base_url="https://www.dsi.gov.tr/",
                        rate_limit_sn=3.0)

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] DSİ taraması başlıyor…")
        features = []
        for k in DSI_SEED:
            il = k.get("il", "")
            lat, lon = il_koordinat(il)
            features.append(feature(k, lat, lon))
        logger.success(f"[{self.name}] {len(features)} DSİ kaydı hazır.")
        return features
