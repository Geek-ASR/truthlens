// Loosely mirrors backend/app/templates/brand.py so the dashboard and the
// rendered slides read as the same visual system.
import type { ConfidenceBand, FactCheckStatus, VerdictLabel } from "./types";

export const VERDICT_COLORS: Record<VerdictLabel, string> = {
  TRUE: "#1B6E3C",
  MOSTLY_TRUE: "#3E8E5A",
  MISLEADING: "#B8860B",
  MOSTLY_FALSE: "#C06A2C",
  FALSE: "#A6321F",
  UNVERIFIED: "#5B6472",
  OUTDATED: "#7A5C9E",
  MISSING_CONTEXT: "#946B1F",
};

export const VERDICT_LABELS: Record<VerdictLabel, string> = {
  TRUE: "True",
  MOSTLY_TRUE: "Mostly True",
  MISLEADING: "Misleading",
  MOSTLY_FALSE: "Mostly False",
  FALSE: "False",
  UNVERIFIED: "Unverified",
  OUTDATED: "Outdated",
  MISSING_CONTEXT: "Missing Context",
};

export const STATUS_COLORS: Record<FactCheckStatus, string> = {
  researching: "#6B7280",
  ready_for_review: "#B8860B",
  approved: "#1B4B43",
  rejected: "#A6321F",
  published: "#1B6E3C",
  corrected: "#7A5C9E",
  retracted: "#946B1F",
};

export const STATUS_LABELS: Record<FactCheckStatus, string> = {
  researching: "Researching",
  ready_for_review: "Pending Review",
  approved: "Approved",
  rejected: "Rejected",
  published: "Published",
  corrected: "Corrected",
  retracted: "Retracted",
};

export const CONFIDENCE_COLORS: Record<ConfidenceBand, string> = {
  very_high: "#1B6E3C",
  high: "#3E8E5A",
  moderate: "#B8860B",
  requires_review: "#A6321F",
};

export const CONFIDENCE_LABELS: Record<ConfidenceBand, string> = {
  very_high: "Very High",
  high: "High",
  moderate: "Moderate",
  requires_review: "Requires Review",
};

// Mirrors the thresholds in docs/DATA_MODEL.md / verdicts.confidence_band —
// used when only a raw confidence float is available (e.g. FactCheckSummary
// rows on the queue view, which don't carry the derived band).
export function confidenceBandFromValue(confidence: number | null | undefined): ConfidenceBand {
  if (confidence === null || confidence === undefined) return "requires_review";
  if (confidence >= 0.9) return "very_high";
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.6) return "moderate";
  return "requires_review";
}
