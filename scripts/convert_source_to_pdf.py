import markdown
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

CSS_STYLE = """
* { box-sizing: border-box; }
body {
    font-family: "Microsoft YaHei", "SimHei", "Consolas", monospace;
    font-size: 11px; line-height: 1.6; color: #1a1a2e;
    max-width: 1000px; margin: 0 auto; padding: 30px 40px;
}
h1 { font-size: 24px; border-bottom: 3px solid #2563eb; padding-bottom: 10px; color: #1e3a5f; margin-top: 30px; }
h2 { font-size: 15px; border-bottom: 1px solid #93c5fd; padding-bottom: 5px; color: #1e40af; margin-top: 25px; font-family: "Consolas","Courier New",monospace; }
pre { background: #0f172a; color: #e2e8f0; padding: 12px 16px; border-radius: 6px; overflow-x: auto; font-size: 9px; line-height: 1.4; white-space: pre-wrap; word-break: break-all; }
pre code { background: transparent; padding: 0; color: #e2e8f0; font-size: 9px; }
code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 9px; }
blockquote { border-left: 3px solid #93c5fd; padding: 5px 12px; margin: 10px 0; background: #eff6ff; color: #1e40af; font-size: 11px; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }
@page { size: A4; margin: 1.5cm; }
"""

def find_browser():
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def convert_md_to_pdf(md_filename, pdf_filename):
    md_path = os.path.join(DOCS_DIR, md_filename)
    pdf_path = os.path.join(DOCS_DIR, pdf_filename)

    if not os.path.exists(md_path):
        print(f"[ERROR] File not found: {md_path}")
        return False

    browser = find_browser()
    if not browser:
        print("[ERROR] No browser found!")
        return False

    print(f"  Reading markdown...")
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    print(f"  Converting to HTML...")
    # Limit content to avoid memory issues
    if len(md_content) > 1000000:
        print(f"  [WARN] File too large ({len(md_content)//1024}KB), truncating...")
        md_content = md_content[:1000000]

    html_body = markdown.markdown(md_content, extensions=["fenced_code", "tables"])

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>{CSS_STYLE}</style></head>
<body>{html_body}</body>
</html>"""

    temp_html = os.path.join(DOCS_DIR, f"_temp_source.html")
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(full_html)

    cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
           f"--print-to-pdf={pdf_path}", temp_html]
    
    print(f"  Generating PDF via browser...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(pdf_path):
            sz = os.path.getsize(pdf_path)
            print(f"  [OK] {pdf_filename} ({sz//1024} KB)")
        else:
            print(f"  [WARN] Browser returned {result.returncode}")
            return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False
    finally:
        if os.path.exists(temp_html):
            os.unlink(temp_html)
    return True


if __name__ == "__main__":
    browser_path = find_browser()
    print(f"Browser: {browser_path}")
    
    md_file = "AgentMatrix 源代码.md"
    pdf_file = "AgentMatrix 源代码.pdf"
    
    print(f"Converting: {md_file} -> {pdf_file}")
    convert_md_to_pdf(md_file, pdf_file)
    
    print("\n[DONE] Source code PDF generated!")