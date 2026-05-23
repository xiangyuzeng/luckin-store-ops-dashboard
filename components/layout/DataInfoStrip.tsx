import { labels } from '@/lib/labels';
import { formatDate } from '@/lib/format';
import type { PayloadMeta } from '@/lib/types';
import styles from './DataInfoStrip.module.css';

interface Props {
  meta: PayloadMeta;
}

function daysBetween(fromIso: string, toIso: string): number {
  const a = new Date(fromIso + 'T00:00:00Z').getTime();
  const b = new Date(toIso + 'T00:00:00Z').getTime();
  return Math.round((b - a) / 86400000) + 1;
}

export function DataInfoStrip({ meta }: Props) {
  const totalDays = daysBetween(meta.retained_from, meta.retained_to);
  return (
    <section className={styles.strip} aria-label="数据范围与刷新说明">
      <Item label={labels.dataInfo.titleRange} value={labels.dataInfo.rangeValue(formatDate(meta.retained_from), formatDate(meta.retained_to), totalDays)} />
      <Item label={labels.dataInfo.titleSchedule} value={labels.dataInfo.scheduleValue} />
      <Item label={labels.dataInfo.titleSource} value={labels.dataInfo.sourceValue} />
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.item}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  );
}
