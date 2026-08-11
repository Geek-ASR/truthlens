import {
  CONFIDENCE_COLORS,
  CONFIDENCE_LABELS,
  STATUS_COLORS,
  STATUS_LABELS,
  VERDICT_COLORS,
  VERDICT_LABELS,
} from "@/lib/brand";
import { formatPercent } from "@/lib/format";
import type { ConfidenceBand, FactCheckStatus, VerdictLabel } from "@/lib/types";

function BasePill({
  color,
  bg,
  children,
}: {
  color: string;
  bg: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className="pill"
      style={{ color, background: bg, borderColor: color }}
    >
      {children}
    </span>
  );
}

function tint(hex: string): string {
  // Cheap alpha-tint by appending hex alpha; works for #RRGGBB values.
  return `${hex}1A`;
}

export function VerdictBadge({ verdict }: { verdict: VerdictLabel | string }) {
  const color = VERDICT_COLORS[verdict as VerdictLabel] ?? "#6B7280";
  const label = VERDICT_LABELS[verdict as VerdictLabel] ?? verdict;
  return (
    <BasePill color={color} bg={tint(color)}>
      {label}
    </BasePill>
  );
}

export function StatusBadge({ status }: { status: FactCheckStatus | string }) {
  const color = STATUS_COLORS[status as FactCheckStatus] ?? "#6B7280";
  const label = STATUS_LABELS[status as FactCheckStatus] ?? status;
  return (
    <BasePill color={color} bg={tint(color)}>
      {label}
    </BasePill>
  );
}

export function ConfidenceBadge({
  band,
  confidence,
}: {
  band: ConfidenceBand | string;
  confidence?: number | null;
}) {
  const color = CONFIDENCE_COLORS[band as ConfidenceBand] ?? "#6B7280";
  const label = CONFIDENCE_LABELS[band as ConfidenceBand] ?? band;
  return (
    <BasePill color={color} bg={tint(color)}>
      {label}
      {confidence !== undefined && confidence !== null ? ` · ${formatPercent(confidence)}` : ""}
    </BasePill>
  );
}
