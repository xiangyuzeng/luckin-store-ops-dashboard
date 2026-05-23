import { Header } from '@/components/layout/Header';
import { DataInfoStrip } from '@/components/layout/DataInfoStrip';
import { KpiCard } from '@/components/kpi/KpiCard';
import { KpiGroup } from '@/components/kpi/KpiGroup';
import { loadPayload } from '@/lib/payload';
import { KPI_GROUPS, METRIC_BY_KEY } from '@/lib/metrics';
import { getMetricValue } from '@/lib/aggregate';
import { computeComparison } from '@/lib/compare';
import { labels } from '@/lib/labels';
import styles from './preview.module.css';

// /preview is a static, "everything at a glance" view — no filter bar, no tables.
// Range = today snapshot (last available date in payload).
export default function PreviewPage() {
  const payload = loadPayload();
  const lastDate = payload.meta.retained_to;
  const range = { from: lastDate, to: lastDate };

  const rowsInRange = payload.daily_store_rows.filter((r) => r.date >= range.from && r.date <= range.to);

  return (
    <>
      <Header generatedAt={payload.meta.generated_at} active="preview" />
      <DataInfoStrip meta={payload.meta} />
      <main className={styles.main}>
        <div className={styles.hero}>
          <h1 className={styles.title}>{labels.preview.title}</h1>
          <p className={styles.subtitle}>{labels.preview.subtitle}</p>
        </div>

        <div className={styles.groups}>
          {KPI_GROUPS.map((g) => (
            <KpiGroup key={g.id} id={g.id} label={labels.groups[g.id]}>
              {g.keys.map((k) => {
                const metric = METRIC_BY_KEY[k];
                const value = getMetricValue(rowsInRange, k);
                const comparisons = metric.comparisons.map((kind) => {
                  const c = computeComparison(
                    payload.daily_store_rows,
                    null,
                    range,
                    payload.meta.retained_from,
                    kind,
                    k,
                  );
                  return { kind, delta: c.delta };
                });
                return <KpiCard key={k} metric={metric} value={value} comparisons={comparisons} />;
              })}
            </KpiGroup>
          ))}
        </div>
      </main>
    </>
  );
}
