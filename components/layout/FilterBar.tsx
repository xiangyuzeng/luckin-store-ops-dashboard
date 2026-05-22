'use client';

import { useCallback, useMemo } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import type { Payload } from '@/lib/types';
import {
  ALL,
  defaultFilters,
  filtersToSearch,
  listCities,
  listRegions,
  listStoresMatching,
  parseFiltersFromSearch,
  type FilterState,
} from '@/lib/filters';
import { labels } from '@/lib/labels';
import styles from './FilterBar.module.css';

interface Props {
  payload: Payload;
}

export function FilterBar({ payload }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const filters = useMemo(() => parseFiltersFromSearch(new URLSearchParams(search.toString()), payload), [search, payload]);

  const apply = useCallback(
    (next: FilterState) => {
      const params = filtersToSearch(next);
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router],
  );

  const cities = useMemo(() => listCities(payload.stores), [payload.stores]);
  const regions = useMemo(() => listRegions(payload.stores, filters.city), [payload.stores, filters.city]);
  const stores = useMemo(
    () => listStoresMatching(payload.stores, filters.city, filters.region),
    [payload.stores, filters.city, filters.region],
  );

  const onCityChange = (city: string) => {
    apply({ ...filters, city: city === ALL ? ALL : city, region: ALL, shop: ALL });
  };
  const onRegionChange = (region: string) => {
    apply({ ...filters, region: region === ALL ? ALL : region, shop: ALL });
  };
  const onShopChange = (shop: string) => {
    apply({ ...filters, shop: shop === ALL ? ALL : shop });
  };
  const onFromChange = (from: string) => {
    apply({ ...filters, from });
  };
  const onToChange = (to: string) => {
    apply({ ...filters, to });
  };
  const onReset = () => {
    apply(defaultFilters(payload));
  };

  const { retained_from, retained_to } = payload.meta;

  return (
    <section className={styles.bar} aria-label={labels.filter.dateRange}>
      <div className={styles.group}>
        <label className={styles.label}>{labels.filter.dateRange}</label>
        <div className={styles.dateRow}>
          <input
            type="date"
            className={styles.input}
            value={filters.from}
            min={retained_from}
            max={retained_to}
            onChange={(e) => onFromChange(e.target.value)}
            aria-label={labels.filter.from}
          />
          <span className={styles.dash}>—</span>
          <input
            type="date"
            className={styles.input}
            value={filters.to}
            min={retained_from}
            max={retained_to}
            onChange={(e) => onToChange(e.target.value)}
            aria-label={labels.filter.to}
          />
        </div>
      </div>

      <div className={styles.group}>
        <label className={styles.label} htmlFor="filter-city">{labels.filter.city}</label>
        <select
          id="filter-city"
          className={styles.select}
          value={filters.city}
          onChange={(e) => onCityChange(e.target.value)}
        >
          <option value={ALL}>{labels.filter.all}</option>
          {cities.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className={styles.group}>
        <label className={styles.label} htmlFor="filter-region">{labels.filter.region}</label>
        <select
          id="filter-region"
          className={styles.select}
          value={filters.region}
          onChange={(e) => onRegionChange(e.target.value)}
        >
          <option value={ALL}>{labels.filter.all}</option>
          {regions.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      <div className={styles.group}>
        <label className={styles.label} htmlFor="filter-shop">{labels.filter.store}</label>
        <select
          id="filter-shop"
          className={styles.select}
          value={filters.shop}
          onChange={(e) => onShopChange(e.target.value)}
        >
          <option value={ALL}>{labels.filter.all}</option>
          {stores.map((s) => (
            <option key={s.shop_no} value={s.shop_no}>
              {s.shop_name}（{s.shop_no}）
            </option>
          ))}
        </select>
      </div>

      <button className={styles.reset} type="button" onClick={onReset}>
        {labels.filter.reset}
      </button>
    </section>
  );
}
