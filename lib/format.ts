import type { MetricFormat } from '@/lib/types';

const PERCENT_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const COUNT_FORMATTER = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 0,
});

const SCORE_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DELTA_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
});

export const PENDING_DISPLAY = '数据源待接入';
export const EMPTY_DISPLAY = '—';

// Null = "no data in this window" (use EMPTY_DISPLAY). Use PENDING_DISPLAY only at
// the card level when metric.source === 'pending' — i.e. the source isn't wired yet.
// Returning PENDING_DISPLAY here misleads viewers into thinking the source is missing
// when in reality the aggregation just had zero rows.
export function formatMetricValue(value: number | null, format: MetricFormat): string {
  if (value === null || Number.isNaN(value)) return EMPTY_DISPLAY;
  switch (format) {
    case 'percent':
      return `${PERCENT_FORMATTER.format(value * 100)}%`;
    case 'count':
      return COUNT_FORMATTER.format(Math.round(value));
    case 'score':
      return SCORE_FORMATTER.format(value);
    case 'duration':
      return formatDurationSeconds(value);
    default:
      return String(value);
  }
}

// Cell renderer for the store table; treats a "non-operating" row by returning a dash.
export function formatCell(value: number | null, format: MetricFormat, operating: boolean): string {
  if (!operating) return EMPTY_DISPLAY;
  return formatMetricValue(value, format);
}

export function formatDurationSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s === 0 ? `${m}m` : `${m}m ${s}s`;
}

export function formatDelta(delta: number | null, format: MetricFormat): string {
  if (delta === null || Number.isNaN(delta)) return EMPTY_DISPLAY;
  // Comparisons are always rendered as percent change of the metric value.
  return `${DELTA_FORMATTER.format(delta * 100)}%`;
}

export function formatDate(iso: string): string {
  // ISO YYYY-MM-DD -> MM/DD/YYYY (spec: MM/DD/YYYY display)
  const parts = iso.split('-');
  const y = parts[0] ?? '';
  const m = parts[1] ?? '';
  const d = parts[2] ?? '';
  return `${m}/${d}/${y}`;
}

export function isoToCompact(iso: string): string {
  // YYYY-MM-DD -> MM-DD-YYYY for filenames.
  const parts = iso.split('-');
  const y = parts[0] ?? '';
  const m = parts[1] ?? '';
  const d = parts[2] ?? '';
  return `${m}-${d}-${y}`;
}
