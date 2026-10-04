# -*- coding: utf-8 -*-
"""端到端验证：修复 A 上线后走真实 VisionPlugin.recognize_images 全链路。
与 run_vision_benchmark.py 的区别：那次输出是修复前的原始形态；
这次验证 recognize_images 返回的结果应已不含外层 markdown 围栏。

注意：会覆盖 docs/vision_benchmark/result.json 为"修复后"的输出，
用于对比留档（原"修复前"数据已在评测报告 md 中引用）。
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

OUT = r"D:\AgentMatrix\_fixa_e2e.txt"
lines = []

def main():
    plugin = VisionPlugin()
    results = []
    for name, desc in [
        ("01_ppt.png", "PPT 幻灯片"),
        ("02_word.png", "Word 文档页"),
        ("03_excel.png", "Excel 6x7"),
        ("04_excel_lowres.jpg", "Excel 劣化版"),
    ]:
        path = os.path.join(IMAGES, name)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        t0 = time.time()
        try:
            out = plugin.recognize_images([b64])[0]
        except Exception as e:  # noqa: BLE001
            out = f"[EXCEPTION] {type(e).__name__}: {e}"
        dt = time.time() - t0
        results.append({"file": name, "desc": desc, "elapsed_s": round(dt, 1), "output": out})
        fenced = out.startswith("```markdown") or out.startswith("```md")
        lines.append(f"{name}: {dt:.1f}s, {len(out)} chars, 含外层围栏={fenced}")

    fenced_total = sum(1 for r in results if r["output"].startswith("```"))
    lines.append(f"--> 修复后外层围栏残留: {fenced_total}/4（修复前实测为 7/8 轮次出现）")

    with open(os.path.join(HERE, "result_after_fixA.json"), "w", encoding="utf-8") as f:
        json.dump({"model": plugin.vision_model, "fix": "A-applied", "results": results}, f,
                  ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
