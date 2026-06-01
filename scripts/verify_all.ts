// Comprehensive end-to-end verification. Exits non-zero on any failure.
// Run: npx tsx scripts/verify_all.ts

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Payload, DailyStoreRow, MetricKey } from '../lib/types';
import {
  aggregateCategoryShare,
  aggregateChannelShare,
  aggregateIntervalEfficiency,
  aggregateIntervalSales,
  aggregateSpuTopN,
  filterDaily,
  filterHalfHourEff,
  filterHalfHourSales,
  filterSpuDaily,
  getMetricValue,
} from '../lib/aggregate';
import { computeComparison, priorRange } from '../lib/compare';
import { METRICS, STORE_TABLE_COLUMNS, KPI_GROUPS, METRIC_BY_KEY } from '../lib/metrics';
import { normalize, parseFiltersFromSearch, listStoresMatching } from '../lib/filters';
import { freshness } from '../lib/freshness';

const PATH = resolve(process.cwd(), 'data', 'payload.json');
const data = JSON.parse(readFileSync(PATH, 'utf-8')) as Payload;

let passes = 0;
let fails = 0;

function assertEq<T>(label: string, actual: T, expected: T): void {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { passes += 1; console.log(`  ✓ ${label}`); }
  else { fails += 1; console.error(`  ✗ ${label}\n      expected ${JSON.stringify(expected)}\n      actual   ${JSON.stringify(actual)}`); }
}

function assertTrue(label: string, predicate: boolean, detail?: string): void {
  if (predicate) { passes += 1; console.log(`  ✓ ${label}`); }
  else { fails += 1; console.error(`  ✗ ${label}${detail ? `\n      ${detail}` : ''}`); }
}

function group(label: string, fn: () => void): void {
  console.log(`\n▶ ${label}`);
  fn();
}

// ── 1. Payload meta ─────────────────────────────────────────────────
group('Payload meta', () => {
  assertEq('tenant=LKUS', data.meta.tenant, 'LKUS');
  assertEq('timezone=America/New_York', data.meta.timezone, 'America/New_York');
  assertEq('schema_version=1', data.meta.schema_version, 1);
  assertTrue('generated_at is ISO8601', /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(data.meta.generated_at));
  assertTrue('retained_from is ISO date', /^\d{4}-\d{2}-\d{2}$/.test(data.meta.retained_from));
  assertTrue('retained_to is ISO date', /^\d{4}-\d{2}-\d{2}$/.test(data.meta.retained_to));
  const fromMs = new Date(data.meta.retained_from + 'T00:00:00Z').getTime();
  const toMs = new Date(data.meta.retained_to + 'T00:00:00Z').getTime();
  const days = Math.round((toMs - fromMs) / 86400000) + 1;
  // Window tracks the pipeline's RETAIN_DAYS (default 90) plus the current day,
  // so it drifts by ±1. Assert a sane band + day-by-day continuity instead of
  // pinning an exact count.
  assertTrue(`retention window is a sane size (${days} days)`, days >= 30 && days <= 120);
  const distinctDates = new Set(data.daily_store_rows.map((r) => r.date)).size;
  assertEq('every retained day has rows (continuous)', distinctDates, days);
});

// ── 2. Store roster ─────────────────────────────────────────────────
group('Store roster (derived from payload)', () => {
  // The roster grows/shrinks as stores open and close — derive invariants from
  // the payload rather than pinning a frozen list that goes stale silently.
  assertTrue(`has a plausible store count (${data.stores.length})`, data.stores.length >= 1);
  const shopNos = data.stores.map((s) => s.shop_no);
  assertTrue('every shop_no matches US##### format', shopNos.every((s) => /^US\d{5}$/.test(s)));
  assertEq('shop_no values are unique', new Set(shopNos).size, shopNos.length);
  assertTrue('every store has city + region', data.stores.every((s) => s.city && s.region));
  const operating = data.stores.filter((s) => s.operating_today).length;
  assertTrue(`at least one store operating_today (${operating}/${data.stores.length})`, operating >= 1);
});

// ── 3. METRICS registry ─────────────────────────────────────────────
group('METRICS registry', () => {
  assertEq('16 metrics defined', METRICS.length, 16);
  assertEq('payload.metrics carries the same set', data.metrics.length, 16);
  // KPI groups cover the 9 dashboard cards.
  const kpiKeys = KPI_GROUPS.flatMap((g) => g.keys);
  assertEq('9 KPI card keys', kpiKeys.length, 9);
  // Every KPI key exists in the registry.
  assertTrue('KPI keys all resolve in METRIC_BY_KEY', kpiKeys.every((k) => Boolean(METRIC_BY_KEY[k])));
  // Source-tag distribution.
  const confirmed = METRICS.filter((m) => m.source === 'confirmed').length;
  const pending = METRICS.filter((m) => m.source === 'pending').length;
  const partial = METRICS.filter((m) => m.source === 'partial').length;
  // Don't pin the split — it shifts as pending sources get wired to confirmed.
  // Assert every metric carries a valid tag and the parts sum to the whole.
  assertEq('confirmed + pending + partial = total metrics', confirmed + pending + partial, METRICS.length);
  assertTrue('every metric has a valid source tag',
    METRICS.every((m) => ['confirmed', 'pending', 'partial'].includes(m.source)));
  // 19-col store table: 3 identity + 16 metric columns.
  assertEq('STORE_TABLE_COLUMNS metric count', STORE_TABLE_COLUMNS.length, 16);
});

// ── 4. Per-day-row internal consistency ─────────────────────────────
group('Daily-row internal consistency', () => {
  let badPickupSum = 0, badProductSum = 0, badEquiv = 0, badNonOperatingNotNull = 0;
  let totalOperating = 0;
  for (const r of data.daily_store_rows) {
    if (!r.operating) {
      // All numeric fields should be null on non-operating days.
      const numeric: (keyof DailyStoreRow)[] = ['order_count','pickup_count','delivery_count','product_count','fresh_made_count','purchased_count','equiv_product_count'];
      if (!numeric.every((k) => r[k] === null)) badNonOperatingNotNull += 1;
      continue;
    }
    totalOperating += 1;
    if ((r.pickup_count ?? 0) + (r.delivery_count ?? 0) !== (r.order_count ?? 0)) badPickupSum += 1;
    if ((r.fresh_made_count ?? 0) + (r.purchased_count ?? 0) !== (r.product_count ?? 0)) badProductSum += 1;
    // Equiv = fresh + 0.25 * purchased, then rounded to int. Python uses banker's rounding
    // and JS Math.round rounds half away from zero, so accept any rounding within ±0.5.
    const exact = (r.fresh_made_count ?? 0) + 0.25 * (r.purchased_count ?? 0);
    if (Math.abs((r.equiv_product_count ?? 0) - exact) > 0.5) badEquiv += 1;
  }
  assertTrue(`Non-operating days have null numerics (${badNonOperatingNotNull}/${data.daily_store_rows.length - totalOperating} bad)`, badNonOperatingNotNull === 0);
  assertTrue(`pickup + delivery = order_count on every operating day (${badPickupSum}/${totalOperating} bad)`, badPickupSum === 0);
  assertTrue(`fresh_made + purchased = product_count on every operating day (${badProductSum}/${totalOperating} bad)`, badProductSum === 0);
  assertTrue(`equiv = fresh + 0.25 * purchased on every operating day (${badEquiv}/${totalOperating} bad)`, badEquiv === 0);
});

// ── 5. Source-status integrity + value sanity ───────────────────────
// source_status is "kept in sync by convention" across three places (README):
// the payload meta, the per-metric tag in payload.metrics, and the
// lib/metrics.ts registry. Drift between them is exactly what silently disables
// the "数据源待接入" fallback, so assert that invariant directly instead of
// pinning which sources are pending (that changes as sources get wired up).
group('Source-status integrity + value sanity', () => {
  const VALID = ['confirmed', 'pending', 'partial'];
  const ss = data.meta.source_status as Record<string, string>;
  assertTrue('every source_status value is valid', Object.values(ss).every((v) => VALID.includes(v)));

  // (a) payload meta agrees with the per-metric tag in payload.metrics.
  let metaVsPayload = 0;
  for (const m of data.metrics) {
    if (ss[m.key] !== undefined && ss[m.key] !== m.source) metaVsPayload += 1;
  }
  assertEq('source_status agrees with payload.metrics tags', metaVsPayload, 0);

  // (b) payload tags agree with the lib/metrics.ts registry.
  let payloadVsRegistry = 0;
  for (const m of data.metrics) {
    const reg = METRIC_BY_KEY[m.key as MetricKey];
    if (reg && reg.source !== m.source) payloadVsRegistry += 1;
  }
  assertEq('payload metric tags agree with METRICS registry', payloadVsRegistry, 0);

  // (c) Where a rate/score metric has a value over the full range, it sits in a
  // plausible band. Production sources may legitimately be null (T+1 latency,
  // partial coverage), so assert only over non-null values — never presence.
  const range = filterDaily(data.daily_store_rows, null, data.meta.retained_from, data.meta.retained_to);
  const inBand = (k: MetricKey, lo: number, hi: number) => {
    const v = getMetricValue(range, k);
    assertTrue(`${k} within [${lo}, ${hi}] when present (got ${v})`, v === null || (v >= lo && v <= hi));
  };
  inBand('satisfaction', 0, 1);
  inBand('qcPassRate', 0, 1);
  inBand('qcAvgScore', 0, 100);
  inBand('materialLossRate', 0, 1);
  inBand('hourlyCupAchieve', 0, 5);
});

// ── 6. Aggregation correctness — Σnum/Σden vs simple-avg ────────────
group('Aggregation correctness: Σnum/Σden (not simple averages)', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  const sevenFrom = dates[dates.length - 7]!;
  const sevenDay = filterDaily(data.daily_store_rows, null, sevenFrom, last);
  const share7 = aggregateChannelShare(sevenDay);
  // Manual Σ to cross-check.
  let manualNum = 0, manualDen = 0;
  for (const r of sevenDay) {
    manualNum += r.pickup_count ?? 0;
    manualDen += (r.pickup_count ?? 0) + (r.delivery_count ?? 0);
  }
  assertEq('manual num matches aggregator num', share7.pickup, manualNum);
  assertEq('manual den matches aggregator total', share7.total, manualDen);
  // Same for category share.
  const cat7 = aggregateCategoryShare(sevenDay);
  let mFresh = 0, mPur = 0;
  for (const r of sevenDay) {
    mFresh += r.fresh_made_count ?? 0;
    mPur += r.purchased_count ?? 0;
  }
  assertEq('category share fresh matches manual sum', cat7.freshMade, mFresh);
  assertEq('category share purchased matches manual sum', cat7.purchased, mPur);
  // The simple-avg-of-days share differs from Σnum/Σden — should NOT be equal.
  const perDay: number[] = [];
  for (let i = 0; i < 7; i += 1) {
    const d = dates[dates.length - 1 - i]!;
    const rows = filterDaily(data.daily_store_rows, null, d, d);
    const s = aggregateChannelShare(rows);
    if (s.total > 0) perDay.push(s.pickupShare);
  }
  const simpleAvg = perDay.reduce((a, b) => a + b, 0) / perDay.length;
  assertTrue(`Σnum/Σden (${(share7.pickupShare * 100).toFixed(4)}%) differs from simple-avg (${(simpleAvg * 100).toFixed(4)}%)`,
    Math.abs(share7.pickupShare - simpleAvg) > 1e-6);
});

// ── 7. Comparison logic (wow/mom/sequential) ────────────────────────
group('Comparison logic', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  const from = dates[dates.length - 1]!;
  const r = { from, to: last };
  // prior wow = -7 days
  const wow = priorRange(r, 'wow');
  assertEq('wow prior.from is 7 days earlier', wow.from, dates[dates.length - 8]!);
  // prior sequential = -1 day (since range length = 1)
  const seq = priorRange(r, 'sequential');
  assertEq('sequential prior.from is 1 day earlier', seq.from, dates[dates.length - 2]!);
  // compute wow comparison for orderCount; should be a finite number.
  const cmp = computeComparison(data.daily_store_rows, null, r, data.meta.retained_from, 'wow', 'orderCount');
  assertTrue('wow current is non-null for orderCount', cmp.current !== null);
  assertTrue('wow prior is non-null for orderCount within retention', cmp.prior !== null);
  assertTrue('wow delta is finite', cmp.delta !== null && Number.isFinite(cmp.delta));
  // mom for a 1-day range
  const mom = computeComparison(data.daily_store_rows, null, r, data.meta.retained_from, 'mom', 'orderCount');
  // mom prior may or may not be in retention depending on date — at minimum, no exception.
  assertTrue('mom comparison runs without exception', typeof mom.delta === 'number' || mom.delta === null);
});

// ── 8. Filters: parsing + normalization + cascading ─────────────────
group('Filters: parsing, normalization, cascading', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  // Default = today→today.
  const sp = new URLSearchParams(`from=${last}&to=${last}`);
  const f = parseFiltersFromSearch(sp, data);
  assertEq('parses from from URL', f.from, last);
  assertEq('parses to from URL', f.to, last);
  assertEq('defaults city=ALL', f.city, 'ALL');
  const operatingCount = data.stores.filter((s) => s.operating_today).length;
  const norm = normalize(f, data);
  assertEq('shopNos defaults to operating-today stores', norm.shopNos?.length, operatingCount);
  const nonOperating = data.stores.find((s) => !s.operating_today);
  if (nonOperating) {
    assertTrue(`non-operating store ${nonOperating.shop_no} excluded by default`,
      !(norm.shopNos ?? []).includes(nonOperating.shop_no));
  } else {
    assertEq('all stores operating → none excluded by default', norm.shopNos?.length, data.stores.length);
  }
  // Filter to a specific city — keeps that city's operating stores.
  const someCity = data.stores[0]!.city;
  const f2 = { ...f, city: someCity };
  const norm2 = normalize(f2, data);
  const cityOperating = data.stores.filter((s) => s.operating_today && s.city === someCity).length;
  assertEq(`city=${someCity} keeps its operating stores`, norm2.shopNos?.length, cityOperating);
  // Explicit shop is honored as itself — even if not operating today (real store).
  const someShop = data.stores[0]!.shop_no;
  const f3 = { ...f, shop: someShop };
  const norm3 = normalize(f3, data);
  assertEq('explicit shop narrows to that one shop', norm3.shopNos, [someShop]);
  // A genuinely unknown shop_no (stale URL) falls back to the operating set.
  const f3b = { ...f, shop: 'US99999' as const };
  const norm3b = normalize(f3b, data);
  assertEq('unknown shop falls back to operating set', norm3b.shopNos?.length, operatingCount);
  // Out-of-range dates → clamped with warning
  const f4 = { ...f, from: '2020-01-01' };
  const norm4 = normalize(f4, data);
  assertEq('out-of-range from clamped to retained_from', norm4.from, data.meta.retained_from);
  assertTrue('warning attached when clamped', norm4.warnings.includes('rangeNoteOutside'));
  // listStoresMatching honors operating_today
  const matching = listStoresMatching(data.stores, 'ALL', 'ALL');
  assertEq('listStoresMatching returns operating stores', matching.length, operatingCount);
});

// ── 9. Half-hour rollups: 48 slots when data present ────────────────
group('Half-hour rollups', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  const halfHourEff = filterHalfHourEff(data.half_hour_rows, null, last, last);
  const halfHourSales = filterHalfHourSales(data.half_hour_sales_rows, null, last, last);
  const intEff = aggregateIntervalEfficiency(halfHourEff);
  const intSales = aggregateIntervalSales(halfHourSales);
  assertTrue('Interval efficiency rollup yields up to 48 slots', intEff.length > 0 && intEff.length <= 48);
  assertTrue('Interval sales rollup yields up to 48 slots', intSales.length > 0 && intSales.length <= 48);
  // Each slot in efficiency should have either non-null timings or 0 orders.
  let bad = 0;
  for (const r of intEff) {
    if (r.orderCount > 0 && r.acceptSec === null && r.makeSec === null) bad += 1;
  }
  assertEq('No slot has orders but zero timing data', bad, 0);
});

// ── 10. SPU TOP-N ───────────────────────────────────────────────────
group('SPU TOP-N aggregation', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  const sevenFrom = dates[dates.length - 7]!;
  const spuRows = filterSpuDaily(data.spu_daily_rows, null, sevenFrom, last);
  const top10 = aggregateSpuTopN(spuRows, 10);
  assertTrue('TOP-N returns up to 10 entries', top10.length > 0 && top10.length <= 10);
  // Quantities should be monotonically non-increasing.
  let monotone = true;
  for (let i = 1; i < top10.length; i += 1) {
    if (top10[i]!.quantity > top10[i - 1]!.quantity) { monotone = false; break; }
  }
  assertTrue('TOP-N is sorted descending by quantity', monotone);
  // Shares are 0..1 and sum to <=1 (they're slices of the total, not normalized to top-N).
  for (const r of top10) {
    if (r.share < 0 || r.share > 1) { fails += 1; console.error(`  ✗ share out of range: ${JSON.stringify(r)}`); }
  }
  passes += 1; console.log('  ✓ TOP-N shares all in [0,1]');
});

// ── 11. Freshness ───────────────────────────────────────────────────
group('Freshness logic', () => {
  // Fresh: generated 5 minutes ago.
  const now = new Date('2026-05-22T12:00:00Z');
  const recentIso = new Date(now.getTime() - 5 * 60 * 1000).toISOString();
  const fresh = freshness(recentIso, 60 * 24, now);
  assertEq('age = 5 minutes for 5-min-old payload', fresh.ageMinutes, 5);
  assertEq('not stale at 5 minutes under 24h threshold', fresh.isStale, false);
  // Stale: 2 days old.
  const oldIso = new Date(now.getTime() - 2 * 86_400_000).toISOString();
  const stale = freshness(oldIso, 60 * 24, now);
  assertEq('stale at 48h under 24h threshold', stale.isStale, true);
});

// ── 12. Drill-down (single-shop) aggregation ────────────────────────
group('Single-shop aggregation', () => {
  const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
  const last = dates[dates.length - 1]!;
  const sevenFrom = dates[dates.length - 7]!;
  const rowsAll = filterDaily(data.daily_store_rows, null, sevenFrom, last);
  // Pick a store that actually traded in the window so the subset check is meaningful.
  const candidates = Array.from(new Set(rowsAll.filter((r) => (r.order_count ?? 0) > 0).map((r) => r.shop_no)));
  const shop = candidates[0]!;
  const rowsShop = filterDaily(data.daily_store_rows, [shop], sevenFrom, last);
  assertTrue(`${shop} 7-day filter returns up to 7 rows (${rowsShop.length})`, rowsShop.length > 0 && rowsShop.length <= 7);
  // The store's order count is a positive subset of the all-stores total.
  const allOrders = getMetricValue(rowsAll, 'orderCount') ?? 0;
  const shopOrders = getMetricValue(rowsShop, 'orderCount') ?? 0;
  assertTrue(`${shop} orders is a positive subset of total (${shopOrders} ≤ ${allOrders})`, shopOrders > 0 && shopOrders <= allOrders);
});

// ── 13. Final tally ─────────────────────────────────────────────────
console.log(`\n${fails === 0 ? '✅' : '❌'}  ${passes} passed, ${fails} failed.`);
if (fails > 0) process.exit(1);
