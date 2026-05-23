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
          <span className={styles.brand}>{labels.brand}</span>
          <span className={styles.divider} aria-hidden>·</span>
          <span className={styles.title}>{labels.appTitle}</span>
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
