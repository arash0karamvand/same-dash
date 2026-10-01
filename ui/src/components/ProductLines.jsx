import { useEffect, useMemo, useState } from 'react'
import { furnitureWorksetsApi, salesApi } from '../api/client'
import Select from './Select'
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
  fabric_recipe_id: '',
  paint_recipe_id: '',
  price_note: '',
}

function catalogPrice(product) {
  return Number(product?.default_price || product?.display_price || 0)
}

function jobPieces(product) {
  return product?.workset?.pieces || product?.suite_config || []
}

function pieceSummary(product) {
  const pieces = jobPieces(product)
  if (!pieces.length) return product?.product_model || ''
  return pieces.map((piece) => `${piece.quantity}× ${piece.piece_label}`).join('، ')
}

function fabricSummary(product) {
  const pieces = jobPieces(product)
  const names = [...new Set(pieces.map((piece) => piece.fabric?.name).filter(Boolean))]
  if (names.length) return names.join('، ')
  return product?.fabric || product?.fabric_recipe?.name || ''
}

function consumptionMeters(block) {
  return (block?.materials || []).reduce((sum, row) => sum + Number(row.quantity || 0), 0)
}

function serviceMeters(pieces) {
  return (pieces || []).reduce(
    (sum, piece) => sum + consumptionMeters(piece.fabric) * Number(piece.quantity || 1),
    0,
  )
}

function missingMeterPieces(pieces) {
  return (pieces || [])
    .filter((piece) => consumptionMeters(piece.fabric) <= 0)
    .map((piece) => piece.piece_label || 'قطعه')
}

function recipeLabel(recipe, withRate = false) {
  if (!recipe) return ''
  const color = recipe.color_name && recipe.color_name !== recipe.name ? ` (${recipe.color_name})` : ''
  const rate = withRate && Number(recipe.unit_cost) > 0 ? ` — ${formatMoney(recipe.unit_cost)} هر متر` : ''
  return `${recipe.name}${color}${rate}`
}

function lockedSpecs(pieces) {
  return (pieces || []).map((piece) => {
    const meters = consumptionMeters(piece.fabric)
    const bits = [
      `${toPersianDigits(piece.quantity || 1)}× ${piece.piece_label || 'قطعه'}`,
      meters > 0 ? `${toPersianDigits(meters)} متر` : 'بدون متراژ',
    ]
    if (piece.foam?.name) bits.push(`اسفنج ${piece.foam.name}`)
    if (piece.webbing?.name) bits.push(`تسمه ${piece.webbing.name}`)
    if (piece.cushion?.name) bits.push(`کوسن ${piece.cushion.name}`)
    return bits.join(' · ')
  })
}

function applyFinish(line, fabricRecipe, paintRecipe) {
  const pieces = line.workset_config?.pieces || []
  const needsPaint = pieces.some((piece) => piece.needs_paint !== false)
  const missing = missingMeterPieces(pieces)
  const meters = serviceMeters(pieces)
  const rate = Number(fabricRecipe?.unit_cost || 0)
  let priceNote = ''
  if (!fabricRecipe) priceNote = 'پارچه را انتخاب کنید.'
  else if (needsPaint && !paintRecipe) priceNote = 'رنگ بدنه را انتخاب کنید.'
  else if (missing.length) priceNote = `متراژ مصرف در تعریف کار نیست: ${missing.join('، ')}`
  else if (rate <= 0) priceNote = 'نرخ هر متر این پارچه ثبت نشده است.'
  const unitPrice = !priceNote && meters > 0 ? Math.round(meters * rate) : ''
  const nextPieces = pieces.map((piece) => {
    const pieceMeters = consumptionMeters(piece.fabric)
    const next = { ...piece }
    if (fabricRecipe) {
      next.fabric = {
        ...(piece.fabric || {}),
        id: fabricRecipe.id,
        name: fabricRecipe.name,
        color_name: fabricRecipe.color_name || '',
        kind: 'fabric',
        unit_cost: rate,
        materials: piece.fabric?.materials || [],
        consumption_meters: pieceMeters,
      }
      next.fabric_recipe_id = fabricRecipe.id
    }
    if (paintRecipe && piece.needs_paint !== false) {
      next.paint = {
        id: paintRecipe.id,
        name: paintRecipe.name,
        color_name: paintRecipe.color_name || paintRecipe.name,
        kind: 'paint',
      }
      next.paint_recipe_id = paintRecipe.id
    }
    return next
  })
  return {
    ...line,
    fabric_recipe_id: fabricRecipe?.id || '',
    paint_recipe_id: paintRecipe?.id || '',
    fabric: fabricRecipe ? recipeLabel(fabricRecipe) : line.fabric,
    color_name: paintRecipe ? (paintRecipe.color_name || paintRecipe.name) : line.color_name,
    unit_price: unitPrice === '' ? '' : String(unitPrice),
    price_note: priceNote,
    workset_config: {
      ...(line.workset_config || {}),
      pieces: nextPieces,
      sale_choices: {
        fabric_recipe_id: fabricRecipe?.id || null,
        paint_recipe_id: paintRecipe?.id || null,
        meters,
        price_per_meter: rate,
        unit_price: unitPrice || 0,
      },
    },
  }
}

function lineFromProduct(product, quantity = 1) {
  const variant = product.variants?.[0]
  const pieces = jobPieces(product)
  const base = {
    ...EMPTY_LINE,
    product_id: product.id,
    variant_id: variant?.id || '',
    frame_id: product.frame_id || '',
    furniture_workset_id: product.furniture_workset_id || '',
    furniture_workset_name: product.furniture_workset?.name || '',
    workset_config: product.workset || { pieces },
    product_name: product.name,
    product_model: product.furniture_workset?.name || product.product_model || '',
    fabric: fabricSummary(product),
    color_name: variant?.color_name || '',
    color_hex: variant?.color_hex || '',
    unit_price: pieces.length ? '' : String(catalogPrice(product)),
    target_min_price: product.target_min_price || '',
    quantity,
    price_note: pieces.length ? 'رنگ بدنه و پارچه را انتخاب کنید.' : '',
  }
  return pieces.length ? base : base
}

export default function ProductLines({
  lines,
  onChange,
  seatCount = '',
  onSeatCountChange,
  stockSourceLabel = '',
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [worksets, setWorksets] = useState([])
  const [selectedWorkset, setSelectedWorkset] = useState(null)
  const [worksetProducts, setWorksetProducts] = useState([])
  const [qtys, setQtys] = useState({})
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [paints, setPaints] = useState([])
  const [fabrics, setFabrics] = useState([])

  useEffect(() => {
    let cancelled = false
    salesApi.finishOptions()
      .then((data) => {
        if (cancelled) return
        setPaints(data?.paints || [])
        setFabrics(data?.fabrics || [])
      })
      .catch(() => {
        if (!cancelled) {
          setPaints([])
          setFabrics([])
        }
      })
    return () => { cancelled = true }
  }, [])

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

  const canAdd = (product) => jobPieces(product).length > 0 || catalogPrice(product) > 0
  const picked = useMemo(
    () => worksetProducts.filter((p) => Number(qtys[p.id] || 0) > 0 && canAdd(p)),
    [worksetProducts, qtys],
  )
  const pickTotal = picked.reduce((sum, product) => {
    if (jobPieces(product).length) return sum
    return sum + catalogPrice(product) * Number(qtys[product.id] || 0)
  }, 0)

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

  const chooseFinish = (idx, line, key, value) => {
    const fabricId = key === 'fabric' ? value : line.fabric_recipe_id
    const paintId = key === 'paint' ? value : line.paint_recipe_id
    const fabricRecipe = fabrics.find((row) => String(row.id) === String(fabricId))
    const paintRecipe = paints.find((row) => String(row.id) === String(paintId))
    updateLine(idx, applyFinish(
      { ...line, fabric_recipe_id: fabricId, paint_recipe_id: paintId },
      fabricRecipe,
      paintRecipe,
    ))
  }

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
  const paintOptions = [{ value: '', label: 'انتخاب رنگ بدنه…' }, ...paints.map((row) => ({ value: String(row.id), label: recipeLabel(row) }))]
  const fabricOptions = [{ value: '', label: 'انتخاب پارچه…' }, ...fabrics.map((row) => ({ value: String(row.id), label: recipeLabel(row, true) }))]

  return (
    <div className={fromLegacy('product-lines')}>
      {stockSourceLabel ? <p className={fromLegacy('muted small')}>موجودی از: {stockSourceLabel}</p> : null}
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
          {name !== 'سایر' && <p className={fromLegacy('muted small')}>سرویس: {name}</p>}
          {rows.map(({ line, idx }) => {
            const pieces = line.workset_config?.pieces || []
            const meters = Number(line.workset_config?.sale_choices?.meters || serviceMeters(pieces))
            const rate = Number(line.workset_config?.sale_choices?.price_per_meter || 0)
            const needsPaint = pieces.some((piece) => piece.needs_paint !== false)
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
                      lockedSpecs(pieces).map((text) => <span key={text}>{text}</span>)
                    ) : line.product_model ? (
                      <span><em className={fromLegacy('muted')}>مدل:</em> {line.product_model}</span>
                    ) : null}
                    {!pieces.length && line.fabric ? <span><em className={fromLegacy('muted')}>پارچه:</em> {line.fabric}</span> : null}
                  </div>
                  {pieces.length > 0 && (
                    <>
                      {needsPaint && (
                        <Field label="رنگ بدنه">
                          <Select
                            value={line.paint_recipe_id ? String(line.paint_recipe_id) : ''}
                            onChange={(value) => chooseFinish(idx, line, 'paint', value)}
                            options={paintOptions}
                          />
                        </Field>
                      )}
                      <Field label="پارچه">
                        <Select
                          value={line.fabric_recipe_id ? String(line.fabric_recipe_id) : ''}
                          onChange={(value) => chooseFinish(idx, line, 'fabric', value)}
                          options={fabricOptions}
                        />
                      </Field>
                    </>
                  )}
                  <Field label="تعداد سرویس">
                    <input className={fromLegacy('ltr')} type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, { quantity: e.target.value })} />
                  </Field>
                  {line.price_note ? <p className={fromLegacy('alert-error')}>{line.price_note}</p> : null}
                  {line.unit_price && meters > 0 && rate > 0 && (
                    <p className={fromLegacy('muted small')}>
                      قیمت نهایی: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}
                      {' '}— {toPersianDigits(meters)} متر × {formatMoney(rate)}
                      {Number(line.quantity) > 1 ? ` × ${toPersianDigits(line.quantity)} سرویس` : ''}
                    </p>
                  )}
                  {line.unit_price && !(meters > 0 && rate > 0) && (
                    <p className={fromLegacy('muted small')}>جمع ردیف: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}</p>
                  )}
                  {line.target_min_price && Number(line.unit_price) > 0 && Number(line.unit_price) < Number(line.target_min_price) && (
                    <p className={fromLegacy('doc-unbalanced')}>قیمت از حاشیه سود هدف پایین‌تر است.</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ))}

      <div className={fromLegacy('product-lines-toolbar')}>
        <Button type="button" onClick={() => { setSelectedWorkset(null); setSearch(''); setPickerOpen(true) }}>
          {lines.length ? 'از سرویس دیگر' : 'انتخاب سرویس'}
        </Button>
      </div>
      {lines.length > 0 && <p className={fromLegacy('muted')}>جمع محصولات: {formatMoney(total)}</p>}

      <Modal
        title={selectedWorkset ? `محصول‌های ${selectedWorkset.name}` : 'انتخاب سرویس'}
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
              placeholder="جستجوی سرویس…"
            />
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : worksets.length === 0 ? (
              <p className={fromLegacy('muted')}>سرویسی یافت نشد.</p>
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
            <button type="button" className={fromLegacy('link')} onClick={() => setSelectedWorkset(null)}>← سرویس‌های دیگر</button>
            {selectedWorkset.pieces?.length > 0 && (
              <p className={fromLegacy('muted small')}>
                ترکیب سرویس: {selectedWorkset.pieces.map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
              </p>
            )}
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : worksetProducts.length === 0 ? (
              <p className={fromLegacy('muted')}>برای این سرویس محصولی تعریف نشده.</p>
            ) : (
              <div className={fromLegacy('product-picker-grid')}>
                {worksetProducts.map((p) => {
                  const pieces = jobPieces(p)
                  const price = catalogPrice(p)
                  const missing = missingMeterPieces(pieces)
                  return (
                    <div key={p.id} className={fromLegacy('product-picker-item')}>
                      <strong>{p.name}</strong>
                      <span className={fromLegacy('muted')}>{pieceSummary(p)}</span>
                      {pieces.length > 0 ? (
                        <>
                          {lockedSpecs(pieces).map((text) => <span key={text} className={fromLegacy('muted small')}>{text}</span>)}
                          {missing.length > 0 && <span className={fromLegacy('alert-error')}>متراژ مصرف ناقص است</span>}
                        </>
                      ) : fabricSummary(p) ? <span className={fromLegacy('muted small')}>پارچه: {fabricSummary(p)}</span> : null}
                      {!pieces.length && (price > 0 ? (
                        <span>{formatMoney(price)}</span>
                      ) : (
                        <span className={fromLegacy('alert-error')}>بدون قیمت</span>
                      ))}
                      <Field label="تعداد سرویس">
                        <input
                          className={fromLegacy('ltr')}
                          type="number"
                          min="0"
                          value={qtys[p.id] || 0}
                          onChange={(e) => setQtys((q) => ({ ...q, [p.id]: e.target.value }))}
                          disabled={!canAdd(p)}
                        />
                      </Field>
                    </div>
                  )
                })}
              </div>
            )}
            {picked.length > 0 && (
              <p className={fromLegacy('muted')}>
                {pickTotal > 0 ? `جمع قیمت کاتالوگ: ${formatMoney(pickTotal)} — ` : ''}
                {toPersianDigits(picked.length)} محصول
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
