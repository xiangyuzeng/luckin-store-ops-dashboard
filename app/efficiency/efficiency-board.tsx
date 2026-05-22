'use client';

import { useMemo } from 'react';
import { FilterBar } from '@/components/layout/FilterBar';
import { EfficiencyChart } from '@/components/chart/EfficiencyChart';
import { IntervalEfficiencyTable } from '@/components/table/IntervalEfficiencyTable';
import { aggregateIntervalEfficiency, filterHalfHourEff } from '@/lib/aggregate';
import { normalize } from '@/lib/filters';
import { useUrlFilters } from '@/lib/use-url-filters';
import type { Payload } from '@/lib/types';
import styles from './efficiency.module.css';

interface Props {
  payload: Payload;
}

export function EfficiencyBoard({ payload }: Props) {
  const [filters, setFilters] = useUrlFilters(payload);
  const normalized = useMemo(() => normalize(filters, payload), [filters, payload]);

  const halfHourRows = useMemo(
    () => filterHalfHourEff(payload.half_hour_rows, normalized.shopNos, normalized.from, normalized.to),
    [payload.half_hour_rows, normalized.shopNos, normalized.from, normalized.to],
  );
  const interval = useMemo(() => aggregateIntervalEfficiency(halfHourRows), [halfHourRows]);

  return (
    <main className={styles.main}>
      <FilterBar payload={payload} filters={filters} onChange={setFilters} />
      <EfficiencyChart data={interval} />
      <IntervalEfficiencyTable rows={interval} from={normalized.from} to={normalized.to} />
    </main>
  );
}
