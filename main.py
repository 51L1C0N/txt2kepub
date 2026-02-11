import os
import json
import shutil
import logging
from pathlib import Path
from core.processor import parse_chapters
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
    
    # 2. 初始化 Dropbox 客戶端 (從環境變數讀取密鑰)
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

    # 4. 開始掃描每個子資料夾 (001, 002, 003)
    input_base = io_config['directories']['input_base']
    output_base = io_config['directories']['output_base']
    archive_base = io_config['directories']['archive_base']

    for subfolder in io_config['monitor_subfolders']:
        logging.info(f"📂 正在掃描資料夾: {subfolder} ...")
        
        # 匹配樣式
        target_style_file = profile_map['default_style'] # 預設
        for mapping in profile_map['mappings']:
            if mapping['keyword'] in subfolder:
                target_style_file = mapping['style_file']
                break
        
        # 讀取樣式內容
        style_path = base_dir / 'styles' / target_style_file
        style_config = load_json(style_path)
        # 將 CSS 列表轉換為字符串
        if isinstance(style_config.get('css'), list):
            style_config['css'] = "\n".join(style_config['css'])

        logging.info(f"   🎨 套用樣式: {target_style_file}")

        # 列出 Dropbox 檔案
        current_input_path = f"{input_base}/{subfolder}"
        files = client.list_files(current_input_path)
        
        if not files:
            logging.info("   (無新檔案)")
            continue

        for file_meta in files:
            filename = file_meta['name']
            if not filename.lower().endswith('.txt'):
                continue
                
            logging.info(f"   ⬇️ 發現新書: {filename}")
            
            # 下載 TXT
            local_txt_path = work_dir / filename
            client.download_file(file_meta['path_lower'], local_txt_path)
            
            # 讀取內容並分章
            try:
                # 讀取內容
                from core.processor import read_file_content, s2t_convert
                raw_content = read_file_content(local_txt_path)
                
                if not raw_content:
                    logging.error(f"   ❌ 編碼識別失敗: {filename}")
                    continue

                # 繁簡轉換
                processed_content = s2t_convert(raw_content)
                
                # 分章
                chapters = parse_chapters(processed_content)
                
                # 生成 EPUB
                epub_name = local_txt_path.stem + ".epub"
                local_epub_path = work_dir / epub_name
                
                # 解析作者 (簡單邏輯：書名)
                title = local_txt_path.stem
                author = "Unknown"
                
                generate_epub(title, author, chapters, local_epub_path, style_config)
                
                # 轉換為 KePub
                kepub_dir = work_dir / "kepub_out"
                kepub_dir.mkdir(exist_ok=True)
                
                if run_kepubify(local_epub_path, kepub_dir):
                    kepub_filename = f"{local_txt_path.stem}.kepub.epub"
                    local_kepub_path = kepub_dir / kepub_filename
                    
                    # 上傳到 Output (Kobo 資料夾)
                    target_output_path = f"{output_base}/{subfolder}/{kepub_filename}"
                    client.upload_file(local_kepub_path, target_output_path)
                    
                    # 歸檔原始 TXT
                    target_archive_path = f"{archive_base}/{subfolder}/{filename}"
                    client.move_file(file_meta['path_lower'], target_archive_path)
                    
                    logging.info(f"   ✅ 處理完成: {filename}")
                
            except Exception as e:
                logging.error(f"   ❌ 處理失敗 {filename}: {e}")
                import traceback
                traceback.print_exc()

    # 清理臨時區
    shutil.rmtree(work_dir)
    logging.info("🏁 全部任務結束")

if __name__ == "__main__":
    main()
