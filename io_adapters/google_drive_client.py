import os
import io
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

class GoogleDriveClient:
    def __init__(self, client_id, client_secret, refresh_token, root_folder_name="Ebook-Converter"):
        """
        初始化 Google Drive 客戶端 (OAuth 模式)
        """
        try:
            # 使用 Refresh Token 建立憑證
            creds = Credentials(
                None, # access_token 設為 None，讓它自動刷新
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret
            )
            
            self.service = build('drive', 'v3', credentials=creds)
            
            # 尋找根目錄 ID
            self.root_id = self._find_id_by_name(root_folder_name)
            if not self.root_id:
                raise FileNotFoundError(f"❌ 找不到根目錄: {root_folder_name} (請確認該資料夾存在於您的雲端硬碟)")
            logging.info(f"✅ Google Drive (OAuth) 連線成功，根目錄 ID: {self.root_id}")
            
        except Exception as e:
            logging.error(f"❌ Google Drive 初始化失敗: {e}")
            raise

    def _find_id_by_name(self, name, parent_id=None):
        """在指定父資料夾下尋找檔案/資料夾 ID"""
        query = f"name = '{name}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        # 這裡的邏輯不變
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def _ensure_folder_path(self, path):
        """解析路徑並回傳最終資料夾的 ID (如果不存在則自動建立)"""
        parts = [p for p in path.strip("/").split("/") if p]
        current_parent_id = self.root_id
        
        for part in parts:
            found_id = self._find_id_by_name(part, current_parent_id)
            if found_id:
                current_parent_id = found_id
            else:
                file_metadata = {
                    'name': part,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [current_parent_id]
                }
                folder = self.service.files().create(body=file_metadata, fields='id').execute()
                current_parent_id = folder.get('id')
                logging.info(f"   📁 自動建立資料夾: {part}")
        
        return current_parent_id

    def list_files(self, folder_path):
        """列出指定路徑下的檔案"""
        try:
            folder_id = self._ensure_folder_path(folder_path)
            query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            
            file_list = []
            for f in results.get('files', []):
                file_list.append({
                    'name': f['name'],
                    'id': f['id'],
                    'path_display': f"{folder_path}/{f['name']}",
                    'path_lower': f['id']
                })
            return file_list
        except Exception as e:
            logging.error(f"❌ 無法讀取目錄 {folder_path}: {e}")
            return []

    def download_file(self, file_id, local_path):
        """下載檔案"""
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

    def upload_file(self, local_path, remote_path):
        """上傳檔案"""
        try:
            folder_path = os.path.dirname(remote_path)
            file_name = os.path.basename(remote_path)
            folder_id = self._ensure_folder_path(folder_path)
            
            existing_id = self._find_id_by_name(file_name, folder_id)
            if existing_id:
                self.service.files().delete(fileId=existing_id).execute()

            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(local_path, resumable=True)
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True
        except Exception as e:
            logging.error(f"❌ 上傳失敗 {remote_path}: {e}")
            return False

    def move_file(self, file_id, dest_path):
        """移動檔案"""
        try:
            file = self.service.files().get(fileId=file_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            dest_folder_path = os.path.dirname(dest_path)
            new_parent_id = self._ensure_folder_path(dest_folder_path)
            
            self.service.files().update(
                fileId=file_id,
                addParents=new_parent_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            return True
        except Exception as e:
            logging.error(f"❌ 移動失敗: {e}")
            return False
