import os
import zipfile
import shutil
import re
import logging
from pathlib import Path

def natural_sort_key(s):
    """自然排序算法，確保 '2.jpg' 在 '10.jpg' 之前"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]

def rebuild_manga_epub(input_epub, output_epub, style_config):
    """
    解壓 EPUB，提取圖片，按順序重新打包並生成自定義目錄
    """
    # 從樣式配置獲取參數
    pages_per_chapter = style_config.get('pages_per_chapter', 20)
    template = style_config.get('chapter_template', "({start}-{end}頁)")
    css_rules = "\n".join(style_config.get('css', []))

    # 1. 建立臨時工作區
    temp_extract = Path("temp_extract_zone")
    build_dir = Path("temp_build_zone")
    for d in [temp_extract, build_dir]:
        if d.exists(): shutil.rmtree(d)
        d.mkdir()

    try:
        # 2. 提取所有圖片
        with zipfile.ZipFile(input_epub, 'r') as z:
            z.extractall(temp_extract)
        
        extensions = ('.jpg', '.jpeg', '.png', '.webp')
        images = []
        for ext in extensions:
            images.extend(list(temp_extract.rglob(f"*{ext}")))
        
        # 排除隱藏文件並進行自然排序
        images = sorted([img for img in images if not img.name.startswith('.')], key=lambda x: natural_sort_key(x.name))
        
        if not images:
            logging.error("❌ 在 EPUB 中找不到任何圖片檔")
            return False

        # 3. 初始化 EPUB 結構
        (build_dir / "META-INF").mkdir()
        (build_dir / "OEBPS" / "images").mkdir(parents=True)
        
        with open(build_dir / "mimetype", "w") as f: f.write("application/epub+zip")
        with open(build_dir / "META-INF" / "container.xml", "w") as f:
            f.write('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        
        with open(build_dir / "OEBPS" / "style.css", "w") as f: f.write(css_rules)

        manifest, spine, toc_links = [], [], []

        # 4. 重新封裝每一頁
        for i, img_path in enumerate(images):
            ext = img_path.suffix
            new_img_name = f"img_{i:04d}{ext}"
            shutil.copy(img_path, build_dir / "OEBPS" / "images" / new_img_name)

            xhtml_name = f"page_{i:04d}.xhtml"
            with open(build_dir / "OEBPS" / xhtml_name, "w") as f:
                f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head>
<link rel="stylesheet" type="text/css" href="style.css"/><title>{i+1}</title></head>
<body><div class="page-box"><img src="images/{new_img_name}"/></div></body></html>''')

            manifest.append(f'<item id="p{i}" href="{xhtml_name}" media-type="application/xhtml+xml"/>')
            # 判斷圖片類型
            m_type = "image/jpeg" if "jpg" in ext.lower() or "jpeg" in ext.lower() else f"image/{ext[1:]}"
            manifest.append(f'<item id="i{i}" href="images/{new_img_name}" media-type="{m_type}"/>')
            spine.append(f'<itemref idref="p{i}"/>')

            # 建立分章導航
            if i % pages_per_chapter == 0:
                start = i + 1
                end = min(i + pages_per_chapter, len(images))
                chapter_title = template.format(start=start, end=end)
                toc_links.append(f'<li><a href="{xhtml_name}">{chapter_title}</a></li>')

        # 5. 生成 OPF 和 NAV (EPUB 3 標準)
        opf_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:uuid:{os.urandom(8).hex()}</dc:identifier>
<dc:title>Manga Rebuilt</dc:title><dc:language>zh</dc:language></metadata>
<manifest><item id="css" href="style.css" media-type="text/css"/><item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>{"".join(manifest)}</manifest>
<spine>{"".join(spine)}</spine></package>'''
        
        with open(build_dir / "OEBPS" / "content.opf", "w", encoding="utf-8") as f: f.write(opf_content)

        nav_content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Navigation</title></head><body><nav epub:type="toc"><h1>目錄</h1><ol>{"".join(toc_links)}</ol></nav></body></html>'''
        
        with open(build_dir / "OEBPS" / "nav.xhtml", "w", encoding="utf-8") as f: f.write(nav_content)

        # 6. 最後打包
        with zipfile.ZipFile(output_epub, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            # mimetype 必須是第一個且不壓縮
            z.write(build_dir / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
            for f in build_dir.rglob('*'):
                if f.name != "mimetype":
                    z.write(f, f.relative_to(build_dir))
        
        return True

    except Exception as e:
        logging.error(f"❌ 重組過程發生異常: {e}")
        return False
    finally:
        # 清理
        shutil.rmtree(temp_extract, ignore_errors=True)
        shutil.rmtree(build_dir, ignore_errors=True)
