import type { SourceFilter, SourceModule } from './types'

export const SOURCE_FILTER_OPTIONS: { value: SourceFilter; label: string }[] = [
  { value: 'automatic', label: 'خودکار — انبار، فروش و کارخانه' },
  { value: 'warehouse', label: 'انبار' },
  { value: 'sales', label: 'فروش' },
  { value: 'factory', label: 'کارخانه' },
  { value: 'manual', label: 'دستی' },
  { value: '', label: 'همه اسناد' },
]

export const SOURCE_LABELS: Record<SourceModule, string> = {
  sales: 'فروش',
  warehouse: 'انبار',
  factory: 'کارخانه',
  manual: 'دستی',
}

export function sourceClass(module: string): string {
  if (module === 'sales' || module === 'warehouse' || module === 'factory' || module === 'manual') {
    return `acct-source-badge is-${module}`
  }
  return 'acct-source-badge'
}
