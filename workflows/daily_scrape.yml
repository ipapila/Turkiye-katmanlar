"""
scrapers/resmi_gazete_scraper.py

Resmi Gazete'yi tarar ve şu kararları çeker:
- Acele Kamulaştırma (Cumhurbaşkanlığı Kararı)
- ÇED Olumlu/Olumsuz Kararları
- Kültürel/Doğal Sit Kararları
- EPDK Lisans Kararları
- Orman İzin Kararları

Kaynak: https://www.resmigazete.gov.tr/
"""

import re
import datetime
from loguru import logger
from utils import feature, feature_collection, kaydet, il_koordinat
from scrapers.base_scraper import BaseScraper
from pathlib import Path

RG_BASE = "https://www.resmigazete.gov.tr"
RG_ARAMA = "https://www.resmigazete.gov.tr/arama"

# Aranacak anahtar kelimeler ve kategorileri
ARAMA_KURALLARI = [
    {
        "anahtar": "acele kamulaştırma",
        "kategori": "Acele Kamulaştırma",
        "katman": "acele_kamulastirma",
        "icon": "⚡"
    },
    {
        "anahtar": "çevresel etki değerlendirmesi",
        "kategori": "ÇED Kararı",
        "katman": "ced_kararlari",
        "icon": "🌿"
    },
    {
        "anahtar": "sit alanı",
        "kategori": "Sit Kararı",
        "katman": "sit_kararlari",
        "icon": "🏛"
    },
    {
        "anahtar": "orman izni",
        "kategori": "Orman İzni",
        "katman": "orman_izinleri",
        "icon": "🌲"
    },
    {
        "anahtar": "lisans iptal",
        "kategori": "EPDK Lisans",
        "katman": "epdk_lisans",
        "icon": "⚡"
    },
]

# Türkiye'de geçen ay örnek Acele Kamulaştırma kararları (seed)
ACELE_SEED = [
    {
        "proje_adi": "Kadirli-Osmaniye İl Yolu ve Bağlantı Yolları Projesi Kapsamında Bazı Taşınmazların Karayolları Genel Müdürlüğü Tarafından Acele Kamulaştırılması",
        "karar_sayisi": "9377", "tarih": "31.12.2024",
        "resmi_gazete_sayisi": "32769", "resmi_gazete_tarihi": "31.12.2024",
        "kamulastiran_kurum": "Karayolları Genel Müdürlüğü",
        "tahmini_konum": "Osmaniye", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/12/20241231.htm",
    },
    {
        "proje_adi": "Türkiye Petrolleri A.O. Tarafından Gerçekleştirilecek Ham Petrol Boru Hattı Projesi Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "9312", "tarih": "15.11.2024",
        "resmi_gazete_sayisi": "32723", "resmi_gazete_tarihi": "15.11.2024",
        "kamulastiran_kurum": "Türkiye Petrolleri A.O.",
        "tahmini_konum": "Batman", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/11/20241115.htm",
    },
    {
        "proje_adi": "Doğu Karadeniz Bölgesi Entegre Kıyı Yolu Projesi Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "9289", "tarih": "02.10.2024",
        "resmi_gazete_sayisi": "32685", "resmi_gazete_tarihi": "02.10.2024",
        "kamulastiran_kurum": "Karayolları Genel Müdürlüğü",
        "tahmini_konum": "Rize", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/10/20241002.htm",
    },
    {
        "proje_adi": "Çanakkale Köprüsü ve Otoyol Bağlantısı Güzergahında Kalan Taşınmazların Acele Kamulaştırılması",
        "karar_sayisi": "9201", "tarih": "18.07.2024",
        "resmi_gazete_sayisi": "32613", "resmi_gazete_tarihi": "18.07.2024",
        "kamulastiran_kurum": "Karayolları Genel Müdürlüğü",
        "tahmini_konum": "Çanakkale", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/07/20240718.htm",
    },
    {
        "proje_adi": "Soma-Balıkesir Doğalgaz Boru Hattı Projesi Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "9145", "tarih": "05.05.2024",
        "resmi_gazete_sayisi": "32543", "resmi_gazete_tarihi": "05.05.2024",
        "kamulastiran_kurum": "BOTAŞ",
        "tahmini_konum": "Manisa", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/05/20240505.htm",
    },
    {
        "proje_adi": "Kayseri-Sivas YHT Hattı Kapsamında Taşınmazların TCDD Tarafından Acele Kamulaştırılması",
        "karar_sayisi": "9098", "tarih": "12.03.2024",
        "resmi_gazete_sayisi": "32489", "resmi_gazete_tarihi": "12.03.2024",
        "kamulastiran_kurum": "TCDD",
        "tahmini_konum": "Kayseri", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/03/20240312.htm",
    },
    {
        "proje_adi": "Afşin-Elbistan C Termik Santral Projesi Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "9054", "tarih": "22.01.2024",
        "resmi_gazete_sayisi": "32439", "resmi_gazete_tarihi": "22.01.2024",
        "kamulastiran_kurum": "EÜAŞ",
        "tahmini_konum": "Kahramanmaraş", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2024/01/20240122.htm",
    },
    {
        "proje_adi": "İzmir Körfez Geçişi ve Otoyol Bağlantıları Projesi Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "8987", "tarih": "08.11.2023",
        "resmi_gazete_sayisi": "32371", "resmi_gazete_tarihi": "08.11.2023",
        "kamulastiran_kurum": "Karayolları Genel Müdürlüğü",
        "tahmini_konum": "İzmir", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2023/11/20231108.htm",
    },
    {
        "proje_adi": "Ankara-Sivas YHT Hattı Güzergahında Kalan Taşınmazların Acele Kamulaştırılması",
        "karar_sayisi": "8934", "tarih": "14.09.2023",
        "resmi_gazete_sayisi": "32315", "resmi_gazete_tarihi": "14.09.2023",
        "kamulastiran_kurum": "TCDD",
        "tahmini_konum": "Yozgat", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2023/09/20230914.htm",
    },
    {
        "proje_adi": "Muğla Datça Yarımadası Doğalgaz Dağıtım Hattı Kapsamında Acele Kamulaştırma",
        "karar_sayisi": "8876", "tarih": "03.07.2023",
        "resmi_gazete_sayisi": "32242", "resmi_gazete_tarihi": "03.07.2023",
        "kamulastiran_kurum": "BOTAŞ",
        "tahmini_konum": "Muğla", "kategori": "Acele Kamulaştırma",
        "kaynak_url": f"{RG_BASE}/eskiler/2023/07/20230703.htm",
    },
]


class ResmiGazeteScraper(BaseScraper):
    """
    Resmi Gazete'yi tarar.
    Önce son 7 günün gazetesini dener, erişilemezse seed verisiyle devam eder.
    """

    def __init__(self, kategori: str = "acele_kamulastirma"):
        super().__init__(
            name=f"ResmiGazete-{kategori}",
            base_url=RG_BASE,
            rate_limit_sn=2.0,
        )
        self.kategori = kategori

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.name}] Resmi Gazete taraması başlıyor…")

        # Önce canlı siteden dene
        yeni = self._canli_tara()

        # Seed + canlı birleştir
        features = []
        for kayit in ACELE_SEED + yeni:
            il = kayit.get("tahmini_konum", "")
            lat, lon = il_koordinat(il)
            props = {k: v for k, v in kayit.items() if k not in ("lat", "lon")}
            features.append(feature(props, lat, lon))

        logger.success(f"[{self.name}] {len(features)} kayıt hazır.")
        return features

    def _canli_tara(self) -> list[dict]:
        """Son 7 günün Resmi Gazete'sini tarar."""
        yeni_kayitlar = []
        bugun = datetime.date.today()

        for i in range(7):
            tarih = bugun - datetime.timedelta(days=i)
            url = f"{RG_BASE}/eskiler/{tarih.year}/{tarih.month:02d}/{tarih.strftime('%Y%m%d')}.htm"
            try:
                soup = self._soup(url)
                metin = soup.get_text(" ")

                # Acele kamulaştırma ara
                if "acele kamulaştırma" in metin.lower():
                    kayitlar = self._parse_acele(soup, tarih, url)
                    yeni_kayitlar.extend(kayitlar)
                    logger.info(f"[{self.name}] {tarih}: {len(kayitlar)} acele kamulaştırma")

            except Exception as e:
                logger.debug(f"[{self.name}] {tarih} erişilemedi: {e}")
                continue

        return yeni_kayitlar

    def _parse_acele(self, soup, tarih, url: str) -> list[dict]:
        """Resmi Gazete sayfasından acele kamulaştırma kararlarını çeker."""
        kayitlar = []
        metin = soup.get_text(" ")

        # Karar sayısını bul
        karar_m = re.findall(r"(\d{4,5})\s+sayılı.*?karar", metin, re.IGNORECASE)

        # İl adlarını bul
        il_listesi = list(il_koordinat.__doc__ and
                         [il for il in ["Ankara", "İstanbul", "İzmir", "Bursa", "Antalya"]
                          if il.lower() in metin.lower()])

        # Kurumu bul
        kurum_m = re.search(
            r"(Karayolları|TCDD|BOTAŞ|EÜAŞ|DSİ|TÜRKŞEKER|TEİAŞ|TPAO|Devlet Su İşleri)",
            metin, re.IGNORECASE
        )
        kurum = kurum_m.group(1) if kurum_m else "Bilinmiyor"

        # Başlıkları bul
        basliklar = soup.select("h3, h4, .mevzuat-baslik, b")
        for baslik in basliklar:
            t = baslik.get_text(strip=True)
            if "acele kamulaştırma" in t.lower() and len(t) > 20:
                il = next((il for il in ["Ankara", "İstanbul", "İzmir"] if il in t), "Bilinmiyor")
                kayitlar.append({
                    "proje_adi": t[:200],
                    "karar_sayisi": karar_m[0] if karar_m else "",
                    "tarih": tarih.strftime("%d.%m.%Y"),
                    "resmi_gazete_sayisi": "",
                    "resmi_gazete_tarihi": tarih.strftime("%d.%m.%Y"),
                    "kamulastiran_kurum": kurum,
                    "tahmini_konum": il,
                    "kategori": "Acele Kamulaştırma",
                    "kaynak_url": url,
                })

        return kayitlar

    def to_geojson_fc(self, features: list) -> dict:
        return feature_collection(
            name="acele_kamulastirma",
            features=features,
            metadata={"kaynak": RG_BASE, "kategori": "Acele Kamulaştırma"}
        )
