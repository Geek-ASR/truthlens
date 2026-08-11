"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  approveFactCheck,
  buildFactCheck,
  createCorrection,
  editFactCheck,
  getFactCheck,
  getPublishStatus,
  listInstagramAccounts,
  publishFactCheck,
  rejectFactCheck,
  researchAgain,
} from "@/lib/api";
import { ErrorBanner, InfoBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { ConfidenceBadge, StatusBadge, VerdictBadge } from "@/components/Badge";
import { formatDate, formatPercent, titleCase } from "@/lib/format";
import type {
  FactCheckDetail,
  InstagramAccountOut,
  PublishingJobOut,
  VerdictOut,
} from "@/lib/types";

const STANCE_LABELS: Record<string, string> = {
  supports: "Supports",
  contradicts: "Contradicts",
  provides_context: "Provides Context",
  irrelevant: "Irrelevant",
};

const PRE_PUBLISH_STATUSES = new Set(["researching", "ready_for_review", "approved", "rejected"]);

export default function FactCheckDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [fc, setFc] = useState<FactCheckDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [publishJob, setPublishJob] = useState<PublishingJobOut | null>(null);

  // caption / review-notes editor
  const [captionDraft, setCaptionDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // approve
  const [igAccounts, setIgAccounts] = useState<InstagramAccountOut[] | null>(null);
  const [showApprove, setShowApprove] = useState(false);
  const [approveAccountId, setApproveAccountId] = useState("");
  const [approveNotes, setApproveNotes] = useState("");
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  // reject
  const [showReject, setShowReject] = useState(false);
  const [rejectNotes, setRejectNotes] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [rejectError, setRejectError] = useState<string | null>(null);

  // research again (pre-publish rebuild)
  const [researching, setResearching] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);

  // publish
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  // correction flow (published only)
  const [refreshingVerdict, setRefreshingVerdict] = useState(false);
  const [freshVerdict, setFreshVerdict] = useState<VerdictOut | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionNote, setCorrectionNote] = useState("");
  const [correctionSourceIds, setCorrectionSourceIds] = useState<string[]>([]);
  const [correcting, setCorrecting] = useState(false);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const detail = await getFactCheck(id);
      setFc(detail);
      setCaptionDraft(detail.caption_text ?? "");
      setNotesDraft(detail.review_notes ?? "");
      if (detail.status === "approved" || detail.status === "published") {
        try {
          const job = await getPublishStatus(id);
          setPublishJob(job);
        } catch {
          setPublishJob(null);
        }
      }
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load this fact-check.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    listInstagramAccounts()
      .then(setIgAccounts)
      .catch(() => setIgAccounts([]));
  }, []);

  const isDirty = useMemo(() => {
    if (!fc) return false;
    return captionDraft !== (fc.caption_text ?? "") || notesDraft !== (fc.review_notes ?? "");
  }, [fc, captionDraft, notesDraft]);

  async function handleSave() {
    if (!fc) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const updated = await editFactCheck(fc.id, {
        caption_text: captionDraft,
        review_notes: notesDraft,
      });
      setFc(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save changes.");
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove(e: React.FormEvent) {
    e.preventDefault();
    if (!fc || !approveAccountId) return;
    setApproving(true);
    setApproveError(null);
    try {
      const updated = await approveFactCheck(fc.id, {
        instagram_account_id: approveAccountId,
        review_notes: approveNotes.trim() || undefined,
      });
      setFc(updated);
      setShowApprove(false);
    } catch (err) {
      setApproveError(err instanceof ApiError ? err.message : "Failed to approve.");
    } finally {
      setApproving(false);
    }
  }

  async function handleReject(e: React.FormEvent) {
    e.preventDefault();
    if (!fc || !rejectNotes.trim()) return;
    setRejecting(true);
    setRejectError(null);
    try {
      const updated = await rejectFactCheck(fc.id, { review_notes: rejectNotes.trim() });
      setFc(updated);
      setShowReject(false);
    } catch (err) {
      setRejectError(err instanceof ApiError ? err.message : "Failed to reject.");
    } finally {
      setRejecting(false);
    }
  }

  async function handleResearchAgainAndRebuild() {
    if (!fc) return;
    setResearching(true);
    setResearchError(null);
    try {
      await researchAgain(fc.primary_claim.id);
      const rebuilt = await buildFactCheck(fc.primary_claim.id);
      router.push(`/fact-checks/${rebuilt.id}`);
    } catch (err) {
      setResearchError(err instanceof ApiError ? err.message : "Research failed unexpectedly.");
      setResearching(false);
    }
  }

  async function handlePublish() {
    if (!fc) return;
    setPublishing(true);
    setPublishError(null);
    try {
      const job = await publishFactCheck(fc.id);
      setPublishJob(job);
      await load();
    } catch (err) {
      setPublishError(err instanceof ApiError ? err.message : "Failed to publish.");
    } finally {
      setPublishing(false);
    }
  }

  async function handleRefreshVerdictForCorrection() {
    if (!fc) return;
    setRefreshingVerdict(true);
    setCorrectionError(null);
    try {
      const newVerdict = await researchAgain(fc.primary_claim.id);
      setFreshVerdict(newVerdict);
    } catch (err) {
      setCorrectionError(err instanceof ApiError ? err.message : "Research failed unexpectedly.");
    } finally {
      setRefreshingVerdict(false);
    }
  }

  async function handleFileCorrection(e: React.FormEvent) {
    e.preventDefault();
    if (!fc || !correctionReason.trim() || !correctionNote.trim()) return;
    setCorrecting(true);
    setCorrectionError(null);
    try {
      const updated = await createCorrection(fc.id, {
        correction_reason: correctionReason.trim(),
        published_correction_note: correctionNote.trim(),
        new_evidence_source_ids: correctionSourceIds,
      });
      setFc(updated);
      setFreshVerdict(null);
      setCorrectionReason("");
      setCorrectionNote("");
      setCorrectionSourceIds([]);
    } catch (err) {
      setCorrectionError(err instanceof ApiError ? err.message : "Failed to file correction.");
    } finally {
      setCorrecting(false);
    }
  }

  if (loading) {
    return <Spinner label="Loading fact-check…" />;
  }

  if (loadError || !fc) {
    return <ErrorBanner message={loadError ?? "Fact-check not found."} />;
  }

  const claim = fc.primary_claim;
  const verdict = fc.current_verdict;
  const sortedSlides = [...fc.slides].sort((a, b) => a.position - b.position);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Fact-Check Review</h1>
          <div className="btn-row" style={{ marginTop: 6 }}>
            <StatusBadge status={fc.status} />
            {verdict ? <VerdictBadge verdict={verdict.verdict} /> : null}
            {verdict ? (
              <ConfidenceBadge band={verdict.confidence_band} confidence={verdict.confidence} />
            ) : null}
          </div>
        </div>
        <Link href="/" className="btn btn-ghost btn-sm">
          ← Back to queue
        </Link>
      </div>

      {fc.duplicate_of_fact_check_id ? (
        <ErrorBanner
          message={`DUPLICATE — DO NOT PUBLISH. This overlaps with fact-check ${fc.duplicate_of_fact_check_id}.`}
        />
      ) : null}

      <div className="detail-grid">
        <div>
          {/* Reel */}
          <div className="card">
            <h3>Source Reel</h3>
            <dl className="meta-list">
              <dt>URL</dt>
              <dd>
                <a href={fc.reel.source_url} target="_blank" rel="noreferrer">
                  {fc.reel.source_url}
                </a>
              </dd>
              <dt>Platform</dt>
              <dd>{fc.reel.platform}</dd>
              <dt>Creator</dt>
              <dd>{fc.reel.creator_handle ?? "—"}</dd>
              <dt>Posted</dt>
              <dd>{formatDate(fc.reel.posted_at)}</dd>
            </dl>
            <div className="btn-row" style={{ marginTop: 10 }}>
              <Link href={`/reels/${fc.reel.id}`} className="btn btn-secondary btn-sm">
                Open reel detail →
              </Link>
            </div>
          </div>

          {/* Primary claim */}
          <div className="card">
            <h3>Primary Claim</h3>
            <p style={{ fontWeight: 600, fontSize: 15 }}>{claim.text}</p>
            <div className="claim-tags">
              <span className="tag">{claim.claim_type}</span>
              <span className="tag muted">{claim.status}</span>
              {claim.time_reference ? <span className="tag muted">{claim.time_reference}</span> : null}
              {claim.location ? <span className="tag muted">{claim.location}</span> : null}
            </div>
            {claim.entities && claim.entities.length > 0 ? (
              <div className="claim-tags" style={{ marginTop: 4 }}>
                {claim.entities.map((ent, i) => (
                  <span className="tag muted" key={i}>
                    {String((ent as { name?: string }).name ?? JSON.stringify(ent))}
                  </span>
                ))}
              </div>
            ) : null}

            {fc.covered_claims.length > 0 ? (
              <>
                <hr className="divider" />
                <h3>Also covered in this post</h3>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {fc.covered_claims.map((c) => (
                    <li key={c.id}>{c.text}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>

          {/* Verdict */}
          <div className="card">
            <h3>Current Verdict</h3>
            {verdict ? (
              <>
                <div className="btn-row" style={{ marginBottom: 10 }}>
                  <VerdictBadge verdict={verdict.verdict} />
                  <ConfidenceBadge band={verdict.confidence_band} confidence={verdict.confidence} />
                </div>
                {verdict.validation_status !== "passed" ? (
                  <InfoBanner
                    message={`Validation note: ${titleCase(verdict.validation_status)}`}
                  />
                ) : null}
                <p>{verdict.reasoning_summary}</p>
                <p className="hint">
                  Cites {verdict.cited_evidence_ids.length} evidence row
                  {verdict.cited_evidence_ids.length === 1 ? "" : "s"} · proposed{" "}
                  {formatDate(verdict.created_at)}
                </p>
              </>
            ) : (
              <p className="hint">No verdict recorded.</p>
            )}
          </div>

          {/* Evidence */}
          <div className="card">
            <h3>Evidence ({fc.evidence.length})</h3>
            {fc.evidence.length === 0 ? (
              <p className="hint">No evidence rows recorded for this claim.</p>
            ) : (
              fc.evidence.map((ev) => (
                <div className="evidence-item" key={ev.id}>
                  <div className="evidence-top">
                    <div>
                      <div className="evidence-source">{ev.source.title ?? ev.source.url}</div>
                      <div className="evidence-meta">
                        {ev.source.publisher ?? "Unknown publisher"} ·{" "}
                        {titleCase(ev.source.source_type)} · reliability{" "}
                        {formatPercent(ev.source.reliability_score)}
                      </div>
                    </div>
                    <span
                      className="tag"
                      style={{
                        background:
                          ev.stance === "supports"
                            ? "#e7f0ec"
                            : ev.stance === "contradicts"
                              ? "#fbeae7"
                              : "#eee",
                        color:
                          ev.stance === "supports"
                            ? "#1b4b43"
                            : ev.stance === "contradicts"
                              ? "#a6321f"
                              : "#6b7280",
                      }}
                    >
                      {STANCE_LABELS[ev.stance] ?? ev.stance}
                    </span>
                  </div>
                  <p style={{ margin: "6px 0 0", fontSize: 13 }}>{ev.explanation}</p>
                  <div className="evidence-passage">&ldquo;{ev.source.relevant_passage}&rdquo;</div>
                  <div className="evidence-meta" style={{ marginTop: 6 }}>
                    <a href={ev.source.url} target="_blank" rel="noreferrer">
                      {ev.source.url}
                    </a>{" "}
                    · {ev.directness}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Slides */}
          <div className="card">
            <h3>Carousel Slides ({sortedSlides.length}/4)</h3>
            {sortedSlides.length === 0 ? (
              <p className="hint">No slides generated yet.</p>
            ) : (
              <div className="slide-grid">
                {sortedSlides.map((s) => (
                  <div key={s.id}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={s.image_url} alt={`Slide ${s.position}: ${s.slide_type}`} />
                    <div className="slide-caption">
                      {s.position}. {titleCase(s.slide_type)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Caption + review notes */}
          <div className="card">
            <h3>Caption</h3>
            <textarea
              rows={8}
              value={captionDraft}
              onChange={(e) => setCaptionDraft(e.target.value)}
              disabled={fc.status === "published"}
            />
            <h3 style={{ marginTop: 16 }}>Review Notes (internal)</h3>
            <textarea
              rows={3}
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              disabled={fc.status === "published"}
            />
            {fc.status === "published" ? (
              <p className="hint" style={{ marginTop: 8 }}>
                This fact-check is published — use the correction flow below to change it.
              </p>
            ) : (
              <div className="btn-row" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleSave}
                  disabled={!isDirty || saving}
                >
                  {saving ? "Saving…" : "Save Changes"}
                </button>
                {saved ? <span className="hint">Saved.</span> : null}
              </div>
            )}
            <ErrorBanner message={saveError} onDismiss={() => setSaveError(null)} />
          </div>
        </div>

        {/* Right column: actions */}
        <div>
          <div className="card">
            <h3>Actions</h3>

            {fc.status === "researching" ? (
              <>
                <p className="hint">This fact-check is still being generated.</p>
                <button type="button" className="btn btn-secondary btn-sm" onClick={load}>
                  Refresh
                </button>
              </>
            ) : null}

            {fc.status === "ready_for_review" ? (
              <div className="btn-row" style={{ marginBottom: 12 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setShowApprove((v) => !v)}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setShowReject((v) => !v)}
                >
                  Reject
                </button>
              </div>
            ) : null}

            {showApprove && fc.status === "ready_for_review" ? (
              <form className="card" style={{ background: "var(--paper)" }} onSubmit={handleApprove}>
                <ErrorBanner message={approveError} onDismiss={() => setApproveError(null)} />
                <div className="field">
                  <label htmlFor="ig-account">Publish to Instagram account</label>
                  <select
                    id="ig-account"
                    required
                    value={approveAccountId}
                    onChange={(e) => setApproveAccountId(e.target.value)}
                  >
                    <option value="">Select an account…</option>
                    {(igAccounts ?? []).map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.ig_username ?? a.ig_user_id}
                      </option>
                    ))}
                  </select>
                  {igAccounts !== null && igAccounts.length === 0 ? (
                    <span className="hint">
                      No accounts connected.{" "}
                      <Link href="/settings/instagram">Connect one first →</Link>
                    </span>
                  ) : null}
                </div>
                <div className="field">
                  <label htmlFor="approve-notes">Review notes (optional)</label>
                  <textarea
                    id="approve-notes"
                    rows={2}
                    value={approveNotes}
                    onChange={(e) => setApproveNotes(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={approving || !approveAccountId}
                >
                  {approving ? "Approving…" : "Confirm Approve"}
                </button>
              </form>
            ) : null}

            {showReject && fc.status === "ready_for_review" ? (
              <form className="card" style={{ background: "var(--paper)" }} onSubmit={handleReject}>
                <ErrorBanner message={rejectError} onDismiss={() => setRejectError(null)} />
                <div className="field">
                  <label htmlFor="reject-notes">Reason for rejection (required)</label>
                  <textarea
                    id="reject-notes"
                    rows={3}
                    required
                    value={rejectNotes}
                    onChange={(e) => setRejectNotes(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-danger btn-sm"
                  disabled={rejecting || !rejectNotes.trim()}
                >
                  {rejecting ? "Rejecting…" : "Confirm Reject"}
                </button>
              </form>
            ) : null}

            {fc.status === "approved" ? (
              <div style={{ marginBottom: 12 }}>
                <ErrorBanner message={publishError} onDismiss={() => setPublishError(null)} />
                {publishJob?.status === "published" && publishJob.permalink ? (
                  <InfoBanner message="Already published." />
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={handlePublish}
                    disabled={publishing}
                  >
                    {publishing ? "Publishing…" : "Publish to Instagram"}
                  </button>
                )}
                {publishJob?.last_error ? (
                  <p className="hint" style={{ color: "var(--danger)" }}>
                    Last error: {publishJob.last_error}
                  </p>
                ) : null}
              </div>
            ) : null}

            {fc.status === "published" ? (
              <div style={{ marginBottom: 12 }}>
                {publishJob?.permalink ? (
                  <p>
                    <a href={publishJob.permalink} target="_blank" rel="noreferrer">
                      View published post →
                    </a>
                  </p>
                ) : (
                  <p className="hint">Published — permalink not available.</p>
                )}
              </div>
            ) : null}

            {PRE_PUBLISH_STATUSES.has(fc.status) ? (
              <div>
                <hr className="divider" />
                <ErrorBanner message={researchError} onDismiss={() => setResearchError(null)} />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleResearchAgainAndRebuild}
                  disabled={researching}
                >
                  {researching ? "Researching…" : "Research Again"}
                </button>
                <p className="hint" style={{ marginTop: 6 }}>
                  Re-runs research on the primary claim and rebuilds a new fact-check carousel from
                  the updated verdict. Will redirect to the new fact-check.
                </p>
              </div>
            ) : null}

            {fc.status === "rejected" && fc.review_notes ? (
              <>
                <hr className="divider" />
                <h3>Rejection reason</h3>
                <p className="hint">{fc.review_notes}</p>
              </>
            ) : null}

            {fc.status === "corrected" || fc.status === "retracted" ? (
              <p className="hint">
                This fact-check is {fc.status}. No further review actions are available for this
                status.
              </p>
            ) : null}
          </div>

          {fc.status === "published" ? (
            <div className="card">
              <h3>File a Correction</h3>
              <p className="hint">
                First get an updated verdict, then describe the correction to publish.
              </p>
              <ErrorBanner message={correctionError} onDismiss={() => setCorrectionError(null)} />

              {!freshVerdict ? (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleRefreshVerdictForCorrection}
                  disabled={refreshingVerdict}
                >
                  {refreshingVerdict ? "Researching…" : "1. Research Again"}
                </button>
              ) : (
                <>
                  <InfoBanner message="New verdict obtained. Review it, then file the correction." />
                  <div className="btn-row" style={{ marginBottom: 10 }}>
                    <VerdictBadge verdict={freshVerdict.verdict} />
                    <ConfidenceBadge
                      band={freshVerdict.confidence_band}
                      confidence={freshVerdict.confidence}
                    />
                  </div>
                  <p className="hint">{freshVerdict.reasoning_summary}</p>

                  <form onSubmit={handleFileCorrection}>
                    <div className="field">
                      <label htmlFor="correction-reason">Correction reason (internal)</label>
                      <textarea
                        id="correction-reason"
                        rows={2}
                        required
                        value={correctionReason}
                        onChange={(e) => setCorrectionReason(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="correction-note">Public correction note</label>
                      <textarea
                        id="correction-note"
                        rows={3}
                        required
                        value={correctionNote}
                        onChange={(e) => setCorrectionNote(e.target.value)}
                      />
                    </div>
                    {fc.evidence.length > 0 ? (
                      <div className="field">
                        <label>New evidence sources to cite (optional)</label>
                        {fc.evidence.map((ev) => (
                          <label key={ev.id} className="checkbox-row">
                            <input
                              type="checkbox"
                              checked={correctionSourceIds.includes(ev.source.id)}
                              onChange={(e) => {
                                setCorrectionSourceIds((prev) =>
                                  e.target.checked
                                    ? [...prev, ev.source.id]
                                    : prev.filter((sid) => sid !== ev.source.id)
                                );
                              }}
                            />
                            {ev.source.title ?? ev.source.url}
                          </label>
                        ))}
                      </div>
                    ) : null}
                    <button
                      type="submit"
                      className="btn btn-primary btn-sm"
                      disabled={correcting || !correctionReason.trim() || !correctionNote.trim()}
                    >
                      {correcting ? "Filing…" : "2. File Correction"}
                    </button>
                  </form>
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
