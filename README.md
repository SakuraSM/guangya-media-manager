# 光鸭媒体管家

面向个人 NAS 的单用户影视整理系统。通过第三方 `guangyapan` 包连接光鸭云盘，提供扫码授权、自动续期、递归扫描、规则/AI 识别、TMDB 审核、云内复制、字幕关联、NFO 与图片刮削、媒体库和实时任务看板。

> 光鸭云盘没有公开、稳定的开发者 API。真实云盘能力由独立 `GuangyaProvider` 隔离，接口变化时可单独调整适配器。建议先在 `DEMO_MODE=true` 下完整验收。

## 已实现能力

- 光鸭扫码授权，refresh token 加密落库；API 与 Worker 启动或执行任务前自动续期。
- 任意层级云盘目录浏览，递归扫描视频和字幕；样片、预告片等默认忽略。
- 影视文件名解析、AI 结构化兜底、TMDB 候选评分及人工改选。
- Plex/Jellyfin 通用的 `Movies/TV/Season` 命名与目录结构。
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

当前测试覆盖文件名解析、多集编号、字幕命名、非法字符、Token 加密、Provider 复制/移动契约、候选改选、设置密钥不回显，以及“审核 → 暂存复制 → 正式 Movies/TV 目录”的集成流程。

## 安全边界

- 不移动、重命名或删除源目录内容。
- 同名且指纹不同的目标不覆盖，保留在暂存目录并标记部分失败。
- 失败、取消和重复文件均不自动永久删除。
- Token、TMDB Token 和 AI Key 不在 API 响应中回显。
- AI 只接收低置信度文件名与父目录，不上传媒体内容。
- 真实接口属于非官方适配；升级 `guangyapan` 后应先运行 Provider 契约测试。
