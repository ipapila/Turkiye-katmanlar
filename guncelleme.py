# guncelle.py
import json
import requests

# GitHub repo bilgileri (kendi bilgilerinizle değiştirin)
REPO_OWNER = "ipapila"
REPO_NAME = "Turkiye-katmanlar"
FILE_PATH = "data.json"
GITHUB_TOKEN = "your_token_here"  # GitHub token (repo yazma izni)

def get_remote_data():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        content = data["content"]
        sha = data["sha"]
        import base64
        decoded = base64.b64decode(content).decode("utf-8")
        return json.loads(decoded), sha
    else:
        print("Veri alınamadı.")
        return None, None

def update_remote_data(new_data, sha):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"}
    import base64
    content = base64.b64encode(json.dumps(new_data, ensure_ascii=False, indent=2).encode()).decode()
    payload = {
        "message": "Veri güncellendi",
        "content": content,
        "sha": sha
    }
    resp = requests.put(url, headers=headers, json=payload)
    if resp.status_code == 200:
        print("✅ Güncelleme başarılı.")
    else:
        print(f"❌ Hata: {resp.status_code} - {resp.text}")

# Örnek kullanım
data, sha = get_remote_data()
if data:
    # Burada data üzerinde değişiklik yapabilirsiniz
    # Örneğin tüm kayıtlara yeni bir alan eklemek
    for item in data:
        item["guncellendi"] = "2025-03-23"
    update_remote_data(data, sha)