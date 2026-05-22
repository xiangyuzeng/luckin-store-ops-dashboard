'use client';

import { useRef, useState } from 'react';
import { exportCsv, exportXlsx, type ExportColumn } from '@/lib/export';
import styles from './ExportMenu.module.css';

interface Props<R> {
  rows: R[];
  columns: ExportColumn<R>[];
  filenameBase: string;
  from?: string;
  to?: string;
  label?: string;
}

export function ExportMenu<R>({ rows, columns, filenameBase, from, to, label = '导出数据' }: Props<R>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click (simple, no portal needed).
  const onBlur = (e: React.FocusEvent) => {
    const next = e.relatedTarget as Node | null;
    if (next && rootRef.current && rootRef.current.contains(next)) return;
    setOpen(false);
  };

  return (
    <div className={styles.root} ref={rootRef} onBlur={onBlur}>
      <button
        type="button"
        className={styles.trigger}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden>
          <path d="M8 2v8m0 0l-3-3m3 3l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M3 12.5V13.5C3 14.0523 3.44772 14.5 4 14.5H12C12.5523 14.5 13 14.0523 13 13.5V12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {label}
      </button>
      {open && (
        <div className={styles.menu} role="menu">
          <button
            type="button"
            role="menuitem"
            className={styles.item}
            onClick={() => { exportXlsx({ rows, columns, filenameBase, from, to }); setOpen(false); }}
          >
            导出 Excel (.xlsx)
          </button>
          <button
            type="button"
            role="menuitem"
            className={styles.item}
            onClick={() => { exportCsv({ rows, columns, filenameBase, from, to }); setOpen(false); }}
          >
            导出 CSV
          </button>
        </div>
      )}
    </div>
  );
}
