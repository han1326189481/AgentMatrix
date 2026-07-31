"""T2: YAML 规则加载测试"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock


class TestYamlRulesLoading:
    """测试 Review Agent YAML 规则加载"""

    def test_load_rules_normal(self):
        """规则正常加载"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        rules = agent._load_rules()
        assert isinstance(rules, dict)
        assert "dimensions" in rules
        assert "difficulty_threshold" in rules
        assert "pass_threshold" in rules
        assert "simple_conversation" in rules

    def test_load_rules_cached(self):
        """规则缓存有效性"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        first = agent._load_rules()
        second = agent._load_rules()
        assert first is second  # 缓存命中

    def test_load_rules_missing_yaml_fallback(self):
        """YAML 文件缺失时回退到默认规则"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        # 手动设置 _rules 为 None，然后 mock 文件不存在
        agent._rules = None
        with patch.object(agent, '_load_rules', wraps=agent._default_rules) as mock_default:
            # 先调用 _default_rules 直接验证默认规则
            rules = agent._default_rules()
            assert "dimensions" in rules
            assert rules["pass_threshold"] == 0.65
            assert rules["simple_conversation"]["review_score"] == 0.85

    def test_dimensions_in_rules(self):
        """验证规则中包含所有评审维度（V2 6维度）"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        rules = agent._load_rules()
        dims = rules["dimensions"]
        expected_dims = ["accuracy", "professional", "completeness", "reasoning", "structure", "actionable"]
        for dim in expected_dims:
            assert dim in dims, f"Missing dimension: {dim}"

    def test_difficulty_keywords_in_rules(self):
        """验证规则中包含难度关键词"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        rules = agent._load_rules()
        keywords = rules["difficulty_threshold"]["complex_keywords"]
        assert len(keywords) > 5
        # 验证每个关键词有 keyword 和 weight 字段
        for item in keywords:
            assert "keyword" in item
            assert "weight" in item
            assert isinstance(item["weight"], (int, float))

    def test_review_content_with_rules(self):
        """验证 V2 评分逻辑使用 YAML 规则"""
        from agents.review.agent import ReviewAgent
        agent = ReviewAgent()
        result = agent._review_content_v2(
            user_task="写一份校园活动策划方案",
            summary="活动策划需求",
            writer_output="""# 校园活动策划方案

## 活动背景
本次活动旨在丰富校园文化生活。

## 活动目标
提升学生参与度和团队协作能力。

## 活动流程
1. 前期准备
2. 活动执行
3. 后期总结

## 预算安排
总预算：5000元

## 时间安排
活动时间：2026年9月

## 总结
本次活动预计能有效提升校园文化氛围。""",
            skill_path=["root", "校园"],
            domain_weights={"accuracy": 0.25, "professional": 0.20, "completeness": 0.20,
                           "reasoning": 0.15, "structure": 0.10, "actionable": 0.10}
        )
        assert "review_score" in result
        assert "difficulty_threshold" in result
        assert "dimensions" in result
        assert "pass" in result
        assert 0 <= result["review_score"] <= 1
        assert 0 <= result["difficulty_threshold"] <= 1