import type { ISO8601 } from '@/lib/types';

export interface Freshness {
  generatedAt: ISO8601;
  ageMinutes: number;
  isStale: boolean;
}

const DEFAULT_STALE_MIN = 60 * 24; // 24h — pipeline runs daily

export function freshness(generatedAt: ISO8601, staleMin: number = DEFAULT_STALE_MIN, now: Date = new Date()): Freshness {
  const generated = new Date(generatedAt).getTime();
  const ageMs = now.getTime() - generated;
  const ageMinutes = Math.max(0, Math.round(ageMs / 60000));
  return {
    generatedAt,
    ageMinutes,
    isStale: ageMinutes > staleMin,
  };
}

export function formatAge(mins: number): string {
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} 分钟前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} 小时前`;
  const days = Math.floor(hrs / 24);
  return `${days} 天前`;
}

// Metrics whose upstream source is T+1 (labor + QC). When the selected window
// includes today, the empty-value reason is "today not yet settled" rather than
// a generic "no data".
const T_PLUS_1_METRIC_KEYS = new Set([
  'hourlyCups',
  'perfHourlyCups',
  'hourlyCupAchieve',
  'qcPassRate',
  'qcAvgScore',
]);

export function emptyReasonFor(
  metricKey: string,
  from: ISO8601,
  to: ISO8601,
  retainedTo: ISO8601,
): string {
  if (T_PLUS_1_METRIC_KEYS.has(metricKey) && to >= retainedTo) {
    return from === to ? '今日尚未结算' : '今日尚未结算，可前移区间';
  }
  if (metricKey === 'qcPassRate' || metricKey === 'qcAvgScore') {
    return '本周期无稽核记录';
  }
  return '本周期无数据';
}
