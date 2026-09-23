import { utils, writeFile } from 'xlsx'
import { formatDate, formatMoney, formatNumber } from '../../utils/format'
import { Button } from '../ui'

/**
 * تبدیل داده‌ها به فرمت قابل export
 */
function prepareDataForExport(data, type) {
  if (!data || !Array.isArray(data)) return []

  switch (type) {
    case 'stock':
      return data.map((row) => ({
        'نام متریال': row.label,
        'نوع مصرف': row.usage_kind_display,
        'موجودی': row.on_hand,
        'واحد': row.unit,
        'تعهد صف': row.committed,
        'قابل استفاده': row.available,
        'قیمت واحد': formatMoney(row.unit_cost),
        'ارزش موجودی': formatMoney(row.inventory_value),
      }))

    case 'shortage':
      return data.map((row) => ({
        'نام متریال': row.label,
        'موجودی': row.on_hand,
        'واحد': row.unit,
        'تعهد': row.committed,
        'پیشنهاد خرید': row.suggested_quantity,
        'ارزش خرید': formatMoney(row.suggested_value),
      }))

    case 'consumption':
      return data.map((row) => ({
        'نام متریال': row.label,
        'نوع مصرف': row.usage_kind_display,
        'مصرف': row.consumed_quantity,
        'برگشت': row.returned_quantity,
        'خالص': row.net_quantity,
        'واحد': row.unit,
        'ارزش': formatMoney(row.net_value),
      }))

    case 'movements':
      return data.map((row) => ({
        'تاریخ': formatDate(row.created_at),
        'متریال': row.material_name,
        'دلیل': row.reason_label,
        'ورود': row.in_quantity || '—',
        'خروج': row.out_quantity || '—',
        'مانده': row.balance || '—',
        'واحد': row.unit,
        'مبلغ': formatMoney(row.line_value),
      }))

    case 'coverage':
      return data.map((row) => ({
        'نام متریال': row.label,
        'موجودی': row.on_hand,
        'واحد': row.unit,
        'مصرف بازه': row.net_quantity,
        'مصرف روزانه': row.daily_consumption,
        'روز پوشش': formatNumber(row.days_of_cover),
      }))

    case 'idle':
      return data.map((row) => ({
        'نام متریال': row.label,
        'موجودی': row.on_hand,
        'واحد': row.unit,
        'ارزش موجودی': formatMoney(row.inventory_value),
        'آخرین خروج': row.last_out_at ? formatDate(row.last_out_at) : 'خروجی نداشته',
      }))

    case 'abc':
      return data.map((row) => ({
        'دسته': row.abc_class,
        'نام متریال': row.label,
        'موجودی': row.on_hand,
        'واحد': row.unit,
        'ارزش موجودی': formatMoney(row.inventory_value),
        'سهم درصد': `${formatNumber(row.share_percent)}٪`,
        'تجمعی': `${formatNumber(row.cumulative_percent)}٪`,
      }))

    case 'capacity':
      return data.map((row) => ({
        'نام محصول': row.product_name,
        'کد محصول': row.sku || '—',
        'با صف باز': row.buildable_after_queue !== null ? formatNumber(row.buildable_after_queue) : '—',
        'اگر صف نبود': row.buildable_on_hand !== null ? formatNumber(row.buildable_on_hand) : '—',
        'گلوگاه': row.bottleneck_name || '—',
      }))

    default:
      return data
  }
}

/**
 * Export به Excel
 */
export function exportToExcel(data, type, filename) {
  try {
    const preparedData = prepareDataForExport(data, type)
    if (!preparedData || preparedData.length === 0) {
      alert('داده‌ای برای export وجود ندارد.')
      return
    }

    const worksheet = utils.json_to_sheet(preparedData)
    const workbook = utils.book_new()
    utils.book_append_sheet(workbook, worksheet, 'گزارش')

    // تنظیم عرض ستون‌ها
    const maxWidth = preparedData.reduce((acc, row) => {
      Object.keys(row).forEach((key) => {
        const value = String(row[key] || '')
        acc[key] = Math.max(acc[key] || 10, value.length + 2)
      })
      return acc
    }, {})

    worksheet['!cols'] = Object.values(maxWidth).map((width) => ({ wch: Math.min(width, 50) }))

    // ذخیره فایل
    const timestamp = new Date().toISOString().split('T')[0]
    writeFile(workbook, `${filename}_${timestamp}.xlsx`)
  } catch (error) {
    console.error('خطا در export:', error)
    alert('خطا در export به Excel')
  }
}

/**
 * Export به CSV
 */
export function exportToCSV(data, type, filename) {
  try {
    const preparedData = prepareDataForExport(data, type)
    if (!preparedData || preparedData.length === 0) {
      alert('داده‌ای برای export وجود ندارد.')
      return
    }

    // تبدیل به CSV با BOM برای UTF-8
    const headers = Object.keys(preparedData[0])
    const csvContent = [
      '\uFEFF', // BOM for UTF-8
      headers.join(','),
      ...preparedData.map((row) =>
        headers.map((header) => {
          const value = String(row[header] || '')
          // اگر value شامل کاما یا نقل قول بود، در quotes قرار بده
          if (value.includes(',') || value.includes('"') || value.includes('\n')) {
            return `"${value.replace(/"/g, '""')}"`
          }
          return value
        }).join(',')
      ),
    ].join('\n')

    // دانلود فایل
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    const timestamp = new Date().toISOString().split('T')[0]
    
    link.setAttribute('href', url)
    link.setAttribute('download', `${filename}_${timestamp}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    console.error('خطا در export:', error)
    alert('خطا در export به CSV')
  }
}

/**
 * دکمه‌های Export
 */
export function ExportButtons({ data, type, filename = 'warehouse_report' }) {
  return (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      <Button
        type="button"
        variant="ghost"
        onClick={() => exportToExcel(data, type, filename)}
        disabled={!data || data.length === 0}
      >
        📊 Excel
      </Button>
      <Button
        type="button"
        variant="ghost"
        onClick={() => exportToCSV(data, type, filename)}
        disabled={!data || data.length === 0}
      >
        📄 CSV
      </Button>
      <Button
        type="button"
        variant="ghost"
        onClick={() => window.print()}
      >
        🖨️ چاپ
      </Button>
    </div>
  )
}
