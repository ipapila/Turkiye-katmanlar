"""
scrapers/selenium_scraper.py

JavaScript gerektiren sayfalar için Selenium tabanlı tarayıcı.

Kullanım alanları:
  - MAPEG ruhsat haritası (https://www.mapeg.gov.tr)
  - MTA interaktif maden yatakları haritası
  - enerjiatlasi.com'un dinamik grafik bileşenleri

Headless Chrome kullanır — sunucu (GitHub Actions / VPS) ortamında çalışır.
"""

import time
import json
from typing import Optional
from loguru import logger

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def chrome_driver(headless: bool = True) -> "webdriver.Chrome":
    """
    GitHub Actions / Docker ortamında çalışan headless Chrome sürücüsü.
    webdriver_manager Chrome versiyonunu otomatik indirir.
    """
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("selenium ve webdriver-manager kurulu değil: pip install selenium webdriver-manager")

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")       # Chrome 112+
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=tr")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Görsel işleme kapatılır → hız artar
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
    })

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(45)
    return driver


class MapegScraper:
    """
    MAPEG e-Maden sistemi — ruhsat bazında il/koordinat taraması.

    NOT: MAPEG'in resmi API'si yoktur. Bu tarayıcı, halka açık
    "istatistik" sayfasından il bazlı veriye ulaşır.
    """

    STATS_URL = "https://www.mapeg.gov.tr/istatistik.aspx"

    def scrape(self) -> list[dict]:
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium kurulu değil — MAPEG taraması atlandı.")
            return []

        logger.info("[MAPEG] Selenium taraması başlıyor…")
        driver = chrome_driver()
        features = []

        try:
            driver.get(self.STATS_URL)
            # Sayfanın yüklenmesini bekle
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            time.sleep(2)

            # Tablo satırlarını oku
            satirlar = driver.find_elements(By.CSS_SELECTOR, "table tr")
            for satir in satirlar[1:]:
                hücreler = satir.find_elements(By.TAG_NAME, "td")
                if len(hücreler) < 3:
                    continue
                il = hücreler[0].text.strip()
                ruhsat_sayisi = hücreler[1].text.strip()
                features.append({
                    "il": il,
                    "ruhsat_sayisi": ruhsat_sayisi,
                    "kategori": "MAPEG_Ruhsat_İstatistik",
                    "lat": None,
                    "lon": None,
                })

        except TimeoutException:
            logger.warning("[MAPEG] Sayfa zaman aşımı.")
        except Exception as e:
            logger.error(f"[MAPEG] Selenium hatası: {e}")
        finally:
            driver.quit()

        logger.success(f"[MAPEG] {len(features)} il istatistiği alındı.")
        return features


class MtaMineScraper:
    """
    MTA Genel Müdürlüğü maden yatakları sayfası.
    Statik HTML + PDF bağlantıları içerir; Selenium ile navigasyon yapılır.
    """

    BASE_URL = "https://www.mta.gov.tr/v3.0/hizmetler/maden-yataklari"

    def scrape(self) -> list[dict]:
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium kurulu değil — MTA taraması atlandı.")
            return []

        logger.info("[MTA] Selenium taraması başlıyor…")
        driver = chrome_driver()
        features = []

        try:
            driver.get(self.BASE_URL)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href]"))
            )
            time.sleep(1.5)

            # Bağlantı listesinden maden haritası PDF'lerini ve harita sayfalarını al
            linkler = driver.find_elements(By.CSS_SELECTOR, "a")
            for link in linkler:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if "harita" in text.lower() or "maden" in text.lower():
                    features.append({
                        "ad": text,
                        "url": href,
                        "kategori": "MTA_Harita_Kaynağı",
                        "lat": None,
                        "lon": None,
                    })

        except Exception as e:
            logger.error(f"[MTA] Selenium hatası: {e}")
        finally:
            driver.quit()

        logger.success(f"[MTA] {len(features)} harita kaynağı bulundu.")
        return features
