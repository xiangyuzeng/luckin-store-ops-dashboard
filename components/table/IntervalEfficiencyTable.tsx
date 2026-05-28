'use client';

import { useMemo, useState } from 'react';
import type { IntervalEffAgg } from '@/lib/aggregate';
import { ExportMenu } from '@/components/shared/ExportMenu';
import { labels } from '@/lib/labels';
import { formatDurationSeconds } from '@/lib/format';
import styles from './IntervalTable.module.css';

interface Props {
  rows: IntervalEffAgg[];
  from?: string;
  to?: string;
}

type SortKey = 'slot' | 'accept' | 'make' | 'total';
type SortDir = 'asc' | 'desc';

// ET operating hours 06:00–21:30 (32 half-hour slots). Slots outside this
// window were almost always empty in NA and added noise.
const ALL_SLOTS: string[] = (() => {
  const out: string[] = [];
  for (let h = 6; h <= 21; h += 1) {
    for (const m of [0, 30]) out.push(`${String(h).padStart(2, '0')}:${m === 0 ? '00' : '30'}`);
  }
  return out;
})();

function padRows(input: IntervalEffAgg[]): IntervalEffAgg[] {
  const map = new Map(input.map((r) => [r.slot, r]));
  return ALL_SLOTS.map((slot) => map.get(slot) ?? {
    slot,
    acceptSec: null,
    makeSec: null,
    totalSec: null,
    orderCount: 0,
    equivCount: 0,
  });
}

function cmpNullable(a: number | null, b: number | null, mult: number): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return (a - b) * mult;
}

export function IntervalEfficiencyTable({ rows, from, to }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('slot');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const padded = useMemo(() => padRows(rows), [rows]);
  const sorted = useMemo(() => {
    const mult = sortDir === 'asc' ? 1 : -1;
    return [...padded].sort((a, b) => {
      if (sortKey === 'slot') return a.slot.localeCompare(b.slot) * mult;
      if (sortKey === 'accept') return cmpNullable(a.acceptSec, b.acceptSec, mult);
      if (sortKey === 'make') return cmpNullable(a.makeSec, b.makeSec, mult);
      return cmpNullable(a.totalSec, b.totalSec, mult);
    });
  }, [padded, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir(key === 'slot' ? 'asc' : 'desc');
    }
  };
  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' => {
    if (sortKey !== key) return 'none';
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const exportColumns = [
    { header: labels.intervalEfficiency.slot,   accessor: (r: IntervalEffAgg) => r.slot },
    { header: labels.intervalEfficiency.accept, accessor: (r: IntervalEffAgg) => r.acceptSec === null ? '' : formatDurationSeconds(r.acceptSec) },
    { header: labels.intervalEfficiency.make,   accessor: (r: IntervalEffAgg) => r.makeSec === null ? '' : formatDurationSeconds(r.makeSec) },
    { header: labels.intervalEfficiency.total,  accessor: (r: IntervalEffAgg) => r.totalSec === null ? '' : formatDurationSeconds(r.totalSec) },
  ];

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>{labels.intervalEfficiency.title}</h3>
          <p className={styles.subtitle}>{labels.intervalEfficiency.subtitle}</p>
        </div>
        <ExportMenu rows={sorted} columns={exportColumns} filenameBase="区间效能明细" from={from} to={to} />
      </header>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              {([
                ['slot',  labels.intervalEfficiency.slot,   false],
                ['accept', labels.intervalEfficiency.accept, true],
                ['make',   labels.intervalEfficiency.make,   true],
                ['total',  labels.intervalEfficiency.total,  true],
              ] as Array<[SortKey, string, boolean]>).map(([k, lbl, numeric]) => (
                <th
                  key={k}
                  scope="col"
                  aria-sort={ariaSort(k)}
                  className={`${styles.th} ${numeric ? styles.numeric : ''}`}
                >
                  <button type="button" className={styles.thBtn} onClick={() => toggle(k)}>
                    <span>{lbl}</span>
                    <span aria-hidden className={styles.sortIcon}>
                      {sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.slot}>
                <td className={styles.cell}>{r.slot}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.acceptSec === null ? '—' : formatDurationSeconds(r.acceptSec)}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.makeSec === null ? '—' : formatDurationSeconds(r.makeSec)}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.totalSec === null ? '—' : formatDurationSeconds(r.totalSec)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
