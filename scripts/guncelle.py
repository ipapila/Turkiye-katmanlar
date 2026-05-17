import json
import requests
import os
import base64

REPO_OWNER = "ipapila"
REPO_NAME  = "Turkiye-katmanlar"
FILE_PATH  = "data.json"

def get_remote_data():
    # Büyük dosyalar için raw URL kullan (API base64 limitini aşıyor)
    raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{FILE_PATH}"
    resp = requests.get(raw_url)
    if resp.status_code == 200:
        try:
            return resp.json(), get_sha()
        except Exception as e:
            print(f"❌ JSON parse hatası: {e}")
            return None, None
    else:
        print(f"❌ Veri alınamadı. HTTP {resp.status_code}")
        return None, None

def get_sha():
    token = os.environ.get('GITHUB_TOKEN')
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("sha")
    else:
        print(f"⚠️  SHA alınamadı: HTTP {resp.status_code}")
        return None

def update_remote_data(new_data, sha):
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN bulunamadı!")
        return
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    content = base64.b64encode(
        json.dumps(new_data, ensure_ascii=False, indent=2).encode()
    ).decode()
    payload = {"message": "Veri otomatik güncellendi", "content": content}
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        print(f"✅ GitHub güncellendi. ({len(new_data)} kayıt)")
    else:
        print(f"❌ Güncelleme hatası: {resp.status_code}")
        print(resp.text)

def main():
    print("📥 Veri çekiliyor...")
    data, sha = get_remote_data()
    if data is None:
        print("❌ Veri alınamadı, işlem durduruluyor.")
        return
    print(f"✅ {len(data)} kayıt yüklendi.")
    update_remote_data(data, sha)

if __name__ == "__main__":
    main()
