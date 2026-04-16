"""
main_v2.py - Genişletilmiş Tarama Orkestratörü (tarih filtreli)

Kullanım:
    python main_v2.py
    python main_v2.py --baslangic 2024-01-01
    python main_v2.py --baslangic 2024-01-01 --bitis 2024-12-31
    python main_v2.py --sadece-yeni
    python main_v2.py --scrapers acele ced --dry-run
"""

import sys
import argparse
import datetime
from pathlib import Path
from loguru import logger

from scrapers.jeotermal_scraper import JeotermalScraper
from scrapers.milli_park_scraper import MilliParkScraper
from scrapers.ockkb_scraper import OCKBScraper
from scrapers.ramsar_scraper import RamsarScraper
from scrapers.maden_scraper import MadenScraper
from scrapers.resmi_gazete_scraper import ResmiGazeteScraper
from scrapers.ced_epdk_scraper import CEDScraper, EPDKScraper, OGMScraper, DSIScraper
from scrapers.kurumsal_scraper import (
    MAPEGRuhsatScraper, TOKIScraper, BOTASScraper,
    MilliEmlakScraper, UABScraper, KulturSitScraper,
    MPGMScraper, EKAPScraper
)
from utils import feature_collection, kaydet, yeni_mi

DATA_DIR = Path("data")
LOG_DIR = Path("logs")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "tarama_{time:YYYY-MM-DD}.log",
    rotation="1 day", retention="30 days",
    level="INFO", encoding="utf-8",
)

TARAYICILAR = {
    "jes":        (JeotermalScraper,   "jeotermal_santraller.geojson",    "jeotermal_santraller"),
    "milli_park": (MilliParkScraper,   "milli_parklar.geojson",           "milli_parklar"),
    "ockkb":      (OCKBScraper,        "ockkb.geojson",                   "ockkb"),
    "ramsar":     (RamsarScraper,      "ramsar_sulak_alanlar.geojson",    "ramsar_sulak_alanlar"),
    "maden":      (MadenScraper,       "madenleri.geojson",               "madenleri"),
    "acele":      (ResmiGazeteScraper, "acele_kamulastirma.geojson",      "acele_kamulastirma"),
    "ced":        (CEDScraper,         "ced_kararlari.geojson",           "ced_kararlari"),
    "epdk":       (EPDKScraper,        "epdk_lisans.geojson",             "epdk_lisans"),
    "ogm":        (OGMScraper,         "orman_izinleri.geojson",          "orman_izinleri"),
    "dsi":        (DSIScraper,         "dsi_projeler.geojson",            "dsi_projeler"),
    "mapeg":      (MAPEGRuhsatScraper, "mapeg_ruhsatlar.geojson",         "mapeg_ruhsatlar"),
    "toki":       (TOKIScraper,        "toki_ihaleler.geojson",           "toki_ihaleler"),
    "botas":      (BOTASScraper,       "botas_boru.geojson",              "botas_boru"),
    "milli_emlak":(MilliEmlakScraper,  "milli_emlak.geojson",             "milli_emlak"),
    "uab":        (UABScraper,         "kiyi_izinleri.geojson",           "kiyi_izinleri"),
    "sit":        (KulturSitScraper,   "sit_kararlari.geojson",           "sit_kararlari"),
    "mpgm":       (MPGMScraper,        "imar_plan_degisiklikleri.geojson","imar_plan_degisiklikleri"),
    "ekap":       (EKAPScraper,        "ekap_ihaleler.geojson",           "ekap_ihaleler"),
}


def calistir(secili=None, dry_run=False,
             baslangic=None, bitis=None, sadece_yeni=False):

    t0 = datetime.datetime.now(datetime.timezone.utc)
    logger.info(f"=== Tarama basladi: {t0.isoformat()} ===")
    if baslangic or bitis:
        logger.info(f"    Tarih filtresi: {baslangic or 'baslangic'} -> {bitis or 'bugun'}")
    if sadece_yeni:
        logger.info("    Mod: sadece son 7 gun")

    hedefler = {k: v for k, v in TARAYICILAR.items()
                if secili is None or k in secili}

    sonuclar = {}
    for ad, (Sinif, dosya, fc_adi) in hedefler.items():
        logger.info(f"-- [{ad}] basliyor --")
        try:
            t = Sinif()
            ham = t.scrape()
            if not ham:
                logger.warning(f"[{ad}] veri donmedi.")
                sonuclar[ad] = {"basarili": False, "nokta": 0, "yeni": 0, "dosya": dosya}
                continue

            fc = feature_collection(fc_adi, ham, baslangic=baslangic, bitis=bitis)

            if sadece_yeni:
                fc["features"] = [
                    f for f in fc["features"]
                    if f.get("properties", {}).get("yeni", False)
                ]

            yeni_sayisi = sum(
                1 for f in fc["features"]
                if f.get("properties", {}).get("yeni", False)
            )

            if not dry_run:
                kaydet(fc, DATA_DIR / dosya)
                logger.success(
                    f"[{ad}] ok {len(fc['features'])} nokta ({yeni_sayisi} yeni son 7 gun)"
                )
            else:
                logger.info(
                    f"[{ad}] DRY-RUN {len(fc['features'])} nokta ({yeni_sayisi} yeni)"
                )

            sonuclar[ad] = {
                "basarili": True,
                "nokta": len(fc["features"]),
                "yeni": yeni_sayisi,
                "dosya": dosya
            }

        except Exception as e:
            logger.error(f"[{ad}] HATA: {e}", exc_info=True)
            sonuclar[ad] = {"basarili": False, "nokta": 0, "yeni": 0, "dosya": dosya}

    sure = (datetime.datetime.now(datetime.timezone.utc) - t0).total_seconds()
    logger.info(f"=== Tamamlandi: {sure:.1f} saniye ===")
    for ad, s in sonuclar.items():
        ikon = "ok" if s["basarili"] else "hata"
        logger.info(f"  {ikon} {ad:15s} -> {s['nokta']:4d} nokta ({s['yeni']} yeni) -> {s['dosya']}")

    if not dry_run:
        _github_push(sonuclar)

    return sonuclar


def _github_push(sonuclar):
    import os
    token = os.getenv("GITHUB_TOKEN")
    repo_adi = os.getenv("GITHUB_REPO")
    veri_klasoru = os.getenv("GITHUB_DATA_PATH", "data")
    if not token or not repo_adi:
        logger.warning("GITHUB_TOKEN veya GITHUB_REPO yok - push atlandi.")
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
    except Exception as e:
        logger.error(f"GitHub push: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrapers", nargs="+", choices=list(TARAYICILAR.keys()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--baslangic", default=None, help="YYYY-MM-DD")
    parser.add_argument("--bitis", default=None, help="YYYY-MM-DD")
    parser.add_argument("--sadece-yeni", action="store_true")
    args = parser.parse_args()

    sonuclar = calistir(
        secili=args.scrapers,
        dry_run=args.dry_run,
        baslangic=args.baslangic,
        bitis=args.bitis,
        sadece_yeni=args.sadece_yeni,
    )
    basarisiz = [k for k, s in sonuclar.items() if not s["basarili"]]
    sys.exit(1 if basarisiz else 0)
