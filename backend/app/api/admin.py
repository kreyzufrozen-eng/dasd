"""REST API: /api/admin — system-wide overview + user management.

Every route requires get_current_admin_user (is_admin=True on the JWT
session's User) — there is no separate "admin login": the existing
account system already has an is_admin flag (see app/models/user.py),
and migration 0004 set it on the legacy account. Adding a second,
parallel admin-auth system would just fragment the one that already
works.
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInputError, NotFoundError
from app.core.security import get_current_admin_user
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.admin_schemas import (
    AdminOverview,
    AdminProfileKeywordRead,
    AdminProfileSourceRead,
    AdminSearchProfileDetail,
    AdminUserRead,
    AdminUserUpdate,
)
from app.services.admin_stats import AdminStatsService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOverview:
    stats = await AdminStatsService(db).get_overview()
    return AdminOverview(
        total_users=stats.total_users,
        total_search_profiles=stats.total_search_profiles,
        total_sources=stats.total_sources,
        active_sources=stats.active_sources,
        total_keywords=stats.total_keywords,
        total_raw_items=stats.total_raw_items,
        total_leads=stats.total_leads,
        leads_today=stats.leads_today,
        database_status="ok",
    )


@router.get("/users", response_model=List[AdminUserRead])
async def admin_list_users(
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[AdminUserRead]:
    rows = await AdminStatsService(db).get_users_with_stats()
    return [
        AdminUserRead(
            id=row.user.id,
            email=row.user.email,
            telegram_username=row.user.telegram_username,
            name=row.user.name,
            is_admin=row.user.is_admin,
            is_active=row.user.is_active,
            created_at=row.user.created_at,
            last_login_at=row.last_login_at,
            search_profile_count=row.search_profile_count,
            lead_count=row.lead_count,
        )
        for row in rows
    ]


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserRead:
    user_repo = UserRepository(db)
    target = await user_repo.get(user_id)
    if target is None:
        raise NotFoundError("User not found")

    update_data = payload.model_dump(exclude_unset=True)
    if target.id == admin.id and (
        update_data.get("is_admin") is False or update_data.get("is_active") is False
    ):
        # A lone admin locking themselves out has no recovery path short of
        # a manual DB edit — refuse rather than let that happen by mistake.
        raise InvalidInputError("You cannot remove your own admin access or deactivate yourself")

    updated = await user_repo.update(target, **update_data)
    await db.commit()

    stats_by_user = {row.user.id: row for row in await AdminStatsService(db).get_users_with_stats()}
    row = stats_by_user[updated.id]
    return AdminUserRead(
        id=row.user.id,
        email=row.user.email,
        telegram_username=row.user.telegram_username,
        name=row.user.name,
        is_admin=row.user.is_admin,
        is_active=row.user.is_active,
        created_at=row.user.created_at,
        last_login_at=row.last_login_at,
        search_profile_count=row.search_profile_count,
        lead_count=row.lead_count,
    )


@router.get("/users/{user_id}/profiles", response_model=List[AdminSearchProfileDetail])
async def admin_get_user_profiles(
    user_id: int,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[AdminSearchProfileDetail]:
    target = await UserRepository(db).get(user_id)
    if target is None:
        raise NotFoundError("User not found")

    profiles = await AdminStatsService(db).get_user_profiles_detailed(user_id)
    return [
        AdminSearchProfileDetail(
            id=p.id,
            name=p.name,
            profession=p.profession,
            profession_description=p.profession_description,
            services=p.services,
            target_clients=p.target_clients,
            preferred_niches=p.preferred_niches,
            excluded_niches=p.excluded_niches,
            geography=p.geography,
            is_active=p.is_active,
            created_at=p.created_at,
            sources=[
                AdminProfileSourceRead(
                    id=link.source.id,
                    name=link.source.name,
                    type=link.source.type,
                    url=link.source.url,
                    enabled=link.enabled,
                    is_custom=link.source.added_by_user_id is not None,
                )
                for link in p.source_links
            ],
            keywords=[
                AdminProfileKeywordRead(text=kl.text, category=kl.category, enabled=kl.enabled)
                for kl in p.keyword_links
            ],
        )
        for p in profiles
    ]
