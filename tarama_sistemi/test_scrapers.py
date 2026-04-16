"""
tests/test_scrapers.py

Temel entegrasyon testleri — network gerektirmez (mock kullanır).
Çalıştır: pytest tests/ -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


# ── Yardımcılar ──────────────────────────────────────────────────────────────
def sahte_soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")


# ── BaseScraper ───────────────────────────────────────────────────────────────
class TestBaseScraper:
    def test_to_geojson_bos(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        with patch.object(JeotermalScraper, '__init__', lambda s: None):
            js = JeotermalScraper()
            js.name = "test"
            js.base_url = "http://test.example"
            geojson = js.to_geojson([])
        assert geojson["type"] == "FeatureCollection"
        assert geojson["features"] == []

    def test_to_geojson_koordinatsiz_atlanir(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        with patch.object(JeotermalScraper, '__init__', lambda s: None):
            js = JeotermalScraper()
            js.name = "test"
            js.base_url = "http://test.example"
            geojson = js.to_geojson([
                {"ad": "A", "lat": None, "lon": None},
                {"ad": "B", "lat": 38.5, "lon": 27.1},
            ])
        # lat/lon=None olanlar dahil edilmemeli
        assert len(geojson["features"]) == 1
        assert geojson["features"][0]["properties"]["ad"] == "B"

    def test_to_geojson_koordinat_geometry(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        with patch.object(JeotermalScraper, '__init__', lambda s: None):
            js = JeotermalScraper()
            js.name = "test"
            js.base_url = "http://test.example"
            geojson = js.to_geojson([{"ad": "X", "lat": 39.0, "lon": 28.0}])
        feat = geojson["features"][0]
        assert feat["geometry"]["type"] == "Point"
        assert feat["geometry"]["coordinates"] == [28.0, 39.0]  # [lon, lat] sırası


# ── JeotermalScraper ──────────────────────────────────────────────────────────
class TestJeotermalScraper:
    HTML_ORNEGI = """
    <html><body>
    <h3>İşletmedeki Santral</h3>
    <table>
      <tr><th>Sıra</th><th>Ad</th><th>İl</th><th>Firma</th><th>Güç</th></tr>
      <tr><td>1</td><td><a href="/jes/germencik">Germencik JES</a></td>
          <td>Aydın</td><td>Güriş</td><td>165 MW</td></tr>
    </table>
    </body></html>
    """

    def test_guc_parse(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        assert JeotermalScraper._guc_parse("165 MW") == 165.0
        assert JeotermalScraper._guc_parse("24,5 MW") == 24.5
        assert JeotermalScraper._guc_parse("") is None

    def test_tablo_durumu_isletme(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        soup = sahte_soup("<h3>İşletmedeki Santral</h3><table></table>")
        tablo = soup.find("table")
        assert JeotermalScraper._tablo_durumu(tablo) == "İşletmede"

    def test_tablo_durumu_insaat(self):
        from scrapers.jeotermal_scraper import JeotermalScraper
        soup = sahte_soup("<h3>Yapım Halindeki Santral</h3><table></table>")
        tablo = soup.find("table")
        assert JeotermalScraper._tablo_durumu(tablo) == "İnşaat Halinde"


# ── RamsarScraper ─────────────────────────────────────────────────────────────
class TestRamsarScraper:
    def test_seed_verisi_14_alan(self):
        from scrapers.ramsar_scraper import RAMSAR_SEED
        assert len(RAMSAR_SEED) == 14, "Türkiye'de 14 Ramsar alanı olmalı"

    def test_seed_alanlari_koordinat_var(self):
        from scrapers.ramsar_scraper import _KOORD, RAMSAR_SEED
        for seed in RAMSAR_SEED:
            assert seed["ad"] in _KOORD, f"{seed['ad']} için koordinat eksik"

    def test_scrape_network_olmadan(self):
        from scrapers.ramsar_scraper import RamsarScraper
        with patch.object(RamsarScraper, '__init__', lambda s: None):
            rs = RamsarScraper()
            rs.name = "test"
            rs.base_url = "http://test.example"
            rs._geocode = lambda q, **kw: None

        with patch.object(rs, "_canli_kontrol", return_value=[]):
            with patch.object(rs, "_koord", return_value=(38.0, 32.0)):
                features = rs.scrape()

        assert len(features) == 14


# ── MadenScraper ──────────────────────────────────────────────────────────────
class TestMadenScraper:
    def test_seed_verisi_bos_degil(self):
        from scrapers.maden_scraper import MADEN_SEED
        assert len(MADEN_SEED) > 10

    def test_seed_koordinatlari_gecerli(self):
        from scrapers.maden_scraper import MADEN_SEED
        for m in MADEN_SEED:
            assert "lat" in m and "lon" in m, f"{m['ad']} için koordinat eksik"
            if m["lat"] is not None:
                assert 36 <= m["lat"] <= 43, f"{m['ad']} lat aralık dışı: {m['lat']}"
            if m["lon"] is not None:
                assert 25 <= m["lon"] <= 46, f"{m['ad']} lon aralık dışı: {m['lon']}"


# ── GeoJSON format doğrulama ───────────────────────────────────────────────────
class TestGeoJSONFormat:
    def test_geojson_crs(self):
        """Üretilen GeoJSON'larda CRS alanı olmalı."""
        from scrapers.jeotermal_scraper import JeotermalScraper
        with patch.object(JeotermalScraper, '__init__', lambda s: None):
            js = JeotermalScraper()
            js.name = "x"
            js.base_url = "http://x.example"
        geojson = js.to_geojson([{"lat": 39.0, "lon": 28.0, "ad": "test"}])
        # metadata içinde guncelleme tarihi olmalı
        assert "guncelleme" in geojson.get("metadata", {})

    def test_geojson_dosya_okunabilir(self, tmp_path):
        """Diske yazılan GeoJSON dosyası tekrar okunabilmeli."""
        cikti = tmp_path / "test.geojson"
        veri = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [28.0, 39.0]},
                    "properties": {"ad": "test"},
                }
            ],
        }
        cikti.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        geri = json.loads(cikti.read_text(encoding="utf-8"))
        assert geri["type"] == "FeatureCollection"
        assert len(geri["features"]) == 1
