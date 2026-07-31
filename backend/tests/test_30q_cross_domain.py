"""
Skill Engine V2 — 30题跨领域综合测试
代码领域(10) + 日常办公(10) + 日常生活(10)
"""
import sys
import os
import json
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8000"
WORKFLOW_URL = f"{API_BASE}/api/v1/workflow/execute"
TIMEOUT = 180  # 每题最多等待3分钟

# ============================================================
# 30道测试题目
# ============================================================
QUESTIONS = {
    "代码领域": [
        {"id": "C01", "type": "simple", "q": "Python中如何读取文件？请给出示例代码"},
        {"id": "C02", "type": "simple", "q": "什么是Git？请简要说明"},
        {"id": "C03", "type": "medium", "q": "写一个Python函数实现快速排序算法"},
        {"id": "C04", "type": "medium", "q": "设计RESTful API有哪些最佳实践？"},
        {"id": "C05", "type": "medium", "q": "什么是Docker容器化？有什么优势？"},
        {"id": "C06", "type": "complex", "q": "设计一个多Agent系统的任务编排方案"},
        {"id": "C07", "type": "complex", "q": "分析量子计算对现代密码学的影响"},
        {"id": "C08", "type": "complex", "q": "RAG系统中如何优化文档分块策略？"},
        {"id": "C09", "type": "simple", "q": "如何在Linux中查看正在运行的进程？"},
        {"id": "C10", "type": "medium", "q": "解释一下MCP（Model Context Protocol）是什么"},
    ],
    "日常办公": [
        {"id": "O01", "type": "simple", "q": "如何写一封正式的商务邮件？"},
        {"id": "O02", "type": "medium", "q": "写一份项目周报的模板"},
        {"id": "O03", "type": "medium", "q": "策划一个团队建设活动方案"},
        {"id": "O04", "type": "complex", "q": "写一份市场调研分析报告的大纲"},
        {"id": "O05", "type": "simple", "q": "如何提高工作效率？"},
        {"id": "O06", "type": "medium", "q": "如何做一次有效的PPT演讲？"},
        {"id": "O07", "type": "complex", "q": "对某创业公司进行SWOT分析并给出战略建议"},
        {"id": "O08", "type": "simple", "q": "会议纪要应该怎么写？"},
        {"id": "O09", "type": "medium", "q": "如何制定年度工作计划？"},
        {"id": "O10", "type": "simple", "q": "商务谈判中有什么技巧？"},
    ],
    "日常生活": [
        {"id": "L01", "type": "simple", "q": "今天天气怎么样？"},
        {"id": "L02", "type": "simple", "q": "推荐一道简单的家常菜及其做法"},
        {"id": "L03", "type": "medium", "q": "写一首关于春天的短诗"},
        {"id": "L04", "type": "simple", "q": "如何保持健康的生活方式？"},
        {"id": "L05", "type": "medium", "q": "写一篇简短的日记"},
        {"id": "L06", "type": "simple", "q": "推荐几本值得阅读的好书"},
        {"id": "L07", "type": "medium", "q": "写一封简短的情书"},
        {"id": "L08", "type": "simple", "q": "如何缓解工作压力？"},
        {"id": "L09", "type": "medium", "q": "写一个周末旅行计划"},
        {"id": "L10", "type": "simple", "q": "养宠物需要注意哪些事项？"},
    ],
}


def run_single_test(domain, item):
    """执行单题测试"""
    qid = item["id"]
    question = item["q"]
    qtype = item["type"]

    print(f"\n{'='*60}")
    print(f"[{domain}] {qid} ({qtype})")
    print(f"Q: {question[:80]}...")
    print(f"  Start: {datetime.now().strftime('%H:%M:%S')}")

    start = time.time()
    try:
        resp = requests.post(
            WORKFLOW_URL,
            json={"user_input": question},
            timeout=TIMEOUT,
        )
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            result = data.get("final_result", "")
            steps = data.get("steps", [])
            executed_locally = data.get("executed_locally", True)
            complexity = data.get("complexity_score", 0)
            duration = data.get("total_duration_seconds", 0)

            # 提取 agents 信息
            agents_info = []
            for s in steps:
                agents_info.append({
                    "agent": s.get("agent_name", "?"),
                    "success": s.get("success", False),
                    "duration": s.get("duration_seconds", 0),
                })

            # 提取 skill_path
            skill_path = None
            for s in steps:
                meta = s.get("metadata", {})
                if meta.get("skill_path"):
                    skill_path = meta["skill_path"]
                    break

            # 提取 review
            review_info = None
            for s in steps:
                if s.get("agent_id") == "review":
                    try:
                        meta = s.get("metadata", {})
                        review_info = {
                            "score": meta.get("review_score", 0),
                            "difficulty": meta.get("difficulty_threshold", 0),
                            "decision": meta.get("decision", "?"),
                        }
                    except Exception:
                        pass
                    break

            return {
                "id": qid,
                "domain": domain,
                "type": qtype,
                "question": question,
                "success": True,
                "elapsed": round(elapsed, 2),
                "duration": round(duration, 2),
                "executed_locally": executed_locally,
                "complexity_score": round(complexity, 2),
                "result_length": len(result),
                "result_preview": result[:300],
                "agents": agents_info,
                "skill_path": skill_path,
                "review": review_info,
                "error": None,
                "issues": [],
            }
        else:
            return {
                "id": qid,
                "domain": domain,
                "type": qtype,
                "question": question,
                "success": False,
                "elapsed": round(elapsed, 2),
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "issues": [f"HTTP {resp.status_code}"],
            }
    except requests.Timeout:
        elapsed = time.time() - start
        return {
            "id": qid, "domain": domain, "type": qtype, "question": question,
            "success": False, "elapsed": round(elapsed, 2),
            "error": "Timeout", "issues": ["Timeout"],
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": qid, "domain": domain, "type": qtype, "question": question,
            "success": False, "elapsed": round(elapsed, 2),
            "error": str(e)[:200], "issues": [str(e)[:100]],
        }


def analyze_results(all_results):
    """分析并打印结果"""
    print("\n\n" + "=" * 80)
    print("RESULTS ANALYSIS")
    print("=" * 80)

    total = len(all_results)
    success = [r for r in all_results if r["success"]]
    failed = [r for r in all_results if not r["success"]]

    print(f"\nTotal: {total} | Success: {len(success)} | Failed: {len(failed)}")

    if failed:
        print(f"\n--- FAILED ({len(failed)}) ---")
        for r in failed:
            print(f"  [{r['id']}] {r['domain']} | {r['question'][:50]}... | {r['error']}")

    # 按领域分组
    for domain in ["代码领域", "日常办公", "日常生活"]:
        domain_results = [r for r in success if r["domain"] == domain]
        if not domain_results:
            continue

        local = [r for r in domain_results if r["executed_locally"]]
        cloud = [r for r in domain_results if not r["executed_locally"]]
        avg_time = sum(r["elapsed"] for r in domain_results) / len(domain_results)
        avg_len = sum(r["result_length"] for r in domain_results) / len(domain_results)

        print(f"\n--- {domain} ({len(domain_results)}题) ---")
        print(f"  本地执行: {len(local)} | 云端增强: {len(cloud)}")
        print(f"  平均耗时: {avg_time:.1f}s | 平均长度: {int(avg_len)}字符")

        # 按复杂度分类
        for qtype in ["simple", "medium", "complex"]:
            typed = [r for r in domain_results if r["type"] == qtype]
            if typed:
                avg_c = sum(r["complexity_score"] for r in typed) / len(typed)
                print(f"  [{qtype}] {len(typed)}题, 平均复杂度: {avg_c:.2f}")

        # 逐题分析
        for r in domain_results:
            local_tag = "本地" if r["executed_locally"] else "云端"
            issues = ""
            if r.get("issues"):
                issues = f" ISSUES: {r['issues']}"
            print(f"  [{r['id']}] {r['type']:6s} | {local_tag} | {r['elapsed']:5.1f}s | "
                  f"len={r['result_length']:4d} | complexity={r['complexity_score']:.2f}{issues}")
            if r.get("skill_path"):
                print(f"         skill_path: {r['skill_path']}")

    # 质量评估
    print(f"\n--- QUALITY ASSESSMENT ---")
    quality_issues = []
    for r in success:
        result = r.get("result_preview", "")
        issues = r.get("issues", [])

        # 模板化检测
        template_headers = [kw for kw in ["任务概述", "核心需求", "解决方案", "实施计划"]
                          if kw in result]
        if len(template_headers) >= 3:
            issues.append(f"模板化({len(template_headers)}个标题)")

        # 过短检测
        if r["result_length"] < 60:
            issues.append("回答过短")

        # 过长检测
        if r["result_length"] > 2000:
            issues.append("回答过长")

        # 开场白检测
        if result.startswith("根据您的要求") or result.startswith("根据您的"):
            issues.append("含开场白")

        if issues:
            r["issues"] = issues
            quality_issues.append(r)

    if quality_issues:
        print(f"质量问题: {len(quality_issues)}题")
        for r in quality_issues:
            print(f"  [{r['id']}] {r['domain']} | {r['issues']}")
    else:
        print("无质量问题")

    return success, failed


def main():
    print("=" * 80)
    print("Skill Engine V2 — 30题跨领域综合测试")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API: {WORKFLOW_URL}")
    print("=" * 80)

    # 先检查后端健康
    try:
        h = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"Health: {h.json()}")
    except Exception as e:
        print(f"ERROR: Backend not reachable: {e}")
        return

    all_results = []

    for domain, items in QUESTIONS.items():
        print(f"\n{'#'*60}")
        print(f"# {domain}")
        print(f"{'#'*60}")
        for item in items:
            result = run_single_test(domain, item)
            all_results.append(result)

            # 打印简要结果
            if result["success"]:
                tag = "LOCAL" if result["executed_locally"] else "CLOUD"
                print(f"  OK [{tag}] {result['elapsed']:.1f}s | len={result['result_length']} "
                      f"| complexity={result['complexity_score']:.2f}")
                if result.get("skill_path"):
                    print(f"    skill_path: {result['skill_path']}")
                print(f"    Preview: {result['result_preview'][:150]}...")
            else:
                print(f"  FAIL [{result['elapsed']:.1f}s] | {result['error']}")

            # 题目间短暂等待
            time.sleep(1)

    # 分析
    success, failed = analyze_results(all_results)

    # 保存详细结果
    output_file = os.path.join(
        os.path.dirname(__file__),
        f"test_results_30q_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nDetailed results saved to: {output_file}")

    print(f"\n{'='*80}")
    print(f"Done: {len(success)}/{len(all_results)} passed, {len(failed)} failed")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()