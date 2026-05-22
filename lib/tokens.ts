// Design tokens — the single source of truth for color, spacing, type, radius, shadow.
// Palette confirmed against luckin-ops-dashboard/app/data/constants.js:3-27.

export const palette = {
  primary: '#0A2E6C',
  primaryLight: '#1A4B9C',
  accent: '#4A90D9',
  accentLight: '#7CB9E8',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',

  bg: '#FFFFFF',
  surface: '#FFFFFF',
  surfaceAlt: '#F9FAFB',
  border: '#E5E7EB',
  borderStrong: '#D1D5DB',

  text: '#0F172A',
  textMuted: '#64748B',
  textInverted: '#FFFFFF',
  textPlaceholder: '#94A3B8',

  gray50: '#F9FAFB',
  gray100: '#F3F4F6',
  gray200: '#E5E7EB',
  gray300: '#D1D5DB',
  gray400: '#9CA3AF',
  gray500: '#6B7280',
  gray600: '#4B5563',
  gray700: '#374151',
  gray800: '#1F2937',
  gray900: '#111827',
} as const;

export const space = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  '2xl': '32px',
  '3xl': '48px',
} as const;

export const radius = {
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  pill: '999px',
} as const;

export const shadow = {
  sm: '0 1px 2px rgba(15, 23, 42, 0.05)',
  md: '0 2px 6px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04)',
  lg: '0 8px 24px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.04)',
} as const;

export const type = {
  family: '"Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, -apple-system, sans-serif',
  sizeKpiValue: '28px',
  sizeKpiTitle: '13px',
  sizeBody: '14px',
  sizeSmall: '12px',
  sizeHeader: '15px',
  weightRegular: 400,
  weightMedium: 500,
  weightSemibold: 600,
  weightBold: 700,
} as const;

export const cssVars = `
  --color-primary: ${palette.primary};
  --color-primary-light: ${palette.primaryLight};
  --color-accent: ${palette.accent};
  --color-accent-light: ${palette.accentLight};
  --color-success: ${palette.success};
  --color-warning: ${palette.warning};
  --color-danger: ${palette.danger};
  --color-bg: ${palette.bg};
  --color-surface: ${palette.surface};
  --color-surface-alt: ${palette.surfaceAlt};
  --color-border: ${palette.border};
  --color-border-strong: ${palette.borderStrong};
  --color-text: ${palette.text};
  --color-text-muted: ${palette.textMuted};
  --color-text-inverted: ${palette.textInverted};
  --color-gray-50: ${palette.gray50};
  --color-gray-100: ${palette.gray100};
  --color-gray-200: ${palette.gray200};
  --color-gray-300: ${palette.gray300};
  --color-gray-400: ${palette.gray400};
  --color-gray-500: ${palette.gray500};
  --color-gray-600: ${palette.gray600};
  --color-gray-700: ${palette.gray700};
  --space-xs: ${space.xs};
  --space-sm: ${space.sm};
  --space-md: ${space.md};
  --space-lg: ${space.lg};
  --space-xl: ${space.xl};
  --space-2xl: ${space['2xl']};
  --space-3xl: ${space['3xl']};
  --radius-sm: ${radius.sm};
  --radius-md: ${radius.md};
  --radius-lg: ${radius.lg};
  --radius-xl: ${radius.xl};
  --radius-pill: ${radius.pill};
  --shadow-sm: ${shadow.sm};
  --shadow-md: ${shadow.md};
  --shadow-lg: ${shadow.lg};
  --font-family: ${type.family};
`;
