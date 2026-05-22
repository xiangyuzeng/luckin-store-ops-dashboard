import type { ComparisonKind, GoodDirection } from '@/lib/types';
import { deltaTone } from '@/lib/compare';
import { formatDelta } from '@/lib/format';
import { labels } from '@/lib/labels';
import styles from './ComparisonBadge.module.css';

interface Props {
  kind: ComparisonKind;
  delta: number | null;
  goodDirection: GoodDirection;
}

const KIND_LABEL: Record<ComparisonKind, string> = {
  wow: labels.comparison.wow,
  mom: labels.comparison.mom,
  sequential: labels.comparison.sequential,
};

export function ComparisonBadge({ kind, delta, goodDirection }: Props) {
  const tone = deltaTone(delta, goodDirection);
  const cls = `${styles.badge} ${styles[tone] ?? ''}`;
  const arrow = delta === null || delta === 0 ? '' : delta > 0 ? '↑' : '↓';

  return (
    <span className={cls}>
      <span className={styles.kind}>{KIND_LABEL[kind]}</span>
      <span className={styles.value} aria-label={`${KIND_LABEL[kind]} ${formatDelta(delta, 'percent')}`}>
        {arrow && <span aria-hidden className={styles.arrow}>{arrow}</span>}
        {delta === null ? labels.comparison.noData : formatDelta(delta, 'percent')}
      </span>
    </span>
  );
}
