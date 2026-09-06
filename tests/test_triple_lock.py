"""Tests for Triple-Lock character consistency module."""
from __future__ import annotations

import pytest


class TestTripleLockWorkflow:
    def test_build_triple_lock_workflow_structure(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="a warrior in a forest",
            negative="blurry, deformed",
            reference_image="ref.png",
        )
        prompt_dict = wf["prompt"]
        class_types = [n["class_type"] for n in prompt_dict.values()]

        # Layer 1: IPAdapter FaceID
        assert "IPAdapterUnifiedLoader" in class_types
        assert "IPAdapterFaceID" in class_types
        assert "LoadImage" in class_types

        # Layer 2: ControlNet
        assert "ControlNetLoader" in class_types
        assert "ControlNetApplyAdvanced" in class_types
        assert "OpenposePreprocessor" in class_types

        # Layer 3: FaceDetailer
        assert "FaceDetailer" in class_types

        # Core generation
        assert "CheckpointLoaderSimple" in class_types
        assert "KSampler" in class_types
        assert "VAEDecode" in class_types
        assert "SaveImage" in class_types

    def test_ipadapter_weight_is_0_75(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
        )
        # Node 7 is IPAdapterFaceID
        ipadapter_node = wf["prompt"]["7"]
        assert ipadapter_node["class_type"] == "IPAdapterFaceID"
        assert ipadapter_node["inputs"]["weight"] == 0.75

    def test_controlnet_strength_is_0_8(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
        )
        # Node 11 is ControlNetApplyAdvanced
        cn_node = wf["prompt"]["11"]
        assert cn_node["class_type"] == "ControlNetApplyAdvanced"
        assert cn_node["inputs"]["strength"] == 0.8

    def test_facedetailer_denoise_is_0_4(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
        )
        # Node 14 is FaceDetailer
        fd_node = wf["prompt"]["14"]
        assert fd_node["class_type"] == "FaceDetailer"
        assert fd_node["inputs"]["denoise"] == 0.4

    def test_depth_controlnet_uses_depth_preprocessor(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
            controlnet_type="depth",
        )
        class_types = [n["class_type"] for n in wf["prompt"].values()]
        assert "DepthPreprocessor" in class_types
        assert "OpenposePreprocessor" not in class_types

    def test_seed_is_set_when_negative(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
            seed=-1,
        )
        ksampler = wf["prompt"]["12"]
        assert ksampler["inputs"]["seed"] > 0

    def test_seed_is_preserved_when_positive(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
            seed=42,
        )
        ksampler = wf["prompt"]["12"]
        assert ksampler["inputs"]["seed"] == 42

    def test_extra_dict_is_empty(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_workflow
        wf = build_triple_lock_workflow(
            prompt="test", negative="", reference_image="ref.png",
        )
        assert wf["extra"] == {}


class TestTripleLockMetadata:
    def test_metadata_has_three_layers(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_metadata
        meta = build_triple_lock_metadata(
            prompt="test",
            reference_image="ref.png",
            controlnet_type="openpose",
            seed=42,
        )
        assert len(meta["layers"]) == 3
        assert meta["layers"][0]["name"] == "IPAdapter FaceID"
        assert meta["layers"][1]["name"] == "ControlNet"
        assert meta["layers"][2]["name"] == "FaceDetailer"

    def test_metadata_has_correct_weights(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_metadata
        meta = build_triple_lock_metadata(
            prompt="test", reference_image="ref.png",
            controlnet_type="openpose", seed=1,
        )
        assert meta["ipadapter_weight"] == 0.75
        assert meta["controlnet_strength"] == 0.8
        assert meta["facedetailer_denoise"] == 0.4

    def test_metadata_pipeline_name(self):
        from aicomic.image_consistency.triple_lock import build_triple_lock_metadata
        meta = build_triple_lock_metadata(
            prompt="test", reference_image="ref.png",
            controlnet_type="openpose", seed=1,
        )
        assert meta["pipeline"] == "triple_lock"
