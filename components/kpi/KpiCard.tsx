import type { ComparisonKind, MetricDefinition } from '@/lib/types';
import { Tooltip } from '@/components/shared/Tooltip';
import { ComparisonBadge } from '@/components/kpi/ComparisonBadge';
import { formatMetricValue, PENDING_DISPLAY } from '@/lib/format';
import { labels } from '@/lib/labels';
import styles from './KpiCard.module.css';

interface ComparisonInput {
  kind: ComparisonKind;
  delta: number | null;
}

interface Props {
  metric: MetricDefinition;
  value: number | null;
  comparisons: ComparisonInput[];
  emptyReason?: string;
}

export function KpiCard({ metric, value, comparisons, emptyReason }: Props) {
  const isPending = metric.source === 'pending';
  const pending = isPending && value === null;
  const empty = !pending && value === null;
  const display = pending ? PENDING_DISPLAY : formatMetricValue(value, metric.format);

  return (
    <article className={`${styles.card} ${pending ? styles.pending : ''}`}>
      <header className={styles.header}>
        <span className={styles.title}>{metric.label_zh}</span>
        <Tooltip content={metric.formula_zh}>
          <span aria-hidden>i</span>
        </Tooltip>
      </header>

      <div className={pending ? styles.valuePending : styles.value} title={pending ? labels.pending : undefined}>
        {display}
      </div>

      {empty && emptyReason && <div className={styles.emptyReason}>{emptyReason}</div>}

      <div className={styles.badges}>
        {comparisons.map((c) => (
          <ComparisonBadge key={c.kind} kind={c.kind} delta={c.delta} goodDirection={metric.good_direction} />
        ))}
      </div>
    </article>
  );
}
