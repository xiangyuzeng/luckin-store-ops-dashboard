import styles from './KpiGroup.module.css';

interface Props {
  id: 'business' | 'efficiency' | 'quality';
  label: string;
  children: React.ReactNode;
}

export function KpiGroup({ id, label, children }: Props) {
  return (
    <section className={styles.group} data-group={id}>
      <header className={styles.header}>
        <span className={styles.bar} aria-hidden />
        <h2 className={styles.label}>{label}</h2>
      </header>
      <div className={styles.grid}>{children}</div>
    </section>
  );
}
