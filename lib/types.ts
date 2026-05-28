// Payload data contract — emitted by pipeline, consumed by client, validated by CI.

export type ISO8601 = string;
export type ISODate = string;
export type HalfHourSlot = string;
export type ShopNo = string;

export type DataSource = 'confirmed' | 'pending' | 'partial';
export type MetricFormat = 'percent' | 'count' | 'score' | 'duration';
export type ComparisonKind = 'wow' | 'mom' | 'sequential';
export type GoodDirection = 'up' | 'down';

export interface RatioPair {
  num: number;
  den: number;
}

export interface DurationPair {
  total_seconds: number;
  weight: number;
}

export interface StoreInfo {
  shop_no: ShopNo;
  shop_name: string;
  shop_name_zh?: string;
  city: string;
  region: string;
  operating_today: boolean;
  opened_on?: ISODate;
}

export interface MetricDefinition {
  key: MetricKey;
  label_zh: string;
  format: MetricFormat;
  comparisons: ComparisonKind[];
  good_direction: GoodDirection;
  source: DataSource;
  formula_zh: string;
}

export type MetricKey =
  | 'orderCount'
  | 'productCount'
  | 'satisfaction'
  | 'hourlyCups'
  | 'perfHourlyCups'
  | 'hourlyCupAchieve'
  | 'qcPassRate'
  | 'qcAvgScore'
  | 'materialLossRate'
  | 'avgDailyProducts'
  | 'avgDailyFreshMade'
  | 'avgDailyEquiv'
  | 'efficiencyDuration'
  | 'pickupCount'
  | 'deliveryCount'
  | 'freshMadeCount';

export interface DailyStoreRow {
  shop_no: ShopNo;
  date: ISODate;
  operating: boolean;

  // counts
  order_count: number | null;
  pickup_count: number | null;
  delivery_count: number | null;
  product_count: number | null;
  fresh_made_count: number | null;
  purchased_count: number | null;
  equiv_product_count: number | null;
  avg_daily_products: number | null;
  avg_daily_fresh_made: number | null;
  avg_daily_equiv: number | null;

  // ratios — null if source unmapped
  satisfaction: RatioPair | null;
  qc_pass_rate: RatioPair | null;
  qc_avg_score: RatioPair | null;
  hourly_cup_achieve: RatioPair | null;
  material_loss_rate: RatioPair | null;

  // labor inputs
  labor_hours_total: number | null;
  labor_hours_productive: number | null;

  // durations (per-store-day)
  accept_response_duration: DurationPair | null;
  make_duration: DurationPair | null;
}

export interface HalfHourEfficiencyRow {
  shop_no: ShopNo;
  date: ISODate;
  slot: HalfHourSlot;
  accept_response: DurationPair | null;
  make_duration: DurationPair | null;
  order_count: number;
  equiv_product_count: number;
}

// Per-day per-store per-half-hour SALES counts (separate from efficiency rows above).
// Feeds the 区间销售明细 48-row table on the home page.
export interface HalfHourSalesRow {
  shop_no: ShopNo;
  date: ISODate;
  slot: HalfHourSlot;
  pickup_count: number;     // channel in {1,2,3}
  delivery_count: number;   // channel in {8,9,10}
  fresh_made_count: number; // one_category_name in fresh
  purchased_count: number;  // one_category_name in purchased
}

// Per-day per-store SPU quantity. Used by the 商品TOP10 table; aggregated as
// Sum(quantity) per spu_name across the selected dates and stores.
export interface SpuDailyRow {
  shop_no: ShopNo;
  date: ISODate;
  spu_name: string;
  quantity: number;
}

export interface PrecomputedComparison {
  metric_key: MetricKey;
  shop_no: ShopNo | 'ALL';
  current_range: { from: ISODate; to: ISODate };
  prior_range: { from: ISODate; to: ISODate };
  kind: ComparisonKind;
  current: { num?: number; den?: number; value?: number } | null;
  prior: { num?: number; den?: number; value?: number } | null;
}

export interface PayloadMeta {
  generated_at: ISO8601;
  tenant: 'LKUS';
  timezone: 'America/New_York';
  retained_from: ISODate;
  retained_to: ISODate;
  schema_version: number;
  source_status: Partial<Record<MetricKey, DataSource>>;
  // Optional — per-collector last-run timestamps. Surfaces in the ?debug=1 overlay.
  collector_timestamps?: Partial<Record<string, ISO8601>>;
  theoretical_hourly_cups?: number;
}

export interface Payload {
  meta: PayloadMeta;
  stores: StoreInfo[];
  metrics: MetricDefinition[];
  daily_store_rows: DailyStoreRow[];
  half_hour_rows: HalfHourEfficiencyRow[];
  half_hour_sales_rows: HalfHourSalesRow[];
  spu_daily_rows: SpuDailyRow[];
  precomputed_comparisons?: PrecomputedComparison[];
}

// Convenience aliases for aggregation
export type RatioKey =
  | 'satisfaction'
  | 'qc_pass_rate'
  | 'qc_avg_score'
  | 'hourly_cup_achieve'
  | 'material_loss_rate';

export type CountKey =
  | 'order_count'
  | 'pickup_count'
  | 'delivery_count'
  | 'product_count'
  | 'fresh_made_count'
  | 'purchased_count'
  | 'equiv_product_count';

export type DurationKey = 'accept_response_duration' | 'make_duration';
