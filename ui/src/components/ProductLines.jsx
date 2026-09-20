import { useEffect, useMemo, useState } from 'react'
import { furnitureWorksetsApi } from '../api/client'
import { Button, Field, Modal } from './ui'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_LINE = {
  product_id: '',
  variant_id: '',
  frame_id: '',
  frame_model_id: '',
  frame_config: {},
  workset_config: {},
  furniture_workset_id: '',
  furniture_workset_name: '',
  product_name: '',
  product_model: '',
  fabric: '',
  color_name: '',
  color_hex: '',
  quantity: 1,
  unit_price: '',
}

function catalogPrice(product) {
  return Number(product?.default_price || product?.display_price || 0)
}

function pieceSummary(product) {
  const pieces = product?.suite_config || product?.workset?.pieces || []
  if (!pieces.length) return product?.product_model || ''
  return pieces.map((piece) => `${piece.quantity}× ${piece.piece_label}`).join('، ')
}

function fabricSummary(product) {
  const pieces = product?.suite_config || product?.workset?.pieces || []
  const names = [...new Set(pieces.map((piece) => piece.fabric?.name).filter(Boolean))]
  if (names.length) return names.join('، ')
  return product?.fabric || product?.fabric_recipe?.name || ''
}

function lineFromProduct(product, quantity = 1) {
  const variant = product.variants?.[0]
  return {
    ...EMPTY_LINE,
    product_id: product.id,
    variant_id: variant?.id || '',
    frame_id: product.frame_id || '',
    furniture_workset_id: product.furniture_workset_id || '',
    furniture_workset_name: product.furniture_workset?.name || '',
    workset_config: product.workset || { pieces: product.suite_config || [] },
    product_name: product.name,
    product_model: product.furniture_workset?.name || product.product_model || '',
    fabric: fabricSummary(product),
    color_name: variant?.color_name || '',
    color_hex: variant?.color_hex || '',
    unit_price: String(catalogPrice(product)),
    quantity,
  }
}

export default function ProductLines({
  lines,
  onChange,
  seatCount = '',
  onSeatCountChange,
  stockSourceKey = '',
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [worksets, setWorksets] = useState([])
  const [selectedWorkset, setSelectedWorkset] = useState(null)
  const [worksetProducts, setWorksetProducts] = useState([])
  const [qtys, setQtys] = useState({})
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!pickerOpen) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const data = await furnitureWorksetsApi.list({ search: search.trim(), limit: 80 })
        if (!cancelled) setWorksets(data.results || [])
      } catch {
        if (!cancelled) setWorksets([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    const t = setTimeout(load, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [pickerOpen, search])

  const openWorkset = async (workset) => {
    setSelectedWorkset(workset)
    setLoading(true)
    try {
      const data = await furnitureWorksetsApi.products(workset.id)
      const results = data.results || []
      setWorksetProducts(results)
      const next = {}
      results.forEach((p) => { next[p.id] = 0 })
      setQtys(next)
      if (onSeatCountChange && !seatCount && workset.seat_count) {
        onSeatCountChange(String(workset.seat_count))
      }
    } catch {
      setWorksetProducts([])
    } finally {
      setLoading(false)
    }
  }

  const picked = useMemo(
    () => worksetProducts.filter((p) => Number(qtys[p.id] || 0) > 0 && catalogPrice(p) > 0),
    [worksetProducts, qtys],
  )
  const pickTotal = picked.reduce((s, p) => s + catalogPrice(p) * Number(qtys[p.id] || 0), 0)

  const confirmPick = () => {
    if (!picked.length) return
    const newLines = picked.map((p) => lineFromProduct(p, Number(qtys[p.id] || 1)))
    onChange([...lines.filter((l) => l.product_id), ...newLines])
    setPickerOpen(false)
    setSelectedWorkset(null)
    setWorksetProducts([])
    setQtys({})
  }

  const updateLine = (idx, patch) => {
    onChange(lines.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }
  const removeLine = (idx) => onChange(lines.filter((_, i) => i !== idx))

  const grouped = useMemo(() => {
    const map = new Map()
    lines.forEach((line, idx) => {
      const key = line.furniture_workset_name || 'سایر'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push({ line, idx })
    })
    return [...map.entries()]
  }, [lines])

  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 1), 0)

  return (
    <div className={fromLegacy('product-lines')}>
      {onSeatCountChange && (
        <Field label="تعداد نفر (دستی)">
          <input
            className={fromLegacy('ltr')}
            type="number"
            min="1"
            value={seatCount}
            onChange={(e) => onSeatCountChange(e.target.value)}
            placeholder="مثلاً ۸"
          />
        </Field>
      )}

      {grouped.map(([name, rows]) => (
        <div key={name}>
          {name !== 'سایر' && <p className={fromLegacy('muted small')}>دست: {name}</p>}
          {rows.map(({ line, idx }) => {
            const pieces = line.workset_config?.pieces || []
            return (
              <div key={idx} className={fromLegacy('sale-line-card')}>
                <div className={fromLegacy('sale-line-head')}>
                  <strong>{line.product_name}</strong>
                  <Button type="button" variant="ghost" size="sm" className={fromLegacy('sale-line-remove')} onClick={() => removeLine(idx)}>
                    حذف
                  </Button>
                </div>
                <div className={fromLegacy('sale-line-body')}>
                  <div className={fromLegacy('sale-line-meta-grid')}>
                    {pieces.length > 0 ? (
                      <span>
                        <em className={fromLegacy('muted')}>قطعات:</em>{' '}
                        {pieces.map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
                      </span>
                    ) : line.product_model ? (
                      <span><em className={fromLegacy('muted')}>مدل:</em> {line.product_model}</span>
                    ) : null}
                    {line.fabric && <span><em className={fromLegacy('muted')}>پارچه:</em> {line.fabric}</span>}
                    {pieces.filter((piece) => piece.paint?.name || piece.needs_paint === false).map((piece) => (
                      <span key={`${piece.piece_kind}-${piece.arm_style}`}>
                        <em className={fromLegacy('muted')}>{piece.piece_label}:</em>{' '}
                        {piece.needs_paint === false ? 'بدون رنگ' : piece.paint?.name}
                        {piece.fabric?.name ? ` / ${piece.fabric.name}` : ''}
                      </span>
                    ))}
                    {line.unit_price && <span><em className={fromLegacy('muted')}>قیمت:</em> {formatMoney(line.unit_price)}</span>}
                  </div>
                  <Field label="تعداد دست">
                    <input className={fromLegacy('ltr')} type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, { quantity: e.target.value })} />
                  </Field>
                  {line.unit_price && (
                    <p className={fromLegacy('muted small')}>جمع ردیف: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ))}

      <div className={fromLegacy('product-lines-toolbar')}>
        <Button type="button" onClick={() => { setSelectedWorkset(null); setSearch(''); setPickerOpen(true) }}>
          {lines.length ? 'از دست دیگر' : 'انتخاب دست'}
        </Button>
      </div>
      {lines.length > 0 && <p className={fromLegacy('muted')}>جمع محصولات: {formatMoney(total)}</p>}

      <Modal
        title={selectedWorkset ? `محصول‌های ${selectedWorkset.name}` : 'انتخاب دست'}
        open={pickerOpen}
        onClose={() => { setPickerOpen(false); setSelectedWorkset(null) }}
        wide
      >
        {!selectedWorkset ? (
          <div className={fromLegacy('product-picker')}>
            <input
              className={fromLegacy('search-input')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجوی دست…"
            />
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : worksets.length === 0 ? (
              <p className={fromLegacy('muted')}>دستی یافت نشد.</p>
            ) : (
              <div className={fromLegacy('product-picker-grid')}>
                {worksets.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    className={fromLegacy('product-picker-item')}
                    onClick={() => openWorkset(w)}
                  >
                    <strong>{w.name}</strong>
                    <span className={fromLegacy('muted small')}>{toPersianDigits(w.piece_count || 0)} قطعه</span>
                    {(w.pieces || []).length > 0 && (
                      <span className={fromLegacy('muted small')}>
                        {(w.pieces || []).map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
                      </span>
                    )}
                    {w.seat_count ? <span className={fromLegacy('muted small')}>{toPersianDigits(w.seat_count)} نفر</span> : null}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={fromLegacy('product-picker')}>
            <button type="button" className={fromLegacy('link')} onClick={() => setSelectedWorkset(null)}>← دست‌های دیگر</button>
            {selectedWorkset.pieces?.length > 0 && (
              <p className={fromLegacy('muted small')}>
                ترکیب دست: {selectedWorkset.pieces.map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
              </p>
            )}
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : worksetProducts.length === 0 ? (
              <p className={fromLegacy('muted')}>برای این دست محصولی با قیمت تعریف نشده.</p>
            ) : (
              <div className={fromLegacy('product-picker-grid')}>
                {worksetProducts.map((p) => {
                  const price = catalogPrice(p)
                  return (
                    <div key={p.id} className={fromLegacy('product-picker-item')}>
                      <strong>{p.name}</strong>
                      <span className={fromLegacy('muted')}>{pieceSummary(p)}</span>
                      {fabricSummary(p) ? <span className={fromLegacy('muted small')}>پارچه: {fabricSummary(p)}</span> : null}
                      {price > 0 ? (
                        <span>{formatMoney(price)}</span>
                      ) : (
                        <span className={fromLegacy('alert-error')}>بدون قیمت</span>
                      )}
                      <Field label="تعداد دست">
                        <input
                          className={fromLegacy('ltr')}
                          type="number"
                          min="0"
                          value={qtys[p.id] || 0}
                          onChange={(e) => setQtys((q) => ({ ...q, [p.id]: e.target.value }))}
                          disabled={price <= 0}
                        />
                      </Field>
                    </div>
                  )
                })}
              </div>
            )}
            {picked.length > 0 && (
              <p className={fromLegacy('muted')}>
                جمع این دست: {formatMoney(pickTotal)} — {toPersianDigits(picked.length)} محصول
              </p>
            )}
            <div className={fromLegacy('form-actions')}>
              <Button type="button" variant="ghost" onClick={() => { setPickerOpen(false); setSelectedWorkset(null) }}>انصراف</Button>
              <Button type="button" onClick={confirmPick} disabled={!picked.length}>
                افزودن به فاکتور
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export { EMPTY_LINE as EMPTY_PRODUCT_LINE }
