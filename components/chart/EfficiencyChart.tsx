'use client';

import { useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  Legend,
  Line,
  ComposedChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { IntervalEffAgg } from '@/lib/aggregate';
import { labels } from '@/lib/labels';
import { formatDurationSeconds } from '@/lib/format';
import styles from './EfficiencyChart.module.css';

interface Props {
  data: IntervalEffAgg[];
}

interface TipPayloadEntry {
  name?: string;
  value?: number | null;
  color?: string;
}

interface TipProps {
  active?: boolean;
  payload?: TipPayloadEntry[];
  label?: string;
}

function Tip({ active, payload, label }: TipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className={styles.tip}>
      <div className={styles.tipSlot}>{label}</div>
      {payload.map((p) => (
        <div key={p.name} className={styles.tipRow}>
          <span className={styles.dot} style={{ background: p.color }} aria-hidden />
          <span className={styles.tipName}>{p.name}</span>
          <span className={styles.tipVal}>{typeof p.value === 'number' ? formatDurationSeconds(p.value) : '—'}</span>
        </div>
      ))}
    </div>
  );
}

function findPeakSlot(data: IntervalEffAgg[]): { from: string; to: string } | null {
  // Peak by order volume; highlight ±30min around the slot with the most orders.
  if (data.length === 0) return null;
  let peakIx = 0;
  for (let i = 1; i < data.length; i += 1) {
    const a = data[peakIx];
    const b = data[i];
    if (!a || !b) continue;
    if (b.orderCount > a.orderCount) peakIx = i;
  }
  const prev = data[Math.max(0, peakIx - 1)];
  const next = data[Math.min(data.length - 1, peakIx + 1)];
  if (!prev || !next) return null;
  return { from: prev.slot, to: next.slot };
}

export function EfficiencyChart({ data }: Props) {
  const peak = useMemo(() => findPeakSlot(data), [data]);
  const empty = data.length === 0 || data.every((d) => d.orderCount === 0);

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>{labels.efficiency.chartTitle}</h2>
          <p className={styles.subtitle}>{labels.efficiency.chartHint}</p>
        </div>
        {peak && !empty && (
          <span className={styles.peakBadge}>
            峰值时段 {peak.from}–{peak.to}
          </span>
        )}
      </header>

      {empty ? (
        <div className={styles.empty}>所选范围内无数据</div>
      ) : (
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={data} margin={{ top: 10, right: 24, bottom: 8, left: 0 }}>
            <defs>
              <linearGradient id="total-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#4A90D9" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#4A90D9" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis
              dataKey="slot"
              interval={3}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-border-strong)' }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-border-strong)' }}
              tickFormatter={(v: number) => formatDurationSeconds(Number(v))}
              width={64}
            />
            {peak && (
              <ReferenceArea x1={peak.from} x2={peak.to} fill="#F59E0B" fillOpacity={0.08} strokeOpacity={0} />
            )}
            <Tooltip content={<Tip />} />
            <Legend
              iconSize={10}
              iconType="circle"
              wrapperStyle={{ fontSize: 12, color: 'var(--color-text-muted)', paddingTop: 8 }}
            />
            <Area
              type="monotone"
              dataKey="totalSec"
              name={labels.efficiency.totalDuration}
              stroke="#4A90D9"
              strokeWidth={2}
              fill="url(#total-fill)"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="acceptSec"
              name={labels.efficiency.acceptResponse}
              stroke="#14B8A6"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="makeSec"
              name={labels.efficiency.makeDuration}
              stroke="#0A2E6C"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
