import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

print("=" * 60)
print("查看当前的 DeepSeek 配置")
print("=" * 60)

print(f"\nDEEPSEEK_API_KEY: {settings.deepseek_api_key[:15]}..." if settings.deepseek_api_key else "DEEPSEEK_API_KEY: None")
print(f"DEEPSEEK_API_BASE: {settings.deepseek_api_base}")
print(f"DEEPSEEK_MODEL: {settings.deepseek_model}")
print(f"COMPLEXITY_THRESHOLD: {settings.complexity_threshold}")

print("\n✅ 配置加载完成！")

if settings.deepseek_model == "deepseek-v4-flash":
    print("\n🎉 模型名称正确！当前使用的是: deepseek-v4-flash")
    print("这就是您平台上显示消费的模型！")
else:
    print(f"\n❌ 当前模型: {settings.deepseek_model}, 期望: deepseek-v4-flash")
