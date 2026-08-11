"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ApiError,
  analyzeReel,
  createReel,
  getClaimVerdicts,
  getReelClaims,
} from "@/lib/api";
import { ErrorBanner, InfoBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { VerdictBadge, ConfidenceBadge } from "@/components/Badge";
import type { ClaimOut, Platform, ReelOut, VerdictOut } from "@/lib/types";

const PLATFORMS: Platform[] = ["instagram", "youtube", "x", "tiktok", "other"];

interface FormState {
  sourceUrl: string;
  platform: Platform;
  creatorHandle: string;
  captionText: string;
  postedAt: string;
  viewCount: string;
  likeCount: string;
  commentCount: string;
  shareCount: string;
  hashtags: string;
  pastedTranscript: string;
}

const EMPTY_FORM: FormState = {
  sourceUrl: "",
  platform: "instagram",
  creatorHandle: "",
  captionText: "",
  postedAt: "",
  viewCount: "",
  likeCount: "",
  commentCount: "",
  shareCount: "",
  hashtags: "",
  pastedTranscript: "",
};

export default function NewReelPage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [autoFetch, setAutoFetch] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reel, setReel] = useState<ReelOut | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [claims, setClaims] = useState<ClaimOut[] | null>(null);
  const [verdicts, setVerdicts] = useState<Record<string, VerdictOut | undefined>>({});

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function parseIntOrUndefined(v: string): number | undefined {
    if (v.trim() === "") return undefined;
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setSubmitError(null);

    if (!form.sourceUrl.trim()) {
      setValidationError("A source URL is required.");
      return;
    }
    if (!videoFile && !form.pastedTranscript.trim() && !autoFetch) {
      setValidationError(
        "Provide at least one media source: upload the reel's video file, paste a transcript, or enable auto-fetch."
      );
      return;
    }

    setSubmitting(true);
    try {
      const created = await createReel({
        source_url: form.sourceUrl.trim(),
        platform: form.platform,
        creator_handle: form.creatorHandle.trim() || undefined,
        caption_text: form.captionText.trim() || undefined,
        posted_at: form.postedAt ? new Date(form.postedAt).toISOString() : undefined,
        view_count: parseIntOrUndefined(form.viewCount),
        like_count: parseIntOrUndefined(form.likeCount),
        comment_count: parseIntOrUndefined(form.commentCount),
        share_count: parseIntOrUndefined(form.shareCount),
        hashtags: form.hashtags.trim() || undefined,
        pasted_transcript: form.pastedTranscript.trim() || undefined,
        auto_fetch: autoFetch,
        video: videoFile,
      });
      setReel(created);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to create the reel.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAnalyze() {
    if (!reel) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const updated = await analyzeReel(reel.id);
      setReel(updated);
      const extractedClaims = await getReelClaims(reel.id);
      setClaims(extractedClaims);
      const verdictEntries = await Promise.all(
        extractedClaims.map(async (c) => {
          if (!c.verifiable) return [c.id, undefined] as const;
          try {
            const vs = await getClaimVerdicts(c.id);
            const current = vs.find((v) => v.is_current) ?? vs[0];
            return [c.id, current] as const;
          } catch {
            return [c.id, undefined] as const;
          }
        })
      );
      setVerdicts(Object.fromEntries(verdictEntries));
    } catch (err) {
      setAnalyzeError(
        err instanceof ApiError
          ? err.message
          : "Analysis failed unexpectedly. You can try again."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>New Reel</h1>
          <div className="subtitle">
            Paste the source URL and supply the media — an uploaded video, or a pasted transcript.
          </div>
        </div>
      </div>

      {!reel ? (
        <form className="form-card" onSubmit={handleSubmit}>
          <ErrorBanner message={validationError} onDismiss={() => setValidationError(null)} />
          <ErrorBanner message={submitError} onDismiss={() => setSubmitError(null)} />

          <div className="field">
            <label htmlFor="sourceUrl">Reel URL *</label>
            <input
              id="sourceUrl"
              type="url"
              required
              placeholder="https://www.instagram.com/reel/…"
              value={form.sourceUrl}
              onChange={(e) => update("sourceUrl", e.target.value)}
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="platform">Platform</label>
              <select
                id="platform"
                value={form.platform}
                onChange={(e) => update("platform", e.target.value as Platform)}
              >
                {PLATFORMS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="creatorHandle">Creator handle</label>
              <input
                id="creatorHandle"
                type="text"
                placeholder="@handle"
                value={form.creatorHandle}
                onChange={(e) => update("creatorHandle", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="postedAt">Posted at</label>
              <input
                id="postedAt"
                type="datetime-local"
                value={form.postedAt}
                onChange={(e) => update("postedAt", e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="captionText">Caption text (as posted)</label>
            <textarea
              id="captionText"
              rows={2}
              value={form.captionText}
              onChange={(e) => update("captionText", e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="hashtags">Hashtags</label>
            <input
              id="hashtags"
              type="text"
              placeholder="comma, separated, tags"
              value={form.hashtags}
              onChange={(e) => update("hashtags", e.target.value)}
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="viewCount">Views</label>
              <input
                id="viewCount"
                type="number"
                min={0}
                value={form.viewCount}
                onChange={(e) => update("viewCount", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="likeCount">Likes</label>
              <input
                id="likeCount"
                type="number"
                min={0}
                value={form.likeCount}
                onChange={(e) => update("likeCount", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="commentCount">Comments</label>
              <input
                id="commentCount"
                type="number"
                min={0}
                value={form.commentCount}
                onChange={(e) => update("commentCount", e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="shareCount">Shares</label>
              <input
                id="shareCount"
                type="number"
                min={0}
                value={form.shareCount}
                onChange={(e) => update("shareCount", e.target.value)}
              />
            </div>
          </div>

          <hr className="divider" />

          <div className="field">
            <label htmlFor="video">Upload video file</label>
            <input
              id="video"
              type="file"
              accept="video/*"
              disabled={autoFetch}
              onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
            />
            <span className="hint">Up to 200MB. Or paste a transcript below instead.</span>
          </div>

          <div className="field">
            <label htmlFor="pastedTranscript">Pasted transcript</label>
            <textarea
              id="pastedTranscript"
              rows={6}
              placeholder="Paste a transcript if no video file is available…"
              disabled={autoFetch}
              value={form.pastedTranscript}
              onChange={(e) => update("pastedTranscript", e.target.value)}
            />
          </div>

          <div className="hint" style={{ textAlign: "center", margin: "4px 0" }}>
            — or —
          </div>

          <div className="field">
            <label className="checkbox-row" htmlFor="autoFetch">
              <input
                id="autoFetch"
                type="checkbox"
                checked={autoFetch}
                onChange={(e) => setAutoFetch(e.target.checked)}
              />
              Auto-fetch video, caption &amp; metadata from the URL above (skip manual upload)
            </label>
            {autoFetch ? (
              <InfoBanner
                message={
                  form.platform === "instagram"
                    ? "For Instagram URLs, auto-fetch works outside Instagram's Terms of Service (no official API exists for downloading arbitrary posts) and can flag or rate-limit the account. Off by default — you've explicitly enabled it. See docs/ARCHITECTURE.md §2a."
                    : `Auto-fetch will download the video and read whatever metadata ${form.platform} exposes for this URL. This runs server-side and may take a minute.`
                }
              />
            ) : null}
          </div>

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? (autoFetch ? "Fetching…" : "Submitting…") : "Submit Reel"}
          </button>
          {submitting && autoFetch ? (
            <Spinner label="Downloading video and reading metadata from the source URL — this can take a minute." />
          ) : null}
        </form>
      ) : (
        <div>
          <div className="card">
            <div className="card-header">
              <h2>Reel submitted</h2>
              <Link href={`/reels/${reel.id}`} className="btn btn-secondary btn-sm">
                Open full reel detail →
              </Link>
            </div>
            <dl className="meta-list">
              <dt>Source URL</dt>
              <dd>
                <a href={reel.source_url} target="_blank" rel="noreferrer">
                  {reel.source_url}
                </a>
              </dd>
              <dt>Platform</dt>
              <dd>{reel.platform}</dd>
              <dt>Ingestion status</dt>
              <dd>{reel.ingestion_status}</dd>
              {reel.auto_fetched ? (
                <>
                  <dt>Media source</dt>
                  <dd>Auto-fetched via yt-dlp</dd>
                </>
              ) : null}
            </dl>

            <hr className="divider" />

            <ErrorBanner message={analyzeError} onDismiss={() => setAnalyzeError(null)} />

            {claims === null ? (
              <div className="btn-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleAnalyze}
                  disabled={analyzing}
                >
                  {analyzing ? "Analyzing…" : "Analyze Reel"}
                </button>
                {analyzing ? (
                  <Spinner label="Running transcription, claim extraction, research, and verdicts — this can take a few minutes." />
                ) : null}
              </div>
            ) : (
              <div>
                <InfoBanner
                  message={`Analysis complete — ${claims.length} claim${claims.length === 1 ? "" : "s"} extracted.`}
                />
                {claims.length === 0 ? (
                  <p className="hint">No claims were extracted from this reel.</p>
                ) : (
                  claims.map((c) => {
                    const v = verdicts[c.id];
                    return (
                      <div className="claim-card" key={c.id} id={`claim-${c.id}`}>
                        <div className="claim-text">{c.text}</div>
                        <div className="claim-tags">
                          <span className="tag">{c.claim_type}</span>
                          {!c.verifiable ? <span className="tag muted">not verifiable</span> : null}
                          <span className="tag muted">{c.status}</span>
                        </div>
                        <div className="btn-row" style={{ marginTop: 8 }}>
                          {v ? (
                            <>
                              <VerdictBadge verdict={v.verdict} />
                              <ConfidenceBadge band={v.confidence_band} confidence={v.confidence} />
                            </>
                          ) : c.verifiable ? (
                            <span className="hint">No verdict yet.</span>
                          ) : null}
                          <Link
                            href={`/reels/${reel.id}#claim-${c.id}`}
                            className="btn btn-ghost btn-sm"
                          >
                            View &amp; take action →
                          </Link>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
