import zipfile
import uuid
import subprocess
import os
import stat
from datetime import datetime
from pathlib import Path

def generate_epub(title, author, chapters, output_path, style_config):
    """
    生成標準 EPUB 文件
    """
    book_uuid = uuid.uuid4()
    
    # CSS 處理
    css_content = style_config.get('css', "")
    
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('OEBPS/style.css', css_content)
        
        manifest, spine, toc_html = [], [], []
        
        for i, (ch_title, ch_text) in enumerate(chapters):
            filename = f"chapter_{i}.xhtml"
            paras = "".join([f"<p>{p}</p>" for p in ch_text.splitlines()])
            xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{ch_title}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body><h2>{ch_title}</h2>{paras}</body></html>'''
            
            z.writestr(f'OEBPS/{filename}', xhtml)
            manifest.append(f'<item id="ch{i}" href="{filename}" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="ch{i}"/>')
            toc_html.append(f'<li><a href="{filename}">{ch_title}</a></li>')

        opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>zh-TW</dc:language>
    <meta property="dcterms:modified">{datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>
</metadata>
<manifest>
    <item id="style" href="style.css" media-type="text/css"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    {"".join(manifest)}
</manifest>
<spine>{"".join(spine)}</spine>
</package>'''
        z.writestr('OEBPS/content.opf', opf)
        
        nav = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head><body><nav epub:type="toc"><h1>目录</h1><ol>{"".join(toc_html)}</ol></nav></body></html>'''
        z.writestr('OEBPS/nav.xhtml', nav)

def run_kepubify(epub_path, output_dir):
    """
    調用 bin/kepubify 進行轉換 (Debug 模式)
    """
    project_root = Path(__file__).resolve().parent.parent
    kepubify_path = project_root / 'bin' / 'kepubify'

    if not kepubify_path.exists():
        print(f"🚨 錯誤：找不到工具 {kepubify_path}")
        return False

    st = os.stat(kepubify_path)
    os.chmod(kepubify_path, st.st_mode | stat.S_IEXEC)

    # 打印調試信息
    print(f"🔧 執行工具: {kepubify_path}")
    print(f"📄 輸入檔案: {epub_path} (Size: {epub_path.stat().st_size} bytes)")
    print(f"📂 輸出目錄: {output_dir}")

    try:
        # 強制捕獲並打印所有輸出
        result = subprocess.run(
            [str(kepubify_path), str(epub_path), '-o', str(output_dir)], 
            check=False, # 不自動報錯，讓我們自己處理
            capture_output=True
        )
        
        # 打印工具的「心聲」
        if result.stdout:
            print(f"📋 [Kepubify Stdout]:\n{result.stdout.decode(errors='ignore')}")
        if result.stderr:
            print(f"⚠️ [Kepubify Stderr]:\n{result.stderr.decode(errors='ignore')}")
            
        if result.returncode != 0:
            print(f"❌ Kepubify 返回錯誤代碼: {result.returncode}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ 執行異常: {e}")
        return False
