"""Phase 1 稳定性集成测试 — Review Guard + Template WhiteList

测试目标：
1. Review Guard: 验证 Review Agent 在任何情况下都返回合法 JSON，不会 success=False
2. Template WhiteList: 验证模板仅在白名单匹配时触发，非白名单问题使用自然语言回答
3. 回归测试: 确保 30 题测试中之前的问题得到修复
"""
import requests
import json
import time
import sys
import os
import re
from datetime import datetime

API_URL = "http://localhost:8000/api/v1/workflow/execute"
HEALTH_URL = "http://localhost:8000/health"
TIMEOUT = 180

# ============================================================
# 测试用例
# ============================================================

# 测试1: Review Guard — 验证 Review Agent 不会因为 JSON 解析失败而返回 success=False
REVIEW_GUARD_TESTS = [
    {
        "id": "RG01",
        "name": "Python文件读取",
        "query": "Python中如何读取文件？请给出示例代码",
        "check": "review_success",
        "desc": "之前 Review Agent 可能因 JSON 解析失败"
    },
    {
        "id": "RG02",
        "name": "多Agent系统编排",
        "query": "设计一个多Agent系统的任务编排方案，需要考虑任务分配、通信协议和容错机制",
        "check": "review_success",
        "desc": "之前 C06 的 Review Agent 失败"
    },
    {
        "id": "RG03",
        "name": "RESTful API设计",
        "query": "设计RESTful API有哪些最佳实践？请详细说明",
        "check": "review_success",
        "desc": "之前 C04 的 Review Agent 失败"
    },
    {
        "id": "RG04",
        "name": "量子密码学",
        "query": "分析量子计算对现代密码学的影响，特别是RSA和ECC算法",
        "check": "review_success",
        "desc": "复杂问题，Review需要稳定输出"
    },
    {
        "id": "RG05",
        "name": "简单问候",
        "query": "你好，今天天气怎么样？",
        "check": "review_success",
        "desc": "简单对话，Review应该正确识别"
    },
]

# 测试2: Template WhiteList — 验证模板仅在白名单匹配时触发
TEMPLATE_WHITELIST_TESTS = [
    {
        "id": "TW01",
        "name": "白名单-方案",
        "query": "设计一个团队建设活动方案",
        "check": "template_expected",
        "desc": "包含'方案'关键词，应该触发模板"
    },
    {
        "id": "TW02",
        "name": "白名单-报告",
        "query": "写一份市场调研分析报告",
        "check": "template_expected",
        "desc": "包含'报告'关键词，应该触发模板"
    },
    {
        "id": "TW03",
        "name": "白名单-计划",
        "query": "制定年度工作计划",
        "check": "template_expected",
        "desc": "包含'计划'关键词，应该触发模板"
    },
    {
        "id": "TW04",
        "name": "非白名单-Python编码",
        "query": "Python中如何读取文件？请给出示例代码",
        "check": "template_forbidden",
        "desc": "编程问题，不应该触发模板"
    },
    {
        "id": "TW05",
        "name": "非白名单-Git介绍",
        "query": "什么是Git？请简要说明",
        "check": "template_forbidden",
        "desc": "问答问题，不应该触发模板"
    },
    {
        "id": "TW06",
        "name": "非白名单-家常菜",
        "query": "推荐一道简单的家常菜及其做法",
        "check": "template_forbidden",
        "desc": "生活问题，不应该触发模板"
    },
    {
        "id": "TW07",
        "name": "非白名单-商务谈判",
        "query": "商务谈判中有什么技巧？",
        "check": "template_forbidden",
        "desc": "技巧问答，不应该触发模板"
    },
    {
        "id": "TW08",
        "name": "非白名单-宠物",
        "query": "养宠物需要注意哪些事项？",
        "check": "template_forbidden",
        "desc": "生活问题，不应该触发模板"
    },
]

# 测试3: 回归测试 — 之前30题中表现最差的题目
REGRESSION_TESTS = [
    {
        "id": "RG01",
        "name": "O05-工作效率",
        "query": "如何提高工作效率？",
        "check": "min_length_80",
        "desc": "之前仅30字，现在应该 >= 80字"
    },
    {
        "id": "RG02",
        "name": "L01-天气",
        "query": "今天天气怎么样？",
        "check": "min_length_40",
        "desc": "之前仅23字"
    },
    {
        "id": "RG03",
        "name": "L07-情书",
        "query": "写一封简短的情书",
        "check": "min_length_60",
        "desc": "之前仅38字，情书应该更长"
    },
    {
        "id": "RG04",
        "name": "L02-家常菜",
        "query": "推荐一道简单的家常菜及其做法",
        "check": "no_template_headers",
        "desc": "之前被模板化，应该给出具体菜谱"
    },
    {
        "id": "RG05",
        "name": "L10-宠物",
        "query": "养宠物需要注意哪些事项？",
        "check": "no_template_headers",
        "desc": "之前被模板化，应该是自然回答"
    },
]


def check_health():
    """检查后端是否运行"""
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        return r.status_code == 200
    except:
        return False


def execute_query(query: str) -> dict:
    """执行单次查询并返回完整结果"""
    payload = {"user_input": query}
    try:
        r = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        return {
            "status_code": r.status_code,
            "body": r.json() if r.status_code == 200 else {"error": r.text},
            "success": r.status_code == 200
        }
    except Exception as e:
        return {"status_code": 0, "body": {"error": str(e)}, "success": False}


def has_template_headers(content: str) -> bool:
    """检测回答是否使用模板结构

    检测策略：
    1. 旧模板：3个以上 "任务概述/核心需求/解决方案/实施计划" 标题
    2. 新模板：有 `# ` 主标题 + 3个以上 `## ` 二级标题（如方案/报告类文档）
    3. 结构化文档：有 `# ` 主标题 + `## ` 章节 + 内容长度 > 800 字
    """
    # 旧模板模式
    old_patterns = [
        r'##\s*任务概述', r'##\s*核心需求',
        r'##\s*解决方案', r'##\s*实施计划', r'##\s*写作模板',
    ]
    old_count = sum(1 for p in old_patterns if re.search(p, content, re.IGNORECASE))
    if old_count >= 3:
        return True

    # 新模板检测：有主标题 + 二级标题 + 编号格式
    has_main_title = bool(re.search(r'^#\s+.+$', content, re.MULTILINE))
    h2_matches = re.findall(r'^##\s+.+$', content, re.MULTILINE)
    numbered_sections = re.findall(r'##\s*[一二三四五六七八九十]、', content)

    # 3+ 二级标题 + 编号格式
    if len(h2_matches) >= 3 and len(numbered_sections) >= 2:
        return True

    # 主标题 + 3+ 二级标题 + 内容充足（> 800字）
    if has_main_title and len(h2_matches) >= 3 and len(content) > 800:
        return True

    return False


def run_test_suite(name: str, tests: list, results: list):
    """运行一组测试"""
    print(f"\n{'='*60}")
    print(f"  {name} ({len(tests)}题)")
    print(f"{'='*60}")

    passed = 0
    failed = 0

    for i, test in enumerate(tests):
        tid = test["id"]
        tname = test["name"]
        query = test["query"]
        check = test["check"]
        desc = test["desc"]

        print(f"\n[{tid}] {tname}")
        print(f"  Q: {query[:60]}...")
        start = time.time()
        result = execute_query(query)
        elapsed = time.time() - start

        if not result["success"]:
            print(f"  FAIL | HTTP {result['status_code']}: {result['body'].get('error', '')[:100]}")
            failed += 1
            results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                           "detail": f"HTTP {result['status_code']}", "elapsed": f"{elapsed:.1f}s"})
            continue

        body = result["body"]
        steps = body.get("steps", [])
        final_result = body.get("final_result", "")

        # 找到 Review 步骤
        review_step = next((s for s in steps if s.get("agent_id") == "review"), None)
        review_success = review_step.get("success", False) if review_step else False

        # 检查项
        if check == "review_success":
            if review_success:
                print(f"  PASS | Review OK, score={body.get('complexity_score', 'N/A')}, "
                      f"len={len(final_result)}, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": f"Review success", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | Review failed! steps={[(s['agent_id'], s['success']) for s in steps]}")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": "Review Agent returned success=False", "elapsed": f"{elapsed:.1f}s"})

        elif check == "template_expected":
            is_template = has_template_headers(final_result)
            if is_template:
                print(f"  PASS | Template triggered as expected, len={len(final_result)}, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": "Template triggered", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | Template NOT triggered when expected! len={len(final_result)}")
                print(f"    Preview: {final_result[:150]}...")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": "Template not triggered", "elapsed": f"{elapsed:.1f}s"})

        elif check == "template_forbidden":
            is_template = has_template_headers(final_result)
            if not is_template:
                print(f"  PASS | No template, len={len(final_result)}, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": "No template", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | Template detected when forbidden! len={len(final_result)}")
                print(f"    Preview: {final_result[:200]}...")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": "Template detected when forbidden", "elapsed": f"{elapsed:.1f}s"})

        elif check == "min_length_80":
            if len(final_result) >= 80:
                print(f"  PASS | len={len(final_result)} >= 80, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": f"len={len(final_result)}", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | len={len(final_result)} < 80, too short!")
                print(f"    Content: {final_result[:200]}")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": f"len={len(final_result)} < 80", "elapsed": f"{elapsed:.1f}s"})

        elif check == "min_length_40":
            if len(final_result) >= 40:
                print(f"  PASS | len={len(final_result)} >= 40, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": f"len={len(final_result)}", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | len={len(final_result)} < 40, too short!")
                print(f"    Content: {final_result[:200]}")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": f"len={len(final_result)} < 40", "elapsed": f"{elapsed:.1f}s"})

        elif check == "min_length_60":
            if len(final_result) >= 60:
                print(f"  PASS | len={len(final_result)} >= 60, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": f"len={len(final_result)}", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | len={len(final_result)} < 60, too short!")
                print(f"    Content: {final_result[:200]}")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": f"len={len(final_result)} < 60", "elapsed": f"{elapsed:.1f}s"})

        elif check == "no_template_headers":
            is_template = has_template_headers(final_result)
            if not is_template:
                print(f"  PASS | No template headers, len={len(final_result)}, {elapsed:.1f}s")
                passed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "PASS",
                               "detail": "No template headers", "elapsed": f"{elapsed:.1f}s"})
            else:
                print(f"  FAIL | Template headers found! len={len(final_result)}")
                print(f"    Preview: {final_result[:200]}...")
                failed += 1
                results.append({"id": tid, "name": tname, "check": check, "result": "FAIL",
                               "detail": "Template headers found", "elapsed": f"{elapsed:.1f}s"})

    return passed, failed


def main():
    print("=" * 60)
    print("Phase 1 稳定性集成测试 — Review Guard + Template WhiteList")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not check_health():
        print("ERROR: 后端未运行，请先启动后端服务")
        sys.exit(1)

    print("Health: OK")

    all_results = []
    total_passed = 0
    total_failed = 0

    # 测试1: Review Guard
    p, f = run_test_suite("Review Guard — 验证 Review Agent 100%成功率", REVIEW_GUARD_TESTS, all_results)
    total_passed += p
    total_failed += f

    # 测试2: Template WhiteList
    p, f = run_test_suite("Template WhiteList — 验证模板仅白名单触发", TEMPLATE_WHITELIST_TESTS, all_results)
    total_passed += p
    total_failed += f

    # 测试3: 回归测试
    p, f = run_test_suite("回归测试 — 之前30题中表现最差的题目", REGRESSION_TESTS, all_results)
    total_passed += p
    total_failed += f

    total = total_passed + total_failed

    # 汇总
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {total_passed}/{total} passed, {total_failed} failed")
    print(f"  Pass Rate: {total_passed/total*100:.1f}%")
    print(f"{'='*60}")

    # 保存结果
    result_file = os.path.join(os.path.dirname(__file__),
                               f"test_results_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {"total": total, "passed": total_passed, "failed": total_failed,
                       "pass_rate": f"{total_passed/total*100:.1f}%"},
            "results": all_results
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {result_file}")

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)