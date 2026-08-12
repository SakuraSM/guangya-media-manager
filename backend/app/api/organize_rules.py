from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, Services
from app.domain import JobTriggerType
from app.models import OrganizeRule
from app.schemas import (
    CreateOrganizeRuleRequest,
    JobView,
    OrganizeRuleRunResult,
    OrganizeRuleView,
    UpdateOrganizeRuleRequest,
)
from app.security import require_admin_session
from app.services.organize_rules import OrganizeRuleError

router = APIRouter(
    prefix="/organize-rules",
    tags=["organize-rules"],
    dependencies=[Depends(require_admin_session)],
)


@router.get("", response_model=list[OrganizeRuleView])
async def list_rules(session: DatabaseSession) -> list[OrganizeRule]:
    return list(
        (
            await session.scalars(
                select(OrganizeRule).order_by(OrganizeRule.updated_at.desc())
            )
        ).all()
    )


@router.post("", response_model=OrganizeRuleView, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: CreateOrganizeRuleRequest,
    session: DatabaseSession,
    services: Services,
) -> OrganizeRule:
    try:
        rule = await services.rules.create(request, session)
        if request.run_immediately:
            await services.rules.run(
                rule,
                session,
                trigger=JobTriggerType.MANUAL,
            )
        return rule
    except OrganizeRuleError as error:
        raise _http_error(error) from error


@router.get("/{rule_id}", response_model=OrganizeRuleView)
async def get_rule(rule_id: str, session: DatabaseSession) -> OrganizeRule:
    return await _rule_or_404(session, rule_id)


@router.put("/{rule_id}", response_model=OrganizeRuleView)
async def update_rule(
    rule_id: str,
    request: UpdateOrganizeRuleRequest,
    session: DatabaseSession,
    services: Services,
) -> OrganizeRule:
    rule = await _rule_or_404(session, rule_id)
    try:
        return await services.rules.update(rule, request, session)
    except OrganizeRuleError as error:
        raise _http_error(error) from error


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: str, session: DatabaseSession) -> Response:
    rule = await _rule_or_404(session, rule_id)
    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{rule_id}/run", response_model=OrganizeRuleRunResult)
async def run_rule(
    rule_id: str,
    session: DatabaseSession,
    services: Services,
) -> OrganizeRuleRunResult:
    rule = await _rule_or_404(session, rule_id)
    try:
        job, coalesced = await services.rules.run(
            rule,
            session,
            trigger=JobTriggerType.MANUAL,
        )
    except OrganizeRuleError as error:
        raise _http_error(error) from error
    return OrganizeRuleRunResult(job=JobView.model_validate(job), coalesced=coalesced)


async def _rule_or_404(session: DatabaseSession, rule_id: str) -> OrganizeRule:
    rule = await session.get(OrganizeRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="整理规则不存在")
    return rule


def _http_error(error: OrganizeRuleError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
