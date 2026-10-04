"""pipeline — 验收回路编排（V4.5）

流程（每轮全部确定性，格式修正零云调用）:
    audit → violations → 机械生成 patches → apply → re-audit
    ├─ 合规率 100% 或无新进展 → 返回
    └─ 轮次 < MAX_ROUNDS → 下一轮

无进展检测: 两轮 violation 指纹相同则提前终止（避免无效循环）
降级输出: 达到轮次上限仍有违规 → 成品 + 未达标项清单
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.document_engine.format_rules import FormatRules
from core.document_engine.docx_audit import audit_docx, DocxReadError
from core.document_engine.docx_modifier import violations_to_patches, apply_patches

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3


def _violation_fingerprint(violations: List[Dict[str, Any]]) -> str:
    """违规指纹（检测修复是否有效推进）"""
    return "|".join(sorted(
        f"{v['target']}#{v.get('index')}:{v['field']}" for v in violations))


def repair_docx(docx_path: Path, rules: FormatRules,
                max_rounds: int = MAX_ROUNDS) -> Dict[str, Any]:
    """修改回路: 按规则修复文档至合规（或 3 轮后降级输出）

    Returns:
        {status, rounds, final_audit, remaining_violations, history}
    """
    history: List[Dict[str, Any]] = []
    prev_fingerprint = None

    for round_no in range(1, max_rounds + 1):
        try:
            audit = audit_docx(docx_path, rules)
        except DocxReadError as e:
            return {"status": "error", "detail": str(e),
                    "rounds": round_no - 1, "history": history}

        violations = audit["violations"]
        history.append({
            "round": round_no,
            "compliance_rate": audit["compliance_rate"],
            "violation_count": len(violations),
            "phase": "audit",
        })

        if audit["compliance_rate"] == 1.0 or not violations:
            return {"status": "compliant", "rounds": round_no,
                    "final_audit": audit, "remaining_violations": [],
                    "history": history}

        # 无进展检测
        fp = _violation_fingerprint(violations)
        if fp == prev_fingerprint:
            history.append({"round": round_no, "phase": "abort",
                            "reason": "违规无变化，终止回路"})
            break
        prev_fingerprint = fp

        # 机械生成 + 应用 patch
        patches = violations_to_patches(violations)
        if not patches:
            history.append({"round": round_no, "phase": "abort",
                            "reason": "无可自动修复项（需人工/LLR 处理）"})
            break

        apply_result = apply_patches(docx_path, patches)
        history.append({
            "round": round_no,
            "phase": "apply",
            "patches": len(patches),
            "applied": apply_result["applied"],
            "rejected": len(apply_result.get("rejected", [])),
        })

    # 降级输出
    final_audit = audit_docx(docx_path, rules)
    status = "compliant" if final_audit["compliance_rate"] == 1.0 else "degraded"
    return {
        "status": status,
        "rounds": max_rounds,
        "final_audit": final_audit,
        "remaining_violations": final_audit["violations"],
        "history": history,
    }
