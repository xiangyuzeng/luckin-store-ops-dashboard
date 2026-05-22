'use client';

import { useId, useState } from 'react';
import styles from './Tooltip.module.css';

interface Props {
  content: string;
  children: React.ReactNode;
}

export function Tooltip({ content, children }: Props) {
  const id = useId();
  const [open, setOpen] = useState(false);

  return (
    <span className={styles.wrap}>
      <span
        className={styles.trigger}
        tabIndex={0}
        role="button"
        aria-describedby={open ? id : undefined}
        aria-label="查看公式"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        {children}
      </span>
      {open && (
        <span id={id} role="tooltip" className={styles.pop}>
          {content}
        </span>
      )}
    </span>
  );
}
