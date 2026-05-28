// METRICS registry — single source of truth for cards + table.
// The pipeline reads this file's structure (via the seed/probe scripts) to keep payload.metrics in sync.

import type { MetricDefinition, MetricKey } from '@/lib/types';

export const METRICS: MetricDefinition[] = [
  { key: 'orderCount',         label_zh: '订单数量',           format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: '已完成订单数 (t_order.status=已完成)' },
  { key: 'productCount',       label_zh: '商品数量',           format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: '已完成订单的商品数 (t_order_item ⋈ t_order)' },
  { key: 'satisfaction',       label_zh: '满意度',             format: 'percent',  comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: '1 − (自取不满意 + 外送不满意) / 订单总数' },
  { key: 'hourlyCups',         label_zh: '小时杯量',           format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'pending',   formula_zh: '等效商品数 / 总工时' },
  { key: 'perfHourlyCups',     label_zh: '绩效小时杯量',       format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'pending',   formula_zh: '等效商品数 / (考勤工时 − 会议 − 培训 − 帮带训)' },
  { key: 'hourlyCupAchieve',   label_zh: '小时杯量达成比',     format: 'percent',  comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'pending',   formula_zh: '(绩效小时杯量 / 理论小时杯量) × 100%' },
  { key: 'qcPassRate',         label_zh: '品控稽核达标率',     format: 'percent',  comparisons: ['sequential'],   good_direction: 'up',   source: 'pending',   formula_zh: '≥80分稽核任务数 / 稽核任务数' },
  { key: 'qcAvgScore',         label_zh: '品控稽核平均分',     format: 'score',    comparisons: ['sequential'],   good_direction: 'up',   source: 'pending',   formula_zh: '稽核总分 / 稽核任务数' },
  { key: 'materialLossRate',   label_zh: '原料损耗率',         format: 'percent',  comparisons: ['wow', 'mom'],   good_direction: 'down', source: 'partial',   formula_zh: '(实际 − 理论消耗成本) / 理论消耗成本' },
  { key: 'avgDailyProducts',   label_zh: '单店日均商品数',     format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: 't_order_store_fact 商品数 / 运营天数' },
  { key: 'avgDailyFreshMade',  label_zh: '单店日均现制商品数', format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: 't_order_item 现制类目计数 / 运营天数' },
  { key: 'avgDailyEquiv',      label_zh: '单店日均等效商品数', format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: '(现制 + 0.25 × 外购) / 运营天数' },
  { key: 'efficiencyDuration', label_zh: '效能时长',           format: 'duration', comparisons: ['wow', 'mom'],   good_direction: 'down', source: 'confirmed', formula_zh: '单均接单响应 + 平均等效制作' },
  { key: 'pickupCount',        label_zh: '自取订单数',         format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: 'channel ∈ {1,2,3}' },
  { key: 'deliveryCount',      label_zh: '外送订单数',         format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: 'channel ∈ {8,9,10}' },
  { key: 'freshMadeCount',     label_zh: '现制商品数',         format: 'count',    comparisons: ['wow', 'mom'],   good_direction: 'up',   source: 'confirmed', formula_zh: 't_order_item.one_category_name ∈ 现制类目' },
];

export const METRIC_BY_KEY: Record<MetricKey, MetricDefinition> = METRICS.reduce(
  (acc, m) => {
    acc[m.key] = m;
    return acc;
  },
  {} as Record<MetricKey, MetricDefinition>,
);

// Semantic groups for KPI card layout (业务量 / 效率 / 品质).
export const KPI_GROUPS: Array<{ id: 'business' | 'efficiency' | 'quality'; keys: MetricKey[] }> = [
  { id: 'business',   keys: ['orderCount', 'productCount', 'satisfaction'] },
  { id: 'efficiency', keys: ['hourlyCups', 'perfHourlyCups', 'hourlyCupAchieve'] },
  { id: 'quality',    keys: ['qcPassRate', 'qcAvgScore', 'materialLossRate'] },
];

// Columns rendered by the 19-column store table, in order.
export const STORE_TABLE_COLUMNS: MetricKey[] = [
  'avgDailyProducts',
  'avgDailyFreshMade',
  'avgDailyEquiv',
  'satisfaction',
  'hourlyCups',
  'perfHourlyCups',
  'hourlyCupAchieve',
  'qcPassRate',
  'qcAvgScore',
  'materialLossRate',
  'efficiencyDuration',
  'orderCount',
  'pickupCount',
  'deliveryCount',
  'productCount',
  'freshMadeCount',
];
