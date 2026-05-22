'use client';

import { useMemo, useState } from 'react';
import type { SpuAgg } from '@/lib/aggregate';
import { ExportMenu } from '@/components/shared/ExportMenu';
import { labels } from '@/lib/labels';
import styles from './TopSpuTable.module.css';

interface Props {
  rows: SpuAgg[];
  from?: string;
  to?: string;
}

type SortKey = 'quantity' | 'share' | 'spu_name';
type SortDir = 'asc' | 'desc';

export function TopSpuTable({ rows, from, to }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('quantity');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const sorted = useMemo(() => {
    const mult = sortDir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (sortKey === 'spu_name') return a.spu_name.localeCompare(b.spu_name, 'zh-CN') * mult;
      const av = a[sortKey];
      const bv = b[sortKey];
      return (av - bv) * mult;
    });
  }, [rows, sortKey, sortDir]);

  const toggle = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'spu_name' ? 'asc' : 'desc');
    }
  };

  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' => {
    if (sortKey !== key) return 'none';
    return sortDir === 'asc' ? 'ascending' : 'descending';
  };

  const exportRows = sorted.map((r) => ({
    spu_name: r.spu_name,
    quantity: r.quantity,
    share: `${(r.share * 100).toFixed(2)}%`,
  }));
  const exportColumns = [
    { header: labels.charts.spuName,     accessor: (r: { spu_name: string; quantity: number; share: string }) => r.spu_name },
    { header: labels.charts.spuQuantity, accessor: (r: { spu_name: string; quantity: number; share: string }) => r.quantity },
    { header: labels.charts.spuShare,    accessor: (r: { spu_name: string; quantity: number; share: string }) => r.share },
  ];

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <div>
          <h3 className={styles.title}>{labels.charts.topSpu}</h3>
          <p className={styles.subtitle}>{labels.charts.topSpuSubtitle}</p>
        </div>
        <ExportMenu
          rows={exportRows}
          columns={exportColumns}
          filenameBase="商品TOP10"
          from={from}
          to={to}
        />
      </header>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" aria-sort={ariaSort('spu_name')} className={styles.th}>
                <button type="button" onClick={() => toggle('spu_name')} className={styles.thBtn}>
                  {labels.charts.spuName}
                  <SortIcon active={sortKey === 'spu_name'} dir={sortDir} />
                </button>
              </th>
              <th scope="col" aria-sort={ariaSort('quantity')} className={`${styles.th} ${styles.numeric}`}>
                <button type="button" onClick={() => toggle('quantity')} className={styles.thBtn}>
                  {labels.charts.spuQuantity}
                  <SortIcon active={sortKey === 'quantity'} dir={sortDir} />
                </button>
              </th>
              <th scope="col" aria-sort={ariaSort('share')} className={`${styles.th} ${styles.numeric}`}>
                <button type="button" onClick={() => toggle('share')} className={styles.thBtn}>
                  {labels.charts.spuShare}
                  <SortIcon active={sortKey === 'share'} dir={sortDir} />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr><td colSpan={3} className={styles.empty}>无数据</td></tr>
            )}
            {sorted.map((r, ix) => (
              <tr key={r.spu_name}>
                <td className={styles.cell}>
                  <span className={styles.rank}>{ix + 1}</span>
                  <span className={styles.name}>{r.spu_name}</span>
                </td>
                <td className={`${styles.cell} ${styles.numeric}`}>{r.quantity.toLocaleString('en-US')}</td>
                <td className={`${styles.cell} ${styles.numeric}`}>{(r.share * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span aria-hidden className={styles.sortIcon}>
      {active ? (dir === 'asc' ? '▲' : '▼') : '↕'}
    </span>
  );
}
