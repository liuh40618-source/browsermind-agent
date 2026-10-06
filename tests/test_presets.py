"""PRESETS 结构测试：前端模型选择器渲染依赖的数据契约。

只验证真实存在的数据结构：models 为纯字符串列表（模型名），
不包含任何编造的倍率/标签元数据。
"""

from settings_store import PRESETS


class TestPresetsContract:
    def test_all_providers_have_required_fields(self):
        """每个供应商必须有 label / base_url / models 列表。"""
        assert len(PRESETS) >= 4
        for provider, spec in PRESETS.items():
            assert spec["label"], f"{provider} 缺少 label"
            assert spec["base_url"].startswith("http"), f"{provider} 的 base_url 非法"
            assert isinstance(spec["models"], list) and spec["models"], f"{provider} 的 models 为空"

    def test_models_are_plain_string_names(self):
        """models 必须是纯字符串模型名，不含编造的倍率/标签对象。"""
        for provider, spec in PRESETS.items():
            for m in spec["models"]:
                assert isinstance(m, str) and m.strip(), f"{provider} 存在非法模型项: {m!r}"

    def test_model_names_unique_within_provider(self):
        """同一供应商内模型名不重复（前端下拉 value 会冲突）。"""
        for provider, spec in PRESETS.items():
            names = spec["models"]
            assert len(names) == len(set(names)), f"{provider} 存在重复模型名"

    def test_no_fabricated_metadata(self):
        """PRESETS 中不得出现倍率/标签等虚构字段。"""
        import json
        raw = json.dumps(PRESETS, ensure_ascii=False)
        for bad in ("cost_weight", "tag", "×", "倍率"):
            assert bad not in raw, f"PRESETS 中包含虚构元数据: {bad}"

    def test_known_models_present(self):
        """关键模型应存在于预设中（用户常用）。"""
        all_names = {m for spec in PRESETS.values() for m in spec["models"]}
        assert "gpt-4o" in all_names
        assert "deepseek-chat" in all_names
        assert "qwen-plus" in all_names
        assert "glm-4-air" in all_names
