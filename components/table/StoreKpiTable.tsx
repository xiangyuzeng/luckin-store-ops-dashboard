'use client';

import { useMemo, useState } from 'react';
import type { DailyStoreRow, MetricKey, StoreInfo } from '@/lib/types';
import { METRIC_BY_KEY, STORE_TABLE_COLUMNS } from '@/lib/metrics';
import { getMetricValue } from '@/lib/aggregate';
import { formatCell, formatMetricValue } from '@/lib/format';
import { labels } from '@/lib/labels';
import { ExportMenu } from '@/components/shared/ExportMenu';
import styles from './StoreKpiTable.module.css';

interface Props {
  stores: StoreInfo[];
  daily: DailyStoreRow[];
  from: string;
  to: string;
  selectedShop: string | null; // when set, only that row is highlighted (drill-down state lives in parent)
  onSelectShop?: (shopNo: string | null) => void;
}

type SortDir = 'asc' | 'desc';
type SortKey = 'city' | 'region' | 'shop' | MetricKey;

interface ComputedRow {
  store: StoreInfo;
  operating: boolean;
  values: Partial<Record<MetricKey, number | null>>;
}

function isOperatingInRange(rows: DailyStoreRow[]): boolean {
  return rows.some((r) => r.operating);
}

function computeRows(stores: StoreInfo[], daily: DailyStoreRow[], from: string, to: string): ComputedRow[] {
  // Index daily rows by shop for O(N) per shop lookup.
  const byShop = new Map<string, DailyStoreRow[]>();
  for (const r of daily) {
    if (r.date < from || r.date > to) continue;
    let arr = byShop.get(r.shop_no);
    if (!arr) {
      arr = [];
      byShop.set(r.shop_no, arr);
    }
    arr.push(r);
  }
  return stores.map((store) => {
    const rows = byShop.get(store.shop_no) ?? [];
    const operating = isOperatingInRange(rows);
    const values: Partial<Record<MetricKey, number | null>> = {};
    for (const k of STORE_TABLE_COLUMNS) {
      values[k] = operating ? getMetricValue(rows, k) : null;
    }
    return { store, operating, values };
  });
}

function compareForSort(a: ComputedRow, b: ComputedRow, key: SortKey, dir: SortDir): number {
  const mult = dir === 'asc' ? 1 : -1;
  let av: number | string | null = null;
  let bv: number | string | null = null;
  if (key === 'city') { av = a.store.city; bv = b.store.city; }
  else if (key === 'region') { av = a.store.region; bv = b.store.region; }
  else if (key === 'shop') { av = a.store.shop_name; bv = b.store.shop_name; }
  else { av = a.values[key] ?? null; bv = b.values[key] ?? null; }
  // nulls sort last regardless of dir
  if (av === null && bv === null) return 0;
  if (av === null) return 1;
  if (bv === null) return -1;
  if (typeof av === 'string' && typeof bv === 'string') return av.localeCompare(bv, 'zh-CN') * mult;
  return ((av as number) - (bv as number)) * mult;
}

// Conditional formatting — render a subtle data bar overlay sized to the row's value
// vs the column's range. Returns null when value is null or all values are equal.
function dataBarStyle(value: number | null, min: number | null, max: number | null, isInverse: boolean): React.CSSProperties | undefined {
  if (value === null || min === null || max === null || max === min) return undefined;
  // For "good_direction=down" metrics (loss rate, duration), invert the fill so lower is greener.
  const ratio = (value - min) / (max - min);
  const filled = isInverse ? 1 - ratio : ratio;
  const pct = Math.max(0, Math.min(1, filled)) * 100;
  return {
    background: `linear-gradient(90deg, rgba(74, 144, 217, 0.14) 0%, rgba(74, 144, 217, 0.14) ${pct}%, transparent ${pct}%)`,
  };
}

interface ColumnRange {
  min: number | null;
  max: number | null;
}

function computeRanges(rows: ComputedRow[]): Record<MetricKey, ColumnRange> {
  const out = {} as Record<MetricKey, ColumnRange>;
  for (const k of STORE_TABLE_COLUMNS) {
    let min: number | null = null;
    let max: number | null = null;
    for (const r of rows) {
      const v = r.values[k];
      if (v === null || v === undefined) continue;
      if (min === null || v < min) min = v;
      if (max === null || v > max) max = v;
    }
    out[k] = { min, max };
  }
  return out;
}

function computeFooter(daily: DailyStoreRow[], from: string, to: string): Partial<Record<MetricKey, number | null>> {
  const inRange = daily.filter((r) => r.date >= from && r.date <= to);
  const totals: Partial<Record<MetricKey, number | null>> = {};
  for (const k of STORE_TABLE_COLUMNS) {
    totals[k] = getMetricValue(inRange, k);
  }
  return totals;
}

const ARIA_SORT: Record<'none' | SortDir, 'none' | 'ascending' | 'descending'> = {
  none: 'none',
  asc: 'ascending',
  desc: 'descending',
};

export function StoreKpiTable({ stores, daily, from, to, selectedShop, onSelectShop }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('shop');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const computed = useMemo(() => computeRows(stores, daily, from, to), [stores, daily, from, to]);

  const sorted = useMemo(() => {
    const arr = [...computed];
    arr.sort((a, b) => compareForSort(a, b, sortKey, sortDir));
    return arr;
  }, [computed, sortKey, sortDir]);

  const ranges = useMemo(() => computeRanges(computed), [computed]);
  const footer = useMemo(() => computeFooter(daily, from, to), [daily, from, to]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'shop' || key === 'city' || key === 'region' ? 'asc' : 'desc');
    }
  };

  const exportRows = sorted.map((r) => {
    const out: Record<string, string | number> = {
      city: r.store.city,
      region: r.store.region,
      store: `${r.store.shop_name} (${r.store.shop_no})`,
    };
    for (const k of STORE_TABLE_COLUMNS) {
      const def = METRIC_BY_KEY[k];
      out[k] = formatCell(r.values[k] ?? null, def.format, r.operating);
    }
    return out;
  });

  const exportColumns = [
    { header: labels.table.city, accessor: (r: Record<string, string | number>) => r.city ?? '' },
    { header: labels.table.region, accessor: (r: Record<string, string | number>) => r.region ?? '' },
    { header: labels.table.store, accessor: (r: Record<string, string | number>) => r.store ?? '' },
    ...STORE_TABLE_COLUMNS.map((k) => ({
      header: METRIC_BY_KEY[k].label_zh,
      accessor: (r: Record<string, string | number>) => r[k] ?? '',
    })),
  ];

  return (
    <section className={styles.wrap}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>门店运营指标</h2>
          <p className={styles.subtitle}>共 {stores.length} 家门店 · {sorted.filter((r) => r.operating).length} 家在所选范围内运营</p>
        </div>
        <ExportMenu
          rows={exportRows}
          columns={exportColumns}
          filenameBase="门店KPI"
          from={from}
          to={to}
        />
      </header>

      <div className={styles.tableScroll}>
        <table className={styles.table} role="grid">
          <thead>
            <tr>
              <Th id="city" label={labels.table.city} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} sticky="col1" />
              <Th id="region" label={labels.table.region} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} sticky="col2" />
              <Th id="shop" label={labels.table.store} sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} sticky="col3" />
              {STORE_TABLE_COLUMNS.map((k) => (
                <Th
                  key={k}
                  id={k}
                  label={METRIC_BY_KEY[k].label_zh}
                  sortKey={sortKey}
                  sortDir={sortDir}
                  onClick={toggleSort}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td className={styles.empty} colSpan={3 + STORE_TABLE_COLUMNS.length}>
                  {labels.table.noOperatingStores}
                </td>
              </tr>
            )}
            {sorted.map((r) => {
              const selected = selectedShop === r.store.shop_no;
              return (
                <tr
                  key={r.store.shop_no}
                  className={`${styles.row} ${selected ? styles.rowSelected : ''} ${!r.operating ? styles.rowDim : ''}`}
                  onClick={() => onSelectShop?.(selected ? null : r.store.shop_no)}
                  tabIndex={onSelectShop ? 0 : -1}
                  onKeyDown={(e) => {
                    if (!onSelectShop) return;
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectShop(selected ? null : r.store.shop_no);
                    }
                  }}
                  aria-selected={selected}
                >
                  <td className={`${styles.cell} ${styles.col1}`}>{r.store.city}</td>
                  <td className={`${styles.cell} ${styles.col2}`}>{r.store.region}</td>
                  <td className={`${styles.cell} ${styles.col3} ${styles.shopCell}`}>
                    <span className={styles.shopName}>{r.store.shop_name}</span>
                    <span className={styles.shopNo}>{r.store.shop_no}</span>
                  </td>
                  {STORE_TABLE_COLUMNS.map((k) => {
                    const def = METRIC_BY_KEY[k];
                    const v = r.values[k] ?? null;
                    const range = ranges[k];
                    const inverse = def.good_direction === 'down';
                    const style = r.operating && def.source === 'confirmed'
                      ? dataBarStyle(v, range.min, range.max, inverse)
                      : undefined;
                    return (
                      <td
                        key={k}
                        className={`${styles.cell} ${styles.numeric} ${def.source !== 'confirmed' ? styles.cellSoft : ''}`}
                        style={style}
                      >
                        {formatCell(v, def.format, r.operating)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td className={`${styles.footerCell} ${styles.col1}`} colSpan={3}>{labels.table.totals}</td>
              {STORE_TABLE_COLUMNS.map((k) => {
                const def = METRIC_BY_KEY[k];
                const v = footer[k] ?? null;
                return (
                  <td key={k} className={`${styles.footerCell} ${styles.numeric}`}>
                    {formatMetricValue(v, def.format)}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

interface ThProps {
  id: SortKey;
  label: string;
  sortKey: SortKey;
  sortDir: SortDir;
  onClick: (id: SortKey) => void;
  sticky?: 'col1' | 'col2' | 'col3';
}

function Th({ id, label, sortKey, sortDir, onClick, sticky }: ThProps) {
  const isActive = sortKey === id;
  const dir: 'none' | SortDir = isActive ? sortDir : 'none';
  const stickyCls = sticky ? styles[sticky] : '';
  return (
    <th
      scope="col"
      aria-sort={ARIA_SORT[dir]}
      className={`${styles.th} ${stickyCls}`}
    >
      <button
        type="button"
        className={styles.thButton}
        onClick={() => onClick(id)}
        aria-label={`${label} ${isActive ? (sortDir === 'asc' ? labels.table.sortDesc : labels.table.sortAsc) : labels.table.sortAsc}`}
      >
        <span>{label}</span>
        <span className={styles.sortIcon} aria-hidden>
          {isActive ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  );
}
