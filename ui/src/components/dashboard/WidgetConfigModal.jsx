// مودال تنظیمات ویجت

import { useMemo, useState } from 'react'
import { Button, Field, Modal } from '../ui'
import { tw } from '../../styles/tw'
import { useAuth } from '../../context/AuthContext'
import { hasPermission } from '../../utils/permissions'

const WIDGET_TYPES = [
  { value: 'stat_card', label: 'کارت آماری' },
  { value: 'chart_bar', label: 'نمودار ستونی' },
  { value: 'chart_line', label: 'نمودار خطی' },
  { value: 'chart_pie', label: 'نمودار دایره‌ای' },
  { value: 'table', label: 'جدول' },
]

const SIZE_OPTIONS = [
  { value: 'small', label: 'کوچک' },
  { value: 'medium', label: 'متوسط' },
  { value: 'large', label: 'بزرگ' },
  { value: 'wide', label: 'عریض' },
]

const METRICS = [
  { value: 'sales_today', label: 'فروش امروز' },
  { value: 'sales_week', label: 'فروش هفته' },
  { value: 'sales_month', label: 'فروش ماه' },
  { value: 'revenue_trend', label: 'روند فروش' },
  { value: 'top_customers', label: 'مشتریان برتر' },
  { value: 'inventory_status', label: 'وضعیت موجودی' },
  { value: 'material_inventory_value', label: 'ارزش موجودی متریال', cost: true },
  { value: 'production_cost_summary', label: 'خلاصه بهای تولید', cost: true },
  { value: 'production_cost_trend', label: 'روند بهای تولید', cost: true },
]

export default function WidgetConfigModal({ widget, open, onClose, onSave }) {
  const { user } = useAuth()
  const canViewCosts = hasPermission(user, 'view_accounting') && hasPermission(user, 'view_reports')
  const metrics = useMemo(() => METRICS.filter((metric) => !metric.cost || canViewCosts), [canViewCosts])
  const [config, setConfig] = useState(
    widget || {
      widget_type: 'stat_card',
      title: '',
      size: 'medium',
      config: {},
    }
  )

  const handleSave = () => {
    onSave(config)
    onClose()
  }

  return (
    <Modal title={widget ? 'ویرایش ویجت' : 'افزودن ویجت'} open={open} onClose={onClose}>
      <div className={tw.form}>
        <Field label="نوع ویجت">
          <select
            value={config.widget_type}
            onChange={(e) => setConfig({ ...config, widget_type: e.target.value })}
            className={tw.searchInput}
          >
            {WIDGET_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="عنوان">
          <input
            type="text"
            value={config.title}
            onChange={(e) => setConfig({ ...config, title: e.target.value })}
            className={tw.searchInput}
            placeholder="عنوان ویجت..."
          />
        </Field>

        <Field label="شاخص">
          <select
            value={config.config?.metric || ''}
            onChange={(e) => setConfig({ ...config, config: { ...(config.config || {}), metric: e.target.value } })}
            className={tw.searchInput}
          >
            <option value="">انتخاب شاخص…</option>
            {metrics.map((metric) => <option key={metric.value} value={metric.value}>{metric.label}</option>)}
          </select>
        </Field>

        <Field label="بازه زمانی">
          <select
            value={config.config?.time_range || 'month'}
            onChange={(e) => setConfig({ ...config, config: { ...(config.config || {}), time_range: e.target.value } })}
            className={tw.searchInput}
          >
            <option value="week">هفته</option>
            <option value="month">ماه</option>
            <option value="year">سال</option>
          </select>
        </Field>

        <Field label="اندازه">
          <select
            value={config.size}
            onChange={(e) => setConfig({ ...config, size: e.target.value })}
            className={tw.searchInput}
          >
            {SIZE_OPTIONS.map((size) => (
              <option key={size.value} value={size.value}>
                {size.label}
              </option>
            ))}
          </select>
        </Field>

        <div className={tw.formActions}>
          <Button onClick={handleSave} disabled={!config.title || !config.config?.metric}>
            ذخیره
          </Button>
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
        </div>
      </div>
    </Modal>
  )
}
