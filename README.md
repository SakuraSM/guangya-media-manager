# 光鸭媒体管家

面向个人 NAS 的单用户影视整理系统。通过第三方 `guangyapan` 包连接光鸭云盘，提供扫码授权、自动续期、递归扫描、规则/AI 识别、TMDB 审核、云内复制、字幕关联、NFO 与图片刮削、媒体库和实时任务看板。

> 光鸭云盘没有公开、稳定的开发者 API。真实云盘能力由独立 `GuangyaProvider` 隔离，接口变化时可单独调整适配器。建议先在 `DEMO_MODE=true` 下完整验收。

## 已实现能力

- 光鸭扫码授权，refresh token 加密落库；API 与 Worker 启动或执行任务前自动续期。
- 任意层级云盘目录浏览，保留完整目录上下文；支持中文季目录、纯数字集名、多季合集、多集文件、日期节目和 `Season 00` 特辑。
- 扫描项按媒体、字幕、附加内容、已有资源、过滤项和未知项分类；支持样片阈值、自定义 glob 排除和人工恢复附加内容。
- 按影视分组优先查询 TMDB，仅在无候选或请求失败时调用 AI 兜底；所有 AI 辅助结果必须人工确认，单组失败原因逐条展示且不中断整个任务。
- 规则解析结果按批次实时落库，TMDB/AI 元数据查询期间即可分页查看已解析记录和“识别中”状态，无需等待整个任务结束。
- TMDB 剧、季、集元数据落库，审核页按“影视 → 季 → 集”展示并支持整组确认。
- 匹配结果使用服务端分页；支持当前页勾选批量批准、整组批准、单文件重新识别、无候选时手动指定 TMDB 匹配、忽略后恢复以及任务安全取消。
- Plex/Jellyfin/TRaSH 兼容的增强 `Movies/TV/Season` 命名，保留可识别的画质、片源、HDR、版本和发布组信息。
- 参考 MoviePilot 的目录级刮削设计：按影视缓存 TMDB 详情，增强 NFO 字段，支持多语言元数据、TMDB 原图、`backdrop/fanart` 别名、季海报双位置和剧集缩略图。
- 源目录零写入；媒体使用 `fs_copy` 云内复制，随后在暂存目录重命名。
- NFO、海报、背景图和季度海报上传；字幕关联并跟随媒体重命名。
- `_整理中/{jobId}` 暂存、任务轮询、幂等操作记录、重复指纹跳过、冲突保留。
- PostgreSQL 数据落库、Redis Worker、SSE 事件、HttpOnly 管理员会话。
- 暗色响应式 Web 控制台：总览、任务、匹配审核、媒体库和设置。

## 架构

```text
React + TypeScript ──> FastAPI ──> PostgreSQL
                           │
                           └──> Redis ──> Python Worker
                                             ├── GuangyaProvider
                                             ├── TMDB
                                             └── OpenAI-compatible AI
```

## Docker Compose 启动

```bash
cp .env.example .env
docker compose up --build
```

API 容器启动时会自动执行 Alembic 增量迁移；已有账号、加密 Token、任务和操作记录会保留。

- Web：<http://localhost:4173>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/healthz>
- 默认管理员密码：`change-me`，部署前务必在 `.env` 中更换。
- 默认仅绑定 `127.0.0.1`；需要从 NAS 局域网访问时，将 `BIND_HOST` 改为 NAS 的内网 IP，并同步调整 `WEB_ORIGIN`。

初次使用保持 `DEMO_MODE=true`。确认页面与流程后，配置以下参数并改为 `false`：

```dotenv
ADMIN_PASSWORD=替换为强密码
BIND_HOST=192.168.1.10
WEB_ORIGIN=http://192.168.1.10:4173
SESSION_SECRET=至少32位随机字符串
TOKEN_ENCRYPTION_KEY=
DEMO_MODE=false
TMDB_API_TOKEN=你的TMDB读取令牌
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=你的AI密钥
AI_MODEL=gpt-4.1-mini
```

`TOKEN_ENCRYPTION_KEY` 留空时会从 `SESSION_SECRET` 派生独立加密密钥；也可填入 Fernet 格式的 32 字节 URL-safe Base64 密钥。系统默认只应暴露在 NAS 内网。

TMDB 同时支持 32 位 v3 API Key 和 v4 API Read Access Token。若任务显示
`TMDB_TIMEOUT` 或 `TMDB_CONNECTION_FAILED`，请先确认 NAS 能正确解析并访问
`api.themoviedb.org`；必要时在 `.env` 中配置 `HTTPS_PROXY` 后重启 API 和 Worker。

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
DEMO_MODE=true DATABASE_URL=sqlite+aiosqlite:///./media_manager.db uvicorn app.main:app --reload
```

前端：

```bash
cd web
npm install
npm run dev
```

## 验证

```bash
cd backend
.venv/bin/ruff check app tests
.venv/bin/mypy app
.venv/bin/pytest -q
```

```bash
cd web
npm run lint
npm test
npm run build
```

当前测试覆盖目录上下文与中英文季集解析、多集编号、样片/附加内容/系统文件过滤、AI 异常回退、字幕命名、非法字符、Token 加密、Provider 复制/移动契约、候选改选、设置密钥不回显，以及“审核 → 暂存复制 → 正式 Movies/TV 目录”的集成流程。

## 安全边界

- 不移动、重命名或删除源目录内容。
- 同名且指纹不同的目标不覆盖，保留在暂存目录并标记部分失败。
- 失败、取消和重复文件均不自动永久删除。
- Token、TMDB Token 和 AI Key 不在 API 响应中回显。
- AI 只接收低置信度文件名与父目录，不上传媒体内容。
- 真实接口属于非官方适配；升级 `guangyapan` 后应先运行 Provider 契约测试。
