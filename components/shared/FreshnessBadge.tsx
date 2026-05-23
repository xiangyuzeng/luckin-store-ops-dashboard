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
  const [, tick] = useState(0);
  const [popoverOpen, setPopoverOpen] = useState(false);

  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  const f = freshness(generatedAt, staleMin);
  const cls = f.isStale ? `${styles.badge} ${styles.stale}` : styles.badge;

  // Format the generated_at timestamp for display in the popover (UTC + local).
  const generatedDate = new Date(generatedAt);
  const generatedDisplay = `${generatedDate.toISOString().slice(0, 16).replace('T', ' ')} UTC`;

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={cls}
        onClick={() => setPopoverOpen((v) => !v)}
        onBlur={(e) => {
          // Don't close when focus moves within the popover.
          if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
            setPopoverOpen(false);
          }
        }}
        aria-expanded={popoverOpen}
        aria-controls="freshness-popover"
        title={`${labels.freshness.tooltipBody} (${generatedDisplay})`}
      >
        <span className={styles.dot} aria-hidden />
        <span className={styles.text}>数据更新于 {formatAge(f.ageMinutes)}</span>
        <span className={styles.sep} aria-hidden>·</span>
        <span className={styles.autoLabel}>{labels.freshness.autoLabel}</span>
        {f.isStale && <span className={styles.staleHint}>{labels.freshness.stale}</span>}
      </button>

      {popoverOpen && (
        <div id="freshness-popover" role="dialog" className={styles.popover}>
          <div className={styles.popHeader}>{labels.freshness.tooltipTitle}</div>
          <p className={styles.popBody}>{labels.freshness.tooltipBody}</p>
          <dl className={styles.popList}>
            <dt>本次生成</dt><dd>{generatedDisplay}</dd>
            <dt>下次刷新</dt><dd>{labels.dataInfo.nextRefreshIn(hoursUntilNext09UTC(generatedDate))}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}

function hoursUntilNext09UTC(from: Date): number {
  const next = new Date(from);
  next.setUTCHours(9, 0, 0, 0);
  if (next.getTime() <= from.getTime()) next.setUTCDate(next.getUTCDate() + 1);
  return Math.round((next.getTime() - from.getTime()) / 3_600_000);
}
