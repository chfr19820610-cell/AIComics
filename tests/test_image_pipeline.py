"""Tests for image_pipeline module — matting, generation, upscaling, composite, pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


# === models.py ===

class TestModelManager:
    def test_check_available(self, tmp_path):
        from aicomic.image_pipeline.models import ModelManager
        mm = ModelManager(comfyui_root=tmp_path)
        (tmp_path / "models" / "checkpoints").mkdir(parents=True)
        (tmp_path / "models" / "checkpoints" / "sd_xl_base_1.0.safetensors").touch()
        avail = mm.check_available()
        assert "sd_xl_base_1.0.safetensors" in avail["checkpoints"]

    def test_missing_models(self, tmp_path):
        from aicomic.image_pipeline.models import ModelManager
        mm = ModelManager(comfyui_root=tmp_path)
        avail = mm.check_available()
        assert avail["checkpoints"] == []

    def test_get_download_instructions(self, tmp_path):
        from aicomic.image_pipeline.models import ModelManager
        mm = ModelManager(comfyui_root=tmp_path)
        instructions = mm.get_download_instructions()
        assert "controlnet" in instructions
        assert "upscale" in instructions
        assert "rmbg" in instructions


# === workflows.py ===

class TestWorkflowBuilder:
    def test_matting_workflow_raises_when_unsupported(self):
        """v3.0: RMBG requires custom node, raise RuntimeError until installed."""
        from aicomic.image_pipeline.workflows import build_matting_workflow
        with pytest.raises(RuntimeError, match="RMBG"):
            build_matting_workflow("input.png", "rmbg_model.onnx")

    def test_generate_workflow_sdxl(self):
        from aicomic.image_pipeline.workflows import build_generate_workflow
        wf = build_generate_workflow(
            prompt="a cute cat", negative="blurry",
            width=1024, height=1024, seed=42, steps=20, cfg=7.0,
            checkpoint="sd_xl_base_1.0.safetensors",
        )
        class_types = [n["class_type"] for n in wf["prompt"].values()]
        assert "CheckpointLoaderSimple" in class_types
        assert "KSampler" in class_types
        assert "VAEDecode" in class_types
        assert "SaveImage" in class_types

    def test_generate_workflow_with_controlnet_raises(self):
        """v3.0: ControlNet requires explicit readiness check before building workflow."""
        from aicomic.image_pipeline.workflows import build_generate_workflow
        with pytest.raises(RuntimeError, match="ControlNet"):
            build_generate_workflow(
                prompt="test", negative="", width=512, height=512,
                seed=1, steps=10, cfg=5.0,
                checkpoint="sd_xl_base_1.0.safetensors",
                controlnet_type="canny",
                controlnet_model="controlnet-canny-sdxl.safetensors",
                controlnet_image="canny_input.png",
            )

    def test_upscale_workflow(self):
        from aicomic.image_pipeline.workflows import build_upscale_workflow
        wf = build_upscale_workflow("input.png", "RealESRGAN_x4plus.pth", 4)
        class_types = [n["class_type"] for n in wf["prompt"].values()]
        assert "LoadImage" in class_types
        assert "SaveImage" in class_types

    def test_full_pipeline_workflow(self):
        from aicomic.image_pipeline.workflows import build_full_pipeline_workflow
        wf = build_full_pipeline_workflow(
            prompt="test", negative="", width=512, height=512,
            seed=1, steps=10, cfg=5.0,
            checkpoint="sd_xl_base_1.0.safetensors",
            upscale_model="RealESRGAN_x4plus.pth", upscale_scale=4,
        )
        class_types = [n["class_type"] for n in wf["prompt"].values()]
        assert "CheckpointLoaderSimple" in class_types
        assert "KSampler" in class_types
        assert "ImageUpscaleWithModel" in class_types
        assert "SaveImage" in class_types


# === matting.py ===

class TestMatting:
    def test_matting_raises_when_rmbg_unsupported(self, tmp_path):
        """v3.0: Matting service should raise when RMBG node is not installed."""
        from aicomic.image_pipeline.matting import MattingService
        mock_client = MagicMock()
        svc = MattingService(mock_client)
        inp = tmp_path / "input.png"
        inp.touch()
        with pytest.raises(RuntimeError, match="RMBG"):
            svc.remove_background(inp, tmp_path / "out.png")

    def test_matting_empty_input_raises(self, tmp_path):
        from aicomic.image_pipeline.matting import MattingService
        mock_client = MagicMock()
        svc = MattingService(mock_client)
        with pytest.raises(FileNotFoundError):
            svc.remove_background(Path("/nonexist.png"), tmp_path / "out.png")


# === generation.py ===

class TestGeneration:
    def test_generate_calls_comfyui(self, tmp_path):
        from aicomic.image_pipeline.generation import GenerationService
        mock_client = MagicMock()
        mock_client.submit_and_wait.return_value = {"output_path": str(tmp_path / "gen.png")}
        svc = GenerationService(mock_client)
        result = svc.generate(
            prompt="a cute cat", negative="blurry",
            width=1024, height=1024, seed=42, steps=20, cfg=7.0,
            checkpoint="sd_xl_base_1.0.safetensors",
            output_path=tmp_path / "gen.png",
        )
        assert result == tmp_path / "gen.png"

    def test_generate_with_controlnet_raises(self, tmp_path):
        """v3.0: ControlNet generation should raise until models are verified available."""
        from aicomic.image_pipeline.generation import GenerationService
        mock_client = MagicMock()
        svc = GenerationService(mock_client)
        with pytest.raises(RuntimeError, match="ControlNet"):
            svc.generate(
                prompt="test", negative="", width=512, height=512,
                seed=1, steps=10, cfg=5.0,
                checkpoint="sd_xl_base_1.0.safetensors",
                controlnet_type="canny",
                controlnet_model="controlnet-canny.safetensors",
                controlnet_image=tmp_path / "canny.png",
                output_path=tmp_path / "gen.png",
            )


# === upscaling.py ===

class TestUpscaling:
    def test_upscale_calls_comfyui(self, tmp_path):
        from aicomic.image_pipeline.upscaling import UpscalingService
        mock_client = MagicMock()
        mock_client.submit_and_wait.return_value = {"output_path": str(tmp_path / "upscaled.png")}
        svc = UpscalingService(mock_client)
        inp = tmp_path / "input.png"
        inp.touch()
        result = svc.upscale(inp, "RealESRGAN_x4plus.pth", 4, tmp_path / "upscaled.png")
        assert result == tmp_path / "upscaled.png"
        mock_client.submit_and_wait.assert_called_once()

    def test_upscale_empty_input_raises(self, tmp_path):
        from aicomic.image_pipeline.upscaling import UpscalingService
        mock_client = MagicMock()
        svc = UpscalingService(mock_client)
        with pytest.raises(FileNotFoundError):
            svc.upscale(Path("/nonexist.png"), "model.pth", 4, tmp_path / "out.png")


# === composite.py ===

class TestComposite:
    def test_composite_foreground_on_background(self, tmp_path):
        from aicomic.image_pipeline.composite import CompositeService
        fg = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        fg_path = tmp_path / "fg.png"
        fg.save(fg_path)
        bg = Image.new("RGB", (20, 20), (0, 0, 255))
        bg_path = tmp_path / "bg.png"
        bg.save(bg_path)
        svc = CompositeService()
        result = svc.composite(fg_path, bg_path, x=5, y=5, output_path=tmp_path / "out.png")
        assert result.exists()
        out = Image.open(result)
        assert out.size == (20, 20)
        assert out.getpixel((7, 7))[:3] == (255, 0, 0)
        assert out.getpixel((0, 0))[:3] == (0, 0, 255)

    def test_composite_no_offset(self, tmp_path):
        from aicomic.image_pipeline.composite import CompositeService
        fg = Image.new("RGBA", (5, 5), (0, 255, 0, 255))
        fg_path = tmp_path / "fg.png"
        fg.save(fg_path)
        bg = Image.new("RGB", (5, 5), (0, 0, 0))
        bg_path = tmp_path / "bg.png"
        bg.save(bg_path)
        svc = CompositeService()
        result = svc.composite(fg_path, bg_path, x=0, y=0, output_path=tmp_path / "out.png")
        out = Image.open(result)
        assert out.getpixel((2, 2))[:3] == (0, 255, 0)

    def test_composite_semi_transparent(self, tmp_path):
        from aicomic.image_pipeline.composite import CompositeService
        fg = Image.new("RGBA", (1, 1), (255, 0, 0, 128))
        fg_path = tmp_path / "fg.png"
        fg.save(fg_path)
        bg = Image.new("RGB", (1, 1), (0, 0, 255))
        bg_path = tmp_path / "bg.png"
        bg.save(bg_path)
        svc = CompositeService()
        result = svc.composite(fg_path, bg_path, x=0, y=0, output_path=tmp_path / "out.png")
        out = Image.open(result)
        r, g, b = out.getpixel((0, 0))[:3]
        assert r > 0 and b > 0


# === pipeline.py ===

class TestImagePipeline:
    def _make_mock_with_files(self, tmp_path, paths_to_create):
        """Create a mock client that creates output files."""
        mock_client = MagicMock()
        def side_effect(workflow, output_path=None):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            # Create a real image file for composite to read
            Image.new("RGB", (10, 10), (100, 100, 100)).save(output_path)
            return {"output_path": output_path}
        mock_client.submit_and_wait.side_effect = side_effect
        return mock_client

    def test_pipeline_generate_only(self, tmp_path):
        from aicomic.image_pipeline.pipeline import ImagePipeline
        mock_client = self._make_mock_with_files(tmp_path, [])
        pipe = ImagePipeline(comfyui_client=mock_client, output_dir=tmp_path)
        result = pipe.run(
            prompt="a cute cat", negative="blurry",
            width=1024, height=1024, seed=42,
            checkpoint="sd_xl_base_1.0.safetensors",
        )
        assert "output_path" in result
        assert result["stages_executed"] == ["generate"]

    def test_pipeline_full_with_matting_raises_without_rmbg(self, tmp_path):
        """v3.0: Pipeline with reference_image should raise when RMBG is unavailable."""
        from aicomic.image_pipeline.pipeline import ImagePipeline
        mock_client = self._make_mock_with_files(tmp_path, [])
        ref = tmp_path / "ref.png"
        ref.touch()
        pipe = ImagePipeline(comfyui_client=mock_client, output_dir=tmp_path)
        with pytest.raises(RuntimeError, match="RMBG"):
            pipe.run(
                prompt="a cute cat", negative="blurry",
                width=1024, height=1024, seed=42,
                checkpoint="sd_xl_base_1.0.safetensors",
                reference_image=ref,
            )

    def test_pipeline_with_upscale(self, tmp_path):
        from aicomic.image_pipeline.pipeline import ImagePipeline
        mock_client = self._make_mock_with_files(tmp_path, [])
        pipe = ImagePipeline(comfyui_client=mock_client, output_dir=tmp_path)
        result = pipe.run(
            prompt="test", negative="",
            width=512, height=512, seed=1,
            checkpoint="sd_xl_base_1.0.safetensors",
            upscale=True,
        )
        assert "upscale" in result["stages_executed"]

    def test_pipeline_metadata(self, tmp_path):
        from aicomic.image_pipeline.pipeline import ImagePipeline
        mock_client = self._make_mock_with_files(tmp_path, [])
        pipe = ImagePipeline(comfyui_client=mock_client, output_dir=tmp_path)
        result = pipe.run(
            prompt="a cute cat", negative="blurry",
            width=1024, height=1024, seed=42,
            checkpoint="sd_xl_base_1.0.safetensors",
        )
        assert result["metadata"]["prompt"] == "a cute cat"
        assert result["metadata"]["seed"] == 42
        assert result["metadata"]["checkpoint"] == "sd_xl_base_1.0.safetensors"

    def test_pipeline_composite(self, tmp_path):
        from aicomic.image_pipeline.pipeline import ImagePipeline
        mock_client = self._make_mock_with_files(tmp_path, [])
        bg = Image.new("RGB", (10, 10), (50, 50, 50))
        bg_path = tmp_path / "bg.png"
        bg.save(bg_path)
        pipe = ImagePipeline(comfyui_client=mock_client, output_dir=tmp_path)
        result = pipe.run(
            prompt="test", negative="",
            width=10, height=10, seed=1,
            checkpoint="sd_xl_base_1.0.safetensors",
            composite_bg=bg_path,
        )
        assert "composite" in result["stages_executed"]


class TestImagePipelineReadiness:
    def test_diagnostics_reports_observed_nodes_models_and_blocked_stages(self, tmp_path):
        from aicomic.image_pipeline.diagnostics import build_readiness

        checkpoints = tmp_path / "models" / "checkpoints"
        upscale = tmp_path / "models" / "upscale_models"
        checkpoints.mkdir(parents=True)
        upscale.mkdir(parents=True)
        (checkpoints / "sd_xl_base_1.0.safetensors").touch()
        (upscale / "RealESRGAN_x4plus.pth").touch()
        client = MagicMock()
        client.get_json.side_effect = [
            {"system": {"os": "test"}},
            {name: {} for name in (
                "CheckpointLoaderSimple", "ControlNetLoader", "ControlNetApplyAdvanced",
                "UpscaleModelLoader", "ImageUpscaleWithModel", "UNETLoader", "DualCLIPLoader",
                "ModelSamplingFlux", "LoadImage",
            )},
        ]

        result = build_readiness(client, comfyui_root=tmp_path, dry_run=True)

        assert result["dry_run"] is True
        assert result["prompt_posted"] is False
        assert result["nodes"]["LoadImage"] is True
        assert result["models"]["checkpoints"] == ["sd_xl_base_1.0.safetensors"]
        assert "RMBG" in result["missing"]
        assert result["stages"]["generate"]["status"] == "ready"
        assert result["stages"]["matting"]["status"] == "blocked"
        assert result["stages"]["upscale"]["status"] == "ready"
        client.post_json.assert_not_called()
        client.submit_and_wait.assert_not_called()

    def test_diagnostics_dry_run_does_not_post_prompt(self, tmp_path):
        from aicomic.image_pipeline.diagnostics import build_readiness

        client = MagicMock()
        client.get_json.side_effect = [{}, {}]
        result = build_readiness(client, comfyui_root=tmp_path, dry_run=True)

        assert result["prompt_posted"] is False
        client.post_json.assert_not_called()
        client.submit_and_wait.assert_not_called()


class TestWorkflowContracts:
    def test_rmbg_workflow_is_explicitly_unsupported(self):
        from aicomic.image_pipeline.workflows import build_matting_workflow

        with pytest.raises(RuntimeError, match="RMBG"):
            build_matting_workflow("input.png")

    def test_controlnet_workflow_requires_available_contract(self):
        from aicomic.image_pipeline.workflows import build_generate_workflow

        with pytest.raises(RuntimeError, match="ControlNet"):
            build_generate_workflow(
                prompt="test", negative="", width=512, height=512,
                seed=1, steps=10, cfg=5.0,
                checkpoint="sd_xl_base_1.0.safetensors",
                controlnet_type="canny",
                controlnet_model="controlnet-canny.safetensors",
                controlnet_image="canny_input.png",
            )
