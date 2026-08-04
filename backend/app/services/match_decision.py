from dataclasses import dataclass
from enum import StrEnum

from app.domain import MatchDecision, MatchOrigin, MediaType


class DecisionOutcome(StrEnum):
    ACCEPT = "ACCEPT"
    WARN = "WARN"
    REJECT = "REJECT"


class DecisionSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


@dataclass(frozen=True, slots=True)
class DecisionReason:
    code: str
    message: str
    severity: DecisionSeverity
    overridable: bool
    origin: MatchOrigin

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "overridable": self.overridable,
            "origin": self.origin.value,
        }


@dataclass(frozen=True, slots=True)
class MatchDecisionResult:
    outcome: DecisionOutcome
    decision: MatchDecision
    reasons: tuple[DecisionReason, ...]


def decide_identity_match(
    *,
    origin: MatchOrigin,
    identity_resolved: bool,
    expected_type: MediaType,
    actual_type: MediaType | None,
    has_local_title: bool,
    has_conflict: bool,
    auto_approve_enabled: bool,
) -> MatchDecisionResult:
    if has_conflict:
        return _result(
            DecisionOutcome.REJECT,
            MatchDecision.UNRESOLVED,
            "IDENTITY_CONFLICT",
            "路径与 NFO 指向不同作品，已阻止自动执行。",
            DecisionSeverity.BLOCKING,
            True,
            origin,
        )
    if actual_type is not None and expected_type not in {
        MediaType.UNKNOWN,
        actual_type,
    }:
        return _result(
            DecisionOutcome.REJECT,
            MatchDecision.UNRESOLVED,
            "MEDIA_TYPE_CONFLICT",
            "明确身份对应的媒体类型与扫描结果不一致。",
            DecisionSeverity.BLOCKING,
            True,
            origin,
        )
    if identity_resolved:
        decision = MatchDecision.AUTO_APPROVED if auto_approve_enabled else MatchDecision.REVIEW
        return _result(
            DecisionOutcome.ACCEPT if auto_approve_enabled else DecisionOutcome.WARN,
            decision,
            "EXPLICIT_ID_RESOLVED",
            "明确外部 ID 已解析，媒体类型一致。",
            DecisionSeverity.INFO,
            False,
            origin,
        )
    if has_local_title:
        return _result(
            DecisionOutcome.WARN,
            MatchDecision.REVIEW,
            "LOCAL_METADATA_REVIEW_REQUIRED",
            "NFO 只有本地标题信息，需要人工确认。",
            DecisionSeverity.WARNING,
            True,
            origin,
        )
    return _result(
        DecisionOutcome.REJECT,
        MatchDecision.UNRESOLVED,
        "IDENTITY_NOT_RESOLVED",
        "外部 ID 无法解析，已保留线索供人工处理。",
        DecisionSeverity.BLOCKING,
        True,
        origin,
    )


def _result(
    outcome: DecisionOutcome,
    decision: MatchDecision,
    code: str,
    message: str,
    severity: DecisionSeverity,
    overridable: bool,
    origin: MatchOrigin,
) -> MatchDecisionResult:
    return MatchDecisionResult(
        outcome=outcome,
        decision=decision,
        reasons=(DecisionReason(code, message, severity, overridable, origin),),
    )
