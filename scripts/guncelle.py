import os, json, time, random, requests, traceback, base64
from datetime import datetime

DATA_FILE = 'data.json'
FIREBASE_API_KEY = 'AIzaSyAvjtSn23YhDYZZmf_G2pUYzTA0Qa5tx1M'
FIRESTORE_URL = f'https://firestore.googleapis.com/v1/projects/turkiye-katmanlar/databases/(default)/documents/harita/veriler?key={FIREBASE_API_KEY}'

def is_auto(r):
    """Otomatik kaynak mı kontrol et — sadece ID prefix'ine bak"""
    rid = r.get('id','')
    auto_prefixes = ('osm_','wdpa_','usgs_','firms_','auto_','unesco_')
    return any(rid.startswith(p) for p in auto_prefixes)

def read_data():
    """Mevcut data.json'u diskten oku, manuel kayitlari Firebase'den kurtar"""
    disk_data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                disk_data = json.load(f)
            except Exception as e:
                print(f"  data.json okuma hatasi: {e}")

    # Disk'teki manuel kayitlari bul (otomatik olmayanlar)
    disk_manuel = [r for r in disk_data if not is_auto(r)]
    print(f"  Disk manuel kayit: {len(disk_manuel)}")

    # Firebase'den TUM kayitlari al, otomatik olmayanları koru
    print("  Firebase'den kayitlar aliniyor...")
    firebase_data = []
    try:
        r = requests.get(FIRESTORE_URL, timeout=30)
        if r.ok:
            doc = r.json()
            raw = doc.get('fields', {}).get('alanlar', {}).get('arrayValue', {}).get('values', [])
            print(f"  Firebase toplam: {len(raw)} kayit")
            for item in raw:
                m = item.get('mapValue', {}).get('fields', {})
                rid = m.get('id', {}).get('stringValue', '')
                # Sadece otomatik olmayanları al
                auto_prefixes = ('osm_','wdpa_','usgs_','firms_','auto_','unesco_')
                if any(rid.startswith(p) for p in auto_prefixes):
                    continue
                lat = float(m.get('koordinatlar', {}).get('mapValue', {}).get('fields', {}).get('lat', {}).get('doubleValue', 0) or
                           m.get('koordinatlar', {}).get('mapValue', {}).get('fields', {}).get('lat', {}).get('integerValue', 0) or 0)
                lng = float(m.get('koordinatlar', {}).get('mapValue', {}).get('fields', {}).get('lng', {}).get('doubleValue', 0) or
                           m.get('koordinatlar', {}).get('mapValue', {}).get('fields', {}).get('lng', {}).get('integerValue', 0) or 0)
                kaynak = m.get('kaynak', {}).get('stringValue', '')
                firebase_data.append({
                    'id':       rid,
                    'tip':      m.get('tip', {}).get('stringValue', ''),
                    'ad':       m.get('ad', {}).get('stringValue', ''),
                    'il':       m.get('il', {}).get('stringValue', ''),
                    'ilce':     m.get('ilce', {}).get('stringValue', ''),
                    'aciklama': m.get('aciklama', {}).get('stringValue', ''),
                    'koordinatlar': {'lat': lat, 'lng': lng},
                    'alan_ha':  float(m.get('alan_ha', {}).get('doubleValue', 0) or m.get('alan_ha', {}).get('integerValue', 0) or 0),
                    'durum':    m.get('durum', {}).get('stringValue', 'Aktif'),
                    'belge_no': m.get('belge_no', {}).get('stringValue', ''),
                    'eklenme':  m.get('eklenme', {}).get('stringValue', ''),
                    'kaynak':   kaynak,
                })
            firebase_data = [r for r in firebase_data if r.get('ad') and r.get('koordinatlar', {}).get('lat')]
            print(f"  Firebase manuel kayit: {len(firebase_data)}")
    except Exception as e:
        print(f"  Firebase okuma hatasi: {e}")

    # En fazla kaydi olan kaynagi kullan
    if len(firebase_data) >= len(disk_manuel):
        print(f"  Firebase'den {len(firebase_data)} kayit kullaniliyor")
        return firebase_data
    else:
        print(f"  Disk'ten {len(disk_manuel)} kayit kullaniliyor")
        return disk_manuel

def write_data(data):
    """data.json'u diske yaz"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"data.json guncellendi: {len(data)} kayit")

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

_geocode_cache = {}
_geocode_count = 0
MAX_GEOCODE = 100  # Tek çalışmada max 100 yeni geocode isteği

def reverse_geocode(lat, lng):
    global _geocode_count
    key = (round(lat,2), round(lng,2))
    if key in _geocode_cache:
        return _geocode_cache[key]
    if _geocode_count >= MAX_GEOCODE:
        # Limit aşıldı, bbox ile tahmin et
        return (guess_il_bbox(lat, lng), '')
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json&accept-language=tr"
        r = requests.get(url, timeout=8, headers={'User-Agent': 'TurkiyeKatmanlarBot/1.0'})
        if r.ok:
            addr = r.json().get('address', {})
            il   = (addr.get('province') or addr.get('state') or addr.get('county') or 'Türkiye').replace(' Province','').replace(' İli','').strip()
            ilce = (addr.get('county') or addr.get('city_district') or addr.get('district') or '').replace(' İlçesi','').strip()
            result = (il, ilce)
            _geocode_cache[key] = result
            _geocode_count += 1
            time.sleep(1)
            return result
    except Exception:
        pass
    result = (guess_il_bbox(lat, lng), '')
    _geocode_cache[key] = result
    return result

def guess_ilce_bbox(lat, lng, il=''):
    """Koordinattan ilçe tahmini — detaylı bbox"""
    ILCE_BOXES = {
        # Antalya ilçeleri
        'Kemer':     (36.35,36.65,30.35,30.75),
        'Manavgat':  (36.70,37.20,31.30,32.10),
        'Alanya':    (36.40,36.85,31.75,32.40),
        'Kaş':       (36.10,36.40,29.00,30.00),
        'Demre':     (36.10,36.45,29.85,30.30),
        'Finike':    (36.20,36.55,30.05,30.65),
        'Kumluca':   (36.25,36.65,30.10,30.75),
        'Serik':     (36.75,37.10,30.95,31.55),
        'Kepez':     (36.95,37.10,30.60,30.90),
        'Muratpaşa': (36.82,36.98,30.60,30.90),
        'Konyaaltı': (36.82,37.05,30.45,30.75),
        'Döşemealtı':(36.92,37.18,30.38,30.72),
        'Akseki':    (36.90,37.45,31.45,32.15),
        'Elmalı':    (36.45,37.10,29.55,30.45),
        'Korkuteli': (36.92,37.35,29.95,30.58),
        'Gazipaşa':  (36.20,36.58,32.05,32.65),
        'Gündoğmuş': (36.65,37.15,31.70,32.35),
        'İbradı':    (36.95,37.45,31.40,32.05),
        'Aksu':      (36.80,37.12,30.78,31.25),
        # Muğla ilçeleri
        'Bodrum':    (36.95,37.20,27.20,27.65),
        'Fethiye':   (36.50,37.00,28.85,29.45),
        'Marmaris':  (36.70,37.05,27.95,28.50),
        'Milas':     (37.05,37.45,27.55,28.20),
        'Datça':     (36.65,36.90,27.30,27.90),
        'Köyceğiz':  (36.85,37.25,28.45,28.90),
        'Ortaca':    (36.75,37.00,28.70,29.10),
        'Dalaman':   (36.72,36.95,28.68,29.00),
        'Menteşe':   (37.05,37.40,28.15,28.65),
        'Yatağan':   (37.25,37.55,28.05,28.50),
        'Ula':       (37.00,37.35,28.35,28.80),
        'Seydikemer':(36.55,36.95,28.80,29.40),
        # İzmir ilçeleri
        'Konak':     (38.38,38.48,27.10,27.20),
        'Bornova':   (38.42,38.55,27.15,27.35),
        'Karşıyaka': (38.44,38.52,27.05,27.18),
        'Aliağa':    (38.75,39.00,26.85,27.05),
        'Bergama':   (38.95,39.35,27.00,27.45),
        'Selçuk':    (37.90,38.05,27.30,27.60),
        'Kuşadası':  (37.82,37.98,27.22,27.45),
        'Çeşme':     (38.25,38.45,26.25,26.48),
        'Urla':      (38.28,38.48,26.72,27.02),
        # Ankara ilçeleri
        'Çankaya':   (39.85,39.98,32.70,32.90),
        'Keçiören':  (39.96,40.05,32.82,32.98),
        'Yenimahalle':(39.90,40.05,32.58,32.82),
        'Altındağ':  (39.93,40.02,32.88,33.02),
        'Sincan':    (39.95,40.10,32.52,32.72),
        'Etimesgut': (39.92,40.00,32.62,32.78),
        'Mamak':     (39.88,39.98,32.95,33.12),
        'Gölbaşı':   (39.68,39.90,32.72,32.98),
        # İstanbul ilçeleri
        'Kadıköy':   (40.96,41.02,29.02,29.12),
        'Beşiktaş':  (41.03,41.08,28.98,29.05),
        'Beyoğlu':   (41.02,41.06,28.95,29.02),
        'Üsküdar':   (41.00,41.08,29.02,29.12),
        'Fatih':     (41.00,41.04,28.90,29.00),
        'Şişli':     (41.05,41.10,28.97,29.04),
        'Bakırköy':  (40.96,41.02,28.82,28.92),
        'Beykoz':    (41.05,41.22,29.05,29.30),
        'Pendik':    (40.85,40.97,29.18,29.40),
        'Maltepe':   (40.90,40.98,29.12,29.22),
        'Kartal':    (40.88,40.96,29.18,29.28),
        'Ataşehir':  (40.96,41.02,29.09,29.18),
        'Çekmeköy':  (41.00,41.12,29.15,29.30),
        'Sancaktepe':(40.96,41.05,29.18,29.30),
        'Sultanbeyli':(40.95,41.02,29.25,29.35),
        'Tuzla':     (40.82,40.92,29.28,29.45),
        'Gebze':     (40.78,40.88,29.38,29.55),  # Kocaeli
        'Arnavutköy':(41.15,41.28,28.62,28.82),
        'Başakşehir':(41.05,41.15,28.72,28.92),
        'Beylikdüzü':(40.98,41.05,28.62,28.78),
        'Büyükçekmece':(41.00,41.08,28.52,28.72),
        'Çatalca':   (41.12,41.35,28.32,28.68),
        'Silivri':   (41.02,41.18,27.98,28.42),
        'Avcılar':   (40.96,41.02,28.70,28.82),
        'Güngören':  (41.01,41.05,28.86,28.92),
        'Bağcılar':  (41.03,41.08,28.82,28.92),
        'Bahçelievler':(41.00,41.05,28.82,28.90),
        'Esenler':   (41.03,41.08,28.85,28.96),
        'Bayrampaşa':(41.04,41.08,28.90,28.97),
        'Gaziosmanpaşa':(41.05,41.12,28.90,29.00),
        'Sultangazi': (41.09,41.16,28.88,29.00),
        'Eyüpsultan':(41.05,41.14,28.90,29.02),
    }
    for ilce, (la1,la2,ln1,ln2) in ILCE_BOXES.items():
        if la1<=lat<=la2 and ln1<=lng<=ln2:
            return ilce
    return ''

def guess_il_bbox(lat, lng):
    """Bounding box ile il tahmini (yedek)"""
    for il, (la1, la2, ln1, ln2) in IL_BOXES.items():
        if la1 <= lat <= la2 and ln1 <= lng <= ln2:
            return il
    return 'Türkiye'

def guess_il(lat, lng):
    """Geriye dönük uyumluluk için"""
    return reverse_geocode(lat, lng)[0]

IL_BOXES = {
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
    'Van':(37.5,39.0,42.5,44.5),'Erzincan':(39.0,40.0,38.5,40.5),
    'Kars':(40.0,41.0,42.0,43.5),'Iğdır':(39.5,40.2,43.5,44.8),
    'Siirt':(37.3,38.3,41.5,42.5),'Hakkari':(37.0,37.8,43.0,44.8),
    'Bitlis':(38.0,39.0,41.5,43.0),'Muş':(38.5,39.5,40.5,42.0),
    'Batman':(37.5,38.5,40.5,41.8),'Mardin':(36.8,37.8,40.0,42.0),
    'Şırnak':(37.0,37.8,41.8,43.5),'Gaziantep':(36.5,37.5,36.5,37.8),
    'Kilis':(36.5,37.2,36.5,37.5),'Kahramanmaraş':(37.0,38.5,35.5,37.5),
    'Osmaniye':(36.8,37.5,35.8,36.8),'Niğde':(37.5,38.5,33.5,35.0),
    'Aksaray':(38.0,39.0,33.0,34.5),'Karaman':(36.8,38.0,32.5,34.0),
    'Konya':(36.8,39.5,31.5,34.5),'Eskişehir':(39.0,40.2,29.5,31.5),
    'Kütahya':(38.8,39.8,28.5,30.5),'Uşak':(38.2,39.0,28.5,29.8),
    'Manisa':(38.2,39.5,26.8,28.8),'Aydın':(37.3,38.3,27.0,28.8),
    'Muğla':(36.3,37.5,27.2,29.5),'Burdur':(36.8,37.8,29.5,31.0),
    'Isparta':(37.3,38.5,30.0,31.5),'Tekirdağ':(40.5,41.5,26.5,28.0),
    'Edirne':(41.0,42.0,25.8,27.0),'Kırklareli':(41.5,42.2,26.5,28.0),
    'Çanakkale':(39.5,40.5,25.9,27.5),'Balıkesir':(39.2,40.3,26.5,28.5),
    'Bursa':(39.8,40.5,28.5,30.0),'Yalova':(40.5,40.8,29.0,29.6),
    'Kocaeli':(40.5,41.0,29.5,30.5),'Sakarya':(40.5,41.0,30.0,31.0),
    'Düzce':(40.7,41.2,30.8,31.5),'Bolu':(40.5,41.2,31.0,32.5),
    'Zonguldak':(41.0,41.8,31.0,32.5),'Bartın':(41.5,42.0,32.0,33.0),
    'Karabük':(41.0,41.8,32.5,33.5),'Kastamonu':(41.0,42.0,32.5,34.5),
    'Sinop':(41.5,42.2,34.5,36.0),'Samsun':(40.8,41.8,35.0,37.0),
    'Ordu':(40.5,41.2,37.0,38.5),'Giresun':(40.5,41.2,38.0,39.5),
    'Trabzon':(40.5,41.2,39.2,40.5),'Rize':(40.5,41.2,40.3,41.4),
    'Artvin':(40.8,41.6,41.0,42.5),'Ardahan':(40.8,41.6,42.5,43.5),
}

# ── 1. WDPA - Dünya Koruma Alanları ─────────────────────────────
def fetch_unesco():
    print("UNESCO Dunya Mirasi cekiliyor...")
    results = []
    try:
        import xml.etree.ElementTree as ET
        r = requests.get("https://whc.unesco.org/en/list/xml/", timeout=30,
                        headers={'User-Agent':'Mozilla/5.0'})
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for row in root.findall('.//row'):
                states = row.findtext('states_name_en','')
                if 'Turkey' not in states and 'Turkiye' not in states:
                    continue
                lat = float(row.findtext('latitude') or 0)
                lng = float(row.findtext('longitude') or 0)
                if not lat or not lng: continue
                name = row.findtext('site') or 'UNESCO Alani'
                category = row.findtext('category','Cultural')
                wdpa_id = row.findtext('id_no','')
                tip = 'Kultur Varligi' if category=='Cultural' else ('Milli Park' if category=='Natural' else 'Ozel Cevre Koruma Alani')
                results.append({
                    'id':'unesco_'+str(wdpa_id),
                    'tip':'Kültür Varlığı' if category=='Cultural' else 'Milli Park',
                    'ad':'[UNESCO] '+name,
                    'il':guess_il(lat,lng),'ilce':'',
                    'aciklama':f"UNESCO Dunya Mirasi ({category}). Tescil: {row.findtext('date_inscribed','')}",
                    'koordinatlar':{'lat':round(lat,6),'lng':round(lng,6)},
                    'alan_ha':float(row.findtext('area_hectares') or 0),
                    'durum':'Aktif','belge_no':f"UNESCO-{wdpa_id}",
                    'eklenme':today(),'kaynak':'UNESCO WHC'
                })
    except Exception as e:
        print(f"  UNESCO hata: {e}")
    print(f"  UNESCO: {len(results)} kayit")
    return results

def fetch_osm_kultur():
    print("OSM Kultur Varliklari cekiliyor...")
    results = []
    queries = [
        ('[out:json][timeout:30];node["historic"="archaeological_site"]["name"](36,26,42,45);out 50;','Arkeolojik Alan'),
        ('[out:json][timeout:30];node["historic"="ruins"]["name"](36,26,42,45);out 50;','Tarihi Kalinti'),
        ('[out:json][timeout:30];node["tourism"="museum"]["name"](36,26,42,45);out 50;','Muze'),
        ('[out:json][timeout:30];node["historic"="castle"]["name"](36,26,42,45);out 30;','Kale'),
    ]
    for query, alt_tip in queries:
        try:
            r = requests.post('https://overpass-api.de/api/interpreter',
                            data={'data':query}, timeout=60)
            if r.status_code != 200: continue
            elements = r.json().get('elements',[])
            for e in elements:
                tags = e.get('tags',{})
                lat,lng = float(e.get('lat',0)),float(e.get('lon',0))
                if not lat or not lng or not in_turkey(lat,lng): continue
                name = tags.get('name:tr') or tags.get('name') or alt_tip
                il, ilce = reverse_geocode(lat, lng)
                results.append({
                    'id':'osm_kv_'+str(e.get('id',uid())),
                    'tip':'Kültür Varlığı','ad':name,
                    'il':il,'ilce':ilce,
                    'aciklama':f"{alt_tip} | OSM ID: {e.get('id')}",
                    'koordinatlar':{'lat':round(lat,6),'lng':round(lng,6)},
                    'alan_ha':0,'durum':'Aktif',
                    'belge_no':str(e.get('id','')),
                    'eklenme':today(),'kaynak':f'OSM/{alt_tip}'
                })
            print(f"  OSM {alt_tip}: {len(elements)}")
            time.sleep(3)
        except Exception as ex:
            print(f"  OSM {alt_tip} hata: {ex}")
    print(f"  OSM Kultur toplam: {len(results)}")
    return results

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

                # Ad: boşsa veya yanlış kategoriyse tip kullan
                bad_names = ('Maden Ocağı','Taş Ocağı','Mermer Ocağı','HES','GES','RES',
                           'Jeotermal','Sulak Alan','Milli Park','Orman Alanı','Kültür Varlığı')
                raw_name = tags.get('name:tr') or tags.get('name') or tags.get('operator') or ''
                name = raw_name if (raw_name and raw_name not in bad_names) else tip

                # İl ve ilçe: Nominatim'den al
                il, ilce = reverse_geocode(lat, lng)

                results.append({
                    'id': 'osm_' + str(e.get('id', uid())),
                    'tip': tip,
                    'ad': name,
                    'il': il,
                    'ilce': ilce,
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

    # Mevcut data.json'u oku + Firebase'den manuel kayitlari kurtar
    print("Mevcut veriler okunuyor...")
    manuel = []
    try:
        manuel = read_data()
        print(f"  Manuel kayit: {len(manuel)}")
    except Exception as e:
        print(f"  Mevcut veri alinamadi: {e}")

    # Mevcut kayitlarda bos il/ilce varsa doldur (bbox ile hizli)
    print("Bos il/ilce bilgileri dolduruluyor...")
    empty_records = [r for r in manuel if (not r.get('il') or r.get('il') == 'Türkiye' or not r.get('ilce'))
                    and r.get('koordinatlar',{}).get('lat',0)]
    print(f"  Bos il/ilce olan kayit: {len(empty_records)}")
    filled = 0
    for r in empty_records:
        lat = r.get('koordinatlar',{}).get('lat',0)
        lng = r.get('koordinatlar',{}).get('lng',0)
        if not lat or not lng:
            continue
        il_bbox = guess_il_bbox(lat, lng)
        if not r.get('il') or r.get('il') == 'Türkiye':
            r['il'] = il_bbox
        # Ilce icin de detayli bbox dene
        if not r.get('ilce'):
            r['ilce'] = guess_ilce_bbox(lat, lng, il_bbox)
        filled += 1
    print(f"  {filled} kayit guncellendi")

    # Alan adi yanlis olan kayitlari duzelt (ornegin RES kategorisinde "Maden Ocagi" yazan)
    bad_names = {'Maden Ocağı','Taş Ocağı','Mermer Ocağı','HES','GES','RES',
                 'Jeotermal','Sulak Alan','Milli Park','Orman Alanı','Kültür Varlığı'}
    name_fixed = 0
    for r in manuel:
        if r.get('ad','').strip() in bad_names and r.get('tip'):
            r['ad'] = r['tip']
            name_fixed += 1
    if name_fixed:
        print(f"  {name_fixed} kayitin alan adi duzeltildi")

    yeni = []
    for fn in [fetch_unesco, fetch_osm_kultur, fetch_wdpa, fetch_osm_data, fetch_gfw, fetch_depremler]:
        try:
            yeni += fn()
        except Exception as e:
            print(f"HATA {fn.__name__}: {e}")

    # Deduplicate: ID ve koordinat+tip bazında
    def dedup(records):
        seen_ids = set()
        seen_coords = set()  # (lat_2, lng_2, tip)
        result = []

        for r in records:
            rid = r.get('id','')
            tip = r.get('tip','')
            lat = round(r.get('koordinatlar',{}).get('lat',0), 3)  # ~100m hassasiyet
            lng = round(r.get('koordinatlar',{}).get('lng',0), 3)

            # 1. ID tekrarı
            if rid and rid in seen_ids:
                continue

            # 2. Aynı koordinat + tip (aynı noktada aynı kategori)
            coord_key = (lat, lng, tip)
            if coord_key in seen_coords:
                continue

            seen_ids.add(rid)
            seen_coords.add(coord_key)
            result.append(r)

        return result

    yeni_unique = dedup(yeni)

    # Manuel kayıtlarla çakışan otomatikleri çıkar
    manuel_coords = set()
    for r in manuel:
        lat = round(r.get('koordinatlar',{}).get('lat',0), 3)
        lng = round(r.get('koordinatlar',{}).get('lng',0), 3)
        manuel_coords.add((lat, lng, r.get('tip','')))

    yeni_no_clash = [r for r in yeni_unique if (
        round(r.get('koordinatlar',{}).get('lat',0), 3),
        round(r.get('koordinatlar',{}).get('lng',0), 3),
        r.get('tip','')
    ) not in manuel_coords]

    tum_veri = dedup(manuel + yeni_no_clash)

    print(f"\n{'='*50}")
    print(f"Manuel: {len(manuel)} | Otomatik: {len(yeni_unique)} | TOPLAM: {len(tum_veri)}")
    print(f"{'='*50}")

    # Diske yaz (git commit Actions tarafindan yapilir)
    try:
        write_data(tum_veri)
        print(f"OK: {len(tum_veri)} kayit yazildi!")
    except Exception as e:
        print(f"HATA: {e}")
        traceback.print_exc()
        raise

    print(f"\nTamamlandi: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")

if __name__ == '__main__':
    main()
