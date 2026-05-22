'use client';

import { useMemo, useState } from 'react';
import type { IntervalSalesAgg } from '@/lib/aggregate';
import { ExportMenu } from '@/components/shared/ExportMenu';
import { labels } from '@/lib/labels';
import styles from './IntervalTable.module.css';

interface Props {
  rows: IntervalSalesAgg[];
  from?: string;
  to?: string;
}

type SortKey = 'slot' | 'delivery' | 'pickup' | 'freshMade' | 'purchased';
type SortDir = 'asc' | 'desc';

const ALL_SLOTS: string[] = (() => {
  const out: string[] = [];
  for (let h = 0; h < 24; h += 1) {
    for (const m of [0, 30]) {
      out.push(`${String(h).padStart(2, '0')}:${m === 0 ? '00' : '30'}`);
    }
  }
  return out;
})();

function padRows(input: IntervalSalesAgg[]): IntervalSalesAgg[] {
  const map = new Map(input.map((r) => [r.slot, r]));
  return ALL_SLOTS.map((slot) => map.get(slot) ?? { slot, pickup: 0, delivery: 0, freshMade: 0, purchased: 0 });
}

export function IntervalSalesTable({ rows, from, to }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('slot');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const padded = useMemo(() => padRows(rows), [rows]);

  const sorted = useMemo(() => {
    const mult = sortDir === 'asc' ? 1 : -1;
    return [...padded].sort((a, b) => {
      if (sortKey === 'slot') return a.slot.localeCompare(b.slot) * mult;
      return (a[sortKey] - b[sortKey]) * mult;
    });
  }, [padded, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'slot' ? 'asc' : 'desc');
    }
  };
  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' => {
    if (sortKey !== key) return 'none';
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const totals = useMemo(() => sorted.reduce((acc, r) => ({
    pickup: acc.pickup + r.pickup,
    delivery: acc.delivery + r.delivery,
    freshMade: acc.freshMade + r.freshMade,
    purchased: acc.purchased + r.purchased,
  }), { pickup: 0, delivery: 0, freshMade: 0, purchased: 0 }), [sorted]);

  const exportColumns = [
    { header: labels.intervalSales.slot,       accessor: (r: IntervalSalesAgg) => r.slot },
    { header: labels.intervalSales.delivery,   accessor: (r: IntervalSalesAgg) => r.delivery },
    { header: labels.intervalSales.pickup,     accessor: (r: IntervalSalesAgg) => r.pickup },
    { header: labels.intervalSales.freshMade,  accessor: (r: IntervalSalesAgg) => r.freshMade },
    { header: labels.intervalSales.purchased,  accessor: (r: IntervalSalesAgg) => r.purchased },
  ];

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>{labels.intervalSales.title}</h3>
          <p className={styles.subtitle}>{labels.intervalSales.subtitle}</p>
        </div>
        <ExportMenu rows={sorted} columns={exportColumns} filenameBase="区间销售明细" from={from} to={to} />
      </header>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              {([
                ['slot', labels.intervalSales.slot, false],
                ['delivery', labels.intervalSales.delivery, true],
                ['pickup', labels.intervalSales.pickup, true],
                ['freshMade', labels.intervalSales.freshMade, true],
                ['purchased', labels.intervalSales.purchased, true],
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
                <td className={`${styles.cell} ${styles.numeric}`}>{r.delivery.toLocaleString('en-US')}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.pickup.toLocaleString('en-US')}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.freshMade.toLocaleString('en-US')}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.purchased.toLocaleString('en-US')}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className={styles.footerCell}>{labels.table.totals}</td>
              <td className={`${styles.footerCell} ${styles.numeric}`}>{totals.delivery.toLocaleString('en-US')}</td>
              <td className={`${styles.footerCell} ${styles.numeric}`}>{totals.pickup.toLocaleString('en-US')}</td>
              <td className={`${styles.footerCell} ${styles.numeric}`}>{totals.freshMade.toLocaleString('en-US')}</td>
              <td className={`${styles.footerCell} ${styles.numeric}`}>{totals.purchased.toLocaleString('en-US')}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
