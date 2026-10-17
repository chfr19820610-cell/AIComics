"""Phase A 回归测试 — 每个 bug 一个测试，防止再次全绿漏网。"""

from aicomic.characters.consistency_service import AttributeEntry, _dedup_attributes


class TestDedupAttributes:
    def test_dedup_keeps_first_occurrence(self):
        attrs = [
            AttributeEntry(category="hair", attribute="黑长发", source_text="黑长发", confidence=0.9),
            AttributeEntry(category="hair", attribute="黑长发", source_text="黑长发", confidence=0.9),
            AttributeEntry(category="eyes", attribute="红瞳", source_text="红瞳", confidence=0.9),
        ]
        result = _dedup_attributes(attrs)
        assert len(result) == 2
        assert [a.attribute for a in result] == ["黑长发", "红瞳"]

    def test_dedup_empty_input(self):
        assert _dedup_attributes([]) == []
