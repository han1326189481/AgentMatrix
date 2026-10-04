"""_e2e_api_test — 通过 API 全链路验证 Document Engine 四场景（UTF-8 安全）"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE = "http://localhost:8000"

SCENARIOS = [
    ("repair_docx", "把 测试报告.docx 按格式规范.md 修复一下格式"),
    ("generate_docx", "按格式规范.md 生成一份项目方案文档"),
    ("fix_pptx", "清理 演示文稿.pptx 的空白页和空文本框"),
    ("read_only", "读一下测试报告.docx 帮我总结主要内容"),
]


def run_scenario(name: str, user_input: str, timeout: float = 600) -> dict:
    print(f"\n>>> 场景 {name}: {user_input}")
    t0 = time.time()
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{BASE}/api/v1/workflow/execute", json={
            "user_input": user_input, "context": {},
        })
        resp.raise_for_status()
        result = resp.json()
    dt = time.time() - t0

    doc_task = {}
    doc_meta = {}
    for s in result.get("steps", []):
        if s["agent_id"] == "knowledge":
            doc_task = (s.get("metadata") or {}).get("doc_task", {})
        if s["agent_id"] == "result":
            doc_meta = (s.get("metadata") or {}).get("doc_result", {})

    print(f"    耗时 {dt:.1f}s | steps: {[(s['agent_id'], s['success']) for s in result.get('steps', [])]}")
    print(f"    doc_task: {json.dumps(doc_task, ensure_ascii=False)}")
    print(f"    doc_result: {json.dumps(doc_meta, ensure_ascii=False)}")
    print(f"    final_result 尾部: ...{result['final_result'][-300:]}")
    # 报告是否出现在最终回复
    has_report = any(k in result["final_result"] for k in
                     ["文档修复完成", "Word 文档已生成", "PPT 清理完成"])
    print(f"    报告已附在回复尾部: {has_report}")
    return {"doc_task": doc_task, "doc_result": doc_meta, "has_report": has_report,
            "result": result}


def main():
    out = {}
    for name, text in SCENARIOS:
        try:
            out[name] = run_scenario(name, text)
        except Exception as e:
            print(f"    [ERROR] {e}")
            out[name] = {"error": str(e)}

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    ok = True
    for name in ["repair_docx", "generate_docx", "fix_pptx", "read_only"]:
        d = out.get(name, {})
        tt = d.get("doc_task", {}).get("task_type")
        need_report = name != "read_only"
        report_ok = (not need_report) or d.get("has_report")
        line_ok = tt == name and report_ok
        if not line_ok:
            ok = False
        print(f"{name}: 判定={tt} | 报告可见={d.get('has_report')} | 落盘={json.dumps(d.get('doc_result', {}), ensure_ascii=False)} | {'PASS' if line_ok else 'FAIL'}")
    print("=" * 60)
    print("结论:", "PASS" if ok else "FAIL")

    Path(__file__).parent.joinpath("_e2e_api_out.json").write_text(
        json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "result"} for k, v in out.items()},
                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
