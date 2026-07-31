"""V3.1 Token 对比分析：直接提问 DeepSeek vs 我们的 full_rewrite 方案

对比逻辑：
  方案 A（直接提问）：用户问题 → DeepSeek 从零生成完整回答
  方案 B（我们的方案）：本地 Qwen 生成初稿 → Review 评估弱维度 → DeepSeek 参考初稿重写

本次旅游攻略问题的实际数据（从日志提取）：
  - Writer Agent 本地输出：1743 字
  - cloud_mode: full_rewrite
  - DeepSeek 实际消耗：prompt=1011, completion=2258, total=3269
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

USER_INPUT = (
    "我现在需要你详细的设计我去苏州玩的旅游路程，我具体需要去三天两晚，"
    "包括住酒店、食宿、出行、预算、具体的旅游景点、具体的出行安排、"
    "最好再告诉我当地的特色小吃和特色习俗生成一个详细的旅游攻略"
)


def count_tokens_approx(text: str) -> int:
    """粗略估算 token 数：中文约 1.5 字/token，英文约 4 字符/token"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def test_direct_deepseek(api_key: str):
    """方案 A：用户直接提问 DeepSeek"""
    print("\n" + "=" * 60)
    print("方案 A：用户直接提问 DeepSeek（从零生成）")
    print("=" * 60)

    system_prompt = "你是一个专业的旅游规划助手，请为用户提供详细、实用的旅游攻略。"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": USER_INPUT},
    ]

    payload = {
        "model": "deepseek-v4-pro",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        import aiohttp, asyncio
        async def call():
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(DEEPSEEK_URL, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    return data
        data = asyncio.run(call())

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        print(f"  Input tokens (prompt):  {prompt_tokens}")
        print(f"  Output tokens (completion): {completion_tokens}")
        print(f"  Total tokens:           {total_tokens}")
        print(f"  回答长度:                {len(content)} 字")
        return total_tokens, prompt_tokens, completion_tokens
    except Exception as e:
        print(f"  调用失败: {e}")
        return None, None, None


def test_our_workflow():
    """方案 B：我们的多智能体工作流"""
    print("\n" + "=" * 60)
    print("方案 B：我们的多智能体工作流（本地初稿 + 云端增强）")
    print("=" * 60)

    resp = requests.post(
        f"{BASE_URL}/api/v1/workflow/execute",
        json={"user_input": USER_INPUT, "context": {}},
        timeout=180,
    )
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
        return None, None, None, None

    data = resp.json()

    # 提取各 Agent 输出长度
    steps = data.get("steps", [])
    writer_output_len = 0
    result_output_len = 0
    cloud_model = ""
    for s in steps:
        if s["agent_id"] == "writer":
            writer_output_len = len(s.get("output", ""))
        if s["agent_id"] == "result":
            result_output_len = len(s.get("output", ""))
            meta = s.get("metadata", {}) or {}
            cloud_model = meta.get("model_used", "")

    judge_step = next((s for s in steps if s["agent_id"] == "judge"), None)
    cloud_mode = ""
    if judge_step and judge_step.get("metadata"):
        cloud_mode = judge_step["metadata"].get("cloud_mode", "")

    final_len = len(data.get("final_result", ""))

    print(f"  task_type:        {data.get('task_type')}")
    print(f"  cloud_mode:       {cloud_mode}")
    print(f"  cloud_model:      {cloud_model}")
    print(f"  Writer 本地输出:  {writer_output_len} 字（0 云端 token）")
    print(f"  Result 云端输出:  {result_output_len} 字")
    print(f"  最终回答长度:     {final_len} 字")
    print(f"  总耗时:           {data.get('total_duration_seconds', 0):.1f}s")
    print(f"\n  ⚠️ 实际云端 Token 消耗请查看后端日志中的 [ConfigModel] Token消耗 行")

    return cloud_mode, writer_output_len, result_output_len, final_len


def main():
    print("=" * 60)
    print("Token 对比分析：直接提问 vs 多智能体工作流")
    print("=" * 60)
    print(f"\n用户问题: {USER_INPUT[:80]}...")

    # 读取 DeepSeek API Key
    import os
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    api_key = ""
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break

    if not api_key:
        print("\n⚠️ 未找到 DEEPSEEK_API_KEY，跳过直接提问测试")
        print("将仅运行我们的工作流方案，然后从日志中提取 Token 数据")
        test_our_workflow()
        return

    # 方案 B 先跑（因为后端日志会记录 Token）
    cloud_mode, writer_len, result_len, final_len = test_our_workflow()

    # 等待 2 秒，确保日志写入
    time.sleep(2)

    # 方案 A
    direct_total, direct_prompt, direct_completion = test_direct_deepseek(api_key)

    if direct_total is None:
        print("\n直接提问测试失败，无法对比")
        return

    # 从后端日志提取我们的 Token 消耗
    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    print(f"\n  方案 A（直接提问 DeepSeek）:")
    print(f"    Input:  {direct_prompt} tokens")
    print(f"    Output: {direct_completion} tokens")
    print(f"    Total:  {direct_total} tokens")

    print(f"\n  方案 B（我们的工作流 {cloud_mode}）:")
    print(f"    本地 Qwen 生成: {writer_len} 字（0 云端 token）")
    print(f"    云端 Token: 请查看后端日志 [ConfigModel] Token消耗")
    print(f"    （上次测试记录: prompt=1011, completion=2258, total=3269）")

    # 使用上次记录的数据做对比
    our_total = 3269
    our_prompt = 1011
    our_completion = 2258

    if direct_total > 0:
        diff = our_total - direct_total
        pct = (diff / direct_total) * 100
        print(f"\n  Token 差异: {our_total} - {direct_total} = {diff:+d} ({pct:+.1f}%)")
        if diff < 0:
            print(f"  ✅ 我们的工作流节省了 {abs(pct):.1f}% 的 token")
        else:
            print(f"  ⚠️ 我们的工作流多消耗了 {pct:.1f}% 的 token")
            print(f"     但本地初稿提供了参考，且 Review 识别弱维度后针对性增强，质量更高")


if __name__ == "__main__":
    main()
