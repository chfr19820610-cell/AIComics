from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from aicomic.core.edition import EditionCapability, load_edition_capability
from web.backend.settings import WebSettings, load_web_settings


@dataclass(frozen=True)
class EditionPolicy:
    edition_name: str
    display_name: str
    creator_only: bool
    auth_enabled: bool
    batch_enabled: bool
    command_console_enabled: bool
    auth_reason: str
    creator_only_reason: str
    command_console_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_edition_policy(
    settings: WebSettings | None = None,
    edition: EditionCapability | None = None,
) -> EditionPolicy:
    active_settings = settings or load_web_settings()
    active_edition = edition or load_edition_capability()
    auth_enabled = active_settings.auth_enabled and active_edition.auth_enabled

    return EditionPolicy(
        edition_name=active_edition.edition_name,
        display_name=active_edition.display_name,
        creator_only=True,
        auth_enabled=auth_enabled,
        batch_enabled=active_edition.batch_enabled,
        command_console_enabled=True,
        auth_reason=build_auth_reason(active_settings, active_edition, auth_enabled),
        creator_only_reason=build_creator_only_reason(active_edition),
        command_console_reason="",
    )


def build_auth_reason(
    settings: WebSettings,
    edition: EditionCapability,
    enabled: bool,
) -> str:
    if enabled:
        return "个人创作者账号鉴权已启用。"
    if not edition.auth_enabled:
        return f"{edition.display_name} 当前未启用个人账号鉴权。"
    if not settings.auth_enabled:
        return "当前产品版本支持个人账号登录，但 config\\web.yaml 尚未开启 auth.auth_enabled。"
    return "鉴权当前不可用。"


def build_creator_only_reason(edition: EditionCapability) -> str:
    return f"{edition.display_name} 仅保留个人创作、批量生产与复盘链路，企业治理能力已移除。"
