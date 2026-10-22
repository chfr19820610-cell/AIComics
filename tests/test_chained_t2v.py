"""chained_t2v 反漂移链式生成：帧锚接力 + 角色契约 + take 计划。"""

import subprocess

import pytest

from aicomic.video_synthesis.chained_t2v import (
    CharacterContract,
    build_shot_workflow,
    extract_last_frame,
    take_seeds,
)


class TestBuildShotWorkflow:
    def test_t2v_no_addguide(self):
        wf = build_shot_workflow("anime cinematic: sunset rooftop", seed=11)
        types = {n["class_type"] for n in wf.values()}
        assert "MiniMaxH3AddGuide" not in types
        assert "UnetLoaderGGUF" in types
        assert "CLIPLoaderGGUF" in types
        assert "EmptyMiniMaxH3LatentAV" in wf["4"]["class_type"]

    def test_i2v_addguide_wiring(self):
        wf = build_shot_workflow("same woman looks up", seed=5, first_frame_image="relay.png")
        types = {n["class_type"] for n in wf.values()}
        assert "MiniMaxH3AddGuide" in types
        guide = next(n for n in wf.values() if n["class_type"] == "MiniMaxH3AddGuide")
        assert guide["inputs"]["frame_idx"] == 0
        assert guide["inputs"]["image"] == ["5", 0]
        assert guide["inputs"]["vae"] == ["6", 0]
        assert next(n for n in wf.values() if n["class_type"] == "LoadImage")["inputs"]["image"] == "relay.png"
        sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
        assert sampler["inputs"]["positive"] == ["7", 0]

    def test_width_height_propagate(self):
        wf = build_shot_workflow("x", seed=1, width=512, height=910, length=237)
        assert wf["4"]["inputs"] == {"width": 512, "height": 910, "length": 237, "batch_size": 1}


class TestCharacterContract:
    def _contract(self):
        return CharacterContract(
            name="林陌",
            prompts_face="25-year-old woman, long black hair in neat bun",
            prompts_outfit="white blouse under charcoal suit vest, silver drop earrings",
            extra_style="anime style cinematic still, warm realistic lighting",
        )

    def test_verbatim_stable(self):
        c = self._contract()
        a = c.render_block()
        b = c.render_block()
        assert a == b and len(a) > 40

    def test_compose_prompt(self):
        c = self._contract()
        p = c.compose_prompt("she bows at the door")
        assert c.render_block() in p
        assert "she bows at the door" in p


class TestTakeSeeds:
    def test_per_shot_perturb(self):
        base = take_seeds(1000, shot_index=3, n=2)
        assert base[0] != 1000 and len(set(base)) == 2
        assert take_seeds(1000, 0, 2) != take_seeds(1000, 1, 2)


class TestExtractLastFrame:
    @pytest.fixture()
    def sample_video(self, tmp_path):
        ff = str(__import__("imageio_ffmpeg").get_ffmpeg_exe())
        out = tmp_path / "in.mp4"
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:duration=1", str(out)], capture_output=True)
        return ff, out

    def test_extract(self, sample_video):
        ff, src = sample_video
        dst = src.parent / "last.png"
        rc = extract_last_frame(src, dst, ff_bin=ff)
        assert rc == 0 and dst.exists() and dst.stat().st_size > 0
