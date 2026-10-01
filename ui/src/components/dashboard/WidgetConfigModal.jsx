// مودال تنظیمات ویجت

import { useState } from 'react'
import { Button, Field, Modal } from '../ui'
import { cn, tw } from '../../styles/tw'

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

export default function WidgetConfigModal({ widget, open, onClose, onSave }) {
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
          <Button onClick={handleSave} disabled={!config.title}>
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
