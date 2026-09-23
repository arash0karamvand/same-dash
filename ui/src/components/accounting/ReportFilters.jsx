// فیلترهای گزارش‌های حسابداری

import { Field, FilterBar, Button } from '../ui'
import Select from '../Select'
import PersianDateInput from '../PersianDateInput'
import Icon from '../icons/Icon'
import { useConfig } from '../../context/ConfigContext'

export default function ReportFilters({
  filters,
  onChange,
  accountOptions = [],
  subsidiaryOptions = [],
  showSubsidiary = false,
  onReset,
}) {
  const { choices } = useConfig()
  const accountClassOptions = [{ value: '', label: 'همه گروه‌ها' }, ...choices('account_class')]

  const handleChange = (key, value) => {
    onChange({ ...filters, [key]: value })
  }

  return (
    <FilterBar>
      <Field label="گروه حساب">
        <Select
          value={filters.accountClass || ''}
          onChange={(value) => handleChange('accountClass', value)}
          options={accountClassOptions}
        />
      </Field>

      {accountOptions.length > 0 && (
        <Field label="حساب کل">
          <Select
            value={filters.accountId || ''}
            onChange={(value) => handleChange('accountId', value)}
            options={[{ value: '', label: 'همه حساب‌ها' }, ...accountOptions]}
          />
        </Field>
      )}

      {showSubsidiary && subsidiaryOptions.length > 0 && (
        <Field label="حساب معین">
          <Select
            value={filters.subsidiaryId || ''}
            onChange={(value) => handleChange('subsidiaryId', value)}
            options={[{ value: '', label: 'همه معین‌ها' }, ...subsidiaryOptions]}
          />
        </Field>
      )}

      <Field label="از تاریخ">
        <PersianDateInput
          value={filters.dateFrom || ''}
          onChange={(val) => handleChange('dateFrom', val)}
        />
      </Field>

      <Field label="تا تاریخ">
        <PersianDateInput
          value={filters.dateTo || ''}
          onChange={(val) => handleChange('dateTo', val)}
        />
      </Field>

      <Field label="فقط تایید شده">
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input
            type="checkbox"
            checked={filters.approvedOnly || false}
            onChange={(e) => handleChange('approvedOnly', e.target.checked)}
          />
          <span>نمایش اسناد تایید شده</span>
        </label>
      </Field>

      {onReset && (
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <Button variant="secondary" onClick={onReset}>
            <Icon name="x" size={16} />
            <span>پاک کردن فیلترها</span>
          </Button>
        </div>
      )}
    </FilterBar>
  )
}
