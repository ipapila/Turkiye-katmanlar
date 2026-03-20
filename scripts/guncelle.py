#!/usr/bin/env python3
"""
Türkiye Alan Yönetim Haritası - Günlük Veri Güncelleme Scripti
Her gün saat 06:00'da GitHub Actions tarafından çalıştırılır.
Kaynaklar: WDPA, Ramsar, GEM, OGM, DSİ, Global Forest Watch, BirdLife IBA,
           UNESCO Dünya Mirası, OSM Kültür Varlıkları
"""

import os, json, time, random, requests, traceback
from datetime import datetime

# ── Firebase Admin SDK ──────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    project_id   = os.environ['FIREBASE_PROJECT_ID']
    private_key  = os.environ['FIREBASE_PRIVATE_KEY'].replace('\\n', '\n')
    client_email = os.environ['FIREBASE_CLIENT_EMAIL']
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": project_id,
        "private_key": private_key,
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    firebase_admin.initialize_app(cred)
    return firestore.client()

# ── Yardımcı ────────────────────────────────────────────────────
def uid():
    return 'auto_' + hex(random.randint(0, 0xffffff))[2:] + str(int(time.time()*1000))[-6:]

def today():
    return datetime.utcnow().strftime('%Y-%m-%d')

TR_LAT = (35.8, 42.2)
TR_LNG = (25.7, 44.8)

def in_turkey(lat, lng):
    return TR_LAT[0] <= lat <= TR_LAT[1] and TR_LNG[0] <= lng <= TR_LNG[1]

ILCE_BOXES = {
    'Antalya':(36.0,37.6,29.0,32.8),'Muğla':(36.5,37.5,27.2,29.5),
    'İzmir':(37.5,39.2,25.8,28.5),'Ankara':(39.0,40.5,31.5,33.5),
    'İstanbul':(40.8,41.5,27.9,29.9),'Mersin':(36.0,37.5,32.5,35.0),
    'Adana':(36.5,38.0,34.8,36.5),'Hatay':(35.8,37.2,35.8,36.7),
    'Konya':(36.8,39.5,31.5,34.5),'Samsun':(40.8,41.8,35.0,37.0),
    'Trabzon':(40.5,41.2,39.2,40.5),'Artvin':(40.8,41.6,41.0,42.5),
    'Rize':(40.5,41.2,40.3,41.4),'Şanlıurfa':(36.7,38.2,37.5,40.5),
    'Diyarbakır':(37.5,38.8,39.5,41.5),'Erzurum':(39.5,40.8,40.5,42.5),
    'Kayseri':(37.5,39.5,34.5,36.5),'Bursa':(39.8,40.5,28.5,30.0),
    'Balıkesir':(39.2,40.3,26.5,28.5),'Çanakkale':(39.5,40.5,25.9,27.5),
    'Aydın':(37.3,38.3,27.0,28.8),'Denizli':(37.3,38.3,28.5,30.0),
    'Elazığ':(38.3,39.2,38.5,40.0),'Malatya':(37.8,38.8,37.5,39.5),
    'Kastamonu':(41.0,42.0,32.5,34.5),'Tunceli':(38.5,39.5,39.0,40.5),
    'Nevşehir':(38.2,39.2,34.0,35.5),'Burdur':(36.8,37.8,29.5,31.0),
    'Isparta':(37.3,38.3,30.0,31.5),'Afyonkarahisar':(38.0,39.2,29.5,31.5),
}

def guess_il(lat, lng):
    for il, (la1,la2,ln1,ln2) in ILCE_BOXES.items():
        if la1<=lat<=la2 and ln1<=lng<=ln2:
            return il
    return 'Türkiye'

# ── 1. UNESCO Dünya Mirası ───────────────────────────────────────
def fetch_unesco():
    print("📡 UNESCO Dünya Mirası çekiliyor...")
    results = []
    try:
        # UNESCO resmi XML feed
        url = "https://whc.unesco.org/en/list/xml/"
        r = requests.get(url, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)

        for row in root.findall('.//row'):
            try:
                # Türkiye filtresi
                states = row.findtext('states_name_en', '')
                if 'Turkey' not in states and 'Türkiye' not in states:
                    continue
                lat = float(row.findtext('latitude') or 0)
                lng = float(row.findtext('longitude') or 0)
                if not lat or not lng:
                    continue
                name_tr = row.findtext('site') or row.findtext('name_en') or 'UNESCO Alanı'
                category = row.findtext('category', 'Cultural')
                date_inscribed = row.findtext('date_inscribed', '')
                short_desc = row.findtext('short_description', '')
                wdpa_id = row.findtext('id_no', '')

                tip = 'Kültür Varlığı'
                if category == 'Natural':
                    tip = 'Milli Park'
                elif category == 'Mixed':
                    tip = 'Özel Çevre Koruma Alanı'

                results.append({
                    'id': 'unesco_' + str(wdpa_id),
                    'tip': tip,
                    'ad': f"[UNESCO] {name_tr}",
                    'il': guess_il(lat, lng),
                    'ilce': '',
                    'aciklama': f"UNESCO Dünya Mirası ({category}). Tescil: {date_inscribed}. {short_desc[:200] if short_desc else ''}",
                    'koordinatlar': {'lat': round(lat,6), 'lng': round(lng,6)},
                    'alan_ha': float(row.findtext('area_hectares') or 0),
                    'durum': 'Aktif',
                    'belge_no': f"UNESCO-{wdpa_id}",
                    'eklenme': today(),
                    'kaynak': 'UNESCO WHC'
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  UNESCO hata: {e}")

    print(f"  ✅ UNESCO: {len(results)} kayıt")
    return results

# ── 2. OSM Kültür Varlıkları ─────────────────────────────────────
def fetch_osm_kultur():
    print("📡 OSM Kültür Varlıkları çekiliyor...")
    results = []

    queries = [
        # Arkeolojik alanlar
        ('[out:json][timeout:30];'
         'node["historic"="archaeological_site"]["name"](36,26,42,45);out 50;',
         'Kültür Varlığı', 'Arkeolojik Alan'),
        # Antik şehirler
        ('[out:json][timeout:30];'
         'node["historic"="ruins"]["name"](36,26,42,45);out 50;',
         'Kültür Varlığı', 'Tarihi Kalıntı'),
        # Müzeler
        ('[out:json][timeout:30];'
         'node["tourism"="museum"]["name"](36,26,42,45);out 50;',
         'Kültür Varlığı', 'Müze'),
        # Anıtlar
        ('[out:json][timeout:30];'
         'node["historic"="monument"]["name"](36,26,42,45);out 30;',
         'Kültür Varlığı', 'Anıt'),
        # Kaleler
        ('[out:json][timeout:30];'
         'node["historic"="castle"]["name"](36,26,42,45);out 30;',
         'Kültür Varlığı', 'Kale'),
        # Mağaralar
        ('[out:json][timeout:30];'
         'node["natural"="cave_entrance"]["name"](36,26,42,45);out 20;',
         'Kültür Varlığı', 'Mağara'),
    ]

    for query, tip, alt_tip in queries:
        try:
            r = requests.post('https://overpass-api.de/api/interpreter',
                            data={'data': query}, timeout=60)
            if r.status_code != 200:
                continue
            elements = r.json().get('elements', [])
            for e in elements:
                try:
                    tags = e.get('tags', {})
                    lat = float(e.get('lat', 0))
                    lng = float(e.get('lon', 0))
                    if not lat or not lng or not in_turkey(lat, lng):
                        continue
                    name = tags.get('name') or tags.get('name:tr') or alt_tip
                    results.append({
                        'id': 'osm_kv_' + str(e.get('id', uid())),
                        'tip': tip,
                        'ad': name,
                        'il': guess_il(lat, lng),
                        'ilce': '',
                        'aciklama': f"{alt_tip} | OSM ID: {e.get('id')} | {tags.get('description','') or tags.get('wikipedia','')}",
                        'koordinatlar': {'lat': round(lat,6), 'lng': round(lng,6)},
                        'alan_ha': 0,
                        'durum': 'Aktif',
                        'belge_no': str(e.get('id','')),
                        'eklenme': today(),
                        'kaynak': f'OSM/{alt_tip}'
                    })
                except Exception:
                    continue
            print(f"  OSM {alt_tip}: {len(elements)} kayıt")
            time.sleep(3)
        except Exception as ex:
            print(f"  OSM {alt_tip} hata: {ex}")

    print(f"  ✅ OSM Kültür Varlıkları toplam: {len(results)} kayıt")
    return results

# ── 3. WDPA ─────────────────────────────────────────────────────
def fetch_wdpa():
    print("📡 WDPA çekiliyor...")
    token = os.environ.get('WDPA_TOKEN', '')
    results = []
    for page in range(1, 4):
        try:
            url = f"https://api.protected.planet.net/v3/countries/TUR/protected_areas?page={page}&token={token}"
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                break
            areas = r.json().get('protected_areas', [])
            if not areas:
                break
            for a in areas:
                try:
                    lat = float(a.get('latitude') or 0)
                    lng = float(a.get('longitude') or 0)
                    if not (lat and lng and in_turkey(lat, lng)):
                        continue
                    tip = 'Özel Çevre Koruma Alanı'
                    desig = str(a.get('designation','')).lower()
                    if 'national park' in desig: tip = 'Milli Park'
                    elif 'ramsar' in desig: tip = 'Sulak Alan'
                    results.append({
                        'id': 'wdpa_' + str(a.get('wdpaid', uid())),
                        'tip': tip,
                        'ad': a.get('name','WDPA Alanı'),
                        'il': guess_il(lat, lng),
                        'ilce': '',
                        'aciklama': f"WDPA ID: {a.get('wdpaid')} | {a.get('designation','')}",
                        'koordinatlar': {'lat':round(lat,6),'lng':round(lng,6)},
                        'alan_ha': float(a.get('reported_area') or 0),
                        'durum': 'Aktif',
                        'belge_no': str(a.get('wdpaid','')),
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

# ── 4. OSM Enerji & Çevre ───────────────────────────────────────
def fetch_osm_data():
    print("📡 OSM Enerji/Çevre çekiliyor...")
    results = []
    queries = [
        ('[out:json][timeout:30];relation["boundary"="national_park"]["name"](36,26,42,45);out center 30;','Milli Park'),
        ('[out:json][timeout:30];node["power"="plant"]["plant:source"="hydro"]["name"](36,26,42,45);out 30;','HES'),
        ('[out:json][timeout:30];node["power"="plant"]["plant:source"="solar"]["name"](36,26,42,45);out 30;','GES'),
        ('[out:json][timeout:30];node["power"="plant"]["plant:source"="wind"]["name"](36,26,42,45);out 30;','RES'),
        ('[out:json][timeout:30];node["power"="plant"]["plant:source"="geothermal"]["name"](36,26,42,45);out 20;','Jeotermal'),
        ('[out:json][timeout:30];node["landuse"="quarry"]["name"](36,26,42,45);out 30;','Maden Ocağı'),
        ('[out:json][timeout:30];node["natural"="wetland"]["name"](36,26,42,45);out 20;','Sulak Alan'),
    ]
    for query, tip in queries:
        try:
            r = requests.post('https://overpass-api.de/api/interpreter', data={'data':query}, timeout=60)
            if r.status_code != 200: continue
            elements = r.json().get('elements',[])
            for e in elements:
                tags = e.get('tags',{})
                lat = e.get('lat') or e.get('center',{}).get('lat')
                lng = e.get('lon') or e.get('center',{}).get('lon')
                if not lat or not lng: continue
                lat, lng = float(lat), float(lng)
                results.append({
                    'id':'osm_'+str(e.get('id',uid())),
                    'tip':tip,'ad':tags.get('name',tip),
                    'il':guess_il(lat,lng),'ilce':'',
                    'aciklama':' | '.join(f"{k}={v}" for k,v in list(tags.items())[:5] if k!='name'),
                    'koordinatlar':{'lat':round(lat,6),'lng':round(lng,6)},
                    'alan_ha':0,'durum':'Aktif',
                    'belge_no':str(e.get('id','')),
                    'eklenme':today(),'kaynak':'OSM'
                })
            print(f"  OSM {tip}: {len(elements)}")
            time.sleep(2)
        except Exception as e:
            print(f"  OSM hata ({tip}): {e}")
    print(f"  ✅ OSM toplam: {len(results)} kayıt")
    return results

# ── 5. NASA FIRMS Yangınlar ──────────────────────────────────────
def fetch_gfw():
    print("📡 NASA FIRMS yangınlar çekiliyor...")
    results = []
    try:
        url = "https://firms.modaps.eosdis.nasa.gov/api/country/csv/c3dba2d4f8e15698d0a9b58d4e3d6a7f/VIIRS_SNPP_NRT/TUR/1"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            if len(lines) > 1:
                headers = lines[0].split(',')
                for line in lines[1:min(51,len(lines))]:
                    try:
                        d = dict(zip(headers, line.split(',')))
                        lat,lng = float(d.get('latitude',0)), float(d.get('longitude',0))
                        if not in_turkey(lat,lng): continue
                        results.append({
                            'id':'firms_'+uid(),'tip':'Ekolojik İhlal',
                            'ad':f"Aktif Yangın ({d.get('acq_date','?')})",
                            'il':guess_il(lat,lng),'ilce':'',
                            'aciklama':f"VIIRS tespiti. Tarih: {d.get('acq_date')} {d.get('acq_time','')} | Parlaklık: {d.get('bright_ti4','')}K",
                            'koordinatlar':{'lat':round(lat,6),'lng':round(lng,6)},
                            'alan_ha':0,'durum':'Devam Ediyor',
                            'belge_no':'','eklenme':today(),'kaynak':'NASA FIRMS'
                        })
                    except Exception: continue
    except Exception as e:
        print(f"  FIRMS hata: {e}")
    print(f"  ✅ Yangınlar: {len(results)} kayıt")
    return results

# ── 6. USGS Depremler ────────────────────────────────────────────
def fetch_depremler():
    print("📡 USGS depremler çekiliyor...")
    results = []
    try:
        url = ("https://earthquake.usgs.gov/fdsnws/event/1/query"
               "?format=geojson&starttime=-7days"
               "&minlatitude=35.8&maxlatitude=42.2"
               "&minlongitude=25.7&maxlongitude=44.8"
               "&minmagnitude=4.0&orderby=magnitude&limit=20")
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            for f in r.json().get('features',[]):
                try:
                    props = f['properties']
                    coords = f['geometry']['coordinates']
                    lng,lat = float(coords[0]),float(coords[1])
                    mag = props.get('mag',0)
                    t = datetime.utcfromtimestamp(props['time']/1000).strftime('%Y-%m-%d %H:%M')
                    results.append({
                        'id':'usgs_'+str(f['id']),'tip':'Ekolojik İhlal',
                        'ad':f"Deprem M{mag} - {props.get('place','?')}",
                        'il':guess_il(lat,lng),'ilce':'',
                        'aciklama':f"M{mag} | {t} UTC | Derinlik: {coords[2]} km | USGS",
                        'koordinatlar':{'lat':round(lat,6),'lng':round(lng,6)},
                        'alan_ha':0,'durum':'Devam Ediyor',
                        'belge_no':str(f['id']),'eklenme':today(),'kaynak':'USGS'
                    })
                except Exception: continue
    except Exception as e:
        print(f"  Deprem hata: {e}")
    print(f"  ✅ Depremler: {len(results)} kayıt")
    return results

# ── ANA FONKSİYON ────────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"🚀 Güncelleme: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")

    db = init_firebase()
    doc_ref = db.collection('harita').document('veriler')

    # Mevcut veriyi al
    existing = []
    try:
        snap = doc_ref.get()
        if snap.exists:
            existing = snap.to_dict().get('alanlar', [])
            print(f"Mevcut kayıt: {len(existing)}")
    except Exception as e:
        print(f"Mevcut veri alınamadı: {e}")

    # Manuel kayıtları koru
    auto_sources = ('WDPA','OSM','NASA','USGS','UNESCO','FIRMS')
    manuel = [r for r in existing if not any(r.get('kaynak','').startswith(s) for s in auto_sources)]
    print(f"Manuel kayıt korunuyor: {len(manuel)}")

    # Yeni verileri çek
    yeni = []
    for fn in [fetch_unesco, fetch_osm_kultur, fetch_wdpa, fetch_osm_data, fetch_gfw, fetch_depremler]:
        try:
            yeni += fn()
        except Exception as e:
            print(f"❌ {fn.__name__} hatası: {e}")

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

    try:
        doc_ref.set({'alanlar': tum_veri, 'guncelleme': today()})
        print(f"✅ Firebase'e {len(tum_veri)} kayıt yazıldı!")
    except Exception as e:
        print(f"❌ Firebase yazma hatası: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()


import os, json, time, random, requests, traceback
from datetime import datetime

# ── Firebase Admin SDK ──────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    project_id   = os.environ['FIREBASE_PROJECT_ID']
    private_key  = os.environ['FIREBASE_PRIVATE_KEY'].replace('\\n', '\n')
    client_email = os.environ['FIREBASE_CLIENT_EMAIL']

    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": project_id,
        "private_key": private_key,
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    firebase_admin.initialize_app(cred)
    return firestore.client()

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
    print(f"🚀 Güncelleme başladı: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")

    # Firebase'e bağlan
    db = init_firebase()
    doc_ref = db.collection('harita').document('veriler')

    # Mevcut manuel kayıtları al (silinmesin)
    print("📥 Mevcut veriler alınıyor...")
    existing = []
    try:
        snap = doc_ref.get()
        if snap.exists:
            existing = snap.to_dict().get('alanlar', [])
            print(f"  Mevcut kayıt: {len(existing)}")
    except Exception as e:
        print(f"  Mevcut veri alınamadı: {e}")

    # Manuel eklenen kayıtları koru (kaynak='Manuel' veya 'Admin')
    manuel = [r for r in existing if r.get('kaynak') in ('Manuel', 'Admin', '') or 
              not r.get('kaynak','').startswith(('WDPA','OSM','GFW','NASA','USGS','GEM','DSİ'))]
    print(f"  Manuel kayıt korunuyor: {len(manuel)}")

    # Yeni verileri çek
    yeni = []
    
    try:
        yeni += fetch_wdpa()
    except Exception as e:
        print(f"❌ WDPA hatası: {e}")

    try:
        yeni += fetch_osm_data()
    except Exception as e:
        print(f"❌ OSM hatası: {e}")

    try:
        yeni += fetch_gfw()
    except Exception as e:
        print(f"❌ GFW hatası: {e}")

    try:
        yeni += fetch_depremler()
    except Exception as e:
        print(f"❌ Deprem hatası: {e}")

    # ID ile deduplicate
    seen = set()
    yeni_unique = []
    for r in yeni:
        if r['id'] not in seen:
            seen.add(r['id'])
            yeni_unique.append(r)

    # Manuel + Yeni birleştir
    # Eski otomatik kayıtların ID'lerini temizle, yeni gelenleri ekle
    tum_veri = manuel + yeni_unique

    print(f"\n{'='*50}")
    print(f"📊 Sonuç:")
    print(f"  Manuel kayıt: {len(manuel)}")
    print(f"  Otomatik kayıt: {len(yeni_unique)}")
    print(f"  TOPLAM: {len(tum_veri)}")
    print(f"{'='*50}")

    # Firebase'e yaz
    print("\n💾 Firebase'e yazılıyor...")
    try:
        doc_ref.set({'alanlar': tum_veri, 'guncelleme': today()})
        print(f"✅ {len(tum_veri)} kayıt başarıyla yazıldı!")
    except Exception as e:
        print(f"❌ Firebase yazma hatası: {e}")
        traceback.print_exc()

    print(f"\n✅ Güncelleme tamamlandı: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")

if __name__ == '__main__':
    main()
