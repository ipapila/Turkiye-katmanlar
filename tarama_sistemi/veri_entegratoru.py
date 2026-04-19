"""
veri_entegratoru.py
====================
Mevcut scraper sisteminin çıktısını Ekoloji Haritası uygulamasının
(ipapila/Turkiye-katmanlar → data.json) formatına dönüştürür ve
GitHub'daki data.json dosyasını günceller.

Kullanım:
    python veri_entegratoru.py                        # tüm scraper'lar
    python veri_entegratoru.py --scrapers jes ramsar  # seçili
    python veri_entegratoru.py --dry-run              # dosya yazmadan test
"""

import os
import sys
import json
import random
import string
import time
import datetime
import argparse
from pathlib import Path
from loguru import logger

# ── Uygulama sabitleri ────────────────────────────────────────────────────────

REPO_OWNER = "ipapila"
REPO_NAME  = "Turkiye-katmanlar"
DATA_PATH  = "data.json"         # GitHub'daki hedef dosya

GECERLI_TIPLER = [
    "Ekolojik İhlal", "İklim Olayları", "Acele Kamulaştırma",
    "Kültür Varlığı", "Milli Park", "Özel Çevre Koruma Alanı",
    "Maden Ocağı", "Taş-Mermer Ocağı", "Termik Reaktör",
    "HES", "GES", "RES", "Nükleer Enerji", "Jeotermal",
    "Orman Alanı", "Sulak Alan", "Kıyı İhlalleri",
]

GECERLI_DURUMLAR = [
    "Aktif", "Planlama", "İptal", "Devam Ediyor",
    "Durduruldu", "Yargıda", "Kapatıldı",
]

# ── Tip eşleştirme tablosu ───────────────────────────────────────────────────
# Scraper'dan gelen "kategori" veya "proje_turu" alanını → app tip'ine çevirir

TIP_ESLESME = {
    # Doğrudan eşleşmeler
    "Jeotermal": "Jeotermal", "JES": "Jeotermal",
    "Milli Park": "Milli Park",
    "ÖÇKB": "Özel Çevre Koruma Alanı",
    "Ramsar": "Sulak Alan", "Sulak Alan": "Sulak Alan",
    "Maden": "Maden Ocağı", "Maden Ocağı": "Maden Ocağı",
    "Altın": "Maden Ocağı", "Bakır": "Maden Ocağı", "Krom": "Maden Ocağı",
    "Demir": "Maden Ocağı", "Linyit": "Maden Ocağı", "Taş Kömürü": "Maden Ocağı",
    "Bor": "Maden Ocağı", "Trona": "Maden Ocağı", "Petrol": "Maden Ocağı",
    "Doğalgaz": "Maden Ocağı",
    "Taş Ocağı": "Taş-Mermer Ocağı", "Mermer": "Taş-Mermer Ocağı",
    "Taş-Mermer Ocağı": "Taş-Mermer Ocağı",
    "Acele Kamulaştırma": "Acele Kamulaştırma",
    "RES": "RES", "GES": "GES", "HES": "HES",
    "Termik Santral": "Termik Reaktör", "Termik": "Termik Reaktör",
    "Termik Reaktör": "Termik Reaktör",
    "Orman İzni": "Orman Alanı", "Orman Alanı": "Orman Alanı",
    "Kıyı Yapısı İzni": "Kıyı İhlalleri", "Kıyı İhlalleri": "Kıyı İhlalleri",
    "Sit Kararı": "Kültür Varlığı", "Kültür Varlığı": "Kültür Varlığı",
    "ÇED Kararı": "Ekolojik İhlal",       # ÇED kararları → ihlal kategorisi
    "EPDK Lisans": "Ekolojik İhlal",
    "MAPEG Ruhsat": "Maden Ocağı",
    "MAPEG Jeotermal Ruhsatı": "Jeotermal",
    "MAPEG Petrol Ruhsatı": "Maden Ocağı",
    "TOKİ İhale": "Acele Kamulaştırma",
    "BOTAŞ Boru Hattı": "Ekolojik İhlal",
    "Milli Emlak İhale": "Ekolojik İhlal",
    "İmar Planı Değişikliği": "Ekolojik İhlal",
    "EKAP Kamu İhalesi": "Ekolojik İhlal",
    "DSİ HES Projesi": "HES",
    # Proje türü bazlı (ÇED/EPDK'dan gelen proje_turu)
    "Altın Madeni": "Maden Ocağı",
    "Sanayi": "Ekolojik İhlal",
}

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def uid() -> str:
    chars = string.ascii_lowercase + string.digits
    return "r" + "".join(random.choices(chars, k=9)) + str(int(time.time() * 1000))


def tip_belirle(ozellikler: dict) -> str:
    """Feature özelliklerinden uygun tip'i bulur."""
    # Önce doğrudan "tip" alanına bak
    if "tip" in ozellikler and ozellikler["tip"] in GECERLI_TIPLER:
        return ozellikler["tip"]

    # "kategori" alanına bak
    kategori = ozellikler.get("kategori", "")
    if kategori in TIP_ESLESME:
        return TIP_ESLESME[kategori]

    # "proje_turu" veya "tur" alanına bak
    for alan in ("proje_turu", "tur", "maden_turu", "boru_turu"):
        deger = ozellikler.get(alan, "")
        if deger in TIP_ESLESME:
            return TIP_ESLESME[deger]

    # Metinden çıkar
    metin = " ".join(str(v) for v in ozellikler.values()).lower()
    if "ramsar" in metin or "sulak alan" in metin:
        return "Sulak Alan"
    if "milli park" in metin:
        return "Milli Park"
    if "öçkb" in metin or "özel çevre" in metin:
        return "Özel Çevre Koruma Alanı"
    if "jeotermal" in metin or " jes" in metin:
        return "Jeotermal"
    if "rüzgar" in metin or " res " in metin:
        return "RES"
    if "güneş" in metin or " ges " in metin:
        return "GES"
    if "hidroelektrik" in metin or " hes " in metin:
        return "HES"
    if "termik" in metin:
        return "Termik Reaktör"
    if "maden" in metin or "altın" in metin or "bakır" in metin:
        return "Maden Ocağı"
    if "taş ocağı" in metin or "mermer" in metin:
        return "Taş-Mermer Ocağı"
    if "kamulaştırma" in metin:
        return "Acele Kamulaştırma"
    if "sit" in metin or "kültür" in metin or "arkeoloji" in metin:
        return "Kültür Varlığı"
    if "kıyı" in metin or "marina" in metin or "liman" in metin:
        return "Kıyı İhlalleri"
    if "orman" in metin:
        return "Orman Alanı"

    return "Ekolojik İhlal"  # varsayılan


def ad_belirle(ozellikler: dict) -> str:
    for alan in ("ad", "proje_adi", "name", "AD"):
        if ozellikler.get(alan):
            return str(ozellikler[alan])[:200]
    return "Bilinmiyor"


def il_belirle(ozellikler: dict) -> str:
    for alan in ("il", "IL", "province"):
        if ozellikler.get(alan):
            return str(ozellikler[alan]).split("/")[0].strip()
    return ""


def ilce_belirle(ozellikler: dict) -> str:
    for alan in ("ilce", "ilçe", "district"):
        if ozellikler.get(alan):
            return str(ozellikler[alan])
    return ""


def tarih_belirle(ozellikler: dict) -> str:
    """Çeşitli tarih alanlarından ISO tarih döndürür."""
    for alan in ("eklenme", "tarih_iso", "eklenme_tarihi"):
        v = ozellikler.get(alan, "")
        if v and len(v) >= 10:
            return v[:10]
    for alan in ("tarih", "ilan_tarihi", "ramsar_tarihi"):
        v = str(ozellikler.get(alan, ""))
        if not v:
            continue
        # "DD.MM.YYYY" → "YYYY-MM-DD"
        if len(v) == 10 and v[2] == ".":
            parcalar = v.split(".")
            return f"{parcalar[2]}-{parcalar[1]}-{parcalar[0]}"
        if len(v) >= 10 and v[4] == "-":
            return v[:10]
    return datetime.date.today().isoformat()


def alan_ha_belirle(ozellikler: dict) -> float:
    for alan in ("alan_ha", "alan_km2", "alan_m2"):
        v = ozellikler.get(alan)
        if v is not None:
            try:
                v = float(v)
                if alan == "alan_km2":
                    v = v * 100       # km² → ha
                elif alan == "alan_m2":
                    v = v / 10000     # m² → ha
                return round(v, 2)
            except (TypeError, ValueError):
                pass
    return 0


def kaynak_link_belirle(ozellikler: dict) -> str:
    for alan in ("kaynak_url", "kaynak_link", "link", "url"):
        v = ozellikler.get(alan, "")
        if v and v.startswith("http"):
            return v
    return ""


def kaynak_belirle(ozellikler: dict) -> str:
    for alan in ("kaynak", "firma", "proje_sahibi"):
        v = ozellikler.get(alan, "")
        if v:
            return str(v)
    return "Otomatik tarama"


def belge_no_belirle(ozellikler: dict) -> str:
    for alan in ("belge_no", "karar_sayisi", "ruhsat_no", "lisans_no",
                 "izin_no", "ihale_no", "karar_no", "ramsar_no"):
        v = ozellikler.get(alan, "")
        if v:
            return str(v)
    return ""


def aciklama_uret(ozellikler: dict, tip: str) -> str:
    """Anlamlı bir açıklama oluşturur."""
    parcalar = []
    if ozellikler.get("proje_turu") or ozellikler.get("tur"):
        parcalar.append(ozellikler.get("proje_turu") or ozellikler.get("tur"))
    if ozellikler.get("karar"):
        parcalar.append(f"Karar: {ozellikler['karar']}")
    if ozellikler.get("kurulu_guc_mw"):
        parcalar.append(f"{ozellikler['kurulu_guc_mw']} MW")
    if ozellikler.get("alan_ha"):
        parcalar.append(f"{ozellikler['alan_ha']} ha")
    if ozellikler.get("kamulastiran_kurum"):
        parcalar.append(ozellikler["kamulastiran_kurum"])
    if ozellikler.get("firma"):
        parcalar.append(ozellikler["firma"])
    if ozellikler.get("aciklama"):
        return str(ozellikler["aciklama"])
    return " · ".join(parcalar) if parcalar else tip


def feature_to_kayit(feature: dict) -> dict | None:
    """
    GeoJSON Feature'ı Ekoloji Haritası kayıt formatına dönüştürür.
    Koordinat yoksa None döner.
    """
    props = feature.get("properties", {})
    geom  = feature.get("geometry", {})

    # Koordinat çıkar
    if geom.get("type") == "Point":
        coords = geom.get("coordinates", [])
        if len(coords) >= 2:
            lng, lat = float(coords[0]), float(coords[1])
        else:
            return None
    elif props.get("lat") and props.get("lon"):
        lat = float(props["lat"])
        lng = float(props.get("lon") or props.get("lng", 0))
    else:
        return None

    # Türkiye sınırları dışında mı?
    if not (35.0 < lat < 43.0 and 25.0 < lng < 45.0):
        logger.warning(f"Koordinat Türkiye dışı, atlandı: {lat}, {lng}")
        return None

    tip = tip_belirle(props)

    return {
        "id":           uid(),
        "tip":          tip,
        "ad":           ad_belirle(props),
        "il":           il_belirle(props),
        "ilce":         ilce_belirle(props),
        "koordinatlar": {"lat": round(lat, 6), "lng": round(lng, 6)},
        "alan_ha":      alan_ha_belirle(props),
        "durum":        props.get("durum", "Aktif") if props.get("durum") in GECERLI_DURUMLAR else "Aktif",
        "belge_no":     belge_no_belirle(props),
        "eklenme":      tarih_belirle(props),
        "kaynak":       kaynak_belirle(props),
        "kaynak_link":  kaynak_link_belirle(props),
        "aciklama":     aciklama_uret(props, tip),
        "alt_kategori": props.get("alt_kategori") or props.get("kategori", ""),
    }


def duplikasyon_var_mi(yeni: dict, mevcut: list) -> bool:
    """Aynı ad + il + tip kombinasyonu zaten var mı?"""
    tolerans = 0.001
    for m in mevcut:
        if (m.get("ad", "").lower() == yeni["ad"].lower()
                and m.get("tip") == yeni["tip"]
                and m.get("il", "") == yeni["il"]):
            # Koordinat da yakınsa kesin duplikasyon
            mk = m.get("koordinatlar", {})
            yk = yeni["koordinatlar"]
            if (abs(mk.get("lat", 0) - yk["lat"]) < tolerans
                    and abs(mk.get("lng", 0) - yk["lng"]) < tolerans):
                return True
    return False


# ── Ana dönüştürücü ───────────────────────────────────────────────────────────

def scraper_ciktisini_donustur(scraper_adi: str,
                                features: list) -> list:
    """
    Bir scraper'ın ürettiği feature listesini kayıt listesine dönüştürür.
    features: GeoJSON Feature listesi (utils.feature() çıktısı)
    """
    kayitlar = []
    for f in features:
        # utils.feature() direkt dict döndürüyor, GeoJSON Feature formatında
        if isinstance(f, dict) and "geometry" in f:
            kayit = feature_to_kayit(f)
        elif isinstance(f, dict) and ("lat" in f or "lon" in f):
            # Bazı scraper'lar ham dict döndürüyor (lat/lon ayrı)
            kayit = feature_to_kayit({
                "properties": f,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        f.get("lon", f.get("lng", 0)),
                        f.get("lat", 0)
                    ]
                }
            })
        else:
            continue

        if kayit:
            kayitlar.append(kayit)

    logger.info(f"[{scraper_adi}] {len(features)} feature → {len(kayitlar)} kayıt")
    return kayitlar


def mevcut_datajson_yukle() -> list:
    """GitHub'dan mevcut data.json'ı indirir."""
    try:
        import urllib.request
        url = (f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
               f"/main/{DATA_PATH}?t={int(time.time())}")
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"Mevcut data.json alınamadı: {e} — boş liste ile başlanıyor.")
        return []


def github_a_kaydet(kayitlar: list):
    """data.json'ı GitHub'a yükler."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN yok — data.json yerel olarak kaydedildi.")
        Path("data.json").write_text(
            json.dumps(kayitlar, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    try:
        from github import Github, GithubException
        g = Github(token)
        repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
        icerik = json.dumps(kayitlar, ensure_ascii=False, indent=2)
        mesaj = (f"Otomatik güncelleme: {len(kayitlar)} kayıt "
                 f"[{datetime.date.today().isoformat()}]")
        try:
            mevcut = repo.get_contents(DATA_PATH)
            repo.update_file(DATA_PATH, mesaj, icerik, mevcut.sha)
            logger.success(f"GitHub güncellendi: {len(kayitlar)} kayıt.")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(DATA_PATH, mesaj, icerik)
                logger.success(f"GitHub'da data.json oluşturuldu: {len(kayitlar)} kayıt.")
            else:
                raise
    except Exception as e:
        logger.error(f"GitHub kayıt hatası: {e}")
        Path("data.json").write_text(
            json.dumps(kayitlar, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ── Ana akış ─────────────────────────────────────────────────────────────────

def calistir(secili: list = None, dry_run: bool = False):
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
        MPGMScraper, EKAPScraper,
    )

    TARAYICILAR = {
        "jes":        JeotermalScraper,
        "milli_park": MilliParkScraper,
        "ockkb":      OCKBScraper,
        "ramsar":     RamsarScraper,
        "maden":      MadenScraper,
        "acele":      ResmiGazeteScraper,
        "ced":        CEDScraper,
        "epdk":       EPDKScraper,
        "ogm":        OGMScraper,
        "dsi":        DSIScraper,
        "mapeg":      MAPEGRuhsatScraper,
        "toki":       TOKIScraper,
        "botas":      BOTASScraper,
        "milli_emlak":MilliEmlakScraper,
        "uab":        UABScraper,
        "sit":        KulturSitScraper,
        "mpgm":       MPGMScraper,
        "ekap":       EKAPScraper,
    }

    hedefler = {k: v for k, v in TARAYICILAR.items()
                if secili is None or k in secili}

    logger.info(f"=== Entegratör başladı: {len(hedefler)} scraper ===")

    # Mevcut data.json'ı yükle
    mevcut = mevcut_datajson_yukle()
    logger.info(f"Mevcut kayıt sayısı: {len(mevcut)}")

    yeni_kayitlar = []
    atlanan = 0

    for ad, Sinif in hedefler.items():
        logger.info(f"-- [{ad}] taranıyor --")
        try:
            t = Sinif()
            features = t.scrape()
            kayitlar = scraper_ciktisini_donustur(ad, features)

            for k in kayitlar:
                if duplikasyon_var_mi(k, mevcut + yeni_kayitlar):
                    atlanan += 1
                else:
                    yeni_kayitlar.append(k)
        except Exception as e:
            logger.error(f"[{ad}] HATA: {e}", exc_info=True)

    birlesik = mevcut + yeni_kayitlar
    logger.success(
        f"Tamamlandı: {len(mevcut)} mevcut + {len(yeni_kayitlar)} yeni = "
        f"{len(birlesik)} toplam ({atlanan} duplikasyon atlandı)"
    )

    # Tip dağılımı özeti
    from collections import Counter
    dagilim = Counter(k["tip"] for k in birlesik)
    for tip, sayi in dagilim.most_common():
        logger.info(f"  {tip:35s}: {sayi}")

    if not dry_run:
        github_a_kaydet(birlesik)
    else:
        Path("data_preview.json").write_text(
            json.dumps(birlesik[:20], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("DRY-RUN: data_preview.json yazıldı (ilk 20 kayıt).")

    return birlesik


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ekoloji Haritası veri entegratörü")
    parser.add_argument("--scrapers", nargs="+", help="Sadece bu scraper'ları çalıştır")
    parser.add_argument("--dry-run", action="store_true", help="GitHub'a yazmadan test et")
    args = parser.parse_args()

    calistir(secili=args.scrapers, dry_run=args.dry_run)
