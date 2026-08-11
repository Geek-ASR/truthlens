"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  analyzeReel,
  buildFactCheck,
  getClaimVerdicts,
  getReel,
  getReelClaims,
  researchAgain,
} from "@/lib/api";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { VerdictBadge, ConfidenceBadge } from "@/components/Badge";
import { formatCount, formatDate } from "@/lib/format";
import type { ClaimOut, ReelOut, VerdictOut } from "@/lib/types";

interface ClaimRowState {
  researching: boolean;
  building: boolean;
  error: string | null;
}

export default function ReelDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const reelId = params.id;

  const [reel, setReel] = useState<ReelOut | null>(null);
  const [claims, setClaims] = useState<ClaimOut[] | null>(null);
  const [verdicts, setVerdicts] = useState<Record<string, VerdictOut | undefined>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const [rowState, setRowState] = useState<Record<string, ClaimRowState>>({});

  function setRow(claimId: string, patch: Partial<ClaimRowState>) {
    setRowState((prev) => {
      const existing: ClaimRowState = prev[claimId] ?? {
        researching: false,
        building: false,
        error: null,
      };
      return { ...prev, [claimId]: { ...existing, ...patch } };
    });
  }

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [reelData, claimData] = await Promise.all([getReel(reelId), getReelClaims(reelId)]);
      setReel(reelData);
      setClaims(claimData);
      const verdictEntries = await Promise.all(
        claimData.map(async (c) => {
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
      setLoadError(err instanceof ApiError ? err.message : "Failed to load this reel.");
    } finally {
      setLoading(false);
    }
  }, [reelId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      await analyzeReel(reelId);
      await load();
    } catch (err) {
      setAnalyzeError(err instanceof ApiError ? err.message : "Analysis failed unexpectedly.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleResearchAgain(claim: ClaimOut) {
    setRow(claim.id, { researching: true, error: null });
    try {
      const newVerdict = await researchAgain(claim.id);
      setVerdicts((prev) => ({ ...prev, [claim.id]: newVerdict }));
    } catch (err) {
      setRow(claim.id, {
        error: err instanceof ApiError ? err.message : "Research failed unexpectedly.",
      });
    } finally {
      setRow(claim.id, { researching: false });
    }
  }

  async function handleBuildFactCheck(claim: ClaimOut) {
    setRow(claim.id, { building: true, error: null });
    try {
      const factCheck = await buildFactCheck(claim.id);
      router.push(`/fact-checks/${factCheck.id}`);
    } catch (err) {
      setRow(claim.id, {
        building: false,
        error:
          err instanceof ApiError
            ? err.message
            : "Failed to build the fact-check carousel unexpectedly.",
      });
    }
  }

  if (loading) {
    return <Spinner label="Loading reel…" />;
  }

  if (loadError || !reel) {
    return <ErrorBanner message={loadError ?? "Reel not found."} />;
  }

  const needsAnalysis = !reel.transcript && (!claims || claims.length === 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Reel Detail</h1>
          <div className="subtitle">
            <a href={reel.source_url} target="_blank" rel="noreferrer">
              {reel.source_url}
            </a>
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <div className="card">
            <div className="card-header">
              <h2>Transcript</h2>
            </div>
            {reel.transcript ? (
              <pre className="transcript">{reel.transcript}</pre>
            ) : (
              <p className="hint">No transcript yet.</p>
            )}
          </div>

          {reel.ocr_text && reel.ocr_text.length > 0 ? (
            <div className="card">
              <div className="card-header">
                <h2>On-screen text (OCR)</h2>
              </div>
              <pre className="transcript">
                {reel.ocr_text
                  .map((f) => `[${f.frame_ts ?? "?"}s] ${f.text ?? ""}`)
                  .join("\n")}
              </pre>
            </div>
          ) : null}

          <div className="card">
            <div className="card-header">
              <h2>
                Claims{claims && claims.length > 0 ? ` (${claims.length})` : ""}
              </h2>
              {needsAnalysis ? null : (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleAnalyze}
                  disabled={analyzing}
                >
                  {analyzing ? "Re-analyzing…" : "Re-run analysis"}
                </button>
              )}
            </div>

            <ErrorBanner message={analyzeError} onDismiss={() => setAnalyzeError(null)} />

            {needsAnalysis ? (
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
                  <Spinner label="Transcription, claims, research and verdicts — this can take a few minutes." />
                ) : null}
              </div>
            ) : !claims || claims.length === 0 ? (
              <p className="hint">No claims were extracted from this reel.</p>
            ) : (
              claims.map((c) => {
                const v = verdicts[c.id];
                const state = rowState[c.id] ?? { researching: false, building: false, error: null };
                return (
                  <div className="claim-card" key={c.id} id={`claim-${c.id}`}>
                    <div className="claim-text">{c.text}</div>
                    {c.source_quote ? (
                      <div className="hint" style={{ marginBottom: 8 }}>
                        &ldquo;{c.source_quote}&rdquo;
                      </div>
                    ) : null}
                    <div className="claim-tags">
                      <span className="tag">{c.claim_type}</span>
                      {!c.verifiable ? <span className="tag muted">not verifiable</span> : null}
                      <span className="tag muted">{c.status}</span>
                      {c.time_reference ? <span className="tag muted">{c.time_reference}</span> : null}
                      {c.location ? <span className="tag muted">{c.location}</span> : null}
                    </div>

                    {v ? (
                      <div className="btn-row" style={{ marginBottom: 10 }}>
                        <VerdictBadge verdict={v.verdict} />
                        <ConfidenceBadge band={v.confidence_band} confidence={v.confidence} />
                        {v.validation_status !== "passed" ? (
                          <span className="tag muted">{v.validation_status.replace(/_/g, " ")}</span>
                        ) : null}
                      </div>
                    ) : c.verifiable ? (
                      <p className="hint">No verdict yet — run research.</p>
                    ) : null}

                    {v?.reasoning_summary ? (
                      <p className="hint" style={{ marginBottom: 10 }}>
                        {v.reasoning_summary}
                      </p>
                    ) : null}

                    <ErrorBanner message={state.error} onDismiss={() => setRow(c.id, { error: null })} />

                    {c.verifiable ? (
                      <div className="btn-row">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleResearchAgain(c)}
                          disabled={state.researching || state.building}
                        >
                          {state.researching ? "Researching…" : "Research Again"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleBuildFactCheck(c)}
                          disabled={!v || state.researching || state.building}
                          title={!v ? "Research this claim first" : undefined}
                        >
                          {state.building ? "Building…" : "Build Fact-Check Carousel"}
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div>
          <div className="card">
            <h3>Reel Info</h3>
            <dl className="meta-list">
              <dt>Platform</dt>
              <dd>{reel.platform}</dd>
              <dt>Creator</dt>
              <dd>{reel.creator_handle ?? "—"}</dd>
              <dt>Posted</dt>
              <dd>{formatDate(reel.posted_at)}</dd>
              <dt>Ingestion</dt>
              <dd>{reel.ingestion_status}</dd>
              <dt>Discovery</dt>
              <dd>{reel.discovery_source}</dd>
              <dt>Submitted</dt>
              <dd>{formatDate(reel.created_at)}</dd>
            </dl>
            <hr className="divider" />
            <div className="stat-line">
              <span>👁 {formatCount(reel.view_count)}</span>
              <span>♥ {formatCount(reel.like_count)}</span>
              <span>💬 {formatCount(reel.comment_count)}</span>
              <span>↗ {formatCount(reel.share_count)}</span>
            </div>
            {reel.hashtags && reel.hashtags.length > 0 ? (
              <>
                <hr className="divider" />
                <div className="claim-tags">
                  {reel.hashtags.map((h) => (
                    <span className="tag muted" key={h}>
                      #{h}
                    </span>
                  ))}
                </div>
              </>
            ) : null}
            {reel.caption_text ? (
              <>
                <hr className="divider" />
                <p className="hint">{reel.caption_text}</p>
              </>
            ) : null}
          </div>

          <div className="card">
            <Link href="/" className="btn btn-ghost btn-sm">
              ← Back to queue
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
