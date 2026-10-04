"""知识图谱健康检查 —— 输出单行 JSON，供备份脚本做「缩水拦截」判断。

用法:
    python scripts/graph_health.py

输出:
    {"ok": true, "skill_nodes": 636, "skill_edges": 435, "reasoning_patterns": 0, "errors": []}

退出码:
    0 = 能够读取（即使 ok=false，只要 JSON 能输出）
    1 = 脚本自身崩溃（JSON 无法输出）
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "backend")
GRAPHS = os.path.join(BACKEND, "core", "graphs")

if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def main() -> int:
    out = {
        "ok": True,
        "skill_nodes": 0,
        "skill_edges": 0,
        "reasoning_patterns": 0,
        "errors": [],
    }

    # --- skill_graph.yaml ---
    try:
        from core.graphs.skill_graph import SkillGraph

        g = SkillGraph.load(os.path.join(GRAPHS, "skill_graph.yaml"))
        out["skill_nodes"] = len(getattr(g, "nodes", {}) or {})
        out["skill_edges"] = len(getattr(g, "edges", []) or [])
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["errors"].append("skill_graph: %s" % e)

    # --- reasoning_graph.yaml（自学习模式，期望为空或少量）---
    try:
        from core.graphs.reasoning_graph import ReasoningGraph

        rg = ReasoningGraph()
        pats = (
            getattr(rg, "patterns", None)
            or getattr(rg, "_patterns", None)
            or getattr(rg, "learned_patterns", None)
            or {}
        )
        out["reasoning_patterns"] = len(pats)
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["errors"].append("reasoning_graph: %s" % e)

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "fatal": str(exc)}, ensure_ascii=False))
        sys.exit(1)
