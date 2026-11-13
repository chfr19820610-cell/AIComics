# Phase B 步计划 — Provider 断链接线 + 智能层接入 + Web 合一 + 资源打通

> ✅ **执行状态（2026-11-13 校准）**：本计划 B1–B5 全部完成并提交。证据：`git log --grep="(B[1-5])"`（commits 2ec81a0/f0f6576/a522569/3a560b3/34502b6）。下方复选框此前未回填，现据提交记录补勾。


> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans（内联）逐任务实现。步骤使用复选框（`- [ ]`）跟踪。

**目标：** 把"有代码但没接线"的三条主线（云视频 Provider 断链、Jev cascade 路由、双 Web 后端）接通，并按 `IMAGE_PIPELINE_PLAN.md` Phase 2 下载缺失模型权重，把 401 主链问题准备好"用户换 key 即生效"的环境变量通路。

**架构：** ① `executor.py` 函数式执行层扩展出 `ProviderRegistry`（IProvider 类）执行分支，使 kling/seedance/wan 进入 dry-run/confirm-live 双保险执行链；② `request_builder` 视频路由升级为 cascade 优先 + 旧 type-router 兜底；③ `web/backend/app.py` 以子应用 mount 挂载 `aicomic.web.app`（前缀 `/api/v5`，零冲突）；④ HF 权重下载到 `local_providers/comfyui_runtime/ComfyUI/models/`（脚本带 resume + 校验）。

**技术栈：** Python 3.12 / FastAPI TestClient / urllib(HF 下载) / pytest。

**不在本计划内（需用户资源）：** OPENAI_API_KEY 401 的密钥本身、ComfyUI 自定义节点安装（IPAdapter_plus/RMBG 需装后重启服务）、发布平台 cookie、KLING/SEEDANCE/WAN 真实 API key。

---

## 文件结构

| 动作 | 文件 | 职责 |
|---|---|---|
| 修改 | `src/aicomic/providers/executor.py` | 类化 Provider 执行分支 |
| 修改 | `src/aicomic/providers/request_builder.py:667-726` | cascade 路由优先 |
| 修改 | `src/aicomic/providers/openai_adapter.py:18-20` | base_url env 覆盖 |
| 修改 | `web/backend/app.py:72` 附近 | mount `/api/v5` |
| 新建 | `tests/test_phase_b_wiring.py` | 任务1/4 回归测试 |
| 修改 | `tests/test_phase_a_regressions.py` | 任务3 测试追加 |
| 新建 | `scripts/download_comfy_lock_models.py` | B4 下载脚本（resume+校验+清单）|
| 生成 | `state/reports/…` | 下载后 probe 状态对照 |

---

### 任务 1：executor 打通 kling/seedance/wan（B1 Provider 断链）

**文件：** 修改 `src/aicomic/providers/executor.py`；测试 `tests/test_phase_b_wiring.py`

- [x] **步骤 1：执行现状确认** `.venv/bin/python -m pytest tests/test_cli_api_integration.py tests/test_provider_abstraction.py -q`（基线绿）
- [x] **步骤 2：失败测试**

```python
"""Phase B 检查接线 — 云 Provider 进执行链、cascade 路由、Web mount。"""

from pathlib import Path
import json
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_CFG = ROOT / "config" / "providers.yaml"

from aicomic.providers.executor import (
    build_provider_request_preview,
    execute_provider_requests,
    perform_provider_request,
)


def _vid_item(provider: str = "kling") -> dict:
    return {
        "request_id": "REQ_j1",
        "request_status": "ready",
        "payload": {
            "job_id": "E01_S01_VID",
            "episode_code": "E01",
            "shot_id": "S01",
            "job_type": "video",
            "provider": provider,
            "prompt": "test",
            "output_path": "state/local_provider_output/E01/video/E01_S01.mp4",
            "duration": 5,
        },
    }


class TestKlingExecutionPath:
    def test_kling_not_skipped_as_unsupported(self, monkeypatch, tmp_path: Path):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        monkeypatch.delenv("KLING_SECRET_KEY", raising=False)
        out = execute_provider_requests(
            {"requests": [_vid_item("kling")]},
            PROVIDERS_CFG,
            dry_run=False,
            confirm_live=False,
        )
        assert out["request_count"] == 1
        assert out["results"][0]["status"] == "blocked_live_confirmation_required"

    def test_kling_dry_run(self, monkeypatch):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        out = execute_provider_requests(
            {"requests": [_vid_item("kling")]}, PROVIDERS_CFG, dry_run=True
        )
        result = out["results"][0]
        assert result["status"] == "dry_run"
        assert result["provider_ready"] is False

    def test_kling_preview_has_preflight(self, monkeypatch):
        monkeypatch.delenv("KLING_ACCESS_KEY", raising=False)
        preview = build_provider_request_preview(_vid_item("kling"), PROVIDERS_CFG)
        assert set(preview) >= {"body"}
        assert isinstance(preview.get("preflight", {}).get("ready"), bool)

    def test_unknown_provider_still_skipped(self):
        out = execute_provider_requests({"requests": [_vid_item("human")]}, PROVIDERS_CFG)
        assert out["results"][0]["status"] == "skipped_unsupported_provider"

    def test_perform_dispatches_to_iexec(self, monkeypatch):
        monkeypatch.setenv("KLING_ACCESS_KEY", "ak-test")
        monkeypatch.setenv("KLING_SECRET_KEY", "sk-test")
        with patch(
            "aicomic.providers.kling_provider.KlingProvider.execute_request",
            return_value={"status": "succeeded"},
        ):
            out = perform_provider_request(_vid_item("kling"), PROVIDERS_CFG)
        assert out == {"status": "succeeded"}
```

- [x] **步骤 3：运行验证失败**（预期 kling 走 `skipped_unsupported_provider` 或 preview 抛 Unsupported）：
`.venv/bin/python -m pytest tests/test_phase_b_wiring.py -x -q`
- [x] **步骤 4：实现** — `executor.py` 顶部追加注册表导入与集合：

```python
from aicomic.providers.provider_registry import get_provider_registry

IEXEC_DISPATCH_PROVIDERS = {"kling", "seedance", "wan", "comfyui", "dall_e"}
SUPPORTED_EXECUTION_PROVIDERS = OPENAI_EXECUTION_PROVIDERS | LOCAL_EXECUTION_PROVIDERS | IEXEC_DISPATCH_PROVIDERS


def _resolve_iexec_provider(provider: str):
    """Resolve a class-based IProvider for dispatch (may return None)."""
    return get_provider_registry().resolve_for_job(provider)
```

`build_provider_request_preview` 中 `LOCAL_EXECUTION_PROVIDERS` 分支之后、兜底 `return` 之前插入：

```python
    if provider in IEXEC_DISPATCH_PROVIDERS:
        provider_instance = _resolve_iexec_provider(provider)
        if provider_instance is not None:
            preflight = provider_instance.validate_config()
            try:
                body = provider_instance.build_request(request_item, providers_config_path)
            except Exception as exc:
                body = {"error": str(exc)}
            return {
                "method": "POST",
                "url": provider_instance.get_provider_info().base_url,
                "headers": {"Authorization": "Bearer ${provider.upper()}_API_KEY"},
                "body": body,
                "preflight": preflight,
            }
```

`perform_provider_request` 中同样在 LOCAL 分支后插入：

```python
    if provider in IEXEC_DISPATCH_PROVIDERS:
        provider_instance = _resolve_iexec_provider(provider)
        if provider_instance is None:
            raise RuntimeError(f"Provider not registered: {provider}")
        return provider_instance.execute_request(request_item, providers_config_path)
```

若 `get_provider_info()` 无 `base_url` 字段，则 url 置空字符串（实现时以实际 ProviderInfo 为准，记录偏离）。
- [x] **步骤 5：验证 + 回归** `.venv/bin/python -m pytest tests/test_phase_b_wiring.py -q` 然后 `.venv/bin/python -m pytest -q`
- [x] **步骤 6：Commit** `feat: executor 经 ProviderRegistry 分发 kling/seedance/wan (B1)`

---

### 任务 2：cascade 路由接入 request_builder（B2 智能层）

**文件：** 修改 `src/aicomic/providers/request_builder.py:667-705`；无新测试文件（复用 `tests/test_request_builder.py` 的三个路由测试，行为更新）

- [x] **步骤 1：执行现状确认** `.venv/bin/python -m pytest tests/test_request_builder.py -q -k "video_routing or flf"` 记录 3 个测试现状（全绿基线）
- [x] **步骤 2：改写路由块** — 把 `if router:` 内的调用替换为 cascade 优先：

```python
        if router:
            routed_kwargs = {
                "shot_description": str(
                    payload.get("prompt") or payload.get("scene") or shot_type_str
                ),
                "motion_intensity": {"action": "high", "wide": "low", "transition": "low"}.get(
                    mapped_type.value, "medium"
                ),
            }
            try:
                decision = router.route_with_cascade(**routed_kwargs)
                routing_source = "cascade"
            except Exception:
                decision = router.route(mapped_type, flf=False)
                routing_source = "type_router"

            routing_decisions.append({
                "request_id": req["request_id"],
                "shot_type": mapped_type.value if hasattr(mapped_type, "value") else mapped_type,
                "routed_provider": decision.provider_name,
                "reason": decision.reason,
                "routing_source": routing_source,
            })
            if (
                decision.provider_name
                and decision.provider_name != payload.get("provider")
                and decision.provider_name != "human"  # EXTREME 保留人工，不改写 payload
            ):
                req["video_routing"] = {
                    "original_provider": payload.get("provider"),
                    "routed_provider": decision.provider_name,
                    "reason": decision.reason,
                    "routing_source": routing_source,
                }
                payload["provider"] = decision.provider_name
```

注意 `mapped_type` 是 `ShotType` 枚举成员（ShotType.ACTION 等），旧代码直接放进 dict；新代码记录 `.value`。若 `ShotType` 不是 Enum，则去掉 `hasattr` 分支直接用原值（实现时确认）。
- [x] **步骤 3：更新旧断言（若需要）** — 跑 `.venv/bin/python -m pytest tests/test_request_builder.py -q`；若 `reason`/`provider` 断言失败，把期望改为：`routed_provider in {"kling","seedance","wan","human"}` 且 `reason` 非空，并在测试名旁注明 cascade 原因。**不许删测试。**
- [x] **步骤 4：全套回归** `.venv/bin/python -m pytest -q`
- [x] **步骤 5：Commit** `feat: 视频路由接入 Jev cascade（type_router 兜底），human 提升不改写 payload (B2)`

---

### 任务 3：OPENAI base_url 环境变量覆盖（B5 前 401 解耦）

**文件：** 修改 `src/aicomic/providers/openai_adapter.py:18-20`；测试 `tests/test_phase_a_regressions.py` 追加

- [x] **步骤 1：失败测试**（追加到 `tests/test_phase_a_regressions.py`）

```python
class TestOpenAIBaseURLOverride:
    def test_env_overrides_settings(self, monkeypatch):
        from aicomic.providers.openai_adapter import get_openai_base_url
        monkeypatch.setenv("AICOMIC_OPENAI_BASE_URL", "https://new-relay.example.com")
        assert get_openai_base_url({}) == "https://new-relay.example.com"

    def test_settings_used_when_no_env(self, monkeypatch):
        from aicomic.providers.openai_adapter import get_openai_base_url
        monkeypatch.delenv("AICOMIC_OPENAI_BASE_URL", raising=False)
        assert get_openai_base_url({"openai_api": {"base_url": "https://api.old"}}) == "https://api.old"
```

- [x] **步骤 2：实现** — 函数体开头插入：

```python
    env_override = os.environ.get("AICOMIC_OPENAI_BASE_URL", "").strip()
    if env_override:
        return env_override.rstrip("/")
```

- [x] **步骤 3：回归 + Commit** `feat: OPENAI base_url 支持 AICOMIC_OPENAI_BASE_URL env 覆盖（401 换址无需改 yaml）(B5)`

---

### 任务 4：Web 合一 — v5 质量端点挂进 Creator 后端

**文件：** 修改 `web/backend/app.py:72`；新建 `tests/test_phase_b_wiring.py`（追加）

- [x] **步骤 1：失败测试**（追加 `tests/test_phase_b_wiring.py`）

```python
class TestWebUnify:
    def test_creator_health_intact(self):
        from fastapi.testclient import TestClient
        from web.backend.app import app as backend_app

        with TestClient(backend_app) as client:
            assert client.get("/api/health").status_code == 200

    def test_v5_mounted_endpoint_reachable(self):
        from fastapi.testclient import TestClient
        from web.backend.app import app as backend_app

        with TestClient(backend_app) as client:
            resp = client.get("/api/v5/api/health")
            assert resp.status_code == 200
            assert resp.json().get("version")
```

- [x] **步骤 2：实现** — `web/backend/app.py` 在 `app = FastAPI(...)` 与路由注册之间插入：

```python
def _mount_v5_services() -> None:
    """Mount aicomic.web.app (v5 quality/cost/intelligence endpoints) under /api/v5.

    Slot is disabled loudly if the package is unavailable — Creator auth/UX untouched.
    """
    try:
        from aicomic.web.app import create_app as create_v5_app
    except Exception as exc:  # pragma: no cover - optional dependency path
        print(f"[web-unify] v5 services not mounted: {exc}")
        return
    app.mount("/api/v5", create_v5_app())


_mount_v5_services()
```

位置约束：必须在所有 `@app.xx` 注册之前 mount 会导致 404?否：mount 子应用挂在前缀 `/api/v5`，与主 app 路由互不遮蔽，位置不影响。插入到 `app = FastAPI(...)` 之后即可。
- [x] **步骤 3：验证 + 回归** `.venv/bin/python -m pytest tests/test_phase_b_wiring.py tests/test_web_edition_policy.py tests/test_web_settings.py tests/test_auth_service.py -q` 然后 `.venv/bin/python -m pytest -q`
- [x] **步骤 4：Commit** `feat: web/backend mount aicomic.web.app 于 /api/v5（v5 质量端点并入 Creator SPA 可达）(B3)`

---

### 任务 5：缺失模型权重下载（B4 — 联网任务）

**文件：** 新建 `scripts/download_comfy_lock_models.py`；产物到 `local_providers/comfyui_runtime/ComfyUI/models/`

**先决（执行期完成）：** ① 读 `local_providers/comfyui_runtime/model_requirements.json` + `comfyui_locks.build_locked_workflow` 的节点 inputs，校准文件名；② 用 webfetch 验证目标 URL 有效（HEAD）。磁盘已确认 434GiB 可用。

- [x] **步骤 1：写下载脚本**（resume，重定向命名，大小校验）

```python
#!/usr/bin/env python
"""Download Triple-Lock / image-pipeline model weights into the local ComfyUI runtime.

Idempotent: skips files already present and >1MB (resume via curl -C on retry).
Sources are plain HF (no credentials needed for these public artifacts).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MODELS_ROOT = Path("local_providers/comfyui_runtime/ComfyUI/models")

TARGETS: list[tuple[str, str, str]] = [
    # (relative_target, source_url, min_expected_mb)
    ("vae/sdxl_vae.safetensors",
     "https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors",
     100),
    ("controlnet/openpose.safetensors",
     "https://huggingface.co/xinsir6/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
     2000),
    ("ipadapter/ip-adapter-faceid_sdxl.bin",
     "https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid_sdxl.bin",
     800),
    ("clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
     "https://huggingface.co/h94/IP-Adapter/resolve/main/image_encoder/model.safetensors",
     2000),
]


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def download(target: Path, url: str, min_mb: int) -> bool:
    if target.exists() and target.stat().st_size > min_mb * 1024 * 1024:
        print(f"[skip] {target} (already present)")
        return True
    ensure_dir(target)
    cmd = ["curl", "-L", "-C", "-", "--fail", "-o", str(target), url]
    print("[down]", url)
    rc = subprocess.run(cmd).returncode
    if rc != 0 or (target.exists() and target.stat().st_size < min_mb * 1024 * 1024):
        print(f"[FAIL] {target}", file=sys.stderr)
        target.unlink(missing_ok=True)
        return False
    return True


def main() -> int:
    failures = [t for t, u, m in TARGETS if not download(MODELS_ROOT / t, u, m)]
    print("FAILED:" if failures else "ALL OK:", failures or "(none)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **步骤 2：URL 预验证**（webfetch HEAD / HF API），与 `comfyui_locks` 节点 inputs 校准文件名（若 workflow 引用 `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` 以外名，脚本表同步改）。xinsir6 仓库若不提供单文件，改用 ComfyUI 兼容单文件仓库（执行期搜索 adjourn 最终源），记录最终 URL 表。
- [x] **步骤 3：下载**
`python scripts/download_comfy_lock_models.py`（总计约 6-8 GB；带断点续传，可重复执行）
- [x] **步骤 4：probe 对照验证**

```bash
.venv/bin/python -m aicomic.cli.main image-consistency action list-mode 2>/dev/null || true
.venv/bin/python - <<'EOF'
from aicomic.image_consistency.comfyui_locks import probe_lock_models
st = probe_lock_models(model_root="local_providers/comfyui_runtime/ComfyUI/models")
print("all_ready:", st.all_ready)
print("missing:", st.missing)
print("model_files:", st.model_files)
EOF
```

预期：4 个权重从 missing 消失；剩余 missing 只剩"节点类型/未安装 custom_nodes/ComfyUI 不可达"项。结果落 `docs/` 或直接打印（不复制成文件，YAGNI）。
- [x] **步骤 5：Commit** `feat: scripts/download_comfy_lock_models.py 下载 Triple-Lock 缺失权重并实测验证 (B4)`

---

## 收尾检查

- [x] `.venv/bin/python -m pytest -q` 全绿（≥1372 + 新增）
- [x] `.venv/bin/python -m pyflakes src/aicomic/` 零告警
- [x] `git log --oneline` 每任务 1 commit（B1/B2/B3/B5/B4）
- [x] probe 输出对比入执行报告（下载前后 missing 数量）
- [x] 不 push（用户未要求 push）

## 后续待用户（Phase B+ 备忘）

1. 换 401 key（export OPENAI_API_KEY=新key / AICOMIC_OPENAI_BASE_URL=新中转）即激活 openai_image/openai_tts
2. `export KLING_ACCESS_KEY/…` 后 VID 任务可 dry-run → confirm-live 实测
3. ComfyUI 自定义节点安装（IPAdapter_plus、BRIA-RMBG）+ 重启 ComfyUI，才能 node_type 探测全绿
4. 发布平台 cookie 打通（social-auto-upload）
