"""Document Engine — 文档工程引擎（V4.5）

三层协作架构（尺子 + 眼睛 + 大脑）:
- 尺子: python-docx 程序化精确读取/校验格式数值（确定性，零幻觉）
- 眼睛: qwen2.5vl:7b 视觉验收渲染效果（P2 可选）
- 大脑: DeepSeek 云端规划修改指令（JSON Patch 契约）

模块:
- file_ops.py      安全沙盒文件操作（workspace 根目录锁定）
- docx_reader.py   Word 读取: 内容 Markdown + 格式审计表
- format_rules.py  格式规则模型（三入口: 模板/说明文档/对话描述）
- docx_audit.py    尺子: 规则 vs 实际值比对
- docx_generator.py 规则驱动的合规文档生成
- docx_modifier.py JSON Patch 应用器
- pptx_fixer.py    PPT 轻量修复（空白页/空文本框清理）
- pipeline.py      验收回路编排（audit→plan→apply→re-audit, ≤3轮）
"""
