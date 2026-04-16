"""
utils.py — GeoJSON yardımcıları + tarih filtreleme
"""

import datetime
import json
from pathlib import Path


# ── Tarih yardımcıları ────────────────────────────────────────────────────────

def tarih_iso(tarih_str: str) -> str:
    """
    Farklı formatlardaki tarihi ISO 8601'e çevirir.
    "31.12.2024" → "2024-12-31"
    "2024-12-31" → "2024-12-31"
    """
    if not tarih_str:
        return ""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(tarih_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Sadece yıl varsa (örn. "2024")
    if tarih_str.strip().isdigit() and len(tarih_str.strip()) == 4:
        return f"{tarih_str.strip()}-01-01"
    return tarih_str


def yeni_mi(tarih_iso_str: str, gun: int = 7) -> bool:
    """Kayıt son X gün içinde mi eklendi?"""
    if not tarih_iso_str:
        return False
    try:
        t = datetime.date.fromisoformat(tarih_iso_str[:10])
        return (datetime.date.today() - t).days <= gun
    except (ValueError, TypeError):
        return False


def tarih_araliginda_mi(tarih_iso_str: str,
                         baslangic: str = None,
                         bitis: str = None) -> bool:
    """Kayıt belirtilen tarih aralığında mı?"""
    if not tarih_iso_str:
        return True  # tarih yoksa dahil et
    try:
        t = datetime.date.fromisoformat(tarih_iso_str[:10])
        if baslangic:
            if t < datetime.date.fromisoformat(baslangic):
                return False
        if bitis:
            if t > datetime.date.fromisoformat(bitis):
                return False
        return True
    except (ValueError, TypeError):
        return True


# ── GeoJSON üreticiler ────────────────────────────────────────────────────────

def feature(properties: dict, lat: float, lon: float) -> dict:
    """
    Tek bir GeoJSON Feature üretir.
    Otomatik olarak tarih_iso ve yeni alanlarını ekler.
    """
    props = dict(properties)

    # Tarih normalizasyonu
    ham_tarih = props.get("tarih", "")
    iso = tarih_iso(ham_tarih)
    props["tarih_iso"] = iso

    # Eklenme tarihi (scraper'ın çalıştığı gün)
    props["eklenme_tarihi"] = datetime.date.today().isoformat()

    # Yeni işareti (son 7 gün)
    props["yeni"] = yeni_mi(iso, gun=7)

    return {
        "type": "Feature",
        "properties": props,
        "geometry": {
            "type": "Point",
            "coordinates": [round(float(lon), 6), round(float(lat), 6)]
        }
    }


def feature_collection(name: str, features: list,
                        metadata: dict = None,
                        baslangic: str = None,
                        bitis: str = None) -> dict:
    """
    FeatureCollection üretir.
    baslangic/bitis verilirse sadece o aralıktaki kayıtları dahil eder.
    """
    # Tarih filtresi
    if baslangic or bitis:
        features = [
            f for f in features
            if tarih_araliginda_mi(
                f.get("properties", {}).get("tarih_iso", ""),
                baslangic, bitis
            )
        ]

    yeni_sayisi = sum(1 for f in features
                      if f.get("properties", {}).get("yeni", False))

    return {
        "type": "FeatureCollection",
        "name": name,
        "metadata": {
            "guncelleme": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "kayit_sayisi": len(features),
            "yeni_kayit_sayisi": yeni_sayisi,
            "filtre_baslangic": baslangic or "",
            "filtre_bitis": bitis or "",
            **(metadata or {})
        },
        "features": features
    }


def kaydet(fc: dict, dosya: Path):
    dosya.parent.mkdir(parents=True, exist_ok=True)
    dosya.write_text(
        json.dumps(fc, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def filtrele(fc: dict, baslangic: str = None, bitis: str = None,
             sadece_yeni: bool = False) -> dict:
    """
    Mevcut bir FeatureCollection'ı filtreler.
    Harita arayüzünden çağrılmak üzere tasarlanmıştır.
    """
    features = fc.get("features", [])

    if sadece_yeni:
        features = [f for f in features
                    if f.get("properties", {}).get("yeni", False)]
    elif baslangic or bitis:
        features = [
            f for f in features
            if tarih_araliginda_mi(
                f.get("properties", {}).get("tarih_iso", ""),
                baslangic, bitis
            )
        ]

    return {**fc, "features": features,
            "metadata": {**fc.get("metadata", {}),
                         "filtre_baslangic": baslangic or "",
                         "filtre_bitis": bitis or "",
                         "filtre_sonuc_sayisi": len(features)}}


# ── İl koordinat tablosu ─────────────────────────────────────────────────────

IL_KOORDINATLARI = {
    "Adana": (37.0000, 35.3213), "Adıyaman": (37.7648, 38.2786),
    "Afyonkarahisar": (38.7507, 30.5567), "Ağrı": (39.7191, 43.0503),
    "Aksaray": (38.3687, 34.0370), "Amasya": (40.6499, 35.8353),
    "Ankara": (39.9334, 32.8597), "Antalya": (36.8969, 30.7133),
    "Ardahan": (41.1105, 42.7022), "Artvin": (41.1828, 41.8183),
    "Aydın": (37.8560, 27.8416), "Balıkesir": (39.6484, 27.8826),
    "Bartın": (41.6344, 32.3375), "Batman": (37.8812, 41.1351),
    "Bayburt": (40.2552, 40.2249), "Bilecik": (40.1506, 29.9792),
    "Bingöl": (38.8854, 40.4981), "Bitlis": (38.3938, 42.1232),
    "Bolu": (40.7359, 31.6061), "Burdur": (37.7203, 30.2899),
    "Bursa": (40.1826, 29.0665), "Çanakkale": (40.1553, 26.4142),
    "Çankırı": (40.6013, 33.6134), "Çorum": (40.5506, 34.9556),
    "Denizli": (37.7765, 29.0864), "Diyarbakır": (37.9144, 40.2306),
    "Düzce": (40.8438, 31.1565), "Edirne": (41.6818, 26.5623),
    "Elazığ": (38.6810, 39.2264), "Erzincan": (39.7500, 39.5000),
    "Erzurum": (39.9043, 41.2679), "Eskişehir": (39.7767, 30.5206),
    "Gaziantep": (37.0662, 37.3833), "Giresun": (40.9128, 38.3895),
    "Gümüşhane": (40.4386, 39.4814), "Hakkari": (37.5744, 43.7408),
    "Hatay": (36.4018, 36.3498), "Iğdır": (39.9167, 44.0450),
    "Isparta": (37.7648, 30.5566), "İstanbul": (41.0082, 28.9784),
    "İzmir": (38.4192, 27.1287), "Kahramanmaraş": (37.5858, 36.9371),
    "Karabük": (41.2061, 32.6204), "Karaman": (37.1759, 33.2287),
    "Kars": (40.6013, 43.0975), "Kastamonu": (41.3887, 33.7827),
    "Kayseri": (38.7312, 35.4787), "Kırıkkale": (39.8468, 33.5153),
    "Kırklareli": (41.7333, 27.2167), "Kırşehir": (39.1425, 34.1709),
    "Kilis": (36.7184, 37.1212), "Kocaeli": (40.8533, 29.8815),
    "Konya": (37.8714, 32.4846), "Kütahya": (39.4167, 29.9833),
    "Malatya": (38.3552, 38.3095), "Manisa": (38.6191, 27.4289),
    "Mardin": (37.3212, 40.7245), "Mersin": (36.8000, 34.6333),
    "Muğla": (37.2153, 28.3636), "Muş": (38.7337, 41.4918),
    "Nevşehir": (38.6939, 34.6857), "Niğde": (37.9667, 34.6833),
    "Ordu": (40.9862, 37.8797), "Osmaniye": (37.0746, 36.2464),
    "Rize": (41.0201, 40.5234), "Sakarya": (40.6940, 30.4358),
    "Samsun": (41.2867, 36.3300), "Şanlıurfa": (37.1591, 38.7969),
    "Siirt": (37.9333, 41.9500), "Sinop": (42.0231, 35.1531),
    "Şırnak": (37.5164, 42.4611), "Sivas": (39.7477, 37.0179),
    "Tekirdağ": (40.9781, 27.5115), "Tokat": (40.3167, 36.5500),
    "Trabzon": (41.0015, 39.7178), "Tunceli": (39.1079, 39.5478),
    "Uşak": (38.6823, 29.4082), "Van": (38.4891, 43.4089),
    "Yalova": (40.6500, 29.2667), "Yozgat": (39.8181, 34.8147),
    "Zonguldak": (41.4564, 31.7987),
}


def il_koordinat(il_adi: str) -> tuple:
    il = il_adi.strip().split("/")[0].split("-")[0].strip()
    for anahtar, koord in IL_KOORDINATLARI.items():
        if anahtar.lower() in il.lower() or il.lower() in anahtar.lower():
            return koord
    return (39.0, 35.0)  # Türkiye ortası
