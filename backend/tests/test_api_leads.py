"""Stage 9: /api/leads REST endpoints — filters + detail + PATCH status."""
import pytest

from app.models.enums import SourceType
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.lead_repository import LeadRepository


async def _seed_lead(
    api_db, search_profile_id: int, score: int, status: str = "new", source_name: str = "Chan"
) -> tuple[int, int]:
    async with api_db() as session:
        source_repo = SourceRepository(session)
        raw_repo = RawItemRepository(session)
        lead_repo = LeadRepository(session)

        source = await source_repo.create(
            name=source_name, type=SourceType.TELEGRAM.value, external_identifier=source_name
        )
        raw_item = await raw_repo.create(
            source_id=source.id,
            external_id=f"ext-{score}-{status}",
            text="Нужен сайт для магазина",
            content_hash=f"hash-{score}-{status}",
            author_username="ivan",
            url="https://t.me/chan/1",
        )
        lead = await lead_repo.create(
            raw_item_id=raw_item.id,
            search_profile_id=search_profile_id,
            is_lead=True,
            lead_score=score,
            status=status,
            services=["web_design"],
            positive_signals=[],
            negative_signals=[],
            summary="Резюме лида",
        )
        await session.commit()
        return lead.id, source.id


@pytest.mark.asyncio
async def test_list_leads_includes_raw_item_context(api_client, api_db, test_search_profile_id):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.get("/api/leads")
    assert resp.status_code == 200
    leads = resp.json()
    assert len(leads) == 1
    assert leads[0]["id"] == lead_id
    assert leads[0]["raw_text"] == "Нужен сайт для магазина"
    assert leads[0]["author_username"] == "ivan"
    assert leads[0]["source_name"] == "Chan"


@pytest.mark.asyncio
async def test_list_leads_filters_by_score_min(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=30, status="new")
    high_id, _ = await _seed_lead(api_db, test_search_profile_id, score=85, status="new")

    resp = await api_client.get("/api/leads", params={"score_min": 60})
    leads = resp.json()
    assert len(leads) == 1
    assert leads[0]["id"] == high_id


@pytest.mark.asyncio
async def test_list_leads_filters_by_status(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=50, status="new")
    converted_id, _ = await _seed_lead(api_db, test_search_profile_id, score=90, status="converted")

    resp = await api_client.get("/api/leads", params={"status": "converted"})
    leads = resp.json()
    assert len(leads) == 1
    assert leads[0]["id"] == converted_id


@pytest.mark.asyncio
async def test_list_leads_filters_by_source_id(api_client, api_db, test_search_profile_id):
    _, source_a = await _seed_lead(api_db, test_search_profile_id, score=50, source_name="A")
    lead_b, source_b = await _seed_lead(api_db, test_search_profile_id, score=60, source_name="B")

    resp = await api_client.get("/api/leads", params={"source_id": source_b})
    leads = resp.json()
    assert len(leads) == 1
    assert leads[0]["id"] == lead_b


@pytest.mark.asyncio
async def test_list_leads_sort_by_score(api_client, api_db, test_search_profile_id):
    low_id, _ = await _seed_lead(api_db, test_search_profile_id, score=20)
    high_id, _ = await _seed_lead(api_db, test_search_profile_id, score=90)

    resp = await api_client.get("/api/leads", params={"sort": "score"})
    leads = resp.json()
    assert leads[0]["id"] == high_id
    assert leads[1]["id"] == low_id


@pytest.mark.asyncio
async def test_get_lead_detail(api_client, api_db, test_search_profile_id):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.get(f"/api/leads/{lead_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lead_id


@pytest.mark.asyncio
async def test_get_missing_lead_404(api_client):
    resp = await api_client.get("/api/leads/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_lead_status(api_client, api_db, test_search_profile_id):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.patch(f"/api/leads/{lead_id}", json={"status": "contacted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "contacted"


@pytest.mark.asyncio
async def test_patch_lead_invalid_status_rejected(api_client, api_db, test_search_profile_id):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.patch(f"/api/leads/{lead_id}", json={"status": "not_a_real_status"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_missing_lead_404(api_client):
    resp = await api_client.patch("/api/leads/9999", json={"status": "contacted"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_explicit_search_profile_id_param(api_client, api_db, test_search_profile_id):
    """Этап 2: /api/leads now accepts an explicit search_profile_id
    instead of always silently picking "the caller's first profile" —
    needed once a user can have more than one."""
    async with api_db() as session:
        from app.models.search_profile import SearchProfile

        second_profile = SearchProfile(user_id=1, name="Second search")
        session.add(second_profile)
        await session.commit()
        second_profile_id = second_profile.id

    await _seed_lead(api_db, test_search_profile_id, score=70)
    await _seed_lead(api_db, second_profile_id, score=95)

    default_resp = await api_client.get("/api/leads")
    assert len(default_resp.json()) == 1
    assert default_resp.json()[0]["lead_score"] == 70

    explicit_resp = await api_client.get(
        "/api/leads", params={"search_profile_id": second_profile_id}
    )
    assert len(explicit_resp.json()) == 1
    assert explicit_resp.json()[0]["lead_score"] == 95


@pytest.mark.asyncio
async def test_search_profile_id_param_rejects_foreign_profile(api_client, api_db):
    async with api_db() as session:
        from app.models.search_profile import SearchProfile
        from app.models.user import User

        other_user = User(email="foreign@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Not yours")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    resp = await api_client.get("/api/leads", params={"search_profile_id": other_profile_id})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_lead_works_for_any_owned_profile_not_just_first(
    api_client, api_db, test_search_profile_id
):
    """Regression check for the multi-profile ownership fix in
    get_lead/update_lead — previously only checked against
    get_first_id_for_user, so a lead under the caller's SECOND profile
    would incorrectly 404."""
    async with api_db() as session:
        from app.models.search_profile import SearchProfile

        second_profile = SearchProfile(user_id=1, name="Second search")
        session.add(second_profile)
        await session.commit()
        second_profile_id = second_profile.id

    lead_id, _ = await _seed_lead(api_db, second_profile_id, score=88)

    resp = await api_client.get(f"/api/leads/{lead_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lead_id


@pytest.mark.asyncio
async def test_feedback_relevant_flips_is_lead_and_records_action(
    api_client, api_db, test_search_profile_id
):
    async with api_db() as session:
        from app.models.enums import SourceType
        from app.repositories.lead_repository import LeadRepository
        from app.repositories.raw_item_repository import RawItemRepository
        from app.repositories.source_repository import SourceRepository

        source = await SourceRepository(session).create(
            name="Chan", type=SourceType.TELEGRAM.value, external_identifier="fb-chan"
        )
        raw_item = await RawItemRepository(session).create(
            source_id=source.id, external_id="fb-1", text="t", content_hash="fb-hash-1"
        )
        lead = await LeadRepository(session).create(
            raw_item_id=raw_item.id,
            search_profile_id=test_search_profile_id,
            is_lead=False,
            lead_score=20,
            services=[],
            positive_signals=[],
            negative_signals=[],
        )
        await session.commit()
        lead_id = lead.id

    resp = await api_client.post(f"/api/leads/{lead_id}/feedback", json={"action": "relevant"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["action"] == "relevant"
    assert body["feedback_type"] == "good"

    lead_resp = await api_client.get(f"/api/leads/{lead_id}")
    assert lead_resp.json()["is_lead"] is True


@pytest.mark.asyncio
async def test_feedback_irrelevant_does_not_touch_is_lead(
    api_client, api_db, test_search_profile_id
):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.post(f"/api/leads/{lead_id}/feedback", json={"action": "irrelevant"})
    assert resp.status_code == 201
    assert resp.json()["feedback_type"] == "not_interesting"

    lead_resp = await api_client.get(f"/api/leads/{lead_id}")
    assert lead_resp.json()["is_lead"] is True  # unchanged — was already True from _seed_lead


@pytest.mark.asyncio
async def test_feedback_rejects_unknown_action(api_client, api_db, test_search_profile_id):
    lead_id, _ = await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.post(f"/api/leads/{lead_id}/feedback", json={"action": "bogus"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_404_for_missing_lead(api_client):
    resp = await api_client.post("/api/leads/9999/feedback", json={"action": "relevant"})
    assert resp.status_code == 404
