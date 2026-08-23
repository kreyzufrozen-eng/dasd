// Types mirroring the ReadHunter backend API contract (FastAPI / Pydantic
// schemas). Keep these in sync with backend/app if the API ever changes.

export type LeadStatus =
  | 'new'
  | 'viewed'
  | 'contacted'
  | 'interested'
  | 'negotiation'
  | 'converted'
  | 'rejected'
  | 'archived';

export const LEAD_STATUSES: LeadStatus[] = [
  'new',
  'viewed',
  'contacted',
  'interested',
  'negotiation',
  'converted',
  'rejected',
  'archived',
];

export type SourceType = 'telegram' | 'api' | 'freelance' | 'website';

export const SOURCE_TYPES: SourceType[] = ['telegram', 'api', 'freelance', 'website'];

export type KeywordCategory =
  | 'direct_intent'
  | 'service'
  | 'project_type'
  | 'problem'
  | 'technology'
  | 'hidden_intent'
  | 'exclusion';

export const KEYWORD_CATEGORIES: KeywordCategory[] = [
  'direct_intent',
  'service',
  'project_type',
  'problem',
  'technology',
  'hidden_intent',
  'exclusion',
];

export interface LeadRead {
  id: number;
  raw_item_id: number;
  is_lead: boolean;
  lead_probability: number;
  lead_score: number;
  lead_type: string | null;
  services: string[];
  business_niche: string | null;
  project_description: string | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  urgency: string | null;
  complexity: string | null;
  estimated_value: string | null;
  summary: string | null;
  reasoning: string | null;
  positive_signals: string[];
  negative_signals: string[];
  intent_score: number;
  intent_signals: string[];
  status: LeadStatus;
  created_at: string;
  updated_at: string;
}

export interface LeadWithContextRead extends LeadRead {
  raw_text: string | null;
  raw_url: string | null;
  author_name: string | null;
  author_username: string | null;
  source_id: number | null;
  source_name: string | null;
}

export interface LeadsQueryParams {
  search_profile_id?: number;
  score_min?: number;
  score_max?: number;
  intent_score_min?: number;
  status?: LeadStatus | '';
  source_id?: number;
  lead_type?: string;
  is_lead?: boolean;
  date_from?: string;
  date_to?: string;
  sort?: 'newest' | 'score' | 'intent';
  limit?: number;
  offset?: number;
}

export interface Source {
  id: number;
  name: string;
  type: SourceType;
  url: string | null;
  external_identifier: string | null;
  is_active: boolean;
  category: string | null;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
  lead_count: number;
}

export interface SourceCreate {
  name: string;
  type: SourceType;
  url?: string;
  external_identifier?: string;
  category?: string;
  is_active?: boolean;
}

export interface SourceUpdate {
  name?: string;
  url?: string;
  external_identifier?: string;
  category?: string;
  is_active?: boolean;
}

export interface SourceCatalogEntry {
  id: number;
  name: string;
  type: SourceType;
  url: string | null;
  external_identifier: string | null;
  is_active: boolean;
  category: string | null;
  already_added: boolean;
  enabled_for_profile: boolean;
}

export interface Keyword {
  id: number;
  keyword: string;
  category: KeywordCategory;
  weight: number;
  is_active: boolean;
  created_at: string;
}

export interface KeywordCreate {
  keyword: string;
  category: KeywordCategory;
  weight?: number;
  is_active?: boolean;
}

export interface KeywordUpdate {
  keyword?: string;
  category?: KeywordCategory;
  weight?: number;
  is_active?: boolean;
}

export interface AnalyticsPoint {
  date: string;
  count: number;
}

export interface AnalyticsOverview {
  total_leads: number;
  today_leads: number;
  hot_leads: number;
  converted_leads: number;
  hidden_demand_leads: number;
  active_sources: number;
  avg_match_score: number;
  leads_last_7_days: AnalyticsPoint[];
  leads_last_30_days: AnalyticsPoint[];
}

export type AnalyticsPeriod = 'today' | '7d' | '30d' | 'all';

export interface FunnelStats {
  candidates: number;
  leads: number;
  hot_leads: number;
}

export interface SourceStat {
  source_id: number;
  source_name: string;
  lead_count: number;
}

export interface NicheStat {
  niche: string;
  lead_count: number;
}

export interface UsageSummary {
  plan_name: string;
  max_search_profiles: number;
  max_sources_per_profile: number;
  max_ai_analyses_per_month: number;
  price: number | null;
  currency: string;
  search_profiles_used: number;
  ai_analyses_used_this_period: number;
  period_start: string;
}

export interface ProfileAnalytics {
  period: AnalyticsPeriod;
  funnel: FunnelStats;
  avg_match_score: number;
  avg_budget: number | null;
  budget_currency: string | null;
  top_sources: SourceStat[];
  top_niches: NicheStat[];
  leads_by_day: AnalyticsPoint[];
}

// ---- Auth ----
export interface UserRead {
  id: number;
  // Nullable — a Telegram-only account has no email. Use has_password/
  // has_telegram to decide what Settings offers, not these fields' presence.
  email: string | null;
  telegram_username: string | null;
  name: string | null;
  is_admin: boolean;
  created_at: string;
  has_password: boolean;
  has_telegram: boolean;
}

export interface UserRegisterPayload {
  email: string;
  password: string;
  name?: string;
  accept_legal: boolean;
}

// ---- Telegram login ("Войти через Telegram") ----
export interface TelegramLoginStartResponse {
  token: string;
  deep_link: string;
  expires_at: string;
}

export type TelegramLoginStatus = 'pending' | 'confirmed' | 'consumed' | 'expired';

export interface TelegramLoginStatusResponse {
  status: TelegramLoginStatus;
}

export interface UserLoginPayload {
  email: string;
  password: string;
}

export interface ChangePasswordPayload {
  // Omit/undefined only when setting a first password on a Telegram-only
  // account that has none yet.
  current_password?: string;
  new_password: string;
}

// ---- Admin ----
export interface AdminOverview {
  total_users: number;
  total_search_profiles: number;
  total_sources: number;
  active_sources: number;
  total_keywords: number;
  total_raw_items: number;
  total_leads: number;
  leads_today: number;
  database_status: string;
}

export interface AdminUserRead {
  id: number;
  email: string | null;
  telegram_username: string | null;
  name: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  search_profile_count: number;
  lead_count: number;
}

export interface AdminProfileSourceRead {
  id: number;
  name: string;
  type: string;
  url: string | null;
  enabled: boolean;
  is_custom: boolean;
}

export interface AdminProfileKeywordRead {
  text: string;
  category: string;
  enabled: boolean;
}

export interface AdminSearchProfileDetail {
  id: number;
  name: string;
  profession: string | null;
  profession_description: string | null;
  services: string[];
  target_clients: string | null;
  preferred_niches: string[];
  excluded_niches: string[];
  geography: string | null;
  is_active: boolean;
  created_at: string;
  sources: AdminProfileSourceRead[];
  keywords: AdminProfileKeywordRead[];
}

export interface AdminUserUpdate {
  is_admin?: boolean;
  is_active?: boolean;
}

// ---- Search Profiles ----
export interface SearchProfileRead {
  id: number;
  user_id: number;
  name: string;
  profession: string | null;
  profession_description: string | null;
  services: string[];
  skills: string[];
  technologies: string[];
  target_clients: string | null;
  preferred_niches: string[];
  excluded_niches: string[];
  min_budget: number | null;
  max_budget: number | null;
  currency: string;
  geography: string | null;
  languages: string[];
  lead_types: string[];
  notification_threshold: number;
  is_active: boolean;
  ai_profile_context: string | null;
  created_at: string;
  updated_at: string;
}

export interface SearchProfileKeywordCreate {
  text: string;
  category: KeywordCategory;
  weight?: number;
  enabled?: boolean;
}

export interface SearchProfileCreate {
  name: string;
  profession?: string;
  profession_description?: string;
  services?: string[];
  skills?: string[];
  technologies?: string[];
  target_clients?: string;
  preferred_niches?: string[];
  excluded_niches?: string[];
  min_budget?: number | null;
  max_budget?: number | null;
  currency?: string;
  geography?: string;
  languages?: string[];
  lead_types?: string[];
  notification_threshold?: number;
  is_active?: boolean;
  ai_profile_context?: string;
  keywords?: SearchProfileKeywordCreate[];
}

export interface SearchProfileUpdate {
  name?: string;
  profession?: string;
  profession_description?: string;
  services?: string[];
  skills?: string[];
  technologies?: string[];
  target_clients?: string;
  preferred_niches?: string[];
  excluded_niches?: string[];
  min_budget?: number | null;
  max_budget?: number | null;
  currency?: string;
  geography?: string;
  languages?: string[];
  lead_types?: string[];
  notification_threshold?: number;
  is_active?: boolean;
  ai_profile_context?: string;
}

// ---- Onboarding: AI profile draft ----
export interface SuggestedKeyword {
  text: string;
  category: KeywordCategory;
  weight: number;
}

export interface ProfileDraft {
  profession: string;
  services: string[];
  suggested_orders: string[];
  suggested_exclusions: string[];
  suggested_keywords: SuggestedKeyword[];
  ai_profile_context: string;
  summary_direct: string;
  summary_potential: string;
  summary_hidden: string;
  summary_excluded: string;
}

// ---- Per-profile keywords ----
export interface SearchProfileKeywordRead {
  id: number;
  search_profile_id: number;
  keyword_id: number | null;
  text: string;
  category: KeywordCategory;
  weight: number;
  enabled: boolean;
  created_at: string;
}

export interface SearchProfileKeywordUpdate {
  text?: string;
  category?: KeywordCategory;
  weight?: number;
  enabled?: boolean;
}

// ---- Per-profile sources ----
export interface SearchProfileSourceRead {
  id: number;
  search_profile_id: number;
  source_id: number;
  enabled: boolean;
  source: Source;
}

export interface SearchProfileSourceCreateCustom {
  name: string;
  type: SourceType;
  url?: string;
  external_identifier?: string;
}

// ---- Lead feedback ----
export type LeadFeedbackAction = 'relevant' | 'irrelevant' | 'saved' | 'contacted';

export interface LeadFeedbackCreate {
  action: LeadFeedbackAction;
  comment?: string;
}

export interface LeadFeedbackRead {
  id: number;
  lead_id: number;
  action: LeadFeedbackAction | null;
  feedback_type: string;
  comment: string | null;
  created_at: string;
}

// ---- Legal documents ----
export type LegalDocumentType = 'privacy_policy' | 'terms_of_service' | 'cookie_policy';

export interface LegalDocumentRead {
  id: number;
  type: LegalDocumentType;
  version: string;
  title: string;
  content: string;
  published_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LegalDocumentCreate {
  type: LegalDocumentType;
  version: string;
  title: string;
  content: string;
}
