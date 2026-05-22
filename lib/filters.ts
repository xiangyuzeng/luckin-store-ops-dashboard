// Filter state shared by all boards. State lives in URL searchParams so deep links work,
// reloads survive, and stakeholders can share a focused view.

import type { Payload, ShopNo, StoreInfo } from '@/lib/types';

export const ALL = 'ALL' as const;
export type AllOr<T extends string> = T | typeof ALL;

export interface FilterState {
  from: string; // ISO YYYY-MM-DD
  to: string;
  city: AllOr<string>;
  region: AllOr<string>;
  shop: AllOr<ShopNo>;
}

export interface NormalizedFilters extends FilterState {
  shopNos: ShopNo[] | null; // null === all matching stores (no shop filter)
  warnings: string[]; // user-facing notes (e.g. range clamped)
}

export function defaultFilters(payload: Payload): FilterState {
  const today = payload.meta.retained_to;
  return {
    from: today,
    to: today,
    city: ALL,
    region: ALL,
    shop: ALL,
  };
}

export function parseFiltersFromSearch(
  search: URLSearchParams,
  payload: Payload,
): FilterState {
  const d = defaultFilters(payload);
  const from = search.get('from') ?? d.from;
  const to = search.get('to') ?? d.to;
  const city = (search.get('city') ?? ALL) as AllOr<string>;
  const region = (search.get('region') ?? ALL) as AllOr<string>;
  const shop = (search.get('shop') ?? ALL) as AllOr<ShopNo>;
  return { from, to, city, region, shop };
}

export function filtersToSearch(filters: FilterState): URLSearchParams {
  const p = new URLSearchParams();
  p.set('from', filters.from);
  p.set('to', filters.to);
  if (filters.city !== ALL) p.set('city', filters.city);
  if (filters.region !== ALL) p.set('region', filters.region);
  if (filters.shop !== ALL) p.set('shop', filters.shop);
  return p;
}

export function normalize(state: FilterState, payload: Payload): NormalizedFilters {
  const warnings: string[] = [];
  let { from, to } = state;
  const { retained_from, retained_to } = payload.meta;
  if (from > to) [from, to] = [to, from];
  if (from < retained_from) {
    from = retained_from;
    warnings.push('rangeNoteOutside');
  }
  if (to > retained_to) {
    to = retained_to;
    warnings.push('rangeNoteOutside');
  }

  const matching = listStoresMatching(payload.stores, state.city, state.region);
  // Shop filter: keep only operating stores; if explicit shop doesn't exist in matching, ignore it.
  let shopNos: ShopNo[] | null = null;
  if (state.shop !== ALL) {
    if (matching.some((s) => s.shop_no === state.shop)) {
      shopNos = [state.shop];
    } else {
      // Stale explicit shop — fall back to all matching operating stores.
      shopNos = matching.map((s) => s.shop_no);
    }
  } else {
    // No explicit shop: limit to operating-today stores.
    shopNos = matching.map((s) => s.shop_no);
  }

  return { ...state, from, to, shopNos, warnings: dedup(warnings) };
}

function dedup<T>(arr: T[]): T[] {
  return Array.from(new Set(arr));
}

// ── cascading list helpers ──────────────────────────────────────────

export function listCities(stores: StoreInfo[]): string[] {
  return dedup(stores.filter((s) => s.operating_today).map((s) => s.city)).sort();
}

export function listRegions(stores: StoreInfo[], city: AllOr<string>): string[] {
  const filtered = stores.filter((s) => s.operating_today && (city === ALL || s.city === city));
  return dedup(filtered.map((s) => s.region)).sort();
}

export function listStoresMatching(
  stores: StoreInfo[],
  city: AllOr<string>,
  region: AllOr<string>,
): StoreInfo[] {
  return stores
    .filter((s) => s.operating_today)
    .filter((s) => city === ALL || s.city === city)
    .filter((s) => region === ALL || s.region === region);
}
