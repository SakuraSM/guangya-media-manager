from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import MatchDecision, ProgressStage, ProgressState, SourceClassification
from app.models import MediaMatch, OrganizeJob, SourceItem
from app.providers.base import CloudNode
from app.services.directory_episode_inference import (
    DirectoryEpisodeInference,
    infer_directory_episode_sequences,
)
from app.services.media_parser import (
    ParsedMediaName,
    directory_context_evidence,
    parse_media_filename,
)
from app.services.progress_events import record_job_progress, record_match_progress
from app.services.title_preprocessor import apply_title_extraction

RULE_PARSE_START_PROGRESS = 0.36
RULE_PARSE_COMPLETE_PROGRESS = 0.38
RULE_PARSE_COMMIT_BATCH_SIZE = 5
METADATA_PENDING_REASON = "METADATA_PENDING"


@dataclass(frozen=True, slots=True)
class PendingMediaRecord:
    cloud_node: CloudNode
    parsed: ParsedMediaName
    source_item: SourceItem
    media_match: MediaMatch
    group_key: str


class IncrementalMatchStore:
    def __init__(self, session: AsyncSession, job: OrganizeJob) -> None:
        self._session = session
        self._job = job

    async def persist_rule_results(
        self,
        media_nodes: list[CloudNode],
    ) -> list[PendingMediaRecord]:
        records: list[PendingMediaRecord] = []
        total_items = len(media_nodes)
        inferences = infer_directory_episode_sequences(media_nodes)
        for item_number, cloud_node in enumerate(media_nodes, start=1):
            record = self._build_pending_record(cloud_node, inferences)
            records.append(record)
            self._session.add(record.media_match)
            if _should_commit_rule_batch(item_number, total_items):
                self._update_rule_progress(item_number, total_items)
                for persisted_record in records[-RULE_PARSE_COMMIT_BATCH_SIZE:]:
                    record_match_progress(
                        self._session,
                        self._job,
                        persisted_record.media_match,
                        stage=ProgressStage.IDENTIFY,
                        state=ProgressState.QUEUED,
                        message="规则解析完成，等待元数据识别",
                    )
                await self._session.commit()
        return records

    def _build_pending_record(
        self,
        cloud_node: CloudNode,
        inferences: dict[str, DirectoryEpisodeInference],
    ) -> PendingMediaRecord:
        parent_path = str(PurePosixPath(cloud_node.path).parent)
        inference = inferences.get(parent_path)
        inferred_season_number = (
            inference.season_number
            if inference is not None
            and cloud_node.id in inference.episode_numbers_by_node_id
            else None
        )
        parsed = parse_media_filename(
            cloud_node.name,
            parent_path=parent_path,
            source_root=self._job.source_directory_path,
            inferred_season_number=inferred_season_number,
        )
        title_extraction_regex = self._title_extraction_regex
        parsed = apply_title_extraction(
            parsed,
            cloud_node.name,
            title_extraction_regex,
        )
        group_key = _rule_group_key(parsed, parent_path)
        source_item = SourceItem(
            job_id=self._job.id,
            cloud_file_id=cloud_node.id,
            parent_file_id=cloud_node.parent_id,
            source_path=cloud_node.path,
            filename=cloud_node.name,
            extension=PurePosixPath(cloud_node.name).suffix,
            size_bytes=cloud_node.size_bytes,
            fingerprint=cloud_node.fingerprint,
            relative_path=_relative_path(
                cloud_node.path,
                self._job.source_directory_path,
            ),
            classification=SourceClassification.MEDIA,
            filter_reason="SUPPORTED_MEDIA",
            group_key=group_key,
            is_ignored=parsed.is_ignored,
        )
        decision = MatchDecision.IGNORED if parsed.is_ignored else MatchDecision.UNRESOLVED
        reason_codes = list(parsed.reason_codes)
        if not parsed.is_ignored:
            reason_codes.append(METADATA_PENDING_REASON)
        media_match = MediaMatch(
            source_item=source_item,
            media_type=parsed.media_type,
            parsed_title=parsed.title,
            parsed_year=parsed.year,
            season_number=parsed.season_number,
            episode_numbers=list(parsed.episode_numbers),
            edition=parsed.edition,
            confidence=parsed.confidence,
            decision=decision,
            candidates=[],
            target_path="",
            reason_codes=reason_codes,
            group_key=group_key,
            metadata_hint={
                "directory_context": directory_context_evidence(
                    parent_path,
                    self._job.source_directory_path,
                ),
                **(
                    {
                        "title_extraction": {
                            "pattern": title_extraction_regex,
                            "extracted_title": parsed.title,
                        }
                    }
                    if title_extraction_regex
                    and "CUSTOM_TITLE_EXTRACTED" in parsed.reason_codes
                    else {}
                ),
            },
            episode_date=parsed.episode_date,
            release_info={
                "quality_tags": list(parsed.quality_tags),
                "release_group": parsed.release_group,
                "part_number": parsed.part_number,
            },
        )
        return PendingMediaRecord(
            cloud_node=cloud_node,
            parsed=parsed,
            source_item=source_item,
            media_match=media_match,
            group_key=group_key,
        )

    @property
    def _title_extraction_regex(self) -> str:
        value = self._job.config.get("title_extraction_regex", "")
        return value if isinstance(value, str) else ""

    def _update_rule_progress(
        self,
        parsed_items: int,
        total_items: int,
    ) -> None:
        progress_ratio = parsed_items / total_items if total_items else 1
        progress_span = RULE_PARSE_COMPLETE_PROGRESS - RULE_PARSE_START_PROGRESS
        self._job.progress = RULE_PARSE_START_PROGRESS + progress_span * progress_ratio
        self._job.current_stage = f"规则解析 {parsed_items}/{total_items}"
        record_job_progress(
            self._session,
            self._job,
            stage=ProgressStage.IDENTIFY,
            state=ProgressState.RUNNING,
            completed=parsed_items,
            total=total_items,
            message=self._job.current_stage,
        )


def _should_commit_rule_batch(item_number: int, total_items: int) -> bool:
    return item_number % RULE_PARSE_COMMIT_BATCH_SIZE == 0 or item_number == total_items


def _rule_group_key(parsed: ParsedMediaName, parent_path: str) -> str:
    title = parsed.context_group or parsed.title or PurePosixPath(parent_path).name
    return "|".join(
        (
            parsed.media_type.value,
            title.casefold(),
            str(parsed.year or ""),
        )
    )


def _relative_path(path: str, root_path: str) -> str:
    source_path = PurePosixPath(path)
    try:
        return str(source_path.relative_to(PurePosixPath(root_path)))
    except ValueError:
        return str(source_path)
