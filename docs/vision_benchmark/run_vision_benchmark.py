"""文档图像识别能力评测 —— 走项目真实 VisionPlugin 链路

用法（需 Ollama 已就绪且已 pull qwen2.5vl:7b）：
    python docs/vision_benchmark/gen_doc_images.py      # 先生成样本
    python docs/vision_benchmark/run_vision_benchmark.py

产出：同目录 result.json（含逐样本原始输出与耗时，不做任何后处理）
"""
import base64
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
IMAGES = os.path.join(HERE, "images")

os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

from core.llm.vision_plugin import VisionPlugin  # noqa: E402

CASES = [
    ("01_ppt.png", "PPT 幻灯片：标题 + 4 条项目符号 + 3列表格(表头+3行)"),
    ("02_word.png", "Word 文档页：H1 + 段落 + H2 + 有序列表 + 表注 + 2列表格(表头+3行)"),
    ("03_excel.png", "Excel 表格：6列 × 7行（中文表头 + 数字）"),
    ("04_excel_lowres.jpg", "同 Excel，但 540x235 + JPEG q42（模拟模糊截图）"),
]


def main():
    plugin = VisionPlugin()
    results = []
    log = []

    for name, desc in CASES:
        path = os.path.join(IMAGES, name)
        if not os.path.exists(path):
            log.append(f"{name}: 跳过（样本不存在，请先运行 gen_doc_images.py）")
            continue
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        t0 = time.time()
        try:
            out = plugin.recognize_images([b64])[0]
        except Exception as e:  # noqa: BLE001
            out = f"[EXCEPTION] {type(e).__name__}: {e}"
        dt = time.time() - t0
        results.append({"file": name, "desc": desc, "elapsed_s": round(dt, 1), "output": out})
        log.append(f"{name}: {dt:.1f}s, {len(out)} chars")

    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as f:
        json.dump({"model": plugin.vision_model, "results": results}, f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(HERE, "run.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))

    print("\n".join(log) or "(no samples processed)")


if __name__ == "__main__":
    main()
