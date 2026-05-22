'use client';

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { ExportMenu } from '@/components/shared/ExportMenu';
import { labels } from '@/lib/labels';
import styles from './SharePieChart.module.css';

export interface ShareSlice {
  name: string;     // e.g. "自取"
  value: number;    // raw count
  share: number;    // 0..1 (precomputed Σnum/Σden)
  color: string;
}

interface Props {
  title: string;
  subtitle: string;
  slices: ShareSlice[];
  total: number;
  variant?: 'donut' | 'pie';
  filenameBase: string;
  from?: string;
  to?: string;
}

interface TooltipPayloadEntry {
  payload?: ShareSlice;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
}

function TooltipBox({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const slice = payload[0]?.payload;
  if (!slice) return null;
  return (
    <div className={styles.tip}>
      <div className={styles.tipName}>
        <span className={styles.dot} style={{ background: slice.color }} aria-hidden />
        {slice.name}
      </div>
      <div className={styles.tipVal}>{slice.value.toLocaleString('en-US')} 件</div>
      <div className={styles.tipShare}>{(slice.share * 100).toFixed(2)}%</div>
    </div>
  );
}

function renderLabel(entry: { share?: number }): string {
  if (typeof entry.share !== 'number') return '';
  return `${(entry.share * 100).toFixed(2)}%`;
}

export function SharePieChart({
  title,
  subtitle,
  slices,
  total,
  variant = 'donut',
  filenameBase,
  from,
  to,
}: Props) {
  const exportRows = slices.map((s) => ({ name: s.name, value: s.value, share: `${(s.share * 100).toFixed(2)}%` }));
  const exportColumns = [
    { header: '类型',     accessor: (r: { name: string; value: number; share: string }) => r.name },
    { header: '数量',     accessor: (r: { name: string; value: number; share: string }) => r.value },
    { header: '占比 (%)', accessor: (r: { name: string; value: number; share: string }) => r.share },
  ];

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>{title}</h3>
          <p className={styles.subtitle}>{subtitle} {labels.charts.legendRawCounts(total)}</p>
        </div>
        <ExportMenu rows={exportRows} columns={exportColumns} filenameBase={filenameBase} from={from} to={to} />
      </header>

      <div className={styles.chart}>
        {total === 0 ? (
          <div className={styles.empty}>无数据</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="name"
                innerRadius={variant === 'donut' ? 60 : 0}
                outerRadius={92}
                paddingAngle={variant === 'donut' ? 2 : 0}
                label={renderLabel}
                labelLine={false}
                stroke="var(--color-surface)"
                strokeWidth={2}
              >
                {slices.map((s) => (
                  <Cell key={s.name} fill={s.color} />
                ))}
              </Pie>
              <Tooltip content={<TooltipBox />} />
              <Legend
                iconSize={10}
                iconType="circle"
                wrapperStyle={{ fontSize: 12, color: 'var(--color-text-muted)' }}
                formatter={(value, entry) => {
                  const payload = entry?.payload as ShareSlice | undefined;
                  if (!payload) return value;
                  return `${value} · ${(payload.share * 100).toFixed(2)}%`;
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
