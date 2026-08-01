import { MATCH_DECISION, type MediaMatch } from '../types'

const REASON_MESSAGES: Readonly<Record<string, string>> = {
  METADATA_PENDING: '正在查询 TMDB/AI 元数据。',
  TMDB_FAILED: 'TMDB 请求失败，请检查网络或 API Token。',
  TMDB_TIMEOUT: '连接 TMDB 超时，请检查 NAS 的网络、DNS 或代理设置。',
  TMDB_CONNECTION_FAILED: '无法连接 TMDB，请检查 NAS 的 DNS 和网络出口。',
  TMDB_AUTH_FAILED: 'TMDB 鉴权失败，请检查 API Key 或读取访问令牌。',
  TMDB_RATE_LIMITED: 'TMDB 请求触发限流，请稍后重试。',
  TMDB_HTTP_FAILED: 'TMDB 返回服务错误，请稍后重试。',
  TMDB_INVALID_RESPONSE: 'TMDB 返回了无法解析的数据，请稍后重试。',
  TMDB_NO_RESULTS: 'TMDB 未找到匹配结果，已尝试 AI 兜底识别。',
  AI_NOT_CONFIGURED: 'AI 未配置，无法执行兜底识别。',
  AI_INVALID_RESPONSE: 'AI 返回内容格式无效，无法采用识别结果。',
  AI_REQUEST_FAILED: 'AI 识别请求失败，已保留规则解析结果。',
  TMDB_AI_QUERY_FAILED: 'AI 辅助识别后，再次查询 TMDB 失败。',
  TMDB_AI_QUERY_NO_RESULTS: 'AI 辅助识别后，TMDB 仍未找到候选。',
  AI_MANUAL_CONFIRMATION_REQUIRED: '此候选由 AI 辅助识别，必须人工确认。',
  AI_REVIEW_RETAINED: 'AI 无法确认作品名称和类型一致，已保留人工审核。',
  AI_REVIEW_NO_CANDIDATE: '当前影视分组没有可供 AI 审核的 TMDB 候选。',
  AI_REVIEW_GROUP_CANDIDATE_MISSING: '该文件缺少整组采用的 TMDB 候选，未自动批准。',
}

export function isMetadataPending(mediaMatch: MediaMatch): boolean {
  return mediaMatch.reason_codes.includes('METADATA_PENDING')
}

export function matchRecognitionMessages(mediaMatch: MediaMatch): string[] {
  const messages = mediaMatch.reason_codes.flatMap((reasonCode) => {
    const message = REASON_MESSAGES[reasonCode]
    return message ? [message] : []
  })
  if (
    messages.length === 0 &&
    (mediaMatch.decision === MATCH_DECISION.UNRESOLVED ||
      mediaMatch.candidates.length === 0)
  ) {
    messages.push('未找到可用的 TMDB 候选，请重试或手动匹配。')
  }
  return [...new Set(messages)]
}
