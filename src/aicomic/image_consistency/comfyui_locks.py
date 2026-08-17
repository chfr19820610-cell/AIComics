"""ComfyUI 图像级锁脸工作流构建器（ACOM-0.7.1）。

把立绘母版的图像级控制配置（IPAdapter 参考图锁脸 / ControlNet 结构锁定 /
LoRA 角色权重）编排成 ComfyUI API 格式的节点图。

诚实标注：
  - 本模块负责「接入编排」——把母版配置翻译成合法的 ComfyUI API 工作流 JSON。
  - 真实出图依赖权重模型文件（IPAdapter FaceID / ControlNet / LoRA / checkpoint）。
    这些文件需联网下载后才能执行（probe_lock_models 会逐项探测并如实报告缺失项）。
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aicomic.image_consistency.master_sheet import MasterSheetEntry

# ComfyUI 内置节点类型名（用于 /object_info 探测）
REQUIRED_NODE_TYPES = {
    "ipadapter": ("IPAdapterUnifiedLoaderFaceID", "IPAdapterAdvanced", "LoadImage"),
    "controlnet": ("ControlNetLoader", "ControlNetApply"),
    "lora": ("LoraLoader",),
}


@dataclass
class LockModelStatus:
    """图像级锁脸依赖模型的可用性探测结果。"""
    node_types: dict[str, list[str]] = field(default_factory=dict)
    model_files: dict[str, str] = field(default_factory=dict)  # name -> abs path
    missing: list[str] = field(default_factory=list)          # 待联网/缺失项
    all_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_types_present": self.node_types,
            "model_files": self.model_files,
            "missing": self.missing,
            "all_ready": self.all_ready,
        }


# ── 工作流构建（纯数据生成，可离线验证） ───────────────────────────────


def build_locked_workflow(
    master: MasterSheetEntry,
    positive_prompt: str,
    negative_prompt: str = "",
    checkpoint_name: str = "animagineXL_v4.safetensors",
    output_prefix: str = "locked_shot",
) -> dict[str, Any]:
    """把立绘母版 + 分镜 prompt 编排成 ComfyUI API 工作流节点图。

    返回 ComfyUI `/prompt` 所需的 {"prompt": {...}, "extra": {...}} 结构
    （extra 含母版 DNA 元数据，便于追溯）。
    若母版未锁定（locked=False）则在 extra 里注明仍为「未锁定」。
    """
    cfg = master.lock_config or {}
    nodes: dict[str, Any] = {}
    nid = 1

    # 1) 采样器
    def _checkpoint():
        nonlocal nid
        nodes[str(nid)] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        }
        cid = str(nid); nid += 1
        return cid

    # 2) 正/负提示词
    nodes[str(nid)] = {"class_type": "CLIPTextEncode", "inputs": {"text": positive_prompt,
                     "clip": ["MODEL_PLACEHOLDER", 1]}}
    pos_id = str(nid); nid += 1
    nodes[str(nid)] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt,
                     "clip": ["MODEL_PLACEHOLDER", 1]}}
    neg_id = str(nid); nid += 1

    ckpt_id = _checkpoint()

    # 3) 图像级锁脸层（按母版配置叠 IPAdapter / ControlNet / LoRA）
    clip_src = ["MODEL_PLACEHOLDER", 1]  # 将被 LoRA 改写
    model_src = ["MODEL_PLACEHOLDER", 0]
    lora_applied = False

    ip_cfg = cfg.get("ipadapter") or {}
    if ip_cfg.get("enabled"):
        # LoadImage 加载母版参考图（IPAdapter FaceID 参考）
        nodes[str(nid)] = {"class_type": "LoadImage",
                           "inputs": {"image": _rel_input_path(master.master_image_path)}}
        ref_id = str(nid); nid += 1
        nodes[str(nid)] = {
            "class_type": "IPAdapterUnifiedLoaderFaceID",
            "inputs": {"model": model_src, "ipadapter": "ip-adapter-faceid_sdxl.bin",
                       "lora_strength": 1.0},
        }
        loader_id = str(nid); nid += 1
        nodes[str(nid)] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": [loader_id, 0],
                "ipadapter": [loader_id, 1],
                "image": [ref_id, 0],
                "weight": float(ip_cfg.get("weight", 0.85)),
                "weight_type": "linear",
                "start_at": 0.0,
                "end_at": 1.0,
            },
        }
        model_src = [str(nid), 0]; nid += 1
        clip_src = [loader_id, 1]

    cn_cfg = cfg.get("controlnet") or {}
    if cn_cfg.get("enabled"):
        nodes[str(nid)] = {"class_type": "ControlNetLoader",
                           "inputs": {"control_net_name": f"{cn_cfg.get('type','openpose')}.safetensors"}}
        cn_id = str(nid); nid += 1
        nodes[str(nid)] = {"class_type": "ControlNetApply",
                           "inputs": {"conditioning": [neg_id, 0], "control_net": [cn_id, 0],
                                      "image": ["CONTROL_IMAGE", 0], "strength": float(cn_cfg.get("weight", 0.6))}}
        neg_id = str(nid); nid += 1

    lora_cfg = cfg.get("lora") or {}
    if lora_cfg.get("enabled") and lora_cfg.get("name"):
        nodes[str(nid)] = {"class_type": "LoraLoader",
                           "inputs": {"model": model_src, "clip": clip_src,
                                      "lora_name": lora_cfg["name"],
                                      "strength_model": float(lora_cfg.get("strength", 0.8)),
                                      "strength_clip": float(lora_cfg.get("strength", 0.8))}}
        lora_id = str(nid); nid += 1
        model_src = [lora_id, 0]
        clip_src = [lora_id, 1]
        lora_applied = True

    # 4) 补全 clip 引用（LoRA 未应用时直接指向 checkpoint）
    if not lora_applied:
        # 回填 CLIPTextEncode 的 clip 引用
        nodes[pos_id]["inputs"]["clip"] = [ckpt_id, 1]
        nodes[neg_id]["inputs"]["clip"] = [ckpt_id, 1]

    nodes[str(nid)] = {"class_type": "VAELoader", "inputs": {"vae_name": "sdxl_vae.safetensors"}}
    vae_id = str(nid); nid += 1

    nodes[str(nid)] = {
        "class_type": "KSampler",
        "inputs": {"model": model_src, "positive": [pos_id, 0], "negative": [neg_id, 0],
                   "latent_image": ["EMPTY_LATENT", 0],
                   "seed": 42, "steps": 25, "cfg": 7.0,
                   "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
    }
    sampler_id = str(nid); nid += 1
    nodes[str(nid)] = {"class_type": "EmptyLatentImage",
                       "inputs": {"width": 832, "height": 1216, "batch_size": 1}}
    empty_id = str(nid); nid += 1
    nodes[sampler_id]["inputs"]["latent_image"] = [empty_id, 0]

    nodes[str(nid)] = {"class_type": "VAEDecode", "inputs": {"samples": [sampler_id, 0], "vae": [vae_id, 0]}}
    decode_id = str(nid); nid += 1
    nodes[str(nid)] = {"class_type": "SaveImage",
                       "inputs": {"images": [decode_id, 0], "filename_prefix": output_prefix}}
    nid += 1

    return {
        "prompt": nodes,
        "extra": {
            "locked": master.locked,
            "character_name": master.character_name,
            "master_image": master.master_image_path,
            "dna": master.dna,
            "lock_config": master.lock_config,
            "note": "图像级锁脸工作流（IPAdapter/ControlNet/LoRA 按母版配置编排）",
        },
    }


def _rel_input_path(abs_path: str) -> str:
    """ComfyUI 的 LoadImage 需要输入目录内相对路径；此处返回文件名近似。"""
    return Path(abs_path).name


def validate_locked_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    """校验工作流结构完整性（确定性检查）。"""
    prompt = workflow.get("prompt", {})
    classes = [n.get("class_type", "") for n in prompt.values()]
    problems: list[str] = []
    if "CheckpointLoaderSimple" not in classes:
        problems.append("缺少 checkpoint 加载节点")
    if "KSampler" not in classes:
        problems.append("缺少采样节点")
    if "SaveImage" not in classes:
        problems.append("缺少输出节点")
    if "IPAdapterUnifiedLoaderFaceID" not in classes and "LoraLoader" not in classes:
        problems.append("未启用任何图像级锁脸层（IPAdapter/LoRA 均未编排）")
    return {"valid": len(problems) == 0, "problems": problems, "node_count": len(prompt)}


# ── 模型可用性探测（如实报告待联网项） ─────────────────────────────────


def probe_lock_models(
    comfyui_base_url: str = "http://127.0.0.1:8188",
    model_root: str | Path | None = None,
    timeout: float = 4.0,
) -> LockModelStatus:
    """探测 IPAdapter/ControlNet/LoRA 依赖在运行中 ComfyUI 上的可用性。

    1) 通过 /object_info 检查必需节点类型是否注册。
    2) 检查模型权重文件是否落盘（缺则标 missing，即「待联网下载」）。
    """
    status = LockModelStatus()

    # ── 节点类型探测 ──
    node_types_present: dict[str, list[str]] = {}
    try:
        with urllib.request.urlopen(f"{comfyui_base_url}/object_info", timeout=timeout) as resp:
            object_info = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        status.missing.append(f"ComfyUI 不可达({comfyui_base_url})：{exc}")
        status.all_ready = False
        return status

    for group, types in REQUIRED_NODE_TYPES.items():
        present = [t for t in types if t in object_info]
        absent = [t for t in types if t not in object_info]
        node_types_present[group] = present
        for t in absent:
            status.missing.append(f"缺少节点类型: {t}")

    # ── 模型文件探测 ──
    model_files: dict[str, str] = {}
    if model_root is not None:
        root = Path(model_root)
        probes = {
            "ipadapter_faceid": root / "ipadapter" / "ip-adapter-faceid_sdxl.bin",
            "controlnet_openpose": root / "controlnet" / "openpose.safetensors",
            "vae": root / "vae" / "sdxl_vae.safetensors",
            "checkpoint": root / "checkpoints" / "animagineXL_v4.safetensors",
            "lora_dir": root / "loras",
        }
        for name, p in probes.items():
            if name == "lora_dir":
                if p.exists():
                    model_files[name] = str(p)
                continue
            if p.exists():
                model_files[name] = str(p)
            else:
                status.missing.append(f"缺少权重文件: {name}（需联网下载）")

    status.node_types = node_types_present
    status.model_files = model_files
    status.all_ready = not status.missing
    return status
