import os
import json
import shutil
import logging
import uuid
from pathlib import Path
from core.processor import parse_chapters, read_file_content, s2t_convert
from core.engine import generate_epub, run_kepubify
from io_adapters.dropbox_client import DropboxClient

# 設定日誌格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    # 1. 讀取配置
    base_dir = Path(__file__).resolve().parent
    io_config = load_json(base_dir / 'config' / 'io_config.json')
    profile_map = load_json(base_dir / 'config' / 'profile_map.json')
    
    # 2. 初始化 Dropbox 客戶端
    try:
        app_key = os.environ['DROPBOX_APP_KEY']
        app_secret = os.environ['DROPBOX_APP_SECRET']
        refresh_token = os.environ['DROPBOX_REFRESH_TOKEN']
    except KeyError as e:
        logging.error(f"❌ 缺少環境變數: {e}")
        return

    client = DropboxClient(app_key, app_secret, refresh_token)
    
    # 3. 準備臨時工作區
    work_dir = base_dir / 'temp_work'
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir()
    
    # 準備 Kepub 輸出目錄
    kepub_dir = work_dir / "kepub_out"
    kepub_dir.mkdir(exist_ok=True)

    # 4. 開始掃描
    input_base = io_config['directories']['input_base']
    output_base = io_config['directories']['output_base']
    archive_base = io_config['directories']['archive_base']

    for subfolder in io_config['monitor_subfolders']:
        logging.info(f"📂 正在掃描: {subfolder} ...")
        
        # 匹配樣式
        target_style_file = profile_map['default_style']
        for mapping in profile_map['mappings']:
            if mapping['keyword'] in subfolder:
                target_style_file = mapping['style_file']
                break
        
        style_path = base_dir / 'styles' / target_style_file
        style_config = load_json(style_path)
        if isinstance(style_config.get('css'), list):
            style_config['css'] = "\n".join(style_config['css'])

        # 列出 Dropbox 檔案
        current_input_path = f"{input_base}/{subfolder}"
        files = client.list_files(current_input_path)
        
        if not files:
            continue

        for file_meta in files:
            filename = file_meta['name']
            if not filename.lower().endswith('.txt'):
                continue
                
            logging.info(f"   ⬇️ 處理新書: {filename}")
            
            # 使用 UUID 作為本地臨時檔名，避開特殊符號問題
            safe_id = uuid.uuid4().hex
            local_txt_path = work_dir / f"{safe_id}.txt"
            
            try:
                # 下載
                client.download_file(file_meta['path_lower'], local_txt_path)
                
                # 讀取與處理
                raw_content = read_file_content(local_txt_path)
                if not raw_content:
                    logging.error(f"   ❌ 編碼失敗: {filename}")
                    continue

                processed_content = s2t_convert(raw_content)
                chapters = parse_chapters(processed_content)
                
                # 生成標準 EPUB (使用安全檔名)
                temp_epub_path = work_dir / f"{safe_id}.epub"
                
                # 書名和作者依然使用原始資訊
                original_title = Path(filename).stem
                author = "Unknown" # 未來可擴展解析邏輯
                
                generate_epub(original_title, author, chapters, temp_epub_path, style_config)
                
                # 轉換為 KePub (這步最關鍵，現在輸入輸出都是純英文數字)
                if run_kepubify(temp_epub_path, kepub_dir):
                    # 預期的輸出檔名 (kepubify 會自動加上 .kepub.epub)
                    expected_output = kepub_dir / f"{safe_id}.kepub.epub"
                    
                    if not expected_output.exists():
                        logging.error(f"   ❌ 轉換後檔案遺失，可能 kepubify 執行失敗")
                        continue

                    # 準備上傳 (這裡改回原本的中文檔名)
                    final_kepub_name = f"{original_title}.kepub.epub"
                    target_output_path = f"{output_base}/{subfolder}/{final_kepub_name}"
                    
                    logging.info(f"   ☁️ 上傳為: {final_kepub_name}")
                    if client.upload_file(expected_output, target_output_path):
                        # 只有上傳成功才歸檔
                        target_archive_path = f"{archive_base}/{subfolder}/{filename}"
                        client.move_file(file_meta['path_lower'], target_archive_path)
                        logging.info(f"   ✅ 全部完成: {filename}")
                else:
                    logging.error(f"   ❌ Kepubify 轉換指令返回錯誤")
                
            except Exception as e:
                logging.error(f"   ❌ 異常中斷 {filename}: {e}")
                # 發生錯誤時，不要刪除 Dropbox 上的原檔，以便重試

    # 清理臨時區
    if work_dir.exists():
        shutil.rmtree(work_dir)
    logging.info("🏁 任務結束")

if __name__ == "__main__":
    main()
