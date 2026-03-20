import os, json, time, random, requests, traceback, base64
from datetime import datetime

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = 'ipapila/Turkiye-katmanlar'
GITHUB_FILE  = 'data.json'
API_URL      = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
RAW_URL      = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_FILE}'

def github_headers():
    return {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }

def read_data():
    """Mevcut data.json'u GitHub'dan oku"""
    r = requests.get(RAW_URL + '?t=' + str(int(time.time())), timeout=30)
    if r.status_code == 404:
        return [], None
    r.raise_for_status()
    data = r.json()
    # SHA almak için API'ye sor
    r2 = requests.get(API_URL, headers=github_headers(), timeout=30)
    sha = r2.json().get('sha') if r2.ok else None
    return data, sha

def write_data(data, sha=None):
    """data.json'u GitHub'a yaz"""
    content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
    body = {
        'message': f'Otomatik guncelleme {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC',
        'content': content
    }
    if sha:
        body['sha'] = sha
    r = requests.put(API_URL, headers=github_headers(), json=body, timeout=60)
    if not r.ok:
        raise Exception(f'GitHub write failed: {r.status_code} {r.text[:200]}')
    return r.json().get('content', {}).get('sha')

# ── Yardımcı fonksiyonlar ────────────────────────────────────────
def uid():
    return 'auto_' + hex(random.randint(0, 0xffffff))[2:] + str(int(time.time()*1000))[-6:]

def today():
    return datetime.utcnow().strftime('%Y-%m-%d')

# Türkiye bounding box
TR_LAT = (35.8, 42.2)
TR_LNG = (25.7, 44.8)

def in_turkey(lat, lng):
    return TR_LAT[0] <= lat <= TR_LAT[1] and TR_LNG[0] <= lng <= TR_LNG[1]

ILCE_BOXES = {
    'Antalya': (36.0, 37.6, 29.0, 32.8),
    'Muğla':   (36.5, 37.5, 27.2, 29.5),
    'İzmir':   (37.5, 39.2, 25.8, 28.5),
    'Ankara':  (39.0, 40.5, 31.5, 33.5),
    'İstanbul':(40.8, 41.5, 27.9, 29.9),
    'Mersin':  (36.0, 37.5, 32.5, 35.0),
    'Adana':   (36.5, 38.0, 34.8, 36.5),
    'Hatay':   (35.8, 37.2, 35.8, 36.7),
    'Konya':   (36.8, 39.5, 31.5, 34.5),
    'Samsun':  (40.8, 41.8, 35.0, 37.0),
    'Trabzon': (40.5, 41.2, 39.2, 40.5),
    'Artvin':  (40.8, 41.6, 41.0, 42.5),
    'Rize':    (40.5, 41.2, 40.3, 41.4),
    'Şanlıurfa':(36.7,38.2,37.5,40.5),
    'Diyarbakır':(37.5,38.8,39.5,41.5),
    'Erzurum': (39.5, 40.8, 40.5, 42.5),
    'Kayseri': (37.5, 39.5, 34.5, 36.5),
    'Bursa':   (39.8, 40.5, 28.5, 30.0),
    'Balıkesir':(39.2,40.3,26.5,28.5),
    'Çanakkale':(39.5,40.5,25.9,27.5),
    'Aydın':   (37.3, 38.3, 27.0, 28.8),
    'Denizli': (37.3, 38.3, 28.5, 30.0),
    'Elazığ':  (38.3, 39.2, 38.5, 40.0),
    'Malatya': (37.8, 38.8, 37.5, 39.5),
    'Kastamonu':(41.0,42.0,32.5,34.5),
    'Tunceli': (38.5, 39.5, 39.0, 40.5),
}

def guess_il(lat, lng):
    for il, (la1, la2, ln1, ln2) in ILCE_BOXES.items():
        if la1 <= lat <= la2 and ln1 <= lng <= ln2:
            return il
    return 'Türkiye'

# ── 1. WDPA - Dünya Koruma Alanları ─────────────────────────────
def fetch_wdpa():
    print("📡 WDPA çekiliyor...")
    token = os.environ.get('WDPA_TOKEN', '')
    results = []
    
    # WDPA API - Türkiye için
    for page in range(1, 4):  # İlk 3 sayfa (her sayfa 25 kayıt)
        try:
            url = f"https://api.protected.planet.net/v3/countries/TUR/protected_areas?page={page}&token={token}"
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                print(f"  WDPA sayfa {page} hata: {r.status_code}")
                break
            data = r.json()
            areas = data.get('protected_areas', [])
            if not areas:
                break
            for a in areas:
                try:
                    lat = float(a.get('latitude') or 0)
                    lng = float(a.get('longitude') or 0)
                    if not (lat and lng and in_turkey(lat, lng)):
                        continue
                    tip = 'Özel Çevre Koruma Alanı'
                    if 'national' in str(a.get('designation','')).lower():
                        tip = 'Milli Park'
                    elif 'ramsar' in str(a.get('designation','')).lower():
                        tip = 'Sulak Alan'
                    results.append({
                        'id': 'wdpa_' + str(a.get('wdpaid', uid())),
                        'tip': tip,
                        'ad': a.get('name', 'WDPA Alanı'),
                        'il': guess_il(lat, lng),
                        'ilce': '',
                        'aciklama': f"WDPA ID: {a.get('wdpaid')} | {a.get('designation','')}",
                        'koordinatlar': {'lat': round(lat, 6), 'lng': round(lng, 6)},
                        'alan_ha': float(a.get('reported_area') or 0),
                        'durum': 'Aktif',
                        'belge_no': str(a.get('wdpaid', '')),
                        'eklenme': today(),
                        'kaynak': 'WDPA'
                    })
                except Exception:
                    continue
            time.sleep(1)
        except Exception as e:
            print(f"  WDPA hata: {e}")
            break
    
    print(f"  ✅ WDPA: {len(results)} kayıt")
    return results

# ── 2. Global Forest Watch - Orman Yangınları ───────────────────
def fetch_gfw():
    print("📡 Global Forest Watch çekiliyor...")
    results = []
    try:
        # FIRMS aktif yangın noktaları - Türkiye
        url = "https://firms.modaps.eosdis.nasa.gov/api/country/csv/c3dba2d4f8e15698d0a9b58d4e3d6a7f/VIIRS_SNPP_NRT/TUR/1"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            if len(lines) > 1:
                headers = lines[0].split(',')
                for line in lines[1:min(51, len(lines))]:  # Max 50 yangın
                    try:
                        vals = line.split(',')
                        d = dict(zip(headers, vals))
                        lat = float(d.get('latitude', 0))
                        lng = float(d.get('longitude', 0))
                        if not in_turkey(lat, lng):
                            continue
                        results.append({
                            'id': 'gfw_' + uid(),
                            'tip': 'Ekolojik İhlal',
                            'ad': f"Aktif Orman Yangını ({d.get('acq_date','?')})",
                            'il': guess_il(lat, lng),
                            'ilce': '',
                            'aciklama': f"VIIRS uydu tespiti. Tarih: {d.get('acq_date')} {d.get('acq_time','')} | Parlaklık: {d.get('bright_ti4','')}K",
                            'koordinatlar': {'lat': round(lat, 6), 'lng': round(lng, 6)},
                            'alan_ha': 0,
                            'durum': 'Devam Ediyor',
                            'belge_no': '',
                            'eklenme': today(),
                            'kaynak': 'NASA FIRMS/GFW'
                        })
                    except Exception:
                        continue
    except Exception as e:
        print(f"  GFW hata: {e}")
    
    print(f"  ✅ Global Forest Watch: {len(results)} kayıt")
    return results

# ── 3. Overpass API (OSM) - Çeşitli Alan Türleri ───────────────
def fetch_overpass(query, tip, kaynak_tag='OSM'):
    try:
        url = "https://overpass-api.de/api/interpreter"
        r = requests.post(url, data={'data': query}, timeout=60)
        if r.status_code != 200:
            return []
        elements = r.json().get('elements', [])
        results = []
        for e in elements:
            try:
                tags = e.get('tags', {})
                lat = e.get('lat') or e.get('center', {}).get('lat')
                lng = e.get('lon') or e.get('center', {}).get('lon')
                if not lat or not lng:
                    continue
                lat, lng = float(lat), float(lng)
                name = tags.get('name') or tags.get('name:tr') or tip
                results.append({
                    'id': 'osm_' + str(e.get('id', uid())),
                    'tip': tip,
                    'ad': name,
                    'il': guess_il(lat, lng),
                    'ilce': '',
                    'aciklama': ' | '.join(f"{k}={v}" for k, v in list(tags.items())[:5] if k != 'name'),
                    'koordinatlar': {'lat': round(lat, 6), 'lng': round(lng, 6)},
                    'alan_ha': 0,
                    'durum': 'Aktif',
                    'belge_no': str(e.get('id', '')),
                    'eklenme': today(),
                    'kaynak': kaynak_tag
                })
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"  Overpass hata ({tip}): {e}")
        return []

def fetch_osm_data():
    print("📡 OSM/Overpass çekiliyor...")
    results = []
    
    queries = [
        # Milli Parklar
        ('[out:json][timeout:30];'
         'relation["boundary"="national_park"]["name"]["name:tr"](36,26,42,45);'
         'out center 30;', 'Milli Park'),
        # HES/Barajlar  
        ('[out:json][timeout:30];'
         'node["power"="plant"]["plant:source"="hydro"]["name"](36,26,42,45);'
         'out 30;', 'HES'),
        # GES
        ('[out:json][timeout:30];'
         'node["power"="plant"]["plant:source"="solar"]["name"](36,26,42,45);'
         'out 30;', 'GES'),
        # RES
        ('[out:json][timeout:30];'
         'node["power"="plant"]["plant:source"="wind"]["name"](36,26,42,45);'
         'out 30;', 'RES'),
        # Maden
        ('[out:json][timeout:30];'
         'node["landuse"="quarry"]["name"](36,26,42,45);'
         'out 30;', 'Maden Ocağı'),
        # Sulak Alan
        ('[out:json][timeout:30];'
         'node["natural"="wetland"]["name"](36,26,42,45);'
         'out 20;', 'Sulak Alan'),
        # Jeotermal
        ('[out:json][timeout:30];'
         'node["power"="plant"]["plant:source"="geothermal"]["name"](36,26,42,45);'
         'out 20;', 'Jeotermal'),
    ]
    
    for query, tip in queries:
        r = fetch_overpass(query, tip)
        results.extend(r)
        print(f"  OSM {tip}: {len(r)} kayıt")
        time.sleep(2)  # Rate limit
    
    print(f"  ✅ OSM toplam: {len(results)} kayıt")
    return results

# ── 4. Earthquake/Deprem - AFAD/USGS ────────────────────────────
def fetch_depremler():
    print("📡 Son depremler çekiliyor (USGS)...")
    results = []
    try:
        url = ("https://earthquake.usgs.gov/fdsnws/event/1/query"
               "?format=geojson&starttime=-7days"
               "&minlatitude=35.8&maxlatitude=42.2"
               "&minlongitude=25.7&maxlongitude=44.8"
               "&minmagnitude=4.0&orderby=magnitude&limit=20")
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            feats = r.json().get('features', [])
            for f in feats:
                try:
                    props = f['properties']
                    coords = f['geometry']['coordinates']
                    lng, lat = float(coords[0]), float(coords[1])
                    mag = props.get('mag', 0)
                    place = props.get('place', '?')
                    t = datetime.utcfromtimestamp(props['time']/1000).strftime('%Y-%m-%d %H:%M')
                    results.append({
                        'id': 'usgs_' + str(f['id']),
                        'tip': 'Ekolojik İhlal',
                        'ad': f"Deprem M{mag} - {place}",
                        'il': guess_il(lat, lng),
                        'ilce': '',
                        'aciklama': f"Büyüklük: M{mag} | Tarih: {t} UTC | Derinlik: {coords[2]} km | Kaynak: USGS",
                        'koordinatlar': {'lat': round(lat, 6), 'lng': round(lng, 6)},
                        'alan_ha': 0,
                        'durum': 'Devam Ediyor',
                        'belge_no': str(f['id']),
                        'eklenme': today(),
                        'kaynak': 'USGS'
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"  Deprem hata: {e}")
    
    print(f"  ✅ Depremler: {len(results)} kayıt")
    return results

# ── ANA FONKSİYON ─────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"Guncelleme: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")

    # Mevcut data.json'u oku
    print("Mevcut veriler okunuyor...")
    existing, sha = [], None
    try:
        existing, sha = read_data()
        print(f"  Mevcut kayit: {len(existing)}")
    except Exception as e:
        print(f"  Mevcut veri alinamadi: {e}")

    # Manuel kayitlari koru
    auto_sources = ('WDPA','OSM','NASA','USGS','UNESCO','FIRMS','auto_')
    manuel = [r for r in existing if not any(
        r.get('kaynak','').startswith(s) or r.get('id','').startswith('auto_')
        for s in auto_sources
    )]
    print(f"  Manuel kayit korunuyor: {len(manuel)}")

    # Yeni verileri cek
    yeni = []
    for fn in [fetch_unesco, fetch_osm_kultur, fetch_wdpa, fetch_osm_data, fetch_gfw, fetch_depremler]:
        try:
            yeni += fn()
        except Exception as e:
            print(f"HATA {fn.__name__}: {e}")

    # Deduplicate
    seen = set()
    yeni_unique = []
    for r in yeni:
        if r['id'] not in seen:
            seen.add(r['id'])
            yeni_unique.append(r)

    tum_veri = manuel + yeni_unique

    print(f"\n{'='*50}")
    print(f"Manuel: {len(manuel)} | Otomatik: {len(yeni_unique)} | TOPLAM: {len(tum_veri)}")
    print(f"{'='*50}")

    # GitHub'a yaz
    print("\nGitHub'a yaziliyor...")
    try:
        new_sha = write_data(tum_veri, sha)
        print(f"OK: {len(tum_veri)} kayit yazildi! SHA: {new_sha[:8] if new_sha else '?'}")
    except Exception as e:
        print(f"HATA: {e}")
        traceback.print_exc()
        raise

    print(f"\nTamamlandi: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")

if __name__ == '__main__':
    main()
