// Runtime payload validation. Run with: npx tsx scripts/validate_payload.ts
// Exit non-zero on shape mismatch. Useful for the GH Action and pre-commit.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Payload } from '../lib/types';

const PATH = resolve(process.cwd(), 'data', 'payload.json');
const raw = readFileSync(PATH, 'utf-8');
const data = JSON.parse(raw) as Payload;

const errors: string[] = [];

function need<T>(name: string, v: T | undefined, predicate: (x: T) => boolean): void {
  if (v === undefined || !predicate(v)) errors.push(`bad ${name}: ${JSON.stringify(v)}`);
}

need('meta.tenant', data.meta?.tenant, (v) => v === 'LKUS');
need('meta.timezone', data.meta?.timezone, (v) => v === 'America/New_York');
need('meta.generated_at', data.meta?.generated_at, (v) => /^\d{4}-\d{2}-\d{2}T/.test(v));
need('meta.retained_from', data.meta?.retained_from, (v) => /^\d{4}-\d{2}-\d{2}$/.test(v));
need('meta.retained_to', data.meta?.retained_to, (v) => /^\d{4}-\d{2}-\d{2}$/.test(v));
need('meta.schema_version', data.meta?.schema_version, (v) => v === 1);

need('stores', data.stores, (v) => Array.isArray(v) && v.length > 0);
need('metrics', data.metrics, (v) => Array.isArray(v) && v.length >= 16);
need('daily_store_rows', data.daily_store_rows, (v) => Array.isArray(v) && v.length > 0);
need('half_hour_rows', data.half_hour_rows, (v) => Array.isArray(v));
need('half_hour_sales_rows', data.half_hour_sales_rows, (v) => Array.isArray(v));
need('spu_daily_rows', data.spu_daily_rows, (v) => Array.isArray(v));

// Ratio rows that ARE provided must carry both num + den.
for (const r of data.daily_store_rows) {
  for (const k of ['satisfaction', 'qc_pass_rate', 'qc_avg_score', 'hourly_cup_achieve', 'material_loss_rate'] as const) {
    const v = r[k];
    if (v !== null && (typeof v.num !== 'number' || typeof v.den !== 'number')) {
      errors.push(`bad ratio shape in daily_store_rows[${r.shop_no}/${r.date}].${k}: ${JSON.stringify(v)}`);
    }
  }
  for (const k of ['accept_response_duration', 'make_duration'] as const) {
    const v = r[k];
    if (v !== null && (typeof v.total_seconds !== 'number' || typeof v.weight !== 'number')) {
      errors.push(`bad duration shape in daily_store_rows[${r.shop_no}/${r.date}].${k}: ${JSON.stringify(v)}`);
    }
  }
}

if (errors.length > 0) {
  console.error(`Payload validation FAILED (${errors.length} errors):`);
  for (const e of errors) console.error('  •', e);
  process.exit(1);
}

console.log(`Payload OK — ${data.stores.length} stores, ${data.daily_store_rows.length} daily rows, ${data.half_hour_rows.length} eff slots, ${data.half_hour_sales_rows.length} sales slots, ${data.spu_daily_rows.length} SPU rows.`);
