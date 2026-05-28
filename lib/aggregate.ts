// Range aggregation — the correctness-critical layer.
//
// Rules:
//   - Counts: sum the per-row value across rows; null if every row is null.
//   - Ratios: aggregate as Sum(num) / Sum(den) across rows. NEVER average daily percentages.
//   - Durations: weighted average Sum(total_seconds) / Sum(weight).
//   - Averages over operating days (avg_daily_*): sum the per-row value, divide by operating-day count.
//
// All functions return `null` when the input has no usable data; the UI maps null
// to the "数据源待接入" or "—" pill.

import type {
  CountKey,
  DailyStoreRow,
  DurationKey,
  HalfHourEfficiencyRow,
  HalfHourSalesRow,
  MetricKey,
  RatioKey,
  ShopNo,
  SpuDailyRow,
} from '@/lib/types';
import { METRIC_BY_KEY } from '@/lib/metrics';

// ── primitive aggregations ──────────────────────────────────────────

export function sumCount(rows: DailyStoreRow[], key: CountKey): number | null {
  let total = 0;
  let any = false;
  for (const r of rows) {
    const v = r[key];
    if (v === null || v === undefined) continue;
    total += v;
    any = true;
  }
  return any ? total : null;
}

export function aggregateRatio(rows: DailyStoreRow[], key: RatioKey): number | null {
  let num = 0;
  let den = 0;
  let any = false;
  for (const r of rows) {
    const pair = r[key];
    if (!pair) continue;
    num += pair.num;
    den += pair.den;
    any = true;
  }
  if (!any || den === 0) return null;
  return num / den;
}

export function aggregateDuration(rows: DailyStoreRow[], key: DurationKey): number | null {
  let total = 0;
  let weight = 0;
  for (const r of rows) {
    const pair = r[key];
    if (!pair) continue;
    total += pair.total_seconds;
    weight += pair.weight;
  }
  if (weight === 0) return null;
  return total / weight;
}

// ── derived: hourly cups + perf hourly cups + achievement ratio ─────

export function aggregateHourlyCups(rows: DailyStoreRow[]): number | null {
  // Σ equiv_product_count / Σ labor_hours_total ; labor hours are pending → null.
  let equiv = 0;
  let hours = 0;
  let any = false;
  for (const r of rows) {
    if (r.labor_hours_total === null || r.equiv_product_count === null) continue;
    equiv += r.equiv_product_count;
    hours += r.labor_hours_total;
    any = true;
  }
  if (!any || hours === 0) return null;
  return equiv / hours;
}

export function aggregatePerfHourlyCups(rows: DailyStoreRow[]): number | null {
  let equiv = 0;
  let hours = 0;
  let any = false;
  for (const r of rows) {
    if (r.labor_hours_productive === null || r.equiv_product_count === null) continue;
    equiv += r.equiv_product_count;
    hours += r.labor_hours_productive;
    any = true;
  }
  if (!any || hours === 0) return null;
  return equiv / hours;
}

// efficiency_duration = avg accept response + avg make duration (both weighted)
export function aggregateEfficiencyDuration(rows: DailyStoreRow[]): number | null {
  const accept = aggregateDuration(rows, 'accept_response_duration');
  const make = aggregateDuration(rows, 'make_duration');
  if (accept === null && make === null) return null;
  return (accept ?? 0) + (make ?? 0);
}

// avg_daily_* — per-store per-day fact divided by operating-day count.
export function aggregateAvgDaily(
  rows: DailyStoreRow[],
  key: 'avg_daily_products' | 'avg_daily_fresh_made' | 'avg_daily_equiv',
): number | null {
  let total = 0;
  let opDays = 0;
  for (const r of rows) {
    if (!r.operating) continue;
    const v = r[key];
    if (v === null) continue;
    total += v;
    opDays += 1;
  }
  if (opDays === 0) return null;
  return total / opDays;
}

// ── public API: getMetricValue ──────────────────────────────────────
// Returns a number in the metric's "natural" units (e.g. percent as 0..1, count as cups, seconds for duration).
// Callers apply the formatter from lib/format.ts.

export function getMetricValue(rows: DailyStoreRow[], key: MetricKey): number | null {
  const def = METRIC_BY_KEY[key];
  if (!def) return null;
  if (def.source === 'pending') {
    // Pending metrics intentionally have no source mapped — return null even if we
    // could synthesize from nulls. The UI shows "数据源待接入".
    if (key === 'hourlyCupAchieve') return aggregateRatio(rows, 'hourly_cup_achieve');
    if (key === 'qcPassRate') return aggregateRatio(rows, 'qc_pass_rate');
    if (key === 'qcAvgScore') return aggregateRatio(rows, 'qc_avg_score');
  }
  if (def.source === 'partial' && key === 'materialLossRate') {
    return aggregateRatio(rows, 'material_loss_rate');
  }
  switch (key) {
    case 'orderCount':         return sumCount(rows, 'order_count');
    case 'productCount':       return sumCount(rows, 'product_count');
    case 'satisfaction':       return aggregateRatio(rows, 'satisfaction');
    case 'hourlyCups':         return aggregateHourlyCups(rows);
    case 'perfHourlyCups':     return aggregatePerfHourlyCups(rows);
    case 'pickupCount':        return sumCount(rows, 'pickup_count');
    case 'deliveryCount':      return sumCount(rows, 'delivery_count');
    case 'freshMadeCount':     return sumCount(rows, 'fresh_made_count');
    case 'efficiencyDuration': return aggregateEfficiencyDuration(rows);
    case 'avgDailyProducts':   return aggregateAvgDaily(rows, 'avg_daily_products');
    case 'avgDailyFreshMade':  return aggregateAvgDaily(rows, 'avg_daily_fresh_made');
    case 'avgDailyEquiv':      return aggregateAvgDaily(rows, 'avg_daily_equiv');
    default:                   return null;
  }
}

// ── share aggregation for donut/pie ─────────────────────────────────

export interface SharePair {
  pickup: number;
  delivery: number;
  total: number;
  pickupShare: number; // 0..1
  deliveryShare: number;
}

export function aggregateChannelShare(rows: DailyStoreRow[]): SharePair {
  let pickup = 0;
  let delivery = 0;
  for (const r of rows) {
    pickup += r.pickup_count ?? 0;
    delivery += r.delivery_count ?? 0;
  }
  const total = pickup + delivery;
  return {
    pickup,
    delivery,
    total,
    pickupShare: total === 0 ? 0 : pickup / total,
    deliveryShare: total === 0 ? 0 : delivery / total,
  };
}

export interface CategoryShare {
  freshMade: number;
  purchased: number;
  total: number;
  freshShare: number;
  purchasedShare: number;
}

export function aggregateCategoryShare(rows: DailyStoreRow[]): CategoryShare {
  let fresh = 0;
  let purchased = 0;
  for (const r of rows) {
    fresh += r.fresh_made_count ?? 0;
    purchased += r.purchased_count ?? 0;
  }
  const total = fresh + purchased;
  return {
    freshMade: fresh,
    purchased,
    total,
    freshShare: total === 0 ? 0 : fresh / total,
    purchasedShare: total === 0 ? 0 : purchased / total,
  };
}

// ── filter helpers ──────────────────────────────────────────────────

export function filterDaily(
  rows: DailyStoreRow[],
  shopNos: ShopNo[] | null,
  fromIso: string,
  toIso: string,
): DailyStoreRow[] {
  const shopSet = shopNos === null ? null : new Set(shopNos);
  return rows.filter((r) => {
    if (r.date < fromIso || r.date > toIso) return false;
    if (shopSet && !shopSet.has(r.shop_no)) return false;
    return true;
  });
}

export function filterHalfHourEff(
  rows: HalfHourEfficiencyRow[],
  shopNos: ShopNo[] | null,
  fromIso: string,
  toIso: string,
): HalfHourEfficiencyRow[] {
  const shopSet = shopNos === null ? null : new Set(shopNos);
  return rows.filter((r) => {
    if (r.date < fromIso || r.date > toIso) return false;
    if (shopSet && !shopSet.has(r.shop_no)) return false;
    return true;
  });
}

export function filterHalfHourSales(
  rows: HalfHourSalesRow[],
  shopNos: ShopNo[] | null,
  fromIso: string,
  toIso: string,
): HalfHourSalesRow[] {
  const shopSet = shopNos === null ? null : new Set(shopNos);
  return rows.filter((r) => {
    if (r.date < fromIso || r.date > toIso) return false;
    if (shopSet && !shopSet.has(r.shop_no)) return false;
    return true;
  });
}

export function filterSpuDaily(
  rows: SpuDailyRow[],
  shopNos: ShopNo[] | null,
  fromIso: string,
  toIso: string,
): SpuDailyRow[] {
  const shopSet = shopNos === null ? null : new Set(shopNos);
  return rows.filter((r) => {
    if (r.date < fromIso || r.date > toIso) return false;
    if (shopSet && !shopSet.has(r.shop_no)) return false;
    return true;
  });
}

// ── interval tables (per-half-hour roll-ups across selected stores+dates) ──

export interface IntervalSalesAgg {
  slot: string;
  pickup: number;
  delivery: number;
  freshMade: number;
  purchased: number;
}

export function aggregateIntervalSales(rows: HalfHourSalesRow[]): IntervalSalesAgg[] {
  const map = new Map<string, IntervalSalesAgg>();
  for (const r of rows) {
    let agg = map.get(r.slot);
    if (!agg) {
      agg = { slot: r.slot, pickup: 0, delivery: 0, freshMade: 0, purchased: 0 };
      map.set(r.slot, agg);
    }
    agg.pickup += r.pickup_count;
    agg.delivery += r.delivery_count;
    agg.freshMade += r.fresh_made_count;
    agg.purchased += r.purchased_count;
  }
  return Array.from(map.values()).sort((a, b) => a.slot.localeCompare(b.slot));
}

export interface IntervalEffAgg {
  slot: string;
  acceptSec: number | null;
  makeSec: number | null;
  totalSec: number | null;
  orderCount: number;
  equivCount: number;
}

export function aggregateIntervalEfficiency(rows: HalfHourEfficiencyRow[]): IntervalEffAgg[] {
  const map = new Map<string, {
    slot: string;
    acceptTotal: number;
    acceptWeight: number;
    makeTotal: number;
    makeWeight: number;
    orderCount: number;
    equivCount: number;
  }>();
  for (const r of rows) {
    let agg = map.get(r.slot);
    if (!agg) {
      agg = { slot: r.slot, acceptTotal: 0, acceptWeight: 0, makeTotal: 0, makeWeight: 0, orderCount: 0, equivCount: 0 };
      map.set(r.slot, agg);
    }
    if (r.accept_response) {
      agg.acceptTotal += r.accept_response.total_seconds;
      agg.acceptWeight += r.accept_response.weight;
    }
    if (r.make_duration) {
      agg.makeTotal += r.make_duration.total_seconds;
      agg.makeWeight += r.make_duration.weight;
    }
    agg.orderCount += r.order_count;
    agg.equivCount += r.equiv_product_count;
  }
  return Array.from(map.values())
    .sort((a, b) => a.slot.localeCompare(b.slot))
    .map((a) => {
      const accept = a.acceptWeight === 0 ? null : a.acceptTotal / a.acceptWeight;
      const make = a.makeWeight === 0 ? null : a.makeTotal / a.makeWeight;
      const total = accept === null && make === null ? null : (accept ?? 0) + (make ?? 0);
      return {
        slot: a.slot,
        acceptSec: accept,
        makeSec: make,
        totalSec: total,
        orderCount: a.orderCount,
        equivCount: a.equivCount,
      };
    });
}

// ── TOP-N SPU ───────────────────────────────────────────────────────

export interface SpuAgg {
  spu_name: string;
  quantity: number;
  share: number;
}

export function aggregateSpuTopN(rows: SpuDailyRow[], n: number = 10): SpuAgg[] {
  const map = new Map<string, number>();
  let total = 0;
  for (const r of rows) {
    map.set(r.spu_name, (map.get(r.spu_name) ?? 0) + r.quantity);
    total += r.quantity;
  }
  const sorted: SpuAgg[] = Array.from(map.entries())
    .map(([spu_name, quantity]) => ({ spu_name, quantity, share: total === 0 ? 0 : quantity / total }))
    .sort((a, b) => b.quantity - a.quantity);
  return sorted.slice(0, n);
}
