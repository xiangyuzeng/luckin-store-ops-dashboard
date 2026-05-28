'use client';

// HomeBoard renders the 门店看板 layout. Filter state lives here (initialized
// to defaults so SSR has real data) and is synced to/from the URL by
// useUrlFilters — no useSearchParams, no Suspense fallback needed.

import { useMemo, useState } from 'react';
import { FilterBar } from '@/components/layout/FilterBar';
import { DebugOverlay } from '@/components/debug/DebugOverlay';
import { KpiCard } from '@/components/kpi/KpiCard';
import { KpiGroup } from '@/components/kpi/KpiGroup';
import { StoreKpiTable } from '@/components/table/StoreKpiTable';
import { SharePieChart, type ShareSlice } from '@/components/chart/SharePieChart';
import { TopSpuTable } from '@/components/table/TopSpuTable';
import { IntervalSalesTable } from '@/components/table/IntervalSalesTable';
import { KPI_GROUPS, METRIC_BY_KEY } from '@/lib/metrics';
import {
  aggregateCategoryShare,
  aggregateChannelShare,
  aggregateIntervalSales,
  aggregateSpuTopN,
  filterDaily,
  filterHalfHourSales,
  filterSpuDaily,
  getMetricValue,
} from '@/lib/aggregate';
import { computeComparison } from '@/lib/compare';
import { normalize } from '@/lib/filters';
import { useUrlFilters } from '@/lib/use-url-filters';
import { emptyReasonFor } from '@/lib/freshness';
import { labels } from '@/lib/labels';
import type { Payload } from '@/lib/types';
import styles from './home.module.css';

interface Props {
  payload: Payload;
}

export function HomeBoard({ payload }: Props) {
  const [filters, setFilters] = useUrlFilters(payload);
  const normalized = useMemo(() => normalize(filters, payload), [filters, payload]);
  const [selectedShop, setSelectedShop] = useState<string | null>(null);
  const debugEnabled = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('debug') === '1';

  // shopNos for aggregation: drill-down (row click) overrides the filter dropdown.
  const aggShopNos = useMemo(
    () => (selectedShop ? [selectedShop] : normalized.shopNos),
    [selectedShop, normalized.shopNos],
  );

  const rangeRows = useMemo(
    () => filterDaily(payload.daily_store_rows, aggShopNos, normalized.from, normalized.to),
    [payload.daily_store_rows, aggShopNos, normalized.from, normalized.to],
  );

  const halfHourSales = useMemo(
    () => filterHalfHourSales(payload.half_hour_sales_rows, aggShopNos, normalized.from, normalized.to),
    [payload.half_hour_sales_rows, aggShopNos, normalized.from, normalized.to],
  );
  const intervalSales = useMemo(() => aggregateIntervalSales(halfHourSales), [halfHourSales]);

  const spuRange = useMemo(
    () => filterSpuDaily(payload.spu_daily_rows, aggShopNos, normalized.from, normalized.to),
    [payload.spu_daily_rows, aggShopNos, normalized.from, normalized.to],
  );
  const topSpu = useMemo(() => aggregateSpuTopN(spuRange, 10), [spuRange]);

  const channelShare = useMemo(() => aggregateChannelShare(rangeRows), [rangeRows]);
  const categoryShare = useMemo(() => aggregateCategoryShare(rangeRows), [rangeRows]);

  const channelSlices: ShareSlice[] = [
    { name: labels.charts.pickup,   value: channelShare.pickup,   share: channelShare.pickupShare,   color: '#14B8A6' },
    { name: labels.charts.delivery, value: channelShare.delivery, share: channelShare.deliveryShare, color: '#4A90D9' },
  ];
  const categorySlices: ShareSlice[] = [
    { name: labels.charts.freshMade, value: categoryShare.freshMade, share: categoryShare.freshShare,     color: '#14B8A6' },
    { name: labels.charts.purchased, value: categoryShare.purchased, share: categoryShare.purchasedShare, color: '#4A90D9' },
  ];

  // Visible stores in the table: scoped by city/region; ignore drill-down so the highlighted row stays in context.
  const visibleStores = useMemo(() => {
    const set = new Set(normalized.shopNos ?? []);
    return payload.stores.filter((s) => s.operating_today && set.has(s.shop_no));
  }, [payload.stores, normalized.shopNos]);

  return (
    <main className={styles.main}>
      <FilterBar payload={payload} filters={filters} onChange={setFilters} />

      {selectedShop && (
        <div className={styles.drillBanner}>
          <span>
            当前已聚焦门店：<strong>{payload.stores.find((s) => s.shop_no === selectedShop)?.shop_name ?? selectedShop}</strong>
          </span>
          <button type="button" className={styles.drillReset} onClick={() => setSelectedShop(null)}>
            返回全部
          </button>
        </div>
      )}

      <div className={styles.groups}>
        {KPI_GROUPS.map((g) => (
          <KpiGroup key={g.id} id={g.id} label={labels.groups[g.id]}>
            {g.keys.map((k) => {
              const metric = METRIC_BY_KEY[k];
              const value = getMetricValue(rangeRows, k);
              const comparisons = metric.comparisons.map((kind) => {
                const c = computeComparison(
                  payload.daily_store_rows,
                  aggShopNos,
                  { from: normalized.from, to: normalized.to },
                  payload.meta.retained_from,
                  kind,
                  k,
                );
                return { kind, delta: c.delta };
              });
              const emptyReason = value === null
                ? emptyReasonFor(k, normalized.from, normalized.to, payload.meta.retained_to)
                : undefined;
              return <KpiCard key={k} metric={metric} value={value} comparisons={comparisons} emptyReason={emptyReason} />;
            })}
          </KpiGroup>
        ))}
      </div>

      <StoreKpiTable
        stores={visibleStores}
        daily={payload.daily_store_rows}
        from={normalized.from}
        to={normalized.to}
        selectedShop={selectedShop}
        onSelectShop={setSelectedShop}
      />

      <div className={styles.chartRow}>
        <SharePieChart
          title={labels.charts.orderType}
          subtitle={labels.charts.orderTypeSubtitle}
          slices={channelSlices}
          total={channelShare.total}
          variant="donut"
          filenameBase="订单类型占比"
          from={normalized.from}
          to={normalized.to}
        />
        <SharePieChart
          title={labels.charts.productSales}
          subtitle={labels.charts.productSalesSubtitle}
          slices={categorySlices}
          total={categoryShare.total}
          variant="pie"
          filenameBase="商品销售情况"
          from={normalized.from}
          to={normalized.to}
        />
        <TopSpuTable rows={topSpu} from={normalized.from} to={normalized.to} />
      </div>

      <IntervalSalesTable rows={intervalSales} from={normalized.from} to={normalized.to} />

      {debugEnabled && (
        <DebugOverlay
          payload={payload}
          filtered={rangeRows}
          from={normalized.from}
          to={normalized.to}
          shopNos={normalized.shopNos}
        />
      )}
    </main>
  );
}
