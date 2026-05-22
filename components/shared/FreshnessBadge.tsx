'use client';

import { useEffect, useState } from 'react';
import { freshness, formatAge } from '@/lib/freshness';
import { labels } from '@/lib/labels';
import styles from './FreshnessBadge.module.css';

interface Props {
  generatedAt: string;
  staleMin?: number;
}

export function FreshnessBadge({ generatedAt, staleMin }: Props) {
  // Mount-aware so the SSR + hydration produce a stable result, then we re-render with the live clock.
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  const f = freshness(generatedAt, staleMin);
  const cls = f.isStale ? `${styles.badge} ${styles.stale}` : styles.badge;
  return (
    <div className={cls} role="status" aria-live="polite" title={generatedAt}>
      <span className={styles.dot} aria-hidden />
      <span>数据更新于 {formatAge(f.ageMinutes)}</span>
      {f.isStale && <span className={styles.staleHint}>{labels.freshness.stale}</span>}
    </div>
  );
}
