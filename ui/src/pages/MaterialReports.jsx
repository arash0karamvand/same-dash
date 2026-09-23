import { useCallback, useEffect, useMemo, useState } from 'react'
import { fromLegacy } from '../styles/tw.js'
import { materialsApi } from '../api/client'
import MaterialStocktakeReport from './MaterialStocktakeReport'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, StatCard } from '../components/ui'
import { formatDate, formatMoney, formatNumber } from '../utils/format'
import { WarehouseDashboard } from '../components/warehouse/WarehouseDashboard'
import { ExportButtons } from '../components/warehouse/ExportButtons'
import {
  InventoryByUsageChart,
  AbcClassificationChart,
  ConsumptionTrendChart,
  CoverageDaysChart,
  IdleInventoryChart,
  ShortageChart,
} from '../components/warehouse/WarehouseCharts'
import '../styles/print.css'

const GROUPS = [
  {
    id: 'dashboard',
    label: '📊 داشبورد',
    icon: '📊',
    items: [],
  },
  {
    id: 'onhand',
    label: 'موجودی',
    icon: '📦',
    items: [
      { id: 'summary', label: 'خلاصه', hint: 'ارزش انبار، قلم بدون موجودی و کسری صف ساخت در یک نگاه.' },
      { id: 'stock', label: 'ریز موجودی', hint: 'موجودی، تعهد سفارش‌های باز و مقداری که هنوز آزاد است.' },
      { id: 'shortage', label: 'خرید لازم', hint: 'اختلاف تعهد صف با موجودی؛ همان مقداری که برای تمام شدن سفارش‌های باز باید برسد.' },
      { id: 'idle', label: 'راکد', hint: 'موجودی که مدت‌ها خروج نداشته، یا در هیچ دستور ساختی نیست.' },
      { id: 'abc', label: 'ارزش ABC', hint: 'قلم‌هایی که بیشتر پول انبار را گرفته‌اند. A حدود ۸۰٪ ارزش، B تا ۹۵٪ و بقیه C است.' },
    ],
  },
  {
    id: 'make',
    label: 'تولید',
    icon: '🏭',
    items: [
      { id: 'capacity', label: 'ظرفیت ساخت', hint: 'اگر فقط همان محصول ساخته شود چند عدد درمی‌آید. چوب کلاف در این عدد نیست.' },
      { id: 'coverage', label: 'پوشش روز', hint: 'موجودی فعلی، با مصرف ۳۰ روز اخیر، چند روز دوام می‌آورد.' },
      { id: 'consumption', label: 'مصرف', hint: 'مصرف تولید منهای برگشت. تاریخ خالی یعنی ۳۰ روز اخیر.' },
      { id: 'where_used', label: 'محل مصرف', hint: 'هر متریال برای یک عدد از کدام محصول یا دستور دست‌کار مصرف می‌شود.' },
    ],
  },
  {
    id: 'ledger',
    label: 'گردش',
    icon: '📋',
    items: [
      { id: 'movements', label: 'کاردکس', hint: 'ورود و خروج. مانده جاری فقط وقتی یک متریال انتخاب شود درست خوانده می‌شود.' },
    ],
  },
  {
    id: 'count',
    label: 'انبارگردانی',
    icon: '🔢',
    items: [
      { id: 'stocktake', label: 'شمارش', hint: 'شمارش انبار را کنار موجودی سیستم بگذارید. بستن برگه موجودی را عوض نمی‌کند.' },
    ],
  },
]

function findGroup(reportId) {
  if (reportId === 'dashboard') return GROUPS[0]
  return GROUPS.find((group) => group.items.some((item) => item.id === reportId)) || GROUPS[1]
}

const USAGE_OPTIONS = [
  { value: '', label: 'همه نوع‌ها' },
  { value: 'wood', label: 'چوب' },
  { value: 'paint', label: 'رنگ' },
  { value: 'fabric', label: 'پارچه' },
  { value: 'foam', label: 'اسفنج' },
  { value: 'webbing', label: 'تسمه' },
  { value: 'cushion', label: 'کوسن' },
  { value: 'other', label: 'سایر' },
]

const ABC_COLOR = { A: 'var(--danger)', B: 'var(--warning)', C: 'var(--success)' }

function qty(value, unit) {
  const text = formatNumber(value)
  return unit ? `${text} ${unit}` : text
}

function periodLabel(data) {
  if (!data?.date_from && !data?.date_to) return ''
  const from = data.date_from ? formatDate(data.date_from) : '…'
  const to = data.date_to ? formatDate(data.date_to) : '…'
  return `بازه: ${from} تا ${to}`
}

function DataTable({ headers, children, responsive = true }) {
  return (
    <div className={fromLegacy('table-wrap')} style={{ overflowX: 'auto' }}>
      <table className={fromLegacy('table')} style={{ minWidth: responsive ? '800px' : 'auto' }}>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

// Report Components
function SummaryReport({ data, onOpen }) {
  return (
    <>
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '24px' }}>
        <StatCard label="تعداد قلم" value={formatNumber(data.item_count)} />
        <StatCard label="ارزش موجودی" value={formatMoney(data.inventory_value)} />
        <StatCard
          label="بدون موجودی"
          value={formatNumber(data.zero_count)}
          accent="var(--warning)"
          onClick={() => onOpen('stock')}
        />
        <StatCard
          label="کسری صف ساخت"
          value={formatNumber(data.shortage_count)}
          hint={formatMoney(data.shortage_value)}
          accent="var(--danger)"
          onClick={() => onOpen('shortage')}
        />
        <StatCard
          label="ارزش مصرف بازه"
          value={formatMoney(data.consumption_value)}
          hint={periodLabel(data) || '۳۰ روز اخیر'}
          onClick={() => onOpen('consumption')}
        />
      </div>

      <Card title="موجودی به تفکیک نوع مصرف" style={{ marginBottom: '24px' }}>
        {(data.by_usage_kind || []).length === 0 ? (
          <EmptyState text="متریال تاییدشده‌ای نیست." />
        ) : (
          <>
            <InventoryByUsageChart data={data.by_usage_kind} />
            <DataTable headers={['نوع', 'تعداد', 'ارزش موجودی', 'قلم کسری']} responsive={false}>
              {data.by_usage_kind.map((row) => (
                <tr key={row.usage_kind}>
                  <td>{row.usage_kind_display}</td>
                  <td>{formatNumber(row.item_count)}</td>
                  <td>{formatMoney(row.inventory_value)}</td>
                  <td>{formatNumber(row.shortage_count)}</td>
                </tr>
              ))}
            </DataTable>
          </>
        )}
      </Card>

      {(data.consumption_by_unit || []).length > 0 && (
        <Card title="مصرف خالص بازه به تفکیک واحد">
          <DataTable headers={['واحد', 'مقدار خالص']}>
            {data.consumption_by_unit.map((row) => (
              <tr key={row.unit}>
                <td>{row.unit}</td>
                <td>{qty(row.quantity, row.unit === '—' ? '' : row.unit)}</td>
              </tr>
            ))}
          </DataTable>
        </Card>
      )}
    </>
  )
}

function StockReport({ data }) {
  const rows = data.rows || []
  if (!rows.length) return <EmptyState text="متریالی با این فیلتر نیست." />
  return (
    <Card title="موجودی، تعهد صف و قابل استفاده">
      <DataTable headers={['متریال', 'نوع', 'موجودی', 'تعهد صف', 'قابل استفاده', 'ارزش']}>
        {rows.map((row) => (
          <tr key={row.material_id}>
            <td>
              <strong>{row.label}</strong>
              {row.sku && <div className={fromLegacy('muted small ltr')}>{row.sku}</div>}
            </td>
            <td>{row.usage_kind_display}</td>
            <td>{qty(row.on_hand, row.unit)}</td>
            <td>{qty(row.committed, row.unit)}</td>
            <td style={row.available < 0 ? { color: 'var(--danger)', fontWeight: 700 } : undefined}>
              {qty(row.available, row.unit)}
            </td>
            <td>{formatMoney(row.inventory_value)}</td>
          </tr>
        ))}
      </DataTable>
    </Card>
  )
}

function ShortageReport({ data }) {
  const purchase = data.purchase || []
  const zeroUsed = data.zero_used || []
  return (
    <>
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '24px' }}>
        <StatCard label="قلم نیازمند خرید" value={formatNumber(purchase.length)} accent="var(--danger)" />
        <StatCard label="ارزش خرید پیشنهادی" value={formatMoney(data.purchase_value)} />
        <StatCard label="موجودی صفرِ در دستور ساخت" value={formatNumber(zeroUsed.length)} accent="var(--warning)" />
      </div>

      <Card title="کسری صف ساخت" style={{ marginBottom: '24px' }}>
        <p className={fromLegacy('muted small')}>مقدار خرید همان اختلاف تعهد صف با موجودی است تا سفارش‌های باز تمام شوند.</p>
        {purchase.length === 0 ? (
          <EmptyState text="نسبت به صف ساخت کسری نیست." />
        ) : (
          <>
            <ShortageChart data={purchase} />
            <DataTable headers={['متریال', 'موجودی', 'تعهد', 'پیشنهاد خرید', 'ارزش خرید']}>
              {purchase.map((row) => (
                <tr key={row.material_id}>
                  <td>
                    <strong>{row.label}</strong>
                  </td>
                  <td>{qty(row.on_hand, row.unit)}</td>
                  <td>{qty(row.committed, row.unit)}</td>
                  <td>{qty(row.suggested_quantity, row.unit)}</td>
                  <td>{formatMoney(row.suggested_value)}</td>
                </tr>
              ))}
            </DataTable>
          </>
        )}
      </Card>

      <Card title="موجودی صفر در دستور ساخت">
        {zeroUsed.length === 0 ? (
          <EmptyState text="قلم صفرِ استفاده‌شده‌ای خارج از لیست کسری نیست." />
        ) : (
          <DataTable headers={['متریال', 'نوع', 'واحد']}>
            {zeroUsed.map((row) => (
              <tr key={row.material_id}>
                <td>
                  <strong>{row.label}</strong>
                </td>
                <td>{row.usage_kind_display}</td>
                <td>{row.unit}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  )
}

function CapacityReport({ data }) {
  const rows = data.rows || []
  return (
    <Card title="چند عدد از هر محصول ساخته می‌شود">
      <p className={fromLegacy('muted small')}>{data.note}</p>
      {rows.length === 0 ? (
        <EmptyState text="محصول فعالی با این فیلتر نیست." />
      ) : (
        <DataTable headers={['محصول', 'با صف باز', 'اگر صف نبود', 'گلوگاه']}>
          {rows.map((row) => (
            <tr key={row.product_id}>
              <td>
                <strong>{row.product_name}</strong>
                {row.sku && <div className={fromLegacy('muted small ltr')}>{row.sku}</div>}
              </td>
              <td>
                {row.has_bom ? (
                  row.buildable_after_queue > 0 ? (
                    formatNumber(row.buildable_after_queue)
                  ) : (
                    <Badge color="var(--danger)">صفر</Badge>
                  )
                ) : (
                  '—'
                )}
              </td>
              <td>{row.has_bom ? formatNumber(row.buildable_on_hand) : '—'}</td>
              <td>{row.has_bom ? row.bottleneck_name || '—' : 'دستور مصرف ندارد'}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </Card>
  )
}

function MovementsReport({ data, singleMaterial }) {
  const rows = data.rows || []
  return (
    <Card title="کاردکس گردش موجودی">
      {data.truncated && <p className={fromLegacy('muted small')}>فقط ۵۰۰ گردش آخر این بازه نشان داده می‌شود.</p>}
      {singleMaterial && data.opening_balance != null && (
        <div className={fromLegacy('stat-grid')} style={{ marginBottom: '16px' }}>
          <StatCard label="مانده اول" value={formatNumber(data.opening_balance)} />
          <StatCard label="مانده پایان" value={formatNumber(data.closing_balance)} />
        </div>
      )}
      {!singleMaterial && (
        <p className={fromLegacy('muted small')}>
          چند متریال با هم مانده واحد ندارند. برای مانده جاری، یک متریال را از فیلتر بالا انتخاب کنید.
        </p>
      )}
      {periodLabel(data) && <p className={fromLegacy('muted small')}>{periodLabel(data)}</p>}
      {rows.length === 0 ? (
        <EmptyState text="گردشی در این بازه نیست." />
      ) : (
        <DataTable
          headers={
            singleMaterial
              ? ['تاریخ', 'دلیل', 'ورود', 'خروج', 'مانده', 'مبلغ']
              : ['تاریخ', 'متریال', 'دلیل', 'ورود', 'خروج', 'مبلغ']
          }
        >
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{formatDate(row.created_at)}</td>
              {!singleMaterial && <td>{row.material_name}</td>}
              <td>{row.reason_label}</td>
              <td>{row.in_quantity ? qty(row.in_quantity, row.unit) : '—'}</td>
              <td>{row.out_quantity ? qty(row.out_quantity, row.unit) : '—'}</td>
              {singleMaterial && <td>{qty(row.balance, row.unit)}</td>}
              <td>{formatMoney(row.line_value)}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </Card>
  )
}

function ConsumptionReport({ data }) {
  const rows = data.rows || []
  return (
    <>
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '24px' }}>
        <StatCard label="ارزش مصرف خالص" value={formatMoney(data.consumption_value)} hint={periodLabel(data)} />
      </div>

      {(data.by_usage_kind || []).length > 0 && (
        <Card title="مصرف به تفکیک نوع" style={{ marginBottom: '24px' }}>
          <DataTable headers={['نوع', 'تعداد قلم', 'ارزش خالص']}>
            {data.by_usage_kind.map((row) => (
              <tr key={row.usage_kind}>
                <td>{row.usage_kind_display}</td>
                <td>{formatNumber(row.item_count)}</td>
                <td>{formatMoney(row.net_value)}</td>
              </tr>
            ))}
          </DataTable>
        </Card>
      )}

      <Card title="مصرف خالص تولید">
        {rows.length === 0 ? (
          <EmptyState text="در این بازه مصرف تولیدی ثبت نشده." />
        ) : (
          <>
            <ConsumptionTrendChart data={rows} />
            <DataTable headers={['متریال', 'نوع', 'مصرف', 'برگشت', 'خالص', 'ارزش']}>
              {rows.map((row) => (
                <tr key={row.material_id}>
                  <td>
                    <strong>{row.label}</strong>
                  </td>
                  <td>{row.usage_kind_display}</td>
                  <td>{qty(row.consumed_quantity, row.unit)}</td>
                  <td>{qty(row.returned_quantity, row.unit)}</td>
                  <td>{qty(row.net_quantity, row.unit)}</td>
                  <td>{formatMoney(row.net_value)}</td>
                </tr>
              ))}
            </DataTable>
          </>
        )}
      </Card>
    </>
  )
}

function CoverageReport({ data }) {
  const rows = data.rows || []
  return (
    <Card title={`پوشش موجودی بر اساس ${formatNumber(data.days)} روز اخیر`}>
      {periodLabel(data) && <p className={fromLegacy('muted small')}>{periodLabel(data)}</p>}
      {rows.length === 0 ? (
        <EmptyState text="در این بازه مصرف خالصی برای محاسبه پوشش نیست." />
      ) : (
        <>
          <CoverageDaysChart data={rows} />
          <DataTable headers={['متریال', 'موجودی', 'مصرف بازه', 'مصرف روزانه', 'روز پوشش']}>
            {rows.map((row) => (
              <tr key={row.material_id}>
                <td>
                  <strong>{row.label}</strong>
                </td>
                <td>{qty(row.on_hand, row.unit)}</td>
                <td>{qty(row.net_quantity, row.unit)}</td>
                <td>{qty(row.daily_consumption, row.unit)}</td>
                <td style={row.days_of_cover < 7 ? { color: 'var(--danger)' } : undefined}>
                  {formatNumber(row.days_of_cover)}
                </td>
              </tr>
            ))}
          </DataTable>
        </>
      )}
    </Card>
  )
}

function IdleReport({ data }) {
  const idle = data.idle || []
  const unused = data.unused || []
  return (
    <>
      <Card title={`بدون خروج در ${formatNumber(data.idle_days)} روز اخیر`} style={{ marginBottom: '24px' }}>
        {idle.length === 0 ? (
          <EmptyState text="موجودی راکدی با این فیلتر نیست." />
        ) : (
          <>
            <IdleInventoryChart data={idle} />
            <DataTable headers={['متریال', 'موجودی', 'ارزش', 'آخرین خروج']}>
              {idle.map((row) => (
                <tr key={row.material_id}>
                  <td>
                    <strong>{row.label}</strong>
                  </td>
                  <td>{qty(row.on_hand, row.unit)}</td>
                  <td>{formatMoney(row.inventory_value)}</td>
                  <td>{row.last_out_at ? formatDate(row.last_out_at) : 'خروجی نداشته'}</td>
                </tr>
              ))}
            </DataTable>
          </>
        )}
      </Card>

      <Card title="موجودی بدون استفاده در دستور ساخت">
        {unused.length === 0 ? (
          <EmptyState text="همه موجودی‌ها در محصول یا دستور دست‌کار استفاده شده‌اند." />
        ) : (
          <DataTable headers={['متریال', 'نوع', 'موجودی', 'ارزش']}>
            {unused.map((row) => (
              <tr key={row.material_id}>
                <td>
                  <strong>{row.label}</strong>
                </td>
                <td>{row.usage_kind_display}</td>
                <td>{qty(row.on_hand, row.unit)}</td>
                <td>{formatMoney(row.inventory_value)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  )
}

function AbcReport({ data }) {
  const rows = data.rows || []
  const counts = data.counts || {}
  const values = data.values || {}
  return (
    <>
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '24px' }}>
        {['A', 'B', 'C'].map((klass) => (
          <StatCard
            key={klass}
            label={`دسته ${klass}`}
            value={formatNumber(counts[klass] || 0)}
            hint={formatMoney(values[klass] || 0)}
            accent={ABC_COLOR[klass]}
          />
        ))}
      </div>

      <Card title="سهم ارزش موجودی">
        <p className={fromLegacy('muted small')}>دسته A حدود ۸۰ درصد ارزش، B تا ۹۵ درصد، و بقیه C است.</p>
        {rows.length === 0 ? (
          <EmptyState text="موجودی با ارزش ریالی نیست." />
        ) : (
          <>
            <AbcClassificationChart counts={counts} values={values} />
            <DataTable headers={['دسته', 'متریال', 'موجودی', 'ارزش', 'سهم', 'تجمعی']}>
              {rows.map((row) => (
                <tr key={row.material_id}>
                  <td>
                    <Badge color={ABC_COLOR[row.abc_class]}>{row.abc_class}</Badge>
                  </td>
                  <td>
                    <strong>{row.label}</strong>
                  </td>
                  <td>{qty(row.on_hand, row.unit)}</td>
                  <td>{formatMoney(row.inventory_value)}</td>
                  <td>{formatNumber(row.share_percent)}٪</td>
                  <td>{formatNumber(row.cumulative_percent)}٪</td>
                </tr>
              ))}
            </DataTable>
          </>
        )}
      </Card>
    </>
  )
}

function WhereUsedReport({ data }) {
  const rows = data.rows || []
  if (!rows.length) return <EmptyState text="محل مصرفی برای این فیلتر نیست." />
  return (
    <Card title="محصول و دستور دست‌کار">
      <DataTable headers={['متریال', 'محل', 'مسیر', 'مقدار برای یک عدد']}>
        {rows.flatMap((row) => {
          const usages = row.usages || []
          return usages.length === 0
            ? [
                <tr key={row.material_id}>
                  <td>
                    <strong>{row.label}</strong>
                  </td>
                  <td colSpan={3} className={fromLegacy('muted')}>
                    در دستور ساختی نیست
                  </td>
                </tr>,
              ]
            : usages.map((usage, index) => (
                <tr key={`${row.material_id}-${usage.kind}-${usage.place}-${usage.via}-${index}`}>
                  <td>{index === 0 ? <strong>{row.label}</strong> : ''}</td>
                  <td>{usage.place}</td>
                  <td>{usage.via}</td>
                  <td>{qty(usage.quantity, row.unit)}</td>
                </tr>
              ))
        })}
      </DataTable>
    </Card>
  )
}

const VIEWS = {
  summary: SummaryReport,
  stock: StockReport,
  shortage: ShortageReport,
  capacity: CapacityReport,
  movements: MovementsReport,
  consumption: ConsumptionReport,
  coverage: CoverageReport,
  idle: IdleReport,
  abc: AbcReport,
  where_used: WhereUsedReport,
}

export default function MaterialReports() {
  const [report, setReport] = useState('dashboard')
  const [usageKind, setUsageKind] = useState('')
  const [search, setSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [materialId, setMaterialId] = useState('')
  const [idleDays, setIdleDays] = useState('90')
  const [materialOptions, setMaterialOptions] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(60) // seconds

  // Dashboard data
  const [dashboardData, setDashboardData] = useState({
    summary: null,
    shortage: null,
    coverage: null,
    idle: null,
    abc: null,
  })

  const group = findGroup(report)
  const active = report === 'dashboard' ? { id: 'dashboard', hint: 'نمای کلی وضعیت انبار' } : group.items.find((item) => item.id === report) || group.items[0]
  const needsDates = report === 'summary' || report === 'movements' || report === 'consumption'
  const needsMaterial = report === 'movements'
  const needsIdle = report === 'idle'
  const searchLabel = report === 'capacity' ? 'جستجوی محصول' : 'جستجوی متریال'

  // Load saved filters from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('warehouse_filters')
      if (saved) {
        const filters = JSON.parse(saved)
        if (filters.usageKind) setUsageKind(filters.usageKind)
        if (filters.idleDays) setIdleDays(filters.idleDays)
        if (filters.autoRefresh !== undefined) setAutoRefresh(filters.autoRefresh)
        if (filters.refreshInterval) setRefreshInterval(filters.refreshInterval)
      }
    } catch (e) {
      console.error('Error loading filters:', e)
    }
  }, [])

  // Save filters to localStorage
  const saveFilters = useCallback(() => {
    try {
      localStorage.setItem(
        'warehouse_filters',
        JSON.stringify({
          usageKind,
          idleDays,
          autoRefresh,
          refreshInterval,
        })
      )
    } catch (e) {
      console.error('Error saving filters:', e)
    }
  }, [usageKind, idleDays, autoRefresh, refreshInterval])

  useEffect(() => {
    saveFilters()
  }, [saveFilters])

  const openReport = (id) => {
    if (id === report) return
    setReport(id)
    setData(null)
    setLoading(true)
    setError('')
  }

  const openGroup = (groupId) => {
    const next = GROUPS.find((item) => item.id === groupId)
    if (!next) return
    if (groupId === 'dashboard') {
      openReport('dashboard')
    } else if (!next.items.some((item) => item.id === report)) {
      openReport(next.items[0].id)
    }
  }

  const load = useCallback(async () => {
    if (report === 'stocktake' || report === 'dashboard') {
      setLoading(false)
      setError('')
      return
    }

    setLoading(true)
    try {
      const result = await materialsApi.reports({
        report,
        search: search.trim(),
        usage_kind: report === 'capacity' ? '' : usageKind,
        date_from: needsDates ? dateFrom : '',
        date_to: needsDates ? dateTo : '',
        material_id: needsMaterial ? materialId : '',
        idle_days: needsIdle ? idleDays : '',
      })

      if (result?.report && result.report !== report) return

      setData(result)
      if (result?.material_options) setMaterialOptions(result.material_options)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [report, search, usageKind, dateFrom, dateTo, materialId, idleDays, needsDates, needsMaterial, needsIdle])

  // Load dashboard data
  const loadDashboard = useCallback(async () => {
    if (report !== 'dashboard') return

    setLoading(true)
    try {
      const [summary, shortage, coverage, idle, abc] = await Promise.all([
        materialsApi.reports({ report: 'summary' }),
        materialsApi.reports({ report: 'shortage' }),
        materialsApi.reports({ report: 'coverage' }),
        materialsApi.reports({ report: 'idle', idle_days: '90' }),
        materialsApi.reports({ report: 'abc' }),
      ])

      setDashboardData({ summary, shortage, coverage, idle, abc })
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [report])

  useEffect(() => {
    if (report === 'dashboard') {
      loadDashboard()
    } else if (report !== 'stocktake') {
      load()
    }
  }, [report, load, loadDashboard])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) return

    const timer = setInterval(() => {
      if (report === 'dashboard') {
        loadDashboard()
      } else if (report !== 'stocktake') {
        load()
      }
    }, refreshInterval * 1000)

    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval, report, load, loadDashboard])

  const View = VIEWS[report] || SummaryReport
  const singleMaterial = Boolean(materialId)

  // Get export data and type
  const exportData = useMemo(() => {
    if (report === 'dashboard' || report === 'stocktake') return null
    if (!data) return null

    if (report === 'summary') return data.by_usage_kind
    if (report === 'shortage') return data.purchase
    if (report === 'idle') return data.idle
    if (report === 'abc' || report === 'stock' || report === 'consumption' || report === 'coverage' || report === 'capacity' || report === 'movements' || report === 'where_used') {
      return data.rows
    }
    return null
  }, [report, data])

  return (
    <div className="print-container">
      {/* Print Header - فقط در چاپ نمایش داده می‌شود */}
      <div className="print-header">
        <h1>گزارش انبار</h1>
        <div className="print-date">{new Date().toLocaleDateString('fa-IR')}</div>
      </div>

      {/* Navigation Tabs */}
      <div className={fromLegacy('branch-tabs settings-tabs')} style={{ marginBottom: '12px' }}>
        {GROUPS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={fromLegacy(`branch-tab ${group.id === item.id || (report === 'dashboard' && item.id === 'dashboard') ? 'active' : ''}`)}
            onClick={() => openGroup(item.id)}
          >
            {item.icon} {item.label}
          </button>
        ))}
      </div>

      <p className={fromLegacy('muted')} style={{ marginTop: 8, marginBottom: 16 }}>
        {active.hint}
      </p>

      {/* Sub-tabs for groups */}
      {report !== 'dashboard' && group.items.length > 1 && (
        <div className={fromLegacy('workflow-filter-tabs')} style={{ marginBottom: 12 }}>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={fromLegacy(`workflow-filter-tab ${report === item.id ? 'active' : ''}`)}
              onClick={() => openReport(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Dashboard View */}
      {report === 'dashboard' ? (
        loading ? (
          <div className={fromLegacy('loading')}>در حال بارگذاری داشبورد...</div>
        ) : error ? (
          <div className={fromLegacy('alert-error')}>{error}</div>
        ) : (
          <WarehouseDashboard
            summaryData={dashboardData.summary}
            shortageData={dashboardData.shortage}
            coverageData={dashboardData.coverage}
            idleData={dashboardData.idle}
            abcData={dashboardData.abc}
            onNavigate={openReport}
          />
        )
      ) : report === 'stocktake' ? (
        <MaterialStocktakeReport />
      ) : (
        <>
          {/* Filters */}
          <Card style={{ marginBottom: '16px' }}>
            <FilterBar>
              <Field label={searchLabel}>
                <input
                  className={fromLegacy('search-input')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={report === 'capacity' ? 'نام محصول…' : 'نام، رنگ یا کد…'}
                />
              </Field>
              {report !== 'capacity' && (
                <Field label="نوع مصرف">
                  <Select value={usageKind} onChange={setUsageKind} options={USAGE_OPTIONS} placeholder="همه نوع‌ها" />
                </Field>
              )}
              {needsMaterial && (
                <Field label="یک متریال برای مانده">
                  <Select
                    value={materialId}
                    onChange={setMaterialId}
                    options={[
                      { value: '', label: 'همه، بدون مانده واحد' },
                      ...materialOptions.map((item) => ({ value: String(item.id), label: item.label })),
                    ]}
                    placeholder="همه، بدون مانده واحد"
                  />
                </Field>
              )}
              {needsDates && (
                <>
                  <Field label="از تاریخ">
                    <PersianDateInput value={dateFrom} onChange={setDateFrom} onClear={() => setDateFrom('')} placeholder="از تاریخ" />
                  </Field>
                  <Field label="تا تاریخ">
                    <PersianDateInput value={dateTo} onChange={setDateTo} onClear={() => setDateTo('')} placeholder="تا تاریخ" />
                  </Field>
                </>
              )}
              {needsIdle && (
                <Field label="چند روز بدون خروج">
                  <input
                    className={fromLegacy('ltr')}
                    type="number"
                    min="1"
                    value={idleDays}
                    onChange={(e) => setIdleDays(e.target.value)}
                  />
                </Field>
              )}
            </FilterBar>

            {/* Advanced Options */}
            <div style={{ marginTop: '12px', padding: '12px', background: 'var(--surface-2)', borderRadius: '8px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                />
                <span>بروزرسانی خودکار</span>
              </label>
              {autoRefresh && (
                <Field label="بازه (ثانیه)" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 0 }}>
                  <input
                    className={fromLegacy('ltr')}
                    type="number"
                    min="10"
                    max="300"
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(Number(e.target.value))}
                    style={{ width: '80px' }}
                  />
                </Field>
              )}
              <div style={{ marginRight: 'auto' }}>
                <ExportButtons data={exportData} type={report} filename={`warehouse_${report}`} />
              </div>
            </div>
          </Card>

          {error && <div className={fromLegacy('alert-error')} style={{ marginBottom: '16px' }}>{error}</div>}
          {loading ? (
            <div className={fromLegacy('loading')}>در حال بارگذاری…</div>
          ) : data && data.report === report ? (
            report === 'summary' ? (
              <SummaryReport data={data} onOpen={openReport} />
            ) : report === 'movements' ? (
              <MovementsReport data={data} singleMaterial={singleMaterial} />
            ) : (
              <View data={data} />
            )
          ) : null}
        </>
      )}
    </div>
  )
}
