import requests
import json
import os
from pathlib import Path

class DropboxClient:
    def __init__(self, app_key, app_secret, refresh_token):
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.access_token = self._get_new_token()

    def _get_new_token(self):
        url = "https://api.dropbox.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.app_key,
            "client_secret": self.app_secret,
        }
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            token = response.json().get("access_token")
            print("🔑 Dropbox 授權成功")
            return token
        except Exception as e:
            print(f"❌ 授權失敗: {e}")
            raise

    def list_files(self, folder_path):
        url = "https://api.dropboxapi.com/2/files/list_folder"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "path": folder_path,
            "recursive": False
        }
        
        # ✅ 修正這裡：初始化 files 清單
        files = []
        
        try:
            payload = json.dumps(data) 
            response = requests.post(url, headers=headers, data=payload)
            
            if response.status_code == 409: 
                print(f"⚠️ 資料夾不存在或路徑錯誤: {folder_path}")
                return []
                
            response.raise_for_status()
            entries = response.json().get("entries", [])
            
            for entry in entries:
                if entry[".tag"] == "file":
                    files.append(entry)
            return files
        except Exception as e:
            if 'response' in locals() and response.status_code == 400:
                 print(f"❌ 請求內容錯誤: {response.text}")
            print(f"⚠️ 讀取目錄失敗 ({folder_path}): {e}")
            return []

    def download_file(self, dropbox_path, local_path):
        url = "https://content.dropboxapi.com/2/files/download"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Dropbox-API-Arg": json.dumps({"path": dropbox_path})
        }
        
        try:
            with requests.post(url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            print(f"⬇️ 下載完成: {Path(dropbox_path).name}")
            return True
        except Exception as e:
            print(f"❌ 下載失敗: {e}")
            return False

    def upload_file(self, local_path, dropbox_path):
        url = "https://content.dropboxapi.com/2/files/upload"
        
        with open(local_path, "rb") as f:
            data = f.read()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": json.dumps({
                "path": dropbox_path,
                "mode": "overwrite",
                "mute": True
            })
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            print(f"☁️ 上傳成功: {dropbox_path}")
            return True
        except Exception as e:
            print(f"❌ 上傳失敗: {e}")
            return False

    def move_file(self, from_path, to_path):
        url = "https://api.dropboxapi.com/2/files/move_v2"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "from_path": from_path,
            "to_path": to_path,
            "autorename": True
        }
        
        try:
            payload = json.dumps(data)
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            print(f"📦 已歸檔: {Path(from_path).name}")
            return True
        except Exception as e:
            print(f"❌ 歸檔失敗: {e}")
            return False
