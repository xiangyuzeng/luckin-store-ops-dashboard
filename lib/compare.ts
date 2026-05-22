// Comparison logic — given a current range, derive the prior range for wow/mom/sequential
// and compute the percentage change of the metric value.

import type { ComparisonKind, DailyStoreRow, GoodDirection, MetricKey, ShopNo } from '@/lib/types';
import { filterDaily, getMetricValue } from '@/lib/aggregate';

export interface DateRange {
  from: string; // ISO YYYY-MM-DD
  to: string;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function diffDaysInclusive(from: string, to: string): number {
  const a = new Date(from + 'T00:00:00Z').getTime();
  const b = new Date(to + 'T00:00:00Z').getTime();
  return Math.round((b - a) / 86400000) + 1;
}

function addMonths(iso: string, months: number): string {
  const [y, m, d] = iso.split('-').map((v) => parseInt(v, 10));
  if (!y || !m || !d) return iso;
  // Use UTC components to avoid local-zone drift.
  const dt = new Date(Date.UTC(y, m - 1 + months, 1));
  // Clamp to month-end if the target month is shorter.
  const lastDay = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
  dt.setUTCDate(Math.min(d, lastDay));
  return dt.toISOString().slice(0, 10);
}

export function priorRange(current: DateRange, kind: ComparisonKind): DateRange {
  if (kind === 'sequential') {
    const len = diffDaysInclusive(current.from, current.to);
    return { from: addDays(current.from, -len), to: addDays(current.from, -1) };
  }
  if (kind === 'wow') {
    return { from: addDays(current.from, -7), to: addDays(current.to, -7) };
  }
  // mom
  return { from: addMonths(current.from, -1), to: addMonths(current.to, -1) };
}

export interface ComparisonResult {
  kind: ComparisonKind;
  current: number | null;
  prior: number | null;
  delta: number | null; // (current - prior) / prior; null when prior is 0 or unavailable
}

export function computeComparison(
  daily: DailyStoreRow[],
  shopNos: ShopNo[] | null,
  current: DateRange,
  retainedFrom: string,
  kind: ComparisonKind,
  metricKey: MetricKey,
): ComparisonResult {
  const prior = priorRange(current, kind);
  const priorInRetention = prior.from >= retainedFrom;

  const currentRows = filterDaily(daily, shopNos, current.from, current.to);
  const currentValue = getMetricValue(currentRows, metricKey);

  let priorValue: number | null = null;
  if (priorInRetention) {
    const priorRows = filterDaily(daily, shopNos, prior.from, prior.to);
    priorValue = getMetricValue(priorRows, metricKey);
  }

  let delta: number | null = null;
  if (currentValue !== null && priorValue !== null && priorValue !== 0) {
    delta = (currentValue - priorValue) / priorValue;
  }
  return { kind, current: currentValue, prior: priorValue, delta };
}

// Tone of the comparison badge. Up by default is positive; when goodDirection==='down' it flips.
export type DeltaTone = 'positive' | 'negative' | 'neutral';

export function deltaTone(delta: number | null, dir: GoodDirection): DeltaTone {
  if (delta === null || delta === 0) return 'neutral';
  const goingUp = delta > 0;
  if (dir === 'up') return goingUp ? 'positive' : 'negative';
  return goingUp ? 'negative' : 'positive';
}
