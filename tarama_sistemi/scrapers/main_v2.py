"""
main_v2.py — Genişletilmiş Tarama Orkestratörü

Tüm kategorileri tarar ve GeoJSON formatında diske yazar.

Kullanım:
    python main_v2.py                            # tüm tarayıcılar
    python main_v2.py --scrapers acele ced epdk  # seçili
    python main_v2.py --dry-run                  # test
"""

import sys
import json
import argparse
import datetime
from pathlib import Path
from loguru import logger

# Mevcut tarayıcılar
from scrapers.jeotermal_scraper import JeotermalScraper
from scrapers.milli_park_scraper import MilliParkScraper
from scrapers.ockkb_scraper import OCKBScraper
from scrapers.ramsar_scraper import RamsarScraper
from scrapers.maden_scraper import MadenScraper

# Yeni tarayıcılar
from scrapers.resmi_gazete_scraper import ResmiGazeteScraper
from scrapers.ced_epdk_scraper import CEDScraper, EPDKScraper, OGMScraper, DSIScraper
from scrapers.kurumsal_scraper import (
    MAPEGRuhsatScraper, TOKIScraper, BOTASScraper,
    MilliEmlakScraper, UABScraper, KulturSitScraper,
    MPGMScraper, EKAPScraper
)
from utils import feature_collection, kaydet

DATA_DIR = Path("data")
LOG_DIR = Path("logs")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "tarama_{time:YYYY-MM-DD}.log",
    rotation="1 day", retention="14 days",
    level="INFO", encoding="utf-8",
)

# ── Tarayıcı Kaydı ───────────────────────────────────────────────────────────
# format: kisa_ad → (Sinif, dosya_adi, fc_adi, meta)
TARAYICILAR = {
    # Mevcut
    "jes":       (JeotermalScraper,  "jeotermal_santraller.geojson",   "jeotermal_santraller",   {"kategori": "Enerji"}),
    "milli_park":(MilliParkScraper,  "milli_parklar.geojson",           "milli_parklar",           {"kategori": "Koruma"}),
    "ockkb":     (OCKBScraper,       "ockkb.geojson",                   "ockkb",                   {"kategori": "Koruma"}),
    "ramsar":    (RamsarScraper,     "ramsar_sulak_alanlar.geojson",    "ramsar_sulak_alanlar",    {"kategori": "Koruma"}),
    "maden":     (MadenScraper,      "madenleri.geojson",               "madenleri",               {"kategori": "Endüstri"}),
    # Yeni
    "acele":     (ResmiGazeteScraper,"acele_kamulastirma.geojson",      "acele_kamulastirma",      {"kategori": "Kamulaştırma", "kaynak": "Resmi Gazete"}),
    "ced":       (CEDScraper,        "ced_kararlari.geojson",           "ced_kararlari",           {"kategori": "ÇED"}),
    "epdk":      (EPDKScraper,       "epdk_lisans.geojson",             "epdk_lisans",             {"kategori": "Enerji"}),
    "ogm":       (OGMScraper,        "orman_izinleri.geojson",          "orman_izinleri",          {"kategori": "Orman"}),
    "dsi":       (DSIScraper,        "dsi_projeler.geojson",            "dsi_projeler",            {"kategori": "Su"}),
    "mapeg":     (MAPEGRuhsatScraper,"mapeg_ruhsatlar.geojson",         "mapeg_ruhsatlar",         {"kategori": "Maden"}),
    "toki":      (TOKIScraper,       "toki_ihaleler.geojson",           "toki_ihaleler",           {"kategori": "İnşaat"}),
    "botas":     (BOTASScraper,      "botas_boru.geojson",              "botas_boru",              {"kategori": "Enerji"}),
    "milli_emlak":(MilliEmlakScraper,"milli_emlak.geojson",             "milli_emlak",             {"kategori": "Arazi"}),
    "uab":       (UABScraper,        "kiyi_izinleri.geojson",           "kiyi_izinleri",           {"kategori": "Kıyı"}),
    "sit":       (KulturSitScraper,  "sit_kararlari.geojson",           "sit_kararlari",           {"kategori": "Kültür"}),
    "mpgm":      (MPGMScraper,       "imar_plan_degisiklikleri.geojson","imar_plan_degisiklikleri",{"kategori": "İmar"}),
    "ekap":      (EKAPScraper,       "ekap_ihaleler.geojson",           "ekap_ihaleler",           {"kategori": "İhale"}),
}


def calistir(secili=None, dry_run=False):
    baslangic = datetime.datetime.now(datetime.timezone.utc)
    logger.info(f"=== Tarama başladı: {baslangic.isoformat()} ===")

    hedefler = {k: v for k, v in TARAYICILAR.items()
                if secili is None or k in secili}

    sonuclar = {}
    for ad, (Sinif, dosya, fc_adi, meta) in hedefler.items():
        logger.info(f"━━ [{ad}] başlıyor ━━")
        try:
            tarayici = Sinif()
            ham = tarayici.scrape()
            if not ham:
                logger.warning(f"[{ad}] veri dönmedi.")
                sonuclar[ad] = {"basarili": False, "nokta": 0, "dosya": dosya}
                continue

            fc = feature_collection(fc_adi, ham, meta)
            if not dry_run:
                cikti = DATA_DIR / dosya
                kaydet(fc, cikti)
                logger.success(f"[{ad}] ✓ {len(ham)} nokta → {cikti}")
            else:
                logger.info(f"[{ad}] DRY-RUN — {len(ham)} nokta")

            sonuclar[ad] = {"basarili": True, "nokta": len(ham), "dosya": dosya}

        except Exception as e:
            logger.error(f"[{ad}] HATA: {e}", exc_info=True)
            sonuclar[ad] = {"basarili": False, "nokta": 0, "dosya": dosya}

    # Özet
    sure = (datetime.datetime.now(datetime.timezone.utc) - baslangic).total_seconds()
    logger.info(f"=== Tamamlandı: {sure:.1f} saniye ===")
    for ad, s in sonuclar.items():
        ikon = "✓" if s["basarili"] else "✗"
        logger.info(f"  {ikon} {ad:15s} → {s['nokta']:4d} nokta → {s['dosya']}")

    if not dry_run:
        _github_push(sonuclar)

    return sonuclar


def _github_push(sonuclar):
    import os
    token = os.getenv("GITHUB_TOKEN")
    repo_adi = os.getenv("GITHUB_REPO")
    veri_klasoru = os.getenv("GITHUB_DATA_PATH", "data")
    if not token or not repo_adi:
        logger.warning("GITHUB_TOKEN veya GITHUB_REPO tanımlı değil — push atlandı.")
        return
    try:
        from github import Github, GithubException
        g = Github(token)
        repo = g.get_repo(repo_adi)
        tarih = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        for ad, s in sonuclar.items():
            if not s["basarili"]:
                continue
            dosya_yolu = DATA_DIR / s["dosya"]
            if not dosya_yolu.exists():
                continue
            icerik = dosya_yolu.read_text(encoding="utf-8")
            uzak = f"{veri_klasoru}/{s['dosya']}"
            mesaj = f"Otomatik guncelleme: {ad} ({s['nokta']} nokta) [{tarih}]"
            try:
                mevcut = repo.get_contents(uzak)
                repo.update_file(uzak, mesaj, icerik, mevcut.sha)
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(uzak, mesaj, icerik)
                else:
                    raise
            logger.success(f"GitHub: {uzak} güncellendi")
    except Exception as e:
        logger.error(f"GitHub push hatası: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrapers", nargs="+", choices=list(TARAYICILAR.keys()))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sonuclar = calistir(secili=args.scrapers, dry_run=args.dry_run)
    basarisiz = [k for k, s in sonuclar.items() if not s["basarili"]]
    sys.exit(1 if basarisiz else 0)
