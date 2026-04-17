"""
main.py — Tarama Orkestratörü

def deduplicate(features: list) -> list:
    """Aynı koordinata veya aynı ada sahip tekrar eden kayıtları temizler."""
    goruldu = set()
    temiz = []
    for f in features:
        props = f.get("properties", {})
        geo = f.get("geometry", {})
        coords = tuple(geo.get("coordinates", [])) if geo else ()
        ad = props.get("ad") or props.get("name") or props.get("adi") or ""
        anahtar = (coords, ad.strip().lower())
        if anahtar not in goruldu:
            goruldu.add(anahtar)
            temiz.append(f)
    return temiz

Tüm tarayıcıları çalıştırır, çıktıları birleştirir ve
GitHub'daki veri deposunu günceller.

Kullanım:
    python main.py                     # tüm tarayıcılar
    python main.py --scrapers jes ramsar  # seçili tarayıcılar
    python main.py --dry-run           # GitHub'a push etmeden çalıştır
"""

import sys
import json
import argparse
import datetime
from pathlib import Path
from loguru import logger

from scrapers.jeotermal_scraper import JeotermalScraper
from scrapers.milli_park_scraper import MilliParkScraper
from scrapers.ockkb_scraper import OCKBScraper
from scrapers.ramsar_scraper import RamsarScraper
from scrapers.maden_scraper import MadenScraper

# ── Yapılandırma ────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
LOG_DIR  = Path("logs")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "tarama_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="14 days",
    level="INFO",
    encoding="utf-8",
)

# Tarayıcı kaydı: kısa_ad → (Sınıf, çıktı_dosyası, metadata)
TARAYICILAR = {
    "jes": (
        JeotermalScraper,
        "jeotermal_santraller.geojson",
        {"açıklama": "Türkiye JES listesi", "kategori": "Enerji"},
    ),
    "milli_park": (
        MilliParkScraper,
        "milli_parklar.geojson",
        {"açıklama": "Türkiye Milli Parkları", "kategori": "Koruma"},
    ),
    "ockkb": (
        OCKBScraper,
        "ockkb.geojson",
        {"açıklama": "Özel Çevre Koruma Bölgeleri", "kategori": "Koruma"},
    ),
    "ramsar": (
        RamsarScraper,
        "ramsar_sulak_alanlar.geojson",
        {"açıklama": "Türkiye Ramsar Sulak Alanları", "kategori": "Koruma"},
    ),
    "maden": (
        MadenScraper,
        "madenleri.geojson",
        {"açıklama": "Türkiye Madenleri", "kategori": "Endüstri"},
    ),
}


def tarayici_calistir(ad: str, sinif, dosya: str, meta: dict, dry_run: bool) -> dict | None:
    """Tek bir tarayıcıyı çalıştırır; GeoJSON üretir ve diske yazar."""
    logger.info(f"━━ [{ad}] başlıyor ━━")
    try:
        tarayici = sinif()
        ham_veri = tarayici.scrape()

        if not ham_veri:
            logger.warning(f"[{ad}] veri dönmedi — dosya güncellenmedi.")
            return None

        geojson = tarayici.to_geojson(ham_veri, metadata=meta)
        cikti = DATA_DIR / dosya
        
        onceki = len(geojson["features"])
        geojson["features"] = deduplicate(geojson["features"])
        if len(geojson["features"]) < onceki:
            logger.warning(f"[{ad}] {onceki - len(geojson['features'])} duplicate temizlendi.")

        if not dry_run:
            cikti.write_text(
                json.dumps(geojson, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.success(f"[{ad}] ✓ {len(geojson['features'])} nokta → {cikti}")
        else:
            logger.info(f"[{ad}] DRY-RUN — {len(geojson['features'])} nokta bulundu, yazılmadı.")

        return geojson

    except Exception as e:
        logger.error(f"[{ad}] HATA: {e}", exc_info=True)
        return None


def calistir(secili: list[str] | None = None, dry_run: bool = False):
    baslangic = datetime.datetime.utcnow()
    logger.info(f"=== Tarama başladı: {baslangic.isoformat()}Z ===")

    hedefler = {
        ad: v for ad, v in TARAYICILAR.items()
        if secili is None or ad in secili
    }

    sonuclar = {}
    for ad, (sinif, dosya, meta) in hedefler.items():
        geojson = tarayici_calistir(ad, sinif, dosya, meta, dry_run)
        sonuclar[ad] = {
            "basarili": geojson is not None,
            "nokta_sayisi": len(geojson["features"]) if geojson else 0,
            "dosya": dosya,
        }

    # Özet rapor
    bitis = datetime.datetime.utcnow()
    sure = (bitis - baslangic).total_seconds()
    logger.info(f"=== Tarama tamamlandı: {sure:.1f} saniye ===")

    for ad, s in sonuclar.items():
        durum = "✓" if s["basarili"] else "✗"
        logger.info(f"  {durum} {ad:12s} → {s['nokta_sayisi']} nokta → {s['dosya']}")

    # GitHub'a push (dry_run değilse)
    if not dry_run:
        _github_push(sonuclar)

    return sonuclar


def _github_push(sonuclar: dict):
    """Değişen GeoJSON dosyalarını GitHub repo'ya yükler."""
    import os
    token = os.getenv("GITHUB_TOKEN")
    repo_adi = os.getenv("GITHUB_REPO")          # örn: "ekopoli/albatur-papila"
    veri_klasoru = os.getenv("GITHUB_DATA_PATH", "data")  # repo içi hedef klasör

    if not token or not repo_adi:
        logger.warning("GITHUB_TOKEN veya GITHUB_REPO tanımlı değil — push atlandı.")
        return

    try:
        from github import Github, GithubException
        g = Github(token)
        repo = g.get_repo(repo_adi)

        for ad, s in sonuclar.items():
            if not s["basarili"]:
                continue
            dosya_yolu = DATA_DIR / s["dosya"]
            if not dosya_yolu.exists():
                continue

            icerik = dosya_yolu.read_text(encoding="utf-8")
            uzak_yol = f"{veri_klasoru}/{s['dosya']}"
            commit_mesaji = (
                f"🌿 Otomatik güncelleme: {ad} "
                f"({s['nokta_sayisi']} nokta) "
                f"[{datetime.datetime.utcnow().strftime('%Y-%m-%d')}]"
            )

            try:
                mevcut = repo.get_contents(uzak_yol)
                repo.update_file(uzak_yol, commit_mesaji, icerik, mevcut.sha)
                logger.success(f"GitHub güncellendi: {uzak_yol}")
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(uzak_yol, commit_mesaji, icerik)
                    logger.success(f"GitHub'a yeni dosya oluşturuldu: {uzak_yol}")
                else:
                    raise

    except ImportError:
        logger.warning("PyGithub kurulu değil — pip install PyGithub")
    except Exception as e:
        logger.error(f"GitHub push hatası: {e}", exc_info=True)


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Türkiye Çevre Veri Tarayıcı")
    parser.add_argument(
        "--scrapers", nargs="+",
        choices=list(TARAYICILAR.keys()),
        help="Çalıştırılacak tarayıcılar (boş = tümü)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Gerçekten yazmaz/push etmez — test için",
    )
    args = parser.parse_args()
    sonuclar = calistir(secili=args.scrapers, dry_run=args.dry_run)

    basarisiz = [ad for ad, s in sonuclar.items() if not s["basarili"]]
    sys.exit(1 if basarisiz else 0)
