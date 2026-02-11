import os
import json
import shutil
import logging
import uuid
from pathlib import Path
from core.processor import parse_chapters, read_file_content, s2t_convert
from core.engine import generate_epub, run_kepubify
from io_adapters.dropbox_client import DropboxClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    base_dir = Path(__file__).resolve().parent
    io_config = load_json(base_dir / 'config' / 'io_config.json')
    profile_map = load_json(base_dir / 'config' / 'profile_map.json')
    
    try:
        app_key = os.environ['DROPBOX_APP_KEY']
        app_secret = os.environ['DROPBOX_APP_SECRET']
        refresh_token = os.environ['DROPBOX_REFRESH_TOKEN']
    except KeyError as e:
        logging.error(f"❌ 缺少環境變數: {e}")
        return

    client = DropboxClient(app_key, app_secret, refresh_token)
    
    work_dir = base_dir / 'temp_work'
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir()
    
    kepub_dir = work_dir / "kepub_out"
    kepub_dir.mkdir(exist_ok=True)

    # 讀取沙盒路徑配置
    input_base = io_config['directories']['input_base']
    archive_base = io_config['directories']['archive_base']
    epub_base = io_config['directories']['epub_base']
    output_base = io_config['directories']['output_base']

    for subfolder in io_config['monitor_subfolders']:
        logging.info(f"📂 正在掃描沙盒資料夾: {subfolder} ...")
        
        # 樣式選擇邏輯
        target_style_file = profile_map['default_style']
        for mapping in profile_map['mappings']:
            if mapping['keyword'] in subfolder:
                target_style_file = mapping['style_file']
                break
        
        style_path = base_dir / 'styles' / target_style_file
        style_config = load_json(style_path)
        if isinstance(style_config.get('css'), list):
            style_config['css'] = "\n".join(style_config['css'])

        # 在沙盒內列出檔案
        current_input_path = f"{input_base}/{subfolder}"
        files = client.list_files(current_input_path)
        
        if not files:
            continue

        for file_meta in files:
            filename = file_meta['name']
            if not filename.lower().endswith('.txt'):
                continue
                
            logging.info(f"   ⬇️ 處理新書: {filename}")
            safe_id = uuid.uuid4().hex
            local_txt_path = work_dir / f"{safe_id}.txt"
            
            try:
                # 1. 下載原始 TXT
                client.download_file(file_meta['path_lower'], local_txt_path)
                
                # 2. 文本處理與分章
                raw_content = read_file_content(local_txt_path)
                if not raw_content:
                    logging.error(f"   ❌ 編碼失敗: {filename}")
                    continue
                processed_content = s2t_convert(raw_content)
                chapters = parse_chapters(processed_content)
                
                # 3. 生成標準 EPUB (中間產物)
                temp_epub_path = work_dir / f"{safe_id}.epub"
                original_title = Path(filename).stem
                generate_epub(original_title, "Unknown", chapters, temp_epub_path, style_config)
                
                # --- [新增] 上傳標準 EPUB 到 epub/已轉檔 ---
                final_epub_name = f"{original_title}.epub"
                target_epub_path = f"{epub_base}/{subfolder}/{final_epub_name}"
                logging.info(f"   ☁️ 備份標準 EPUB: {final_epub_name}")
                client.upload_file(temp_epub_path, target_epub_path)
                
                # 4. 執行 KePub 轉換
                if run_kepubify(temp_epub_path, kepub_dir):
                    # 尋找轉換後的檔案
                    possible_names = [f"{safe_id}.kepub.epub", f"{safe_id}_converted.kepub.epub"]
                    found_file = next((kepub_dir / n for n in possible_names if (kepub_dir / n).exists()), None)
                    
                    if not found_file:
                        logging.error(f"   ❌ KePub 轉換成功但找不到檔案")
                        continue

                    # 5. 上傳 KePub 到 kepub/已轉檔
                    final_kepub_name = f"{original_title}.kepub.epub"
                    target_output_path = f"{output_base}/{subfolder}/{final_kepub_name}"
                    logging.info(f"   ☁️ 上傳最終 KePub: {final_kepub_name}")
                    
                    if client.upload_file(found_file, target_output_path):
                        # 6. 歸檔原始 TXT
                        target_archive_path = f"{archive_base}/{subfolder}/{filename}"
                        client.move_file(file_meta['path_lower'], target_archive_path)
                        logging.info(f"   ✅ 全部流程完成: {filename}")
                else:
                    logging.error(f"   ❌ Kepubify 執行失敗")
                
            except Exception as e:
                logging.error(f"   ❌ 處理中斷 {filename}: {e}")

    if work_dir.exists():
        shutil.rmtree(work_dir)
    logging.info("🏁 任務結束")

if __name__ == "__main__":
    main()
