import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaCarpentryApi } from '../api/client'

/** اتصال سفارش کارخانه به فرم‌های واحدهای بتا (رنگ، رویه‌کوبی، QC و …). */
export function applyBetaSaleSnapshot(form, sale) {
  if (!sale) return { ...form, sale_id: '' }
  return {
    ...form,
    sale_id: String(sale.id),
    order_ref: sale.order_ref || form.order_ref || '',
    customer_name: sale.customer_name || form.customer_name || '',
    buyer_name: sale.customer_name || form.buyer_name || '',
    product_name: sale.product_name || form.product_name || '',
    wood_type: sale.wood_type || form.wood_type || '',
    wood_color: sale.wood_type || form.wood_color || '',
    due_date: sale.due_date || form.due_date || '',
    quantity: String(sale.quantity || form.quantity || 1),
  }
}

export function useBetaSaleSources() {
  const [sales, setSales] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    betaCarpentryApi.sources()
      .then((src) => { if (active) setSales(src?.sales || []) })
      .catch(() => { if (active) setSales([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const saleOptions = useMemo(() => [
    { value: '', label: 'بدون اتصال به سفارش کارخانه' },
    ...sales.map((s) => ({
      value: String(s.id),
      label: s.has_carpentry_order ? `${s.label} (نجاری ثبت‌شده)` : s.label,
    })),
  ], [sales])

  const applySale = useCallback((saleId, form) => {
    const sale = sales.find((s) => String(s.id) === String(saleId))
    return applyBetaSaleSnapshot(form, sale)
  }, [sales])

  return { sales, saleOptions, applySale, loading }
}
