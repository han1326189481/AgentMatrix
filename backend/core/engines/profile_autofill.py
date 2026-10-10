"""画像 → 模板变量 绑定表（**纯本地**，不进 prompt、不外发）

为什么需要这个模块（实测依据，2026-10-10）：
把 SkillGraph 里 372 个 prompt_template 节点的 763 个去重变量名全量导出后统计，
`student_id` / `student_number` / `major` / `college` / `grade` 出现次数**均为 0**。
真正能承接画像的变量只有下面 BINDINGS 里列的这几类，且大多是
「年级和班级」「我的姓名」这种**复合描述**，不是结构化学号字段。

因此本模块的定位是：
- ✅ 能对上的：直接回填（name / class_info / school_info / my_role …）
- ⚠️ 对不上的：**不做模糊匹配**。宁可少填，绝不把「韩佳文」塞进
  `birthday_person`（寿星）这种语义不同的变量里 —— 那会造成比不填更糟的结果。

回填原则：
1. 变量已有 default_value → **不覆盖**（模板作者已给出更合适的默认值）
2. 画像字段为空 → 不动
3. 一个变量只绑一个画像字段，不做多对一映射
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

#: 变量名 → 画像字段名。
#: 全部来自 skill_graph.yaml 实测存在的变量名，不含臆造项。
BINDINGS: Dict[str, str] = {
    # ---- 姓名类 ----
    "name": "display_name",
    "student_name": "display_name",
    "name_title": "display_name",
    "name_and_job": "display_name",
    "my_info": "display_name",
    "host": "display_name",

    # ---- 学校类 ----
    "school": "school",
    "school_info": "school",
    "affiliation": "school",
    "org_name": "school",

    # ---- 年级 / 班级（复合变量，用 class + grade 拼）----
    "class_info": "class_name",     # 描述多为「年级和班级」
    "current_grade": "grade_year",

    # ---- 专业 ----
    "major": "major",
    "field": "major",
    "research_field": "major",

    # ---- 身份 / 角色（画像的 identity 是英文枚举，可直接用）----
    "my_role": "identity",
    "speaker_role": "identity",
    "your_role": "identity",
    "role": "identity",

    # ---- 学习阶段（用于选模板难度，不直接填进「作者身份」这类语义位）----
    # 注：learning_stage 故意不绑到 author_identity ——
    #     author_identity 的描述是「作家/学者/企业家/素人」，语义不同，
    #     填「advanced」进去是错的。
}

#: 复合变量：需要拼接多个画像字段
COMPOSITE: Dict[str, tuple] = {
    # 「年级和班级」→ 「2023级 计科2301」
    "class_info": ("grade_year", "class_name"),
    # 「我的身份和背景」→ 「计算机科学与技术 大三」
    "my_background": ("major", "grade_year"),
    # 「我的姓名和岗位」→ 只有姓名时先给姓名
    "my_info": ("display_name", "identity"),
    "name_and_job": ("display_name", "identity"),
    "name_title": ("display_name", "identity"),
}


def _join(values: List[str]) -> str:
    """拼接多段值，跳过空段；全空返回空串。"""
    parts = [v for v in values if v]
    return " ".join(parts) if parts else ""


def resolve_value(var_name: str, profile: Dict[str, str]) -> str:
    """按绑定表把画像字段解析成该变量的填充值；无绑定返回空串。"""
    if not var_name or not profile:
        return ""

    if var_name in COMPOSITE:
        keys = COMPOSITE[var_name]
        return _join([str(profile.get(k, "") or "").strip() for k in keys])

    field = BINDINGS.get(var_name)
    if not field:
        return ""
    return str(profile.get(field, "") or "").strip()


def autofill_variables(variables: List[dict], profile: Dict[str, str]) -> List[dict]:
    """用画像回填模板变量列表，返回**新列表**（不修改入参）。

    Args:
        variables: 模板节点 metadata.variables，形如
                   [{"name": "class_info", "description": "年级和班级", "required": true}]
        profile:  画像字段映射，见 PersonalBrain.autofill_variables

    Returns:
        回填后的变量副本。已填的变量带 `autofilled: True` 标记，
        便于前端区分「系统填的」与「用户要自己填的」。
    """
    if not variables:
        return []

    filled: List[dict] = []
    for var in variables:
        if not isinstance(var, dict):
            filled.append(var)
            continue

        # 只改副本，绝不动图谱里的原始对象
        new_var = dict(var)

        # 模板自带默认值的不覆盖 —— 作者的默认值通常比画像更贴合场景
        if new_var.get("default_value"):
            filled.append(new_var)
            continue

        value = resolve_value(new_var.get("name", ""), profile)
        if value:
            new_var["default_value"] = value
            new_var["autofilled"] = True
            filled.append(new_var)
            continue

        filled.append(new_var)

    return filled


def binding_coverage(variables: List[dict]) -> dict:
    """统计一组变量里有多少能被画像回填（用于自检与前端提示）。"""
    total = sum(1 for v in variables if isinstance(v, dict))
    bindable = sum(
        1 for v in variables
        if isinstance(v, dict) and (v.get("name") in BINDINGS
                                    or v.get("name") in COMPOSITE)
    )
    return {"total": total, "bindable": bindable}