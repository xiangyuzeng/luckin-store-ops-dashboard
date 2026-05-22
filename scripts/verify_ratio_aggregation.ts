// Sanity check: confirm that ratio/share aggregations use Σnum/Σden over the range,
// not a simple average of daily shares. Run with: npx tsx scripts/verify_ratio_aggregation.ts

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Payload } from '../lib/types';
import { aggregateChannelShare, filterDaily } from '../lib/aggregate';

const data = JSON.parse(readFileSync(resolve('data', 'payload.json'), 'utf-8')) as Payload;
const dates = Array.from(new Set(data.daily_store_rows.map((r) => r.date))).sort();
const last = dates[dates.length - 1]!;
const twoDayFrom = dates[dates.length - 2]!;
const sevenDayFrom = dates[dates.length - 7]!;

const twoDay = filterDaily(data.daily_store_rows, null, twoDayFrom, last);
const sevenDay = filterDaily(data.daily_store_rows, null, sevenDayFrom, last);

const twoDayShare = aggregateChannelShare(twoDay);
const sevenDayShare = aggregateChannelShare(sevenDay);

// Compute the simple-average-of-days share for the 7-day window (the wrong way) for comparison.
const perDayShares: number[] = [];
for (let i = 0; i < 7; i += 1) {
  const d = dates[dates.length - 1 - i]!;
  const rows = filterDaily(data.daily_store_rows, null, d, d);
  const s = aggregateChannelShare(rows);
  if (s.total > 0) perDayShares.push(s.pickupShare);
}
const simpleAvg = perDayShares.reduce((a, b) => a + b, 0) / perDayShares.length;

const pct = (n: number) => `${(n * 100).toFixed(4)}%`;
console.log(`2-day pickup share (Σnum/Σden):   ${pct(twoDayShare.pickupShare)}  [num=${twoDayShare.pickup}, den=${twoDayShare.total}]`);
console.log(`7-day pickup share (Σnum/Σden):   ${pct(sevenDayShare.pickupShare)}  [num=${sevenDayShare.pickup}, den=${sevenDayShare.total}]`);
console.log(`7-day simple-avg-of-days share:   ${pct(simpleAvg)}  ← would be WRONG if used`);
console.log(`difference (correct - wrong):     ${pct(sevenDayShare.pickupShare - simpleAvg)}`);
console.log(`Σnum/Σden differs from simple avg by ${Math.abs(sevenDayShare.pickupShare - simpleAvg) > 0 ? 'YES' : 'NO'} — the aggregator is correct.`);
