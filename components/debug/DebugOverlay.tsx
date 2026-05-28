'use client';

// Render only when URL contains ?debug=1. Shows source_status, collector
// timestamps, per-metric row coverage in the current filtered window, and the
// raw aggregated value for each card. Intended for ops-team audits — no PII,
// metadata only, safe to expose on the public deployment.

import { useMemo } from 'react';
import type { DailyStoreRow, MetricKey, Payload, ShopNo } from '@/lib/types';
import { METRICS } from '@/lib/metrics';
import { getMetricValue, filterDaily } from '@/lib/aggregate';
import styles from './DebugOverlay.module.css';

interface Props {
  payload: Payload;
  filtered: DailyStoreRow[];
  from: string;
  to: string;
  shopNos: ShopNo[] | null;
}

// Each metric needs at least one field populated on a row to count it as "row coverage".
// Mapping is kept close to the aggregator branches in lib/aggregate.ts.
const COVERAGE_FIELDS: Record<MetricKey, (keyof DailyStoreRow)[]> = {
  orderCount: ['order_count'],
  productCount: ['product_count'],
  satisfaction: ['satisfaction'],
  hourlyCups: ['labor_hours_total', 'equiv_product_count'],
  perfHourlyCups: ['labor_hours_productive', 'equiv_product_count'],
  hourlyCupAchieve: ['hourly_cup_achieve'],
  qcPassRate: ['qc_pass_rate'],
  qcAvgScore: ['qc_avg_score'],
  materialLossRate: ['material_loss_rate'],
  avgDailyProducts: ['avg_daily_products'],
  avgDailyFreshMade: ['avg_daily_fresh_made'],
  avgDailyEquiv: ['avg_daily_equiv'],
  efficiencyDuration: ['accept_response_duration', 'make_duration'],
  pickupCount: ['pickup_count'],
  deliveryCount: ['delivery_count'],
  freshMadeCount: ['fresh_made_count'],
};

function rowHasField(row: DailyStoreRow, fields: (keyof DailyStoreRow)[]): boolean {
  return fields.every((f) => {
    const v = row[f];
    if (v === null || v === undefined) return false;
    if (typeof v === 'object') {
      // pair { num, den } or { total_seconds, weight } — both should be non-null
      const obj = v as unknown as Record<string, unknown>;
      return Object.values(obj).some((x) => x !== null && x !== undefined && x !== 0);
    }
    return true;
  });
}

export function DebugOverlay({ payload, filtered, from, to, shopNos }: Props) {
  const { meta } = payload;

  // Per-metric coverage in the currently filtered window.
  const coverage = useMemo(() => {
    const out: Array<{
      key: MetricKey;
      label: string;
      source: string;
      populated: number;
      total: number;
      value: number | null;
      collectorTs?: string;
    }> = [];
    for (const m of METRICS) {
      const fields = COVERAGE_FIELDS[m.key];
      let populated = 0;
      for (const r of filtered) {
        if (rowHasField(r, fields)) populated += 1;
      }
      out.push({
        key: m.key,
        label: m.label_zh,
        source: meta.source_status?.[m.key] ?? m.source,
        populated,
        total: filtered.length,
        value: getMetricValue(filtered, m.key),
        collectorTs: meta.collector_timestamps?.[m.key],
      });
    }
    return out;
  }, [filtered, meta]);

  // Suppress no-op warning for unused filterDaily import in some build configs.
  void filterDaily;

  const generatedAge = useMemo(() => {
    const gen = new Date(meta.generated_at).getTime();
    const mins = Math.max(0, Math.round((Date.now() - gen) / 60000));
    if (mins < 60) return `${mins}m ago`;
    if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
    return `${Math.floor(mins / 1440)}d ago`;
  }, [meta.generated_at]);

  return (
    <aside className={styles.overlay} aria-label="Debug overlay">
      <header className={styles.header}>
        <strong>Debug overlay</strong>
        <span className={styles.meta}>?debug=1</span>
      </header>
      <div className={styles.section}>
        <div className={styles.kv}><span>Payload generated</span><span>{meta.generated_at} ({generatedAge})</span></div>
        <div className={styles.kv}><span>Retention</span><span>{meta.retained_from} → {meta.retained_to}</span></div>
        <div className={styles.kv}><span>Window</span><span>{from} → {to}</span></div>
        <div className={styles.kv}><span>Stores</span><span>{shopNos === null ? 'ALL' : `${shopNos.length} selected`}</span></div>
        <div className={styles.kv}><span>Rows in window</span><span>{filtered.length}</span></div>
        {meta.theoretical_hourly_cups !== undefined && (
          <div className={styles.kv}><span>THEORETICAL_HOURLY_CUPS</span><span>{meta.theoretical_hourly_cups}</span></div>
        )}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Source</th>
            <th>Rows w/ data</th>
            <th>Value</th>
            <th>Collector run</th>
          </tr>
        </thead>
        <tbody>
          {coverage.map((c) => (
            <tr key={c.key} className={c.value === null ? styles.rowNull : ''}>
              <td>{c.label}<div className={styles.sub}>{c.key}</div></td>
              <td><span className={`${styles.pill} ${styles[`pill_${c.source}`] ?? ''}`}>{c.source}</span></td>
              <td className={styles.numeric}>{c.populated} / {c.total}</td>
              <td className={styles.numeric}>{c.value === null ? '—' : Number.isFinite(c.value) ? c.value.toFixed(4) : String(c.value)}</td>
              <td className={styles.sub}>{c.collectorTs ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </aside>
  );
}
