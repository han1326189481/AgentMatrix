import markdown
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

CSS_STYLE = """
* { box-sizing: border-box; }
body {
    font-family: "Microsoft YaHei", "SimHei", sans-serif;
    font-size: 13px; line-height: 1.8; color: #1a1a2e;
    max-width: 900px; margin: 0 auto; padding: 40px 50px;
}
h1 { font-size: 28px; border-bottom: 3px solid #2563eb; padding-bottom: 12px; color: #1e3a5f; margin-top: 40px; }
h2 { font-size: 22px; border-bottom: 2px solid #93c5fd; padding-bottom: 8px; color: #1e40af; margin-top: 35px; }
h3 { font-size: 17px; color: #1d4ed8; margin-top: 28px; }
h4 { font-size: 15px; color: #2563eb; margin-top: 22px; }
p { margin: 10px 0; }
code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: "Consolas","Courier New",monospace; font-size: 12px; }
pre { background: #0f172a; color: #e2e8f0; padding: 16px 20px; border-radius: 8px; overflow-x: auto; font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
pre code { background: transparent; padding: 0; color: #e2e8f0; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 12px; }
th { background: #1e40af; color: white; padding: 10px 12px; text-align: left; }
td { border: 1px solid #d1d5db; padding: 8px 12px; }
tr:nth-child(even) { background: #f8fafc; }
blockquote { border-left: 4px solid #93c5fd; padding: 8px 16px; margin: 16px 0; background: #eff6ff; color: #1e40af; }
a { color: #2563eb; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 30px 0; }
strong { color: #1e3a5f; }
@page { size: A4; margin: 2cm; }
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

md_file = "AgentMatrix 部署文档与安装说明.md"
pdf_file = "AgentMatrix 部署文档与安装说明.pdf"

md_path = os.path.join(DOCS_DIR, md_file)
pdf_path = os.path.join(DOCS_DIR, pdf_file)

print(f"Converting: {md_file} -> {pdf_file}")

with open(md_path, "r", encoding="utf-8") as f:
    md_content = f.read()

html_body = markdown.markdown(md_content, extensions=["fenced_code", "tables"])

full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>{CSS_STYLE}</style></head>
<body>{html_body}</body>
</html>"""

browser = find_browser()
if not browser:
    print("[ERROR] No browser found!")
    exit(1)

temp_html = os.path.join(DOCS_DIR, f"_temp_merge.html")
with open(temp_html, "w", encoding="utf-8") as f:
    f.write(full_html)

cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
       f"--print-to-pdf={pdf_path}", temp_html]

result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
if result.returncode == 0 and os.path.exists(pdf_path):
    sz = os.path.getsize(pdf_path)
    print(f"[OK] {pdf_file} ({sz//1024} KB)")
else:
    print(f"[WARN] Failed: {result.returncode}")

if os.path.exists(temp_html):
    os.unlink(temp_html)

print("[DONE]")