'use client';

import { useMemo, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { FilterBar } from '@/components/layout/FilterBar';
import { EfficiencyChart } from '@/components/chart/EfficiencyChart';
import { IntervalEfficiencyTable } from '@/components/table/IntervalEfficiencyTable';
import { aggregateIntervalEfficiency, filterHalfHourEff } from '@/lib/aggregate';
import { normalize, parseFiltersFromSearch } from '@/lib/filters';
import type { Payload } from '@/lib/types';
import styles from './efficiency.module.css';

interface Props {
  payload: Payload;
}

function EfficiencyBoardInner({ payload }: Props) {
  const search = useSearchParams();
  const state = useMemo(
    () => parseFiltersFromSearch(new URLSearchParams(search.toString()), payload),
    [search, payload],
  );
  const normalized = useMemo(() => normalize(state, payload), [state, payload]);

  const halfHourRows = useMemo(
    () => filterHalfHourEff(payload.half_hour_rows, normalized.shopNos, normalized.from, normalized.to),
    [payload.half_hour_rows, normalized.shopNos, normalized.from, normalized.to],
  );
  const interval = useMemo(() => aggregateIntervalEfficiency(halfHourRows), [halfHourRows]);

  return (
    <main className={styles.main}>
      <Suspense fallback={null}>
        <FilterBar payload={payload} />
      </Suspense>
      <EfficiencyChart data={interval} />
      <IntervalEfficiencyTable rows={interval} from={normalized.from} to={normalized.to} />
    </main>
  );
}

export function EfficiencyBoard({ payload }: Props) {
  return (
    <Suspense fallback={null}>
      <EfficiencyBoardInner payload={payload} />
    </Suspense>
  );
}
