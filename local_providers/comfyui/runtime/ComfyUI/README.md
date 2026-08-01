# ComfyUI Runtime 占位

本目录用于放置 ComfyUI 运行时（含 SDXL 模型），供
`Dockerfile.comfyui-sidecar` 构建 sidecar 镜像使用。

- 镜像会执行 `COPY local_providers/comfyui/runtime/ComfyUI /opt/comfyui`，
  并把 `/opt/comfyui/requirements.txt` 装进 sidecar。
- 骨架保留为空时 sidecar 镜像仍可构建，但 ComfyUI 推理不可用（stub）。
- 若要启用真实推理，把完整 ComfyUI runtime 放到本目录后重建：
  ```bash
  docker compose -f docker-compose.local-providers.yml build aicomic-comfyui
  ```
- 目录结构（仅提交骨架，重资产被 .gitignore/.dockerignore 排除）：
  ```
  local_providers/
  ├── comfyui/runtime/ComfyUI/   ← 真实 ComfyUI（COPY 源）
  ├── comfyui/models/            ← SDXL 模型
  └── piper/                     ← Piper TTS 运行时/模型
  ```
