import json
import requests
import os
import base64

# GitHub bilgileri
REPO_OWNER = "ipapila"          # kendi kullanıcı adınız
REPO_NAME = "Turkiye-katmanlar" # repo adı
FILE_PATH = "data.json"

def get_remote_data():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        content = data["content"]
        sha = data["sha"]
        decoded = base64.b64decode(content).decode("utf-8")
        return json.loads(decoded), sha
    else:
        print(f"Veri alınamadı. HTTP {resp.status_code}")
        return None, None

def update_remote_data(new_data, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN')}", "Content-Type": "application/json"}
    content = base64.b64encode(json.dumps(new_data, ensure_ascii=False, indent=2).encode()).decode()
    payload = {
        "message": "Veri otomatik güncellendi",
        "content": content,
        "sha": sha
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print("✅ Güncelleme başarılı.")
    else:
        print(f"❌ Hata: {resp.status_code} - {resp.text}")

def main():
    data, sha = get_remote_data()
    if data is None:
        return
    # Burada data üzerinde istediğiniz değişiklikleri yapın
    # Örnek: tüm kayıtlara yeni bir alan eklemek
    for item in data:
        item["son_guncelleme"] = "2025-03-25"
    update_remote_data(data, sha)

if __name__ == "__main__":
    main()
