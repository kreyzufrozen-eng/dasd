import type {
  AdminOverview,
  AdminSearchProfileDetail,
  AdminUserRead,
  AdminUserUpdate,
  AnalyticsOverview,
  AnalyticsPeriod,
  ChangePasswordPayload,
  Keyword,
  KeywordCreate,
  KeywordUpdate,
  LeadFeedbackCreate,
  LeadFeedbackRead,
  LeadRead,
  LeadWithContextRead,
  LeadsQueryParams,
  ProfileAnalytics,
  ProfileDraft,
  SearchProfileCreate,
  SearchProfileKeywordCreate,
  SearchProfileKeywordRead,
  SearchProfileKeywordUpdate,
  SearchProfileRead,
  SearchProfileSourceCreateCustom,
  SearchProfileSourceRead,
  SearchProfileUpdate,
  Source,
  SourceCatalogEntry,
  LegalDocumentCreate,
  LegalDocumentRead,
  LegalDocumentType,
  SourceCreate,
  SourceUpdate,
  TelegramLoginStartResponse,
  TelegramLoginStatusResponse,
  UsageSummary,
  UserLoginPayload,
  UserRead,
  UserRegisterPayload,
} from './types';

// Base URL for the ReadHunter backend. Inlined at build time from
// NEXT_PUBLIC_API_URL (see next.config.js / Dockerfile for the Docker
// build-time nuance). Falls back to the same default used in
// .env.example so local `next dev` without a .env still works.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...(init?.headers || {}),
    },
    // Sends/receives the httpOnly `access_token` session cookie — required
    // for every auth-gated endpoint now that JWT auth replaced the shared
    // API key for user-owned resources (see backend/app/core/security.py).
    credentials: 'include',
    cache: 'no-store',
  });

  if (!res.ok) {
    // Domain errors use the {"error": {"code", "message"}} envelope (see
    // backend/app/core/exceptions.py). Auth dependencies (get_current_user,
    // get_current_admin_user, verify_api_key) raise a plain FastAPI
    // HTTPException instead, which isn't routed through that handler and
    // comes back as Starlette's default {"detail": "..."} shape — check
    // both rather than falling back to a generic "Forbidden"/"Unauthorized".
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.error?.message) {
        detail = String(body.error.message);
      } else if (body?.detail) {
        detail = String(body.detail);
      }
    } catch {
      // ignore body parse errors, fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

function buildQuery<T extends object>(params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [string, unknown][]) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

// ---- Health ----
export function getHealth(): Promise<{ status: string }> {
  return request('/health');
}

// ---- Auth ----
export function registerUser(data: UserRegisterPayload): Promise<UserRead> {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function loginUser(data: UserLoginPayload): Promise<UserRead> {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function logoutUser(): Promise<void> {
  return request('/api/auth/logout', { method: 'POST' });
}

export function getMe(): Promise<UserRead> {
  return request('/api/auth/me');
}

export function changePassword(data: ChangePasswordPayload): Promise<void> {
  return request('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ---- Telegram login ("Войти через Telegram") ----
export function startTelegramLogin(): Promise<TelegramLoginStartResponse> {
  return request('/api/auth/telegram/start', { method: 'POST' });
}

export function startTelegramLink(): Promise<TelegramLoginStartResponse> {
  return request('/api/auth/telegram/link/start', { method: 'POST' });
}

export function getTelegramLoginStatus(token: string): Promise<TelegramLoginStatusResponse> {
  return request(`/api/auth/telegram/status${buildQuery({ token })}`);
}

export function completeTelegramLogin(
  token: string,
  acceptLegal: boolean = false
): Promise<UserRead> {
  return request('/api/auth/telegram/complete', {
    method: 'POST',
    body: JSON.stringify({ token, accept_legal: acceptLegal }),
  });
}

export function deleteAccount(password: string | undefined): Promise<void> {
  return request('/api/auth/delete-account', {
    method: 'POST',
    body: JSON.stringify({ password, confirm: true }),
  });
}

// Triggers a real browser file download rather than returning parsed JSON —
// the export endpoint sends Content-Disposition: attachment specifically
// so this can save straight to disk instead of just handing back an object.
export async function downloadDataExport(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/auth/export-data`, {
    headers: { 'X-API-Key': API_KEY },
    credentials: 'include',
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new ApiError(res.status, 'Не удалось скачать данные');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'readhunter-export.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---- Leads ----
export function getLeads(
  params: LeadsQueryParams = {}
): Promise<LeadWithContextRead[]> {
  return request(`/api/leads${buildQuery(params)}`);
}

export function getLead(id: number): Promise<LeadWithContextRead> {
  return request(`/api/leads/${id}`);
}

export function updateLeadStatus(
  id: number,
  status: string
): Promise<LeadRead> {
  return request(`/api/leads/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

// ---- Sources ----
export function getSources(): Promise<Source[]> {
  return request('/api/sources');
}

export function createSource(data: SourceCreate): Promise<Source> {
  return request('/api/sources', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSource(
  id: number,
  data: SourceUpdate
): Promise<Source> {
  return request(`/api/sources/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteSource(id: number): Promise<void> {
  return request(`/api/sources/${id}`, { method: 'DELETE' });
}

// ---- Keywords ----
export function getKeywords(category?: string): Promise<Keyword[]> {
  return request(`/api/keywords${buildQuery({ category })}`);
}

export function createKeyword(data: KeywordCreate): Promise<Keyword> {
  return request('/api/keywords', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateKeyword(
  id: number,
  data: KeywordUpdate
): Promise<Keyword> {
  return request(`/api/keywords/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteKeyword(id: number): Promise<void> {
  return request(`/api/keywords/${id}`, { method: 'DELETE' });
}

// ---- Analytics ----
export function getAnalyticsOverview(
  searchProfileId?: number
): Promise<AnalyticsOverview> {
  return request(
    `/api/analytics/overview${buildQuery({ search_profile_id: searchProfileId })}`
  );
}

// ---- Search Profiles ----
export function getSearchProfiles(): Promise<SearchProfileRead[]> {
  return request('/api/search-profiles');
}

export function getSearchProfile(id: number): Promise<SearchProfileRead> {
  return request(`/api/search-profiles/${id}`);
}

export function createSearchProfile(
  data: SearchProfileCreate
): Promise<SearchProfileRead> {
  return request('/api/search-profiles', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSearchProfile(
  id: number,
  data: SearchProfileUpdate
): Promise<SearchProfileRead> {
  return request(`/api/search-profiles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteSearchProfile(id: number): Promise<void> {
  return request(`/api/search-profiles/${id}`, { method: 'DELETE' });
}

export function generateProfileDraft(description: string): Promise<ProfileDraft> {
  return request('/api/search-profiles/generate-draft', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}

export function getProfileAnalytics(
  profileId: number,
  period: AnalyticsPeriod = '7d'
): Promise<ProfileAnalytics> {
  return request(`/api/search-profiles/${profileId}/analytics${buildQuery({ period })}`);
}

// ---- Subscription (read-only plan/usage panel) ----
export function getSubscription(): Promise<UsageSummary> {
  return request('/api/subscription');
}

// ---- Per-profile keywords ----
export function getProfileKeywords(
  profileId: number,
  category?: string
): Promise<SearchProfileKeywordRead[]> {
  return request(`/api/search-profiles/${profileId}/keywords${buildQuery({ category })}`);
}

export function createProfileKeyword(
  profileId: number,
  data: SearchProfileKeywordCreate
): Promise<SearchProfileKeywordRead> {
  return request(`/api/search-profiles/${profileId}/keywords`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateProfileKeyword(
  profileId: number,
  keywordId: number,
  data: SearchProfileKeywordUpdate
): Promise<SearchProfileKeywordRead> {
  return request(`/api/search-profiles/${profileId}/keywords/${keywordId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deleteProfileKeyword(
  profileId: number,
  keywordId: number
): Promise<void> {
  return request(`/api/search-profiles/${profileId}/keywords/${keywordId}`, {
    method: 'DELETE',
  });
}

// ---- Per-profile sources ----
export function getProfileSources(
  profileId: number
): Promise<SearchProfileSourceRead[]> {
  return request(`/api/search-profiles/${profileId}/sources`);
}

export function attachProfileSource(
  profileId: number,
  sourceId: number,
  enabled = true
): Promise<SearchProfileSourceRead> {
  return request(`/api/search-profiles/${profileId}/sources`, {
    method: 'POST',
    body: JSON.stringify({ source_id: sourceId, enabled }),
  });
}

export function bulkAttachProfileSources(
  profileId: number,
  sourceIds: number[]
): Promise<{ attached: number }> {
  return request(`/api/search-profiles/${profileId}/sources/bulk`, {
    method: 'POST',
    body: JSON.stringify({ source_ids: sourceIds }),
  });
}

export function addCustomProfileSource(
  profileId: number,
  data: SearchProfileSourceCreateCustom
): Promise<SearchProfileSourceRead> {
  return request(`/api/search-profiles/${profileId}/sources/custom`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateProfileSource(
  profileId: number,
  sourceId: number,
  enabled: boolean
): Promise<SearchProfileSourceRead> {
  return request(`/api/search-profiles/${profileId}/sources/${sourceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  });
}

export function detachProfileSource(
  profileId: number,
  sourceId: number
): Promise<void> {
  return request(`/api/search-profiles/${profileId}/sources/${sourceId}`, {
    method: 'DELETE',
  });
}

export function getSourceCatalog(
  searchProfileId?: number,
  category?: string
): Promise<SourceCatalogEntry[]> {
  return request(
    `/api/sources/catalog${buildQuery({ search_profile_id: searchProfileId, category })}`
  );
}

// ---- Lead feedback ----
export function submitLeadFeedback(
  leadId: number,
  data: LeadFeedbackCreate
): Promise<LeadFeedbackRead> {
  return request(`/api/leads/${leadId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ---- Admin ----
export function getAdminOverview(): Promise<AdminOverview> {
  return request('/api/admin/overview');
}

export function getAdminUsers(): Promise<AdminUserRead[]> {
  return request('/api/admin/users');
}

export function updateAdminUser(
  id: number,
  data: AdminUserUpdate
): Promise<AdminUserRead> {
  return request(`/api/admin/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function getAdminUserProfiles(userId: number): Promise<AdminSearchProfileDetail[]> {
  return request(`/api/admin/users/${userId}/profiles`);
}

// ---- Legal documents (public) ----
export function getActiveLegalDocument(type: LegalDocumentType): Promise<LegalDocumentRead> {
  return request(`/api/legal/${type}`);
}

// ---- Legal documents (admin) ----
export function getAdminLegalDocuments(type: LegalDocumentType): Promise<LegalDocumentRead[]> {
  return request(`/api/admin/legal/${type}`);
}

export function createLegalDocument(data: LegalDocumentCreate): Promise<LegalDocumentRead> {
  return request('/api/admin/legal', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function publishLegalDocument(id: number): Promise<LegalDocumentRead> {
  return request(`/api/admin/legal/${id}/publish`, { method: 'POST' });
}

export { ApiError };
