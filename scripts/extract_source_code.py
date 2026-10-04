import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_MD = os.path.join(PROJECT_ROOT, "docs", "AgentMatrix 源代码.md")

# Directories/files to exclude
EXCLUDE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "venv", ".venv",
    "dist", "build", ".turbo", ".trae", "logs", "data",
    "frontend\\frontend",  # Duplicate nested frontend
}

EXCLUDE_FILES = {
    ".DS_Store", "Thumbs.db", "*.pyc", "*.pyo",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "ollama_models.json",
}

# Only include these extensions
INCLUDE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".css", ".html", ".md", ".bat", ".ps1",
    ".sh", ".txt", ".env.example", ".editorconfig", ".prettierrc",
    ".eslintrc.js", "Dockerfile", ".gitignore",
}

MAX_FILE_SIZE = 200 * 1024

LANG_MAP = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
    ".jsx": "jsx", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".cfg": "ini", ".ini": "ini", ".css": "css",
    ".html": "html", ".md": "markdown", ".bat": "batch", ".ps1": "powershell",
    ".sh": "bash", ".txt": "text",
}


def should_exclude_dir(dirname):
    for ex in EXCLUDE_DIRS:
        if ex in dirname:
            return True
    return False


def should_include_file(filename):
    name = os.path.basename(filename)
    # Exact match
    if name in EXCLUDE_FILES:
        return False
    # Extension match
    _, ext = os.path.splitext(name)
    if ext.lower() in INCLUDE_EXTENSIONS:
        return True
    # Special files without extensions
    special_names = {"Dockerfile", ".gitignore", ".editorconfig", ".prettierrc", ".env.example", ".eslintrc.js"}
    if name in special_names:
        return True
    return False


def get_language(filename):
    _, ext = os.path.splitext(filename)
    if ext.lower() in LANG_MAP:
        return LANG_MAP[ext.lower()]
    name = os.path.basename(filename)
    if name == "Dockerfile":
        return "dockerfile"
    if name in {".gitignore", ".editorconfig", ".prettierrc"}:
        return "text"
    return "text"


def collect_files(root_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter dirs in-place
        dirnames[:] = [d for d in dirnames if not should_exclude_dir(os.path.join(dirpath, d))]
        
        for fname in filenames:
            fullpath = os.path.join(dirpath, fname)
            if should_include_file(fullpath):
                files.append(fullpath)
    return sorted(files)


def generate_source_md():
    all_files = collect_files(PROJECT_ROOT)
    
    with open(OUTPUT_MD, "w", encoding="utf-8") as out:
        out.write("# AgentMatrix 完整源代码\n\n")
        out.write(f"> 项目根目录: {PROJECT_ROOT}\n")
        out.write(f"> 包含文件数: {len(all_files)}\n")
        out.write(f"> 生成日期: 2026-05-17\n\n")
        out.write("---\n\n")
        
        # Table of contents
        out.write("## 文件索引\n\n")
        for fpath in all_files:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            out.write(f"- `{rel}`\n")
        out.write("\n---\n\n")
        
        for fpath in all_files:
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            fsize = os.path.getsize(fpath)
            
            if fsize > MAX_FILE_SIZE:
                out.write(f"## {rel}\n\n")
                out.write(f"> ⚠️ 文件过大 ({fsize//1024} KB)，已跳过内容\n\n")
                out.write("---\n\n")
                continue
            
            lang = get_language(fpath)
            
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                out.write(f"## {rel}\n\n")
                out.write(f"> ⚠️ 二进制文件，无法读取\n\n")
                out.write("---\n\n")
                continue
            
            out.write(f"## {rel}\n\n")
            
            # Add code block
            if len(content) > 50000:
                # Truncate very long files
                content = content[:50000] + "\n\n... (内容过长，已截断) ..."
            
            out.write(f"```{lang}\n")
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write("```\n\n")
            out.write("---\n\n")
    
    md_size = os.path.getsize(OUTPUT_MD)
    print(f"[OK] Generated: {OUTPUT_MD}")
    print(f"     Files: {len(all_files)}")
    print(f"     Size:  {md_size//1024} KB")


if __name__ == "__main__":
    generate_source_md()