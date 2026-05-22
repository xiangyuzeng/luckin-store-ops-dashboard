import Link from 'next/link';
import { labels } from '@/lib/labels';
import { FreshnessBadge } from '@/components/shared/FreshnessBadge';
import styles from './Header.module.css';

interface Props {
  generatedAt: string;
  active: 'home' | 'preview' | 'efficiency';
}

export function Header({ generatedAt, active }: Props) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brandBlock}>
          <span className={styles.brandMark} aria-hidden>
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
              <path d="M8 12.5l2.5 2.5L16 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div>
            <div className={styles.brand}>{labels.brand}</div>
            <div className={styles.title}>{labels.appTitle}</div>
          </div>
        </div>
        <nav className={styles.nav} aria-label="主导航">
          <Link href="/" className={`${styles.tab} ${active === 'home' ? styles.tabActive : ''}`}>
            {labels.nav.home}
          </Link>
          <Link href="/preview" className={`${styles.tab} ${active === 'preview' ? styles.tabActive : ''}`}>
            {labels.nav.preview}
          </Link>
          <Link href="/efficiency" className={`${styles.tab} ${active === 'efficiency' ? styles.tabActive : ''}`}>
            {labels.nav.efficiency}
          </Link>
        </nav>
        <FreshnessBadge generatedAt={generatedAt} />
      </div>
    </header>
  );
}
