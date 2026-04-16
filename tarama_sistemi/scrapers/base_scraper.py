"""
scrapers/base_scraper.py
Tüm tarayıcılar için temel sınıf.
"""

import time
import random
import requests
from abc import ABC, abstractmethod
from typing import Optional
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Türkçe tarayıcı başlıkları — yasaklanma riskini azaltır
HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
]


class BaseScraper(ABC):
    """
    Tüm tarayıcılar için temel sınıf.
    Retry, rate-limiting, loglama ve GeoJSON üretimi sağlar.
    """

    def __init__(
        self,
        name: str,
        base_url: str,
        rate_limit_sn: float = 2.0,
        jitter_sn: float = 1.0,
        timeout_sn: int = 30,
    ):
        self.name = name
        self.base_url = base_url
        self.rate_limit_sn = rate_limit_sn
        self.jitter_sn = jitter_sn
        self.timeout_sn = timeout_sn
        self.session = self._build_session()
        logger.info(f"[{self.name}] tarayıcı başlatıldı → {base_url}")

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(random.choice(HEADERS_POOL))
        return session

    def _polite_wait(self):
        """Sunucuya saygılı bekleme — kaba kuvvet taramasını önler."""
        wait = self.rate_limit_sn + random.uniform(0, self.jitter_sn)
        time.sleep(wait)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
        reraise=True,
    )
    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """HTTP GET — otomatik retry ve loglama ile."""
        self._polite_wait()
        logger.debug(f"[{self.name}] GET {url}")
        resp = self.session.get(url, params=params, timeout=self.timeout_sn)
        resp.raise_for_status()
        return resp

    def _soup(self, url: str, params: Optional[dict] = None) -> BeautifulSoup:
        """HTML sayfasını BeautifulSoup nesnesine çevirir."""
        resp = self._get(url, params=params)
        return BeautifulSoup(resp.text, "lxml")

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Veriyi toplar ve Feature listesi döndürür.
        Her eleman GeoJSON Feature özelliklerini taşır.
        """
        ...

    def to_geojson(self, features: list[dict], metadata: dict = None) -> dict:
        """Feature listesini tam GeoJSON FeatureCollection'a dönüştürür."""
        import datetime

        meta = {
            "kaynak": self.name,
            "url": self.base_url,
            "guncelleme": datetime.datetime.utcnow().isoformat() + "Z",
        }
        if metadata:
            meta.update(metadata)

        return {
            "type": "FeatureCollection",
            "metadata": meta,
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [f.get("lon", 0), f.get("lat", 0)],
                    },
                    "properties": {k: v for k, v in f.items() if k not in ("lat", "lon")},
                }
                for f in features
                if f.get("lat") and f.get("lon")
            ],
        }
