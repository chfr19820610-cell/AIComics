# 🔍 审查报告: 角色一致性系统 Phase 1 MVP

**审查日期:** 2026-07-19  
**审查员:** 审查门禁 — 代码审查 Agent  
**审查类型:** 静态代码审查 + 集成测试验证  

---

## 📋 审查概览

| 维度 | 状态 | 说明 |
|------|------|------|
| 文件完整性 | ✅ 完成 | 7 个源文件 + 1 个测试文件 (595行，36测试) |
| 语法正确性 | ✅ 通过 | 无语法错误，类型标注完整 |
| 测试覆盖率 | ✅ 通过 | 36/36 测试全部通过 (0.18s) |
| 数据库 Schema | ✅ 合理 | 4 表 + 4 索引，外键级联完整 |
| 路由集成 | ✅ 通过 | FastAPI router 已注入 `web/backend/app.py:83-84` |
| 后端启动兼容 | ⚠️ 见下方 | 无运行时测试，但 import 路径兼容 |
| 安全性 | ✅ 良好 | 参数化 SQL，无注入风险 |
| 代码质量 | ✅ 良好 | 清晰的分层架构，类型标注完整 |

---

## 📁 文件清单

| 文件 | 行数 | 功能 |
|------|------|------|
| `src/aicomic/characters/__init__.py` | 1 | 包声明 |
| `src/aicomic/characters/models.py` | 126 | Pydantic 模型 + 内部 dataclass |
| `src/aicomic/characters/database.py` | 257 | SQLite 4-表 Schema + CRUD 操作 |
| `src/aicomic/characters/service.py` | 161 | 业务逻辑层 (CRUD + 搜索) |
| `src/aicomic/characters/script_parser.py` | 160 | 脚本角色解析 + manifest 提取 |
| `src/aicomic/characters/prompt_injector.py` | 176 | Prompt 注入 + 完整性校验 |
| `src/aicomic/characters/routes.py` | 160 | FastAPI 8 端点路由 |
| `tests/test_characters.py` | 595 | 36 个测试用例 (5 个 TestClass) |

---

## 🔴 阻塞项 (必须修复)

无 🔴 阻塞项。

---

## 🟡 建议项 (应该修复)

### 🟡 1. `script_parser.py:73` — 结构不一致：`extract_characters_from_manifest` 与 `extract_characters_with_visuals` 返回不同结构

`extract_characters_from_manifest` 返回 `list[dict[str, str]]`，而 `extract_characters_with_visuals` 返回 `list[dict[str, Any]]`。前者用于 `auto_register_manifest_characters`，后者是独立分析用。虽然功能上没问题，但两个函数处理同一数据源却返回不同的结构，未来维护者可能困惑。

**建议:** 在 docstring 中明确标注两个函数的返回结构差异和各自适用场景。

### 🟡 2. `prompt_injector.py:61` — `build_character_context_block` 每次调用都查询全部项目角色

```python
project_chars = char_service.list_characters(project_id=project_id, limit=200)
```

每次构建 context block 都从数据库加载最多 200 个角色。如果 `enhance_image_prompt` 被高频调用（每个 shot 一次），会产生 N+1 数据库查询开销。

**建议:** 
- 短期: 在 `enhance_image_prompt` 中复用已加载的 `project_chars` 结果
- 长期: 引入内存缓存 (如 `functools.lru_cache` 或 TTL 缓存) 减少重复查询

### 🟡 3. `prompt_injector.py:93-94` — `enhance_image_prompt` 重复查询数据库

`enhance_image_prompt` 内部调用了：
1. `inject_character_descriptions`（需要 `project_chars`）
2. `build_character_context_block`（内部再次调用 `list_characters`）

这意味着 `enhance_image_prompt` 在一次调用中会查询两次数据库（第 93 行 + 第 61 行 → `build_character_context_block` 内部）。

**建议:** 将 `project_chars` 作为参数传入 `build_character_context_block`，避免重复查询。

### 🟡 4. `routes.py:32` — CharacterService 实例在 router 工厂函数内创建

```python
char_service = CharacterService(state_dir=state_dir)
```

`CharacterService.__init__` 直接连接数据库并执行 Schema 迁移。在 FastAPI 启动时调用一次没问题，但如果路由模块被多次 import 或测试时，可能产生多个连接。

**建议:** 考虑将 `CharacterService` 生命周期管理交给 FastAPI 的 `lifespan` 机制或用依赖注入，确保单例单连接。

### 🟡 5. `routes.py:36-37` — `_get_service` 闭包包装器多余

```python
def _get_service() -> CharacterService:
    return char_service
```

`functools.lru_cache` 被 import 但未使用。闭包 `_get_service` 直接返回外层变量，没有抽象价值。每个端点中都调用 `_get_service()` 纯属多余间接层。

**建议:** 直接引用 `char_service` 或移除未使用的 `lru_cache` import。

### 🟡 6. `service.py:42` — 延迟 import 可能产生运行时错误

```python
if state_dir is None:
    from aicomic.core.config import ProjectPaths
    state_dir = ProjectPaths.default_database_path().parent
```

当不传 `state_dir` 时的默认路径依赖于 `aicomic.core.config.ProjectPaths`。该模块是否存在/可导入仅在运行时才知。测试中通过传 `tmp_path` 绕过了，但生产环境中若该模块缺失会导致 500 错误。

**建议:** 在 docstring 或 error message 中明确说明 `state_dir=None` 时的依赖，或使用更稳定的 fallback 路径。

### 🟡 7. `routes.py:107` — Search 路由使用 `{query:path}` 路径参数

```python
@router.get("/search/{query:path}")
```

`{query:path}` 会捕获 `/` 及之后的全部路径，可能产生预料之外的路由行为（例如 `/search/男主/extra` 不会 404 而会被捕获为 `query="男主/extra"`）。

**建议:** 将 `query` 改为 Query 参数：`query: str = Query(default="")`，更符合 RESTful API 惯例，也避免路径冲突。

---

## 💭 小改进 (锦上添花)

### 💭 1. `models.py:125` — `now_utc_iso()` 作为模块级函数而非模型方法

这个工具函数是纯函数，放在 `models.py` 是因为被模型使用。更合适的做法是放在 `utils.py` 或 `database.py` 中，保持关注点分离。

### 💭 2. `database.py:128` — 字段列表硬编码

```python
for field in ("name", "description", "gender", "age_group", "project_id", "reference_prompt"):
```

字段列表在多个地方重复（`ensure_character_schema`、`insert_character`、`update_character`）。建议定义一个 `CHARACTER_FIELDS` 常量元组统一维护。

### 💭 3. `script_parser.py:150-151` — 函数内 import

```python
from aicomic.characters.models import CharacterCreateRequest
```

放在函数内部的 import，虽然 Python 允许，但影响可读性。应该放在文件顶部。

### 💭 4. `models.py:80-93` — `from_row()` 依赖位置索引

`from_row()` 使用 `row[0]`, `row[1]` 等位置索引。如果表结构改变（增删列），该方法会静默返回错误数据。使用 `sqlite3.Row` 的列名访问会更健壮。

**建议:** 将 `from_row` 改为接收 `sqlite3.Row` 而非 `tuple`，用列名访问。

### 💭 5. 测试文件中 `delete_character` 函数重复 import

部分测试在类内额外 import（L228, L234），部分在文件顶部。建议统一在文件顶部 import。

### 💭 6. `prompt_injector.py:71` — Magic number 300 应该定义为常量

```python
if len(desc) > 300:
    desc = desc[:300] + "..."
```

300 字符截断阈值应该是模块级常量 `MAX_CONTEXT_DESC_LENGTH = 300`。

### 💭 7. `service.py:130` — `validate_character_prompt_integrity` 的 `original_length` 参数脆弱

调用方需要手动计算 `original_length` 并传入，容易出错。可考虑在函数内部自动计算。

### 💭 8. 所有文件使用 `from __future__ import annotations` — 好评 ✅

这允许前向引用类型标注，Python 3.11+ 下建议开启。

---

## ✅ 好评要点

1. **分层清晰**: `models` → `database` → `service` → `routes` 分层明确，符合 Clean Architecture 理念
2. **类型标注完整**: 所有函数参数和返回值都有完整类型提示 (Python 3.10+ union syntax)
3. **参数化查询**: 所有 SQL 使用 `?` 占位符，无 SQL 注入风险
4. **Schema 设计合理**: 4 表 + 外键级联删除 + 索引覆盖查询模式
5. **测试覆盖全面**: 36 个测试覆盖数据库、服务、解析器、注入器、模型五个维度
6. **中英文双语注释**: 表字段和 API 描述兼顾中英文，适合国际协作
7. **错误处理完整**: 404/删除不存在/更新不存在的边界情况都正确处理
8. **FastAPI Router 工厂模式**: `build_character_router()` 是工厂函数，便于测试和配置

---

## 📊 测试结果

```
36 passed in 0.18s
```

| Test Class | 测试数 | 覆盖功能 |
|------------|--------|----------|
| `TestCharacterDatabase` | 9 | Schema 创建、插入/查询/更新/删除/列表/标签过滤/项目关联 |
| `TestCharacterService` | 7 | Service CRUD、列表计数、搜索、Response 形状 |
| `TestScriptParser` | 6 | Tag 提取、Manifest 提取、带视觉描述的提取、正则验证 |
| `TestPromptInjector` | 7 | Prompt 注入、Context 块构建、Prompt 增强、Shot 富化、完整性校验 |
| `TestCharacterModels` | 4 | Dict 往返、DB Row 转换、空标签处理、校验 |
| **合计** | **36** | |

---

## 🔗 后端集成验证

`web/backend/app.py` 第 67 行正确导入 `build_character_router`，第 83-84 行完成路由注入：

```python
from aicomic.characters.routes import build_character_router
character_router = build_character_router(state_dir=settings.state_dir)
app.include_router(character_router)
```

路由前缀为 `/api/characters`，不与现有 `/api/creator/*`, `/api/health`, `/api/dashboard` 等端点冲突。

---

## 🎯 总结

**审查结论: PASS** ✅ — 可进入下一阶段

- **0 个阻塞项**
- **7 个建议项** — 主要聚焦在性能优化 (重复 DB 查询) 和路由设计 (search path 参数)
- **8 个小改进** — 代码组织、常量提取、import 位置等

代码质量高于平均水平，架构清晰，测试完善。建议在 Phase 2 开始前优先处理 🟡 #3 (重复查询) 和 🟡 #7 (search 路由) 两个建议项。
