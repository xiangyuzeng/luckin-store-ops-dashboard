// Client-side XLSX + CSV export for any table that can produce a row array.

'use client';

import * as XLSX from 'xlsx';
import { isoToCompact } from '@/lib/format';

export interface ExportColumn<R> {
  header: string;
  accessor: (row: R) => string | number | null;
}

export interface ExportOptions<R> {
  rows: R[];
  columns: ExportColumn<R>[];
  filenameBase: string;        // e.g. "门店KPI"
  from?: string;               // optional range used in filename
  to?: string;
}

function buildFilename(opts: ExportOptions<unknown>, ext: 'xlsx' | 'csv'): string {
  const { filenameBase, from, to } = opts;
  if (from && to) return `${filenameBase}_${isoToCompact(from)}_${isoToCompact(to)}.${ext}`;
  return `${filenameBase}.${ext}`;
}

function toMatrix<R>(opts: ExportOptions<R>): Array<Array<string | number | null>> {
  const headerRow = opts.columns.map((c) => c.header);
  const body = opts.rows.map((r) => opts.columns.map((c) => c.accessor(r)));
  return [headerRow, ...body];
}

export function exportXlsx<R>(opts: ExportOptions<R>): void {
  const matrix = toMatrix(opts);
  const ws = XLSX.utils.aoa_to_sheet(matrix);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1');
  XLSX.writeFile(wb, buildFilename(opts as ExportOptions<unknown>, 'xlsx'));
}

export function exportCsv<R>(opts: ExportOptions<R>): void {
  const matrix = toMatrix(opts);
  const ws = XLSX.utils.aoa_to_sheet(matrix);
  const csv = XLSX.utils.sheet_to_csv(ws);
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = buildFilename(opts as ExportOptions<unknown>, 'csv');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Login-gate for the FULL export — passphrase stored in localStorage; no real auth.
// NEXT_PUBLIC_EXPORT_REQUIRE_AUTH=true requires unlock for unfiltered exports.
const STORAGE_KEY = 'luckin-export-unlocked';

export function isFullExportUnlocked(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(STORAGE_KEY) === '1';
}

export function unlockFullExport(passphrase: string): boolean {
  if (typeof window === 'undefined') return false;
  // The gate is intentionally lightweight — it discourages casual full exports without being a real auth boundary.
  const expected = process.env.NEXT_PUBLIC_EXPORT_PASSPHRASE ?? 'luckin-ops-2026';
  if (passphrase.trim() === expected) {
    window.localStorage.setItem(STORAGE_KEY, '1');
    return true;
  }
  return false;
}

export function isExportAuthRequired(): boolean {
  return process.env.NEXT_PUBLIC_EXPORT_REQUIRE_AUTH === 'true';
}
