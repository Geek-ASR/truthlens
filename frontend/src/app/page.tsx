"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ApiError, listFactChecks } from "@/lib/api";
import { STATUS_LABELS, confidenceBandFromValue } from "@/lib/brand";
import { ConfidenceBadge, StatusBadge, VerdictBadge } from "@/components/Badge";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { formatDateShort } from "@/lib/format";
import type { FactCheckStatus, FactCheckSummary } from "@/lib/types";

const TABS: { key: FactCheckStatus | "all"; label: string }[] = [
  { key: "ready_for_review", label: "Pending Review" },
  { key: "approved", label: "Approved" },
  { key: "published", label: "Published" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
];

const ALL_STATUSES: FactCheckStatus[] = [
  "researching",
  "ready_for_review",
  "approved",
  "rejected",
  "published",
  "corrected",
  "retracted",
];

export default function DashboardPage() {
  const router = useRouter();
  const [items, setItems] = useState<FactCheckSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<FactCheckStatus | "all">("ready_for_review");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listFactChecks(undefined, 200);
      setItems(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load the review queue.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const s of ALL_STATUSES) c[s] = 0;
    for (const item of items ?? []) c[item.status] = (c[item.status] ?? 0) + 1;
    return c;
  }, [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (activeTab === "all") return items;
    return items.filter((i) => i.status === activeTab);
  }, [items, activeTab]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Review Queue</h1>
          <div className="subtitle">Fact-checks awaiting review, and their pipeline status.</div>
        </div>
        <div className="btn-row">
          <Link href="/reels/new" className="btn btn-primary">
            + New Reel
          </Link>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="summary-strip">
        {ALL_STATUSES.map((s) => (
          <div className="summary-tile" key={s}>
            <div className="value">{counts[s] ?? 0}</div>
            <div className="label">{STATUS_LABELS[s]}</div>
          </div>
        ))}
      </div>

      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
            <span className="count">
              ({tab.key === "all" ? items?.length ?? 0 : counts[tab.key] ?? 0})
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner label="Loading fact-checks…" />
      ) : filtered.length === 0 ? (
        <div className="table-wrap">
          <div className="empty-state">
            {items === null
              ? "Could not load fact-checks."
              : "No fact-checks in this status yet."}
          </div>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Claim</th>
                <th>Verdict</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((fc) => (
                <tr
                  key={fc.id}
                  onClick={() => router.push(`/fact-checks/${fc.id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td style={{ maxWidth: 480 }}>
                    <Link href={`/fact-checks/${fc.id}`} className="row-link">
                      {fc.primary_claim_text}
                    </Link>
                  </td>
                  <td>{fc.verdict ? <VerdictBadge verdict={fc.verdict} /> : "—"}</td>
                  <td>
                    {fc.confidence !== null ? (
                      <ConfidenceBadge
                        band={confidenceBandFromValue(fc.confidence)}
                        confidence={fc.confidence}
                      />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <StatusBadge status={fc.status} />
                  </td>
                  <td>{formatDateShort(fc.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
