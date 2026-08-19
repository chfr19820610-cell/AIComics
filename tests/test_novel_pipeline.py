"""Novel → 漫剧 pipeline tests."""
from __future__ import annotations

import pytest

from aicomic.core.novel_pipeline import (
    count_novel_stats,
    import_novel,
    import_novel_file,
)


# Sample novel text for testing
SAMPLE_NOVEL = """
第一章 归来

李明拖着行李箱走出机场，十年了，他终于回到了这座城市。
出租车司机问去哪里，他沉默了许久才说："老城区，幸福路18号。"
那栋老房子还在，只是门口的桂花树比记忆中高了许多。
推开门，灰尘扑面而来。客厅的墙上还挂着他父亲的照片。
"爸，我回来了。"他轻声说，声音在空荡的房间里回响。

第二章 重逢

第二天清晨，李明去楼下的早餐店。
老板娘一眼就认出了他："是小明吧？十年了啊！"
"阿姨好。"他点了碗馄饨，坐在角落里慢慢吃。
这时，一个穿着白裙的女孩走进来，点了一杯豆浆。
她转过头，看到李明，愣住了。
"是你？"她惊讶地说。
"苏晚？"李明也站了起来。

第三章 秘密

下午，李明去父亲的旧书房整理遗物。
在书架最深处，他发现了一个铁盒子。
打开一看，里面是一封泛黄的信和一张老照片。
照片上，父亲和一个陌生男人站在一座老宅前。
信上写着："如果你看到这封信，说明我已经不在了。
那座老宅的地下，藏着我们当年的秘密。"
李明的手开始发抖。
"""


class TestCountNovelStats:
    def test_basic_stats(self):
        stats = count_novel_stats(SAMPLE_NOVEL)
        assert stats["char_count"] > 0
        assert stats["chapter_count"] == 3
        assert stats["estimated_episodes"] >= 1

    def test_empty_text(self):
        stats = count_novel_stats("")
        assert stats["char_count"] == 0
        assert stats["chapter_count"] == 0


class TestImportNovel:
    def test_import_returns_dict(self):
        result = import_novel(SAMPLE_NOVEL, template="workplace")
        assert isinstance(result, dict)
        assert "episodes" in result
        assert result["template"] == "workplace"

    def test_import_generates_episodes(self):
        result = import_novel(SAMPLE_NOVEL, template="mystery")
        assert result["episode_count"] >= 1
        assert len(result["episodes"]) == result["episode_count"]

    def test_each_episode_has_blueprint(self):
        result = import_novel(SAMPLE_NOVEL, template="cultivation", shots_per_episode=5)
        for ep in result["episodes"]:
            assert "blueprint" in ep
            assert "acts" in ep["blueprint"]
            assert ep["blueprint"]["shot_count"] == len(ep["novel_shots"])

    def test_each_episode_has_hook(self):
        result = import_novel(SAMPLE_NOVEL, template="sweetpet")
        for ep in result["episodes"]:
            assert ep["hook"]  # non-empty

    def test_episode_count_capped(self):
        result = import_novel(SAMPLE_NOVEL, episode_target_count=1)
        assert result["episode_count"] == 1

    def test_unknown_template_raises(self):
        with pytest.raises(FileNotFoundError):
            import_novel(SAMPLE_NOVEL, template="nonexistent")

    def test_novel_shots_preserved(self):
        """Original novel content is kept in novel_shots for LLM rewriting."""
        result = import_novel(SAMPLE_NOVEL, template="workplace", shots_per_episode=3)
        ep = result["episodes"][0]
        assert len(ep["novel_shots"]) > 0
        assert "visual" in ep["novel_shots"][0]


class TestImportNovelFile:
    def test_import_from_file(self, tmp_path):
        novel_file = tmp_path / "test_novel.txt"
        novel_file.write_text(SAMPLE_NOVEL, encoding="utf-8")
        result = import_novel_file(novel_file, template="workplace")
        assert result["episode_count"] >= 1

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            import_novel_file("/nonexistent/novel.txt")


class TestNovelPipelineIntegration:
    def test_full_pipeline_workplace(self):
        """Full: novel text → split → workplace template → blueprints."""
        result = import_novel(SAMPLE_NOVEL, template="workplace", episode_target_count=3, shots_per_episode=4)
        assert result["genre"] == "职场逆袭"
        for ep in result["episodes"]:
            assert len(ep["blueprint"]["acts"]) == 5
            assert ep["blueprint"]["acts"][0]["beat"] == "humiliation"

    def test_template_affects_blueprint_style(self):
        """Different templates produce different act structures."""
        r_workplace = import_novel(SAMPLE_NOVEL, template="workplace", episode_target_count=1, shots_per_episode=3)
        r_mystery = import_novel(SAMPLE_NOVEL, template="mystery", episode_target_count=1, shots_per_episode=3)
        wp_beats = [a["beat"] for a in r_workplace["episodes"][0]["blueprint"]["acts"]]
        ms_beats = [a["beat"] for a in r_mystery["episodes"][0]["blueprint"]["acts"]]
        assert wp_beats != ms_beats
