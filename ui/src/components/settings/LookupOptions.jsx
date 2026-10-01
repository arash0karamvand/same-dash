// گزینه‌های فرم — انتخاب دسته از فهرست گروه‌بندی‌شده، نه ردیف تب.

import { useMemo, useState } from 'react'
import { Button, EmptyState } from '../ui'
import Icon from '../icons/Icon'
import { cn, tw } from '../../styles/tw'
import { toPersianDigits } from '../../utils/jalali'

const CATEGORY_LABELS = {
  payment_method: 'روش پرداخت',
  payment_status: 'وضعیت پرداخت',
  order_kind: 'نوع سفارش',
  order_status: 'وضعیت سفارش',
  discount_type: 'نوع تخفیف',
  accounting_mode: 'حالت حسابداری',
  workflow_stage: 'مرحله گردش سفارش',
  fulfillment_route: 'مسیر تحویل',
  receive_kind: 'نوع دریافت کارخانه',
  attendance_status: 'وضعیت حضور',
  approval_status: 'وضعیت تایید',
  staff_kind: 'نوع پرسنل',
  material_unit: 'واحد متریال',
  document_code: 'کد نوع سند',
  account_class: 'گروه حساب',
  normal_balance: 'ماهیت حساب',
  source_module: 'ماژول مبدأ حسابداری',
  stock_source: 'منبع موجودی',
  location_kind: 'نوع محل',
  frame_design_style: 'سبک طراحی کلاف',
  frame_wood_type: 'جنس چوب',
  frame_piece_kind: 'نوع قطعه مبل',
  frame_arm_style: 'حالت دسته',
  frame_component_type: 'نوع قطعه سرویس',
  frame_rule_key: 'قانون متریال کلاف',
  frame_unit: 'واحد کلاف',
  build_model: 'مدل ساخت',
  pipeline_end: 'پایان خط تولید',
  workshop_recipe_kind: 'نوع دستور کارگاه',
  workshop_paint_category: 'دسته رنگ',
  workshop_fabric_category: 'دسته پارچه',
  workshop_fabric_company: 'شرکت پارچه',
  workshop_fabric_country: 'کشور پارچه',
  fabric_issue_status: 'وضعیت حواله پارچه',
  beta_workshop_kind: 'نوع واحد نجاری',
  beta_carpentry_kind: 'نوع دستور نجاری',
  beta_carpentry_status: 'وضعیت دستور نجاری',
  beta_paint_kind: 'نوع سفارش رنگ',
  beta_paint_stage: 'مراحل خط رنگ',
  beta_upholstery_stage: 'مراحل رویه‌کوبی',
  beta_qc_status: 'وضعیت کنترل کیفیت',
  beta_qc_grade: 'گریدهای کنترل کیفیت',
  merchant_service_flow: 'جهت سرویس بازرگان',
  carpentry_tool_status: 'وضعیت ابزار نجاری',
  material_usage_kind: 'نوع مصرف متریال',
  material_valuation_method: 'روش ارزیابی',
  material_freight_treatment: 'نحوه ثبت حمل',
}

const GROUPS = [
  {
    id: 'sales',
    label: 'فروش و سفارش',
    categories: [
      'payment_method',
      'payment_status',
      'order_kind',
      'order_status',
      'discount_type',
      'accounting_mode',
      'workflow_stage',
      'fulfillment_route',
      'receive_kind',
    ],
  },
  {
    id: 'workshop',
    label: 'کارگاه و کارخانه',
    categories: [
      'workshop_recipe_kind',
      'workshop_paint_category',
      'workshop_fabric_category',
      'workshop_fabric_company',
      'workshop_fabric_country',
      'fabric_issue_status',
      'beta_workshop_kind',
      'beta_carpentry_kind',
      'beta_carpentry_status',
      'beta_paint_kind',
      'beta_paint_stage',
      'beta_upholstery_stage',
      'beta_qc_status',
      'beta_qc_grade',
      'merchant_service_flow',
      'carpentry_tool_status',
      'build_model',
      'pipeline_end',
    ],
  },
  {
    id: 'frames',
    label: 'کلاف و مبل',
    categories: [
      'frame_design_style',
      'frame_wood_type',
      'frame_piece_kind',
      'frame_arm_style',
      'frame_component_type',
      'frame_rule_key',
      'frame_unit',
    ],
  },
  {
    id: 'accounting',
    label: 'حسابداری و انبار',
    categories: [
      'material_unit',
      'material_usage_kind',
      'material_valuation_method',
      'material_freight_treatment',
      'document_code',
      'account_class',
      'normal_balance',
      'source_module',
      'stock_source',
      'location_kind',
    ],
  },
  {
    id: 'people',
    label: 'پرسنل',
    categories: ['staff_kind', 'attendance_status', 'approval_status'],
  },
]

function fold(value) {
  return String(value || '').trim().toLowerCase()
}

function categoryTitle(id, stored) {
  const label = String(stored || '').trim()
  if (label && label !== id) return label
  return CATEGORY_LABELS[id] || label || id
}

function CategoryButton({ item, active, onSelect }) {
  return (
    <button
      type="button"
      aria-current={active ? 'true' : undefined}
      className={cn(
        'flex w-full items-center justify-between gap-2 rounded-capsule border px-3 py-2 text-right font-inherit text-sm transition-[background,border-color] duration-150',
        active
          ? 'border-jelly-rim-strong bg-layer-3 font-semibold text-text shadow-[inset_0_1px_0_var(--jelly-gloss-top)]'
          : 'border-transparent bg-transparent text-text hover:border-jelly-rim hover:bg-layer-1',
      )}
      onClick={() => onSelect(item.id)}
    >
      <span className="min-w-0">
        <span className="block truncate">{item.label}</span>
        {item.matchHint && (
          <span className="mt-0.5 block truncate text-xs font-normal text-muted">{item.matchHint}</span>
        )}
      </span>
      <span className={cn('shrink-0 text-xs text-muted', tw.numDisplay)}>{toPersianDigits(item.count)}</span>
    </button>
  )
}

export default function LookupOptions({ lookups, onCreate, onEdit, onToggle }) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState('')
  const needle = fold(query)

  const catalog = useMemo(() => {
    const rowsByCategory = new Map()
    for (const row of lookups) {
      const bucket = rowsByCategory.get(row.category) || []
      bucket.push(row)
      rowsByCategory.set(row.category, bucket)
    }

    const assigned = new Set()
    const groups = []
    for (const group of GROUPS) {
      const items = []
      for (const id of group.categories) {
        const rows = rowsByCategory.get(id)
        if (!rows) continue
        assigned.add(id)
        items.push(describeCategory(id, rows, needle))
      }
      const visible = items.filter((item) => item.visible)
      if (visible.length) groups.push({ ...group, items: visible })
    }

    const other = []
    for (const [id, rows] of rowsByCategory) {
      if (assigned.has(id)) continue
      const item = describeCategory(id, rows, needle)
      if (item.visible) other.push(item)
    }
    other.sort((a, b) => a.label.localeCompare(b.label, 'fa'))
    if (other.length) groups.push({ id: 'other', label: 'سایر', items: other })

    return { groups, rowsByCategory }
  }, [lookups, needle])

  const visibleIds = catalog.groups.flatMap((group) => group.items.map((item) => item.id))
  const activeId = visibleIds.includes(selected) ? selected : (visibleIds[0] || '')

  const current = catalog.groups.flatMap((group) => group.items).find((item) => item.id === activeId)
  const activeGroupId = catalog.groups.find((group) => group.items.some((item) => item.id === activeId))?.id
  const currentRows = (catalog.rowsByCategory.get(activeId) || [])
    .filter((row) => !needle || current?.nameMatch || includesRow(row, needle))
    .slice()
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || String(a.label).localeCompare(String(b.label), 'fa'))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="جستجوی دسته یا گزینه…"
          className={cn(tw.searchInput, 'max-w-none flex-1')}
          aria-label="جستجوی گزینه‌ها"
        />
        {query && (
          <button type="button" className={tw.link} onClick={() => setQuery('')}>
            پاک کردن
          </button>
        )}
      </div>
      <p className={cn(tw.muted, tw.small, 'm-0')}>
        جستجو کنید، یا از فهرست بخش‌ها یکی را انتخاب کنید.
      </p>

      {!catalog.groups.length ? (
        <EmptyState message={query ? 'موردی با این جستجو پیدا نشد' : 'گزینه‌ای ثبت نشده'} />
      ) : (
        <div className="grid grid-cols-[minmax(220px,280px)_minmax(0,1fr)] items-start gap-4 max-md:grid-cols-1">
          <nav
            aria-label="دسته‌های گزینه"
            className="hidden max-h-[min(68vh,560px)] flex-col gap-3 overflow-y-auto rounded-pill border border-jelly-rim bg-layer-0 p-2 shadow-sunken md:flex"
          >
            {catalog.groups.map((group) => {
              const open = Boolean(needle) || group.id === activeGroupId
              return (
                <div key={group.id}>
                  <button
                    type="button"
                    className={cn(
                      'flex w-full items-center justify-between gap-2 rounded-capsule px-2 py-2 text-right font-inherit text-xs font-semibold transition-colors duration-150',
                      open ? 'text-text' : 'text-muted hover:bg-layer-1 hover:text-text',
                    )}
                    aria-expanded={open}
                    onClick={() => {
                      if (group.id !== activeGroupId) setSelected(group.items[0].id)
                    }}
                  >
                    <span>{group.label}</span>
                    <span className="flex items-center gap-1">
                      <span className={tw.numDisplay}>{toPersianDigits(group.items.length)}</span>
                      <Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} />
                    </span>
                  </button>
                  {open && (
                    <div className="flex flex-col gap-0.5">
                      {group.items.map((item) => (
                        <CategoryButton
                          key={item.id}
                          item={item}
                          active={item.id === activeId}
                          onSelect={setSelected}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </nav>

          <label className={cn(tw.field, 'md:hidden')}>
            <span className={tw.fieldLabel}>دسته</span>
            <select
              className={cn(tw.searchInput, 'max-w-none')}
              value={activeId}
              onChange={(e) => setSelected(e.target.value)}
              aria-label="انتخاب دسته"
            >
              {catalog.groups.map((group) => (
                <optgroup key={group.id} label={group.label}>
                  {group.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label} ({toPersianDigits(item.count)})
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          {current && (
            <section className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="m-0 font-display text-base font-bold text-text">{current.label}</h4>
                  <p className={cn(tw.muted, tw.small, 'm-0 mt-1')}>
                    {toPersianDigits(currentRows.filter((row) => row.is_active).length)} فعال از {toPersianDigits(currentRows.length)}
                  </p>
                </div>
                <Button type="button" onClick={() => onCreate(current.id)}>گزینه جدید</Button>
              </div>
              {currentRows.length === 0 ? (
                <EmptyState message="گزینه‌ای در این دسته نیست" />
              ) : (
                <ul className="m-0 flex w-full list-none flex-col gap-1 rounded-pill border border-jelly-rim bg-layer-0 p-2 shadow-sunken">
                  {currentRows.map((row) => (
                    <li
                      key={row.id}
                      className={cn(
                        'flex w-full flex-col gap-2 rounded-capsule px-3 py-2.5 hover:bg-layer-1 md:flex-row md:items-center md:justify-between',
                        !row.is_active && 'opacity-60',
                      )}
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-text">{row.label}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted">
                          <span className={cn(tw.ltr, 'break-all')}>{row.code}</span>
                          <span>ترتیب {toPersianDigits(row.sort_order || 0)}</span>
                          {!row.is_active && <span>غیرفعال</span>}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <button type="button" className={tw.link} onClick={() => onEdit(row)}>ویرایش</button>
                        <button type="button" className={tw.link} onClick={() => onToggle(row)}>
                          {row.is_active ? 'غیرفعال' : 'فعال'}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  )
}

function describeCategory(id, rows, needle) {
  const label = categoryTitle(id, rows.find((row) => row.meta?.category_label)?.meta?.category_label)
  const nameMatch = !needle || fold(label).includes(needle) || fold(id).includes(needle)
  const matched = needle ? rows.find((row) => includesRow(row, needle)) : null
  return {
    id,
    label,
    count: rows.length,
    nameMatch,
    matchHint: !nameMatch && matched ? matched.label : '',
    visible: nameMatch || Boolean(matched),
  }
}

function includesRow(row, needle) {
  return fold(row.label).includes(needle) || fold(row.code).includes(needle)
}
