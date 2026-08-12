import type {
  ClaimOut,
  EvidenceOut,
  FactCheckDetail,
  FactCheckStatus,
  FactCheckSummary,
  InstagramAccountOut,
  PublishingJobOut,
  ReelOut,
  TokenResponse,
  UserOut,
  VerdictOut,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ACCESS_TOKEN_KEY = "tl_access_token";
const REFRESH_TOKEN_KEY = "tl_refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isLoggedIn(): boolean {
  return !!getAccessToken();
}

async function extractErrorMessage(res: Response): Promise<string> {
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    return res.statusText || `Request failed with status ${res.status}`;
  }
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) =>
          typeof d === "object" && d && "msg" in d
            ? `${(d as { loc?: unknown[] }).loc?.join?.(".") ?? ""}: ${(d as { msg: string }).msg}`
            : JSON.stringify(d)
        )
        .join("; ");
    }
    return JSON.stringify(detail);
  }
  return JSON.stringify(data);
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth, ...init } = options;
  const headers = new Headers(init.headers);
  if (!skipAuth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const isFormData = init.body instanceof FormData;
  if (!isFormData && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      `Could not reach the TruthLens API at ${API_BASE}. Is the backend running?`
    );
  }

  if (res.status === 401 && !skipAuth) {
    clearTokens();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired. Please log in again.");
  }

  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorMessage(res));
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

// ---------------------------------------------------------------------------
// auth
// ---------------------------------------------------------------------------

export async function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });
}

export async function getMe(): Promise<UserOut> {
  return request<UserOut>("/api/auth/me");
}

// ---------------------------------------------------------------------------
// reels
// ---------------------------------------------------------------------------

export interface CreateReelInput {
  source_url: string;
  platform: string;
  creator_handle?: string;
  caption_text?: string;
  posted_at?: string;
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  share_count?: number;
  hashtags?: string;
  pasted_transcript?: string;
  auto_fetch?: boolean;
  video?: File | null;
}

export async function createReel(input: CreateReelInput): Promise<ReelOut> {
  const form = new FormData();
  form.set("source_url", input.source_url);
  form.set("platform", input.platform);
  if (input.creator_handle) form.set("creator_handle", input.creator_handle);
  if (input.caption_text) form.set("caption_text", input.caption_text);
  if (input.posted_at) form.set("posted_at", input.posted_at);
  if (input.view_count !== undefined && input.view_count !== null)
    form.set("view_count", String(input.view_count));
  if (input.like_count !== undefined && input.like_count !== null)
    form.set("like_count", String(input.like_count));
  if (input.comment_count !== undefined && input.comment_count !== null)
    form.set("comment_count", String(input.comment_count));
  if (input.share_count !== undefined && input.share_count !== null)
    form.set("share_count", String(input.share_count));
  if (input.hashtags) form.set("hashtags", input.hashtags);
  if (input.pasted_transcript) form.set("pasted_transcript", input.pasted_transcript);
  if (input.auto_fetch) form.set("auto_fetch", "true");
  if (input.video) form.set("video", input.video);

  return request<ReelOut>("/api/reels", { method: "POST", body: form });
}

export async function analyzeReel(reelId: string): Promise<ReelOut> {
  return request<ReelOut>(`/api/reels/${reelId}/analyze`, { method: "POST" });
}

// The one-box flow: paste a URL, get back a finished fact-check in one
// call (ingest+auto_fetch -> analyze -> build). Mirrors backend
// POST /api/reels/quick — a long synchronous call (1-3+ minutes on local
// models), not a background job.
export async function quickFactCheck(
  sourceUrl: string,
  platform: string = "instagram"
): Promise<FactCheckDetail> {
  return request<FactCheckDetail>("/api/reels/quick", {
    method: "POST",
    body: JSON.stringify({ source_url: sourceUrl, platform }),
  });
}

export async function getReel(reelId: string): Promise<ReelOut> {
  return request<ReelOut>(`/api/reels/${reelId}`);
}

export async function getReelClaims(reelId: string): Promise<ClaimOut[]> {
  return request<ClaimOut[]>(`/api/reels/${reelId}/claims`);
}

export async function listReels(limit = 50): Promise<ReelOut[]> {
  return request<ReelOut[]>(`/api/reels?limit=${limit}`);
}

// ---------------------------------------------------------------------------
// claims
// ---------------------------------------------------------------------------

export async function getClaim(claimId: string): Promise<ClaimOut> {
  return request<ClaimOut>(`/api/claims/${claimId}`);
}

export async function getClaimEvidence(claimId: string): Promise<EvidenceOut[]> {
  return request<EvidenceOut[]>(`/api/claims/${claimId}/evidence`);
}

export async function getClaimVerdicts(claimId: string): Promise<VerdictOut[]> {
  return request<VerdictOut[]>(`/api/claims/${claimId}/verdicts`);
}

export async function researchAgain(claimId: string): Promise<VerdictOut> {
  return request<VerdictOut>(`/api/claims/${claimId}/research-again`, { method: "POST" });
}

export async function buildFactCheck(claimId: string): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/claims/${claimId}/build-fact-check`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// fact-checks
// ---------------------------------------------------------------------------

export async function listFactChecks(
  status?: FactCheckStatus,
  limit = 200
): Promise<FactCheckSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  return request<FactCheckSummary[]>(`/api/fact-checks?${params.toString()}`);
}

export async function getFactCheck(id: string): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/fact-checks/${id}`);
}

export async function editFactCheck(
  id: string,
  payload: { caption_text?: string; review_notes?: string }
): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/fact-checks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function approveFactCheck(
  id: string,
  payload: { instagram_account_id: string; review_notes?: string }
): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/fact-checks/${id}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function rejectFactCheck(
  id: string,
  payload: { review_notes: string }
): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/fact-checks/${id}/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createCorrection(
  id: string,
  payload: {
    correction_reason: string;
    new_evidence_source_ids?: string[];
    published_correction_note: string;
  }
): Promise<FactCheckDetail> {
  return request<FactCheckDetail>(`/api/fact-checks/${id}/corrections`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// publishing
// ---------------------------------------------------------------------------

export async function listInstagramAccounts(): Promise<InstagramAccountOut[]> {
  return request<InstagramAccountOut[]>("/api/publishing/instagram-accounts");
}

export async function connectInstagramAccount(payload: {
  ig_user_id: string;
  ig_username?: string;
  facebook_page_id?: string;
  short_lived_user_token: string;
}): Promise<InstagramAccountOut> {
  return request<InstagramAccountOut>("/api/publishing/instagram-accounts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function publishFactCheck(factCheckId: string): Promise<PublishingJobOut> {
  return request<PublishingJobOut>(`/api/publishing/${factCheckId}/publish`, { method: "POST" });
}

export async function getPublishStatus(factCheckId: string): Promise<PublishingJobOut> {
  return request<PublishingJobOut>(`/api/publishing/${factCheckId}/status`);
}
