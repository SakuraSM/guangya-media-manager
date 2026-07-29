from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AccountStatus, JobStatus, MatchDecision, MediaType
from app.models import (
    AuditEvent,
    CloudAccount,
    MediaEntity,
    MediaMatch,
    OrganizeJob,
    SourceItem,
)
from app.providers.demo import DEMO_CAPACITY_BYTES, DEMO_USED_BYTES


async def seed_demo_data(session: AsyncSession) -> None:
    account_count = await session.scalar(select(func.count()).select_from(CloudAccount))
    if not account_count:
        session.add(
            CloudAccount(
                display_name="光鸭账号 · duck****@gmail.com",
                status=AccountStatus.CONNECTED,
                capacity_bytes=DEMO_CAPACITY_BYTES,
                used_bytes=DEMO_USED_BYTES,
            )
        )

    job_count = await session.scalar(select(func.count()).select_from(OrganizeJob))
    if not job_count:
        active_job = OrganizeJob(
            name="电影与剧集 · 首次整理",
            source_directory_id="source",
            source_directory_path="/光鸭云盘/未整理",
            target_directory_id="target",
            target_directory_path="/光鸭云盘/电影与剧集",
            status=JobStatus.REVIEW_REQUIRED,
            progress=0.68,
            current_stage="匹配审核",
            total_items=5,
            approved_items=2,
            review_items=2,
            failed_items=1,
            copied_bytes=412 * 1024**3,
            config={
                "generate_nfo": True,
                "download_poster": True,
                "download_fanart": True,
                "download_season_poster": True,
                "rename_subtitles": True,
                "auto_approve_threshold": 0.9,
                "review_threshold": 0.65,
            },
        )
        completed_job = OrganizeJob(
            name="科幻电影整理",
            source_directory_id="movies",
            source_directory_path="/光鸭云盘/未整理/电影",
            target_directory_id="target",
            target_directory_path="/光鸭云盘/电影与剧集",
            status=JobStatus.COMPLETED,
            progress=1,
            current_stage="整理完成",
            total_items=38,
            approved_items=38,
            review_items=0,
            failed_items=0,
            copied_bytes=412 * 1024**3,
            config={},
            created_at=datetime.now(UTC) - timedelta(hours=5),
            updated_at=datetime.now(UTC) - timedelta(hours=2),
        )
        session.add_all([active_job, completed_job])
        await session.flush()
        demo_matches = [
            (
                "Interstellar.2014.2160p.BluRay.REMUX.HEVC.mkv",
                "星际穿越",
                "Interstellar",
                2014,
                MediaType.MOVIE,
                0.98,
                MatchDecision.AUTO_APPROVED,
                "Movies/星际穿越 (2014)/星际穿越 (2014) - REMUX 2160p.mkv",
                "/posters/interstellar.png",
            ),
            (
                "Breaking.Bad.S01E03.1080p.WEB-DL.mkv",
                "绝命毒师",
                "Breaking Bad",
                2008,
                MediaType.TV,
                0.95,
                MatchDecision.AUTO_APPROVED,
                "TV/绝命毒师 (2008)/Season 01/绝命毒师 (2008) - S01E03.mkv",
                "/posters/breaking-bad.png",
            ),
            (
                "三体.Three.Body.2023.E03.2160p.WEB-DL.mkv",
                "三体",
                "Three-Body",
                2023,
                MediaType.TV,
                0.61,
                MatchDecision.REVIEW,
                "TV/三体 (2023)/Season 01/三体 (2023) - S01E03.mkv",
                "/posters/three-body.png",
            ),
            (
                "Unknown.Title.2022.1080p.mkv",
                "未知之影",
                "Unknown Title",
                2022,
                MediaType.MOVIE,
                0.42,
                MatchDecision.UNRESOLVED,
                "",
                "/posters/unknown.png",
            ),
        ]
        cloud_ids_by_filename = {
            "Interstellar.2014.2160p.BluRay.REMUX.HEVC.mkv": "interstellar",
            "Breaking.Bad.S01E03.1080p.WEB-DL.mkv": "breaking-bad",
            "三体.Three.Body.2023.E03.2160p.WEB-DL.mkv": "three-body",
            "Unknown.Title.2022.1080p.mkv": "unknown",
        }
        for item_index, demo_match in enumerate(demo_matches, start=1):
            (
                filename,
                title,
                original_title,
                year,
                media_type,
                confidence,
                decision,
                target_path,
                poster_url,
            ) = demo_match
            source_item = SourceItem(
                job_id=active_job.id,
                cloud_file_id=cloud_ids_by_filename[filename],
                parent_file_id="source",
                source_path=f"/光鸭云盘/未整理/{filename}",
                filename=filename,
                extension=".mkv",
                size_bytes=(8 + item_index * 5) * 1024**3,
                fingerprint=f"demo-{item_index}",
            )
            entity = MediaEntity(
                tmdb_id=1000 + item_index,
                media_type=media_type,
                title=title,
                original_title=original_title,
                year=year,
                poster_url=poster_url,
                overview="演示影视元数据，用于展示审核工作流。",
            )
            session.add_all([source_item, entity])
            await session.flush()
            candidates = [
                {
                    "tmdb_id": entity.tmdb_id,
                    "title": title,
                    "original_title": original_title,
                    "year": year,
                    "media_type": media_type.value,
                    "score": confidence,
                    "poster_url": poster_url,
                    "overview": entity.overview,
                }
            ]
            if title == "三体":
                candidates.extend(
                    [
                        {
                            "tmdb_id": 2042,
                            "title": "三体",
                            "original_title": "3 Body Problem",
                            "year": 2024,
                            "media_type": MediaType.TV.value,
                            "score": 0.38,
                            "poster_url": "/posters/three-body-alt.png",
                            "overview": "另一候选版本。",
                        },
                        {
                            "tmdb_id": 2043,
                            "title": "三体：锋刃",
                            "original_title": "Three Body: Swordholder",
                            "year": 2023,
                            "media_type": MediaType.TV.value,
                            "score": 0.22,
                            "poster_url": "/posters/unknown.png",
                            "overview": "低置信度候选。",
                        },
                    ]
                )
            session.add(
                MediaMatch(
                    source_item_id=source_item.id,
                    media_entity_id=entity.id,
                    media_type=media_type,
                    parsed_title=original_title,
                    parsed_year=year,
                    season_number=1 if media_type == MediaType.TV else None,
                    episode_numbers=[3] if media_type == MediaType.TV else [],
                    edition="2160p" if item_index in {1, 3} else "1080p",
                    confidence=confidence,
                    decision=decision,
                    candidates=candidates,
                    target_path=target_path,
                    reason_codes=["TITLE_PARSED", "YEAR_PARSED"],
                )
            )
        session.add_all(
            [
                AuditEvent(
                    job_id=active_job.id,
                    event_type="SCAN_COMPLETED",
                    message="扫描完成，共发现 5 个视频文件",
                    created_at=datetime.now(UTC) - timedelta(minutes=21),
                ),
                AuditEvent(
                    job_id=active_job.id,
                    event_type="IDENTIFY_COMPLETED",
                    message="AI 识别完成，2 个文件需要人工审核",
                    created_at=datetime.now(UTC) - timedelta(minutes=14),
                ),
                AuditEvent(
                    job_id=completed_job.id,
                    event_type="JOB_COMPLETED",
                    message="科幻电影整理完成，源目录未修改",
                    created_at=datetime.now(UTC) - timedelta(hours=2),
                ),
            ]
        )
    await session.commit()
