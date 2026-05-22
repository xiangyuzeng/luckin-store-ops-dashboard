'use client';

// useUrlFilters — local filter state with URL sync.
//
// Why this exists: `useSearchParams()` from `next/navigation` forces any client
// component that calls it to be wrapped in <Suspense>, and Next 14 then renders
// only the Suspense fallback in the static prerender. That means the static
// HTML on Vercel has NO board content until client hydration paints it in.
//
// Instead we own the filter state in React useState (initialized to defaults so
// the SSR HTML renders the full board), then sync from / to window.location on
// the client. URL deep-links still work; the SSR snapshot now shows real data.

import { useCallback, useEffect, useState } from 'react';
import type { Payload } from '@/lib/types';
import {
  defaultFilters,
  filtersToSearch,
  parseFiltersFromSearch,
  type FilterState,
} from '@/lib/filters';

export function useUrlFilters(payload: Payload): [FilterState, (next: FilterState) => void] {
  const [filters, setFilters] = useState<FilterState>(() => defaultFilters(payload));

  // Mount sync: if the URL already carries filters, adopt them. Done in an effect
  // so SSR + first paint use defaults — no hydration mismatch.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if ([...params.keys()].length === 0) return;
    setFilters(parseFiltersFromSearch(params, payload));
  }, [payload]);

  const apply = useCallback((next: FilterState) => {
    setFilters(next);
    if (typeof window === 'undefined') return;
    const params = filtersToSearch(next);
    const qs = params.toString();
    const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    window.history.replaceState(null, '', url);
  }, []);

  return [filters, apply];
}
