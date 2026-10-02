// کامپوننت WidgetGrid برای نمایش ویجت‌های داشبورد

import { useEffect, useState } from 'react'
import { dashboardApi } from '../../api/client'
import { formatMoney } from '../../utils/format'
import { cn } from '../../styles/tw'

const SIZE_CLASSES = {
  small: 'col-span-3',
  medium: 'col-span-4',
  large: 'col-span-6',
  wide: 'col-span-12',
}

export default function WidgetGrid({ widgets, editMode, onEdit, onDelete }) {
  return (
    <div className="grid grid-cols-12 gap-5 auto-rows-fr max-compact:grid-cols-6 max-md:grid-cols-1">
      {widgets.map((widget) => (
        <div
          key={widget.id}
          className={cn(
            SIZE_CLASSES[widget.size] || SIZE_CLASSES.medium,
            'max-compact:col-span-full'
          )}
        >
          <WidgetContainer
            widget={widget}
            editMode={editMode}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      ))}
    </div>
  )
}

function WidgetContainer({ widget, editMode, onEdit, onDelete }) {
  return (
    <div className="liquid-glass liquid-glass--panel liquid-glass--jelly h-full rounded-pill overflow-hidden">
      {editMode && (
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2 bg-layer-1">
          <span className="text-xs text-muted">{widget.widget_type}</span>
          <div className="flex gap-1">
            <button
              onClick={() => onEdit(widget)}
              className="text-xs text-accent hover:underline"
            >
              ویرایش
            </button>
            <button
              onClick={() => onDelete(widget.id)}
              className="text-xs text-danger hover:underline"
            >
              حذف
            </button>
          </div>
        </div>
      )}
      
      <div className="p-4">
        <h3 className="mb-3 font-display text-base font-bold">{widget.title}</h3>
        <div className="text-sm text-muted">
          <WidgetContent widget={widget} />
        </div>
      </div>
    </div>
  )
}

function WidgetContent({ widget }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const metric = widget.config?.metric

  useEffect(() => {
    let cancelled = false
    if (!metric) return undefined
    dashboardApi.metric(metric, {
      time_range: widget.config?.time_range || 'month',
      ...(widget.config?.branch ? { branch: widget.config.branch } : {}),
    }).then((result) => {
      if (!cancelled) {
        setData(result)
        setError('')
      }
    }).catch((err) => {
      if (!cancelled) setError(err.message)
    })
    return () => { cancelled = true }
  }, [metric, widget.config?.time_range, widget.config?.branch])

  if (!metric) return <div className="py-8 text-center">شاخص انتخاب نشده است.</div>
  if (error) return <div className="py-8 text-center text-danger">{error}</div>
  if (data == null) return <div className="py-8 text-center">در حال بارگذاری…</div>

  if (widget.widget_type === 'stat_card' && !Array.isArray(data)) {
    const value = data.total ?? data.count ?? 0
    return (
      <div className="py-5 text-center">
        <strong className="block text-2xl text-foreground">{formatMoney(Number(value || 0))}</strong>
        {data.count != null && data.total != null ? <span>{data.count} مورد</span> : null}
      </div>
    )
  }

  const rows = Array.isArray(data)
    ? data
    : Object.entries(data).map(([name, value]) => ({ name, value }))
  const values = rows.map((row) => Number(row.total ?? row.count ?? row.value ?? 0))
  const max = Math.max(...values, 1)

  if (widget.widget_type === 'table') {
    return (
      <div className="space-y-2">
        {rows.slice(0, 10).map((row, index) => (
          <div key={row.id || row.date || row.name || index} className="flex justify-between gap-3 border-b border-border-subtle py-2">
            <span>{row.name || row.date || `ردیف ${index + 1}`}</span>
            <strong>{formatMoney(values[index])}</strong>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {rows.slice(0, 30).map((row, index) => (
        <div key={row.id || row.date || row.name || index} className="flex items-center gap-2">
          <span className="w-20 truncate text-xs">{row.name || row.date || index + 1}</span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-layer-2">
            <div className="h-full rounded bg-accent" style={{ width: `${Math.max(2, (values[index] / max) * 100)}%` }} />
          </div>
          <span className="w-24 text-left text-xs">{formatMoney(values[index])}</span>
        </div>
      ))}
    </div>
  )
}
