# core/processor.py
import html
import re
from pathlib import Path

# 嘗試匯入 OpenCC，如果環境沒有安裝則降級處理
try:
    from opencc import OpenCC
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False

def read_file_content(path: Path):
    """
    全能編碼讀取器
    嘗試列表: utf-8-sig, utf-8, gb18030, big5, utf-16
    """
    try:
        raw_data = path.read_bytes()
    except Exception as e:
        print(f"❌ 读取错误: {e}")
        return None

    encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'big5', 'utf-16']
    for enc in encodings:
        try:
            return raw_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None

def s2t_convert(text, use_opencc=True):
    """
    繁簡轉換與標點標準化
    """
    # 1. HTML 轉義 (防止 XML 結構崩壞)
    text = html.escape(text, quote=False)
    
    # 2. OpenCC 轉換 (如果可用)
    if HAS_OPENCC and use_opencc:
        cc = OpenCC('s2t')
        text = cc.convert(text)
        
    # 3. 標點符號標準化 (將彎引號轉為直角引號)
    return text.replace('“', '「').replace('”', '」').replace('‘', '『').replace('’', '』')

def parse_chapters(full_text):
    """
    智能分章邏輯 (使用強健的正則表達式)
    返回: list of (title, content) tuples
    """
    # 統一換行符號
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # 匹配模式：(行首或換行) + 空白 + 第X章 + (換行或結尾)
    chapter_pattern = re.compile(r'(?:^|\n)\s*(第[0-9一二三四五六七八九十百千万]+[章回卷节].*)(?:\n|$)')
    
    parts = chapter_pattern.split(clean_text)
    chapters = []
    
    # 處理序言
    if parts[0].strip():
        chapters.append(("序言", parts[0]))
    
    # 處理章節 (parts[1]是標題, parts[2]是內容...)
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                chapters.append((parts[i].strip(), parts[i+1]))
    else:
        # 如果沒分章，全本當作一章
        chapters.append(("正文", clean_text))
        
    return chapters
