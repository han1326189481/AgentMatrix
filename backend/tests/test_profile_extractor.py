# -*- coding: utf-8 -*-
"""画像抽取 / 脱敏 / 变量回填 / 难度选择的单元测试

⚠️ 本文件不含任何文件 I/O：抽取器与绑定表都是纯函数/纯数据类，
画像落盘由 PersonalBrain 负责（同「图谱类不碰文件 I/O」设计约定），
因此这些用例天然不会污染生产 storage/profiles/。
"""
import pytest

from core.engines.profile_extractor import (
    ProfileExtractor, mask_for_cloud, SENSITIVE_FIELDS,
)
from core.engines.profile_autofill import (
    autofill_variables, resolve_value, binding_coverage, BINDINGS,
)


@pytest.fixture
def ex():
    return ProfileExtractor()


# ---------------------------------------------------------------- 抽取器


class TestExtractionPositive:
    """主动交代型 —— 系统场景下的真实主路径。"""

    @pytest.mark.parametrize("text,expected", [
        ("我叫韩佳文，学号20230021016，我是计科2301的",
         {"display_name": "韩佳文", "class_name": "计科2301"}),
        ("我是韩佳文，计算机科学与技术专业，大三",
         {"display_name": "韩佳文", "major": "计算机科学与技术"}),
        ("韩佳文，男，计科2301",
         {"display_name": "韩佳文", "class_name": "计科2301"}),
        ("我们班是计科2301，我是韩佳文",
         {"display_name": "韩佳文", "class_name": "计科2301"}),
        ("我专业是软件工程", {"major": "软件工程"}),
        ("我在武汉大学读的大二",
         {"school": "武汉大学", "grade_year": "2年级"}),
        ("我是哈尔滨工业大学计算机专业的大三学生，计科2301",
         {"school": "哈尔滨工业大学", "major": "计算机", "class_name": "计科2301"}),
    ])
    def test_extracts_expected_fields(self, ex, text, expected):
        got = ex.extract(text).fields
        for key, val in expected.items():
            assert got.get(key) == val, f"{key}: 期望 {val!r}，实得 {got.get(key)!r}"

    def test_all_fields_from_one_sentence(self, ex):
        """一句话同时给全六项。

        注：degree_stage 保留原词「本科生」而不归一，
        因为脱敏层（_classify_degree）才负责粗化，入库存原文才填得出「本科生」。
        """
        text = "我叫韩佳文，哈尔滨工业大学，计算机专业，计科2301，2023级，本科生"
        f = ex.extract(text).fields
        assert f.get("display_name") == "韩佳文"
        assert f.get("school") == "哈尔滨工业大学"
        assert f.get("major") == "计算机"
        assert f.get("class_name") == "计科2301"
        assert f.get("grade_year") == "2023级"
        assert f.get("degree_stage") == "本科生"


class TestExtractionNegative:
    """噪音 / 疑问 / 举例 —— 误抽取比漏抽取危险，这些必须抽不到。"""

    @pytest.mark.parametrize("text", [
        "帮我写开题报告",
        "今天天气不错",
        "人工智能是什么",
        "[动画表情]",
        "",
    ])
    def test_noise_yields_nothing(self, ex, text):
        assert ex.extract(text).is_empty()

    @pytest.mark.parametrize("text", [
        "你是大几的学生？",
        "我的学号是多少？",
        "你叫什么名字？",
    ])
    def test_questions_yield_nothing(self, ex, text):
        """疑问句不能当成用户自述。"""
        assert ex.extract(text).is_empty()

    @pytest.mark.parametrize("text", [
        "我叫你不要写这个东西",
        "比如说我叫张三，专业是计算机",
    ])
    def test_negation_and_example_yield_nothing(self, ex, text):
        """否定 / 举例语境必须放弃（宁缺勿错）。"""
        assert ex.extract(text).is_empty()

    def test_non_string_input(self, ex):
        assert ex.extract(None).is_empty()
        assert ex.extract(123).is_empty()


class TestSensitiveFields:
    """强标识绝不能进画像。"""

    def test_sensitive_detected_but_not_stored(self, ex):
        r = ex.extract("我叫张三，学号20230021016，手机13800138000，邮箱 a@b.com")
        assert set(r.sensitive_found) >= {"student_id", "phone", "email"}
        blob = str(r.fields)
        for leak in ("20230021016", "13800138000", "a@b.com"):
            assert leak not in blob, f"敏感值 {leak} 泄漏进了 fields"

    def test_id_card_detected(self, ex):
        r = ex.extract("身份证110101200301011234 我是韩佳文")
        assert "id_card" in r.sensitive_found
        assert "110101" not in str(r.fields)

    def test_sensitive_field_names_are_declared(self):
        """SENSITIVE_FIELDS 是显式黑名单，不是靠正则碰运气。"""
        assert {"student_id", "phone", "email", "id_card"} <= SENSITIVE_FIELDS


class TestConfirmGate:
    """抽取结果必须待确认（ExtractionResult 层面）。"""

    def test_pending_confirm_always_true(self, ex):
        r = ex.extract("我叫韩佳文")
        assert r.pending_confirm is True
        assert r.to_dict()["pending_confirm"] is True

    def test_evidence_present_for_review(self, ex):
        """必须带原文片段，用户才能核对抽得对不对。"""
        r = ex.extract("我叫韩佳文，计科2301")
        for field in r.fields:
            assert r.evidence.get(field), f"{field} 缺少 evidence"


# ---------------------------------------------------------------- 云端脱敏


class TestMaskForCloud:
    def test_class_name_becomes_coarse_grade(self):
        out = mask_for_cloud({"class_name": "计科2301"})
        assert "2301" not in str(out)
        assert out.get("grade_hint") in ("大一", "大二", "大三", "大四")

    def test_major_becomes_discipline_family(self):
        out = mask_for_cloud({"major": "计算机科学与技术"})
        assert out.get("education_field") == "理工科"
        assert "计算机" not in str(out)

    def test_degree_stage_kept(self):
        assert mask_for_cloud({"degree_stage": "硕士研究生"}).get("degree_stage") == "研究生"

    @pytest.mark.parametrize("raw,expected", [
        ("本科生", "本科"), ("本科", "本科"), ("专科生", "专科"),
        ("硕士研究生", "研究生"), ("硕士", "研究生"), ("研究生", "研究生"),
        ("博士生", "博士"),
    ])
    def test_degree_normalization(self, raw, expected):
        """入库存原文，脱敏时归一为粗粒度。"""
        assert mask_for_cloud({"degree_stage": raw})["degree_stage"] == expected

    def test_unrecognizable_degree_dropped(self):
        assert mask_for_cloud({"degree_stage": "大三"}) == {}

    def test_unknown_major_is_dropped_not_guessed(self):
        """映射表外一律丢弃，不猜测。"""
        assert mask_for_cloud({"major": "量子力学"}) == {}

    def test_display_name_never_masked_out(self):
        """姓名无法粗化，正确做法是不参与外发。"""
        out = mask_for_cloud({"display_name": "韩佳文", "major": "汉语言文学"})
        assert "韩佳文" not in str(out)
        assert out.get("education_field") == "文学"

    def test_empty_input(self):
        assert mask_for_cloud({}) == {}


# ---------------------------------------------------------------- 变量回填


class TestAutofill:
    PROFILE = {
        "display_name": "韩佳文",
        "identity": "student",
        "school": "哈尔滨工业大学",
        "major": "计算机科学与技术",
        "class_name": "计科2301",
        "grade_year": "2023级",
        "degree_stage": "本科",
    }

    def test_fills_bound_variable(self):
        out = autofill_variables([{"name": "name", "required": True}], self.PROFILE)
        assert out[0]["default_value"] == "韩佳文"
        assert out[0]["autofilled"] is True

    def test_does_not_overwrite_existing_default(self):
        """模板自带默认值时不得覆盖（作者的值通常更贴合场景）。"""
        out = autofill_variables(
            [{"name": "name", "default_value": "您的名字"}], self.PROFILE)
        assert out[0]["default_value"] == "您的名字"
        assert "autofilled" not in out[0]

    def test_unbound_variable_untouched(self):
        out = autofill_variables([{"name": "topic", "required": True}], self.PROFILE)
        assert "default_value" not in out[0]

    def test_semantically_wrong_binding_not_applied(self):
        """learning_stage 不绑 author_identity（描述是「作家/学者/企业家」）。"""
        assert "learning_stage" not in BINDINGS
        prof = dict(self.PROFILE, learning_stage="advanced")
        out = autofill_variables([{"name": "author_identity"}], prof)
        assert "default_value" not in out[0]

    def test_composite_variable_joins(self):
        out = autofill_variables([{"name": "class_info"}], self.PROFILE)
        assert "计科2301" in out[0]["default_value"]
        assert "2023级" in out[0]["default_value"]

    def test_does_not_mutate_input(self):
        """必须返回副本，绝不能改图谱里的原始对象。"""
        variables = [{"name": "name", "required": True}]
        autofill_variables(variables, self.PROFILE)
        assert "default_value" not in variables[0]

    def test_empty_profile_leaves_all_untouched(self):
        variables = [{"name": "name"}, {"name": "class_info"}]
        out = autofill_variables(variables, {})
        assert all("default_value" not in v for v in out)

    def test_empty_variables(self):
        assert autofill_variables([], self.PROFILE) == []
        assert autofill_variables(None, self.PROFILE) == []

    def test_coverage_report(self):
        cov = binding_coverage([{"name": "name"}, {"name": "topic"}])
        assert cov == {"total": 2, "bindable": 1}

    def test_resolve_value_empty_inputs(self):
        assert resolve_value("", {"name": "x"}) == ""
        assert resolve_value("name", {}) == ""
        assert resolve_value("nonexistent_var", {"name": "x"}) == ""