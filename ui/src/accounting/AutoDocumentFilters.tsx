import { Button, Field, FilterBar } from '../components/ui'
import Select from '../components/Select'
import PersianDateInput from '../components/PersianDateInput'
import Icon from '../components/icons/Icon'
import { SOURCE_FILTER_OPTIONS } from './sourceModules'
import type { DocumentFilters } from './types'

const STATUS_OPTIONS = [
  { value: '', label: 'همه وضعیت‌ها' },
  { value: 'draft', label: 'پیش‌نویس' },
  { value: 'pending_review', label: 'در انتظار بررسی' },
  { value: 'posted', label: 'ثبت شده' },
  { value: 'rejected', label: 'رد شده' },
]

type Props = {
  filters: DocumentFilters
  onChange: (patch: Partial<DocumentFilters>) => void
  onApply: () => void
  onReset: () => void
}

export default function AutoDocumentFilters({ filters, onChange, onApply, onReset }: Props) {
  return (
    <FilterBar>
      <Field label="ماژول مبدا">
        <Select
          value={filters.sourceModule}
          onChange={(value: string) => onChange({ sourceModule: value as DocumentFilters['sourceModule'] })}
          options={SOURCE_FILTER_OPTIONS}
        />
      </Field>
      <Field label="شماره سند">
        <input
          className="acct-filter-input"
          inputMode="numeric"
          value={filters.documentNumber}
          onChange={(event) => onChange({ documentNumber: event.target.value.replace(/[^\d]/g, '') })}
          placeholder="مثلاً ۱۰۲۴"
        />
      </Field>
      <Field label="از تاریخ">
        <PersianDateInput value={filters.dateFrom} onChange={(value: string) => onChange({ dateFrom: value || '' })} />
      </Field>
      <Field label="تا تاریخ">
        <PersianDateInput value={filters.dateTo} onChange={(value: string) => onChange({ dateTo: value || '' })} />
      </Field>
      <Field label="وضعیت">
        <Select
          value={filters.status}
          onChange={(value: string) => onChange({ status: value })}
          options={STATUS_OPTIONS}
        />
      </Field>
      <div className="acct-filter-actions">
        <Button variant="primary" onClick={onApply}>
          <Icon name="search" size={16} />
          <span>اعمال فیلتر</span>
        </Button>
        <Button variant="secondary" onClick={onReset}>پاک کردن</Button>
      </div>
    </FilterBar>
  )
}
