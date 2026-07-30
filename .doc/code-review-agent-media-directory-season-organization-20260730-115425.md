# 代码评审报告

- 分支：`agent/media-directory-season-organization`
- 基线：`origin/agent/media-directory-season-organization@ec6afa4`
- 范围：当前工作区相对 `HEAD` 的全部已跟踪与未跟踪改动
- 结论：通过，无未解决的高、中优先级问题

## 本轮确认并修复

1. 整组批准原先逐条提交；中途候选校验失败会造成部分记录已批准。现改为先校验全组，再在单个事务中提交。
2. TMDB 或 AI 返回 HTTP 200 但正文不是 JSON 时，异常可能逃逸并终止整个扫描。现统一转成记录级原因码并继续处理其他分组。
3. 非演示部署未配置 TMDB Token 时仍会返回演示候选。现仅 `DEMO_MODE=true` 时允许演示候选。
4. 刮削任务重试时，失败的 `file_operations` 可能触发唯一键冲突或重复上传。现复用既有操作记录，并优先识别暂存目录中的同名资产。
5. 审核页每 4 秒重复拉取完整扫描项列表，在万级文件任务中会造成明显数据库和网络负载。现只在任务状态切换或人工修改时刷新，匹配记录仍保持 4 秒增量轮询。
6. 分组键包含 `/` 时，整组批准路由可能无法匹配。现使用 path 参数接收编码后的完整分组键。

## 兼容性结论

- `GET /api/jobs/{id}/matches` 从数组升级为分页对象；仓库内 Web 客户端和类型已同步更新。
- TMDB v3 API Key 与 v4 Read Access Token 均支持；生产环境缺失 Token 时不再混入演示数据。
- 源目录仍保持零写入；执行仍采用暂存目录复制、刮削、再提交的流程。
- AI 结果仍强制人工确认，TMDB 成功结果可依据阈值自动通过。

## 验证

- 后端：`61 passed`
- 前端：`10 passed`
- Ruff：通过
- Mypy strict：通过
- ESLint：通过
- TypeScript + Vite production build：通过
- `git diff --check`：通过

## 剩余风险

- 光鸭 Provider 依赖非官方接口，部署后应先使用小目录执行一次真实账号冒烟验证。
- TMDB、AI、海报下载的公网可用性和配额未在本地 CR 中使用真实凭证验证；相关故障已降级为可见原因码或任务警告。
