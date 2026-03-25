import json
import requests
import os
import base64

REPO_OWNER = "ipapila"
REPO_NAME = "Turkiye-katmanlar"
FILE_PATH = "data.json"

def get_remote_data():
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("❌ HATA: GITHUB_TOKEN ortam değişkeni bulunamadı!")
        return None, None
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        content = data["content"]
        sha = data["sha"]
        decoded = base64.b64decode(content).decode("utf-8")
        return json.loads(decoded), sha
    else:
        print(f"❌ Veri alınamadı. HTTP {resp.status_code}")
        print("Detay:", resp.text)
        return None, None

def update_remote_data(new_data, sha):
    token = os.environ.get('GITHUB_TOKEN')
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    content = base64.b64encode(json.dumps(new_data, ensure_ascii=False, indent=2).encode()).decode()
    payload = {"message": "Veri otomatik güncellendi", "content": content, "sha": sha}
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print("✅ Güncelleme başarılı.")
    else:
        print(f"❌ Güncelleme hatası: {resp.status_code}")
        print(resp.text)

def main():
    data, sha = get_remote_data()
    if data is None:
        return
    # Örnek değişiklik: tüm kayıtlara yeni bir alan ekle
    for item in data:
        item["son_guncelleme"] = "2025-03-25"
    update_remote_data(data, sha)

if __name__ == "__main__":
    main()