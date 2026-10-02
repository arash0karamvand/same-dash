import { useEffect, useState } from 'react'
import { productionApi } from '../api/client'
import { Badge, Button, Card, EmptyState } from '../components/ui'
import { tw } from '../styles/tw'

const labels = {
  draft: 'پیش‌نویس',
  blocked: 'دارای کسری',
  released: 'آزادشده',
  in_progress: 'در جریان',
  completed: 'تکمیل‌شده',
}

export default function ProductionRuns() {
  const [runs, setRuns] = useState([])
  const [boms, setBoms] = useState([])
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async (selectUuid) => {
    setLoading(true)
    try {
      const [data, bomData] = await Promise.all([productionApi.runs(), productionApi.boms()])
      setRuns(data.results || [])
      setBoms(bomData.results || [])
      if (selectUuid) setSelected((data.results || []).find((row) => row.uuid === selectUuid) || null)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const action = async (callback, uuid) => {
    try {
      await callback()
      await load(uuid)
    } catch (e) {
      setError(e.message)
    }
  }

  const extra = (run) => {
    const materialId = window.prompt('شناسه متریال')
    const quantity = window.prompt('مقدار مصرف اضافه')
    const reason = window.prompt('دلیل و مجوز مصرف اضافه')
    if (!materialId || !quantity || !reason) return
    action(() => productionApi.consumeExtra(run.uuid, {
      material_id: Number(materialId),
      quantity,
      reason,
      idempotency_key: crypto.randomUUID(),
    }), run.uuid)
  }

  const returnMaterial = (run) => {
    const original = window.prompt('UUID رویداد مصرف اصلی')
    const quantity = window.prompt('مقدار برگشتی')
    const reason = window.prompt('دلیل برگشت')
    if (!original || !quantity) return
    action(() => productionApi.returnMaterial(run.uuid, {
      original_event_uuid: original,
      quantity,
      reason: reason || '',
      idempotency_key: crypto.randomUUID(),
    }), run.uuid)
  }

  const scrap = (run) => {
    const materialId = window.prompt('شناسه متریال ضایعات')
    const quantity = window.prompt('مقدار ضایعات')
    const reason = window.prompt('دلیل ضایعات')
    if (!materialId || !quantity || !reason) return
    action(() => productionApi.recordScrap(run.uuid, {
      material_id: Number(materialId),
      quantity,
      reason,
      idempotency_key: crypto.randomUUID(),
    }), run.uuid)
  }

  const complete = (run) => {
    const overhead = window.prompt('سربار تخصیص‌یافته', '0')
    if (overhead == null) return
    action(() => productionApi.complete(run.uuid, {
      overhead_cost: overhead,
      idempotency_key: `complete:${run.uuid}`,
    }), run.uuid)
  }

  const publishBom = () => {
    const productId = window.prompt('شناسه محصول برای انتشار نسخه جدید BOM')
    if (!productId) return
    action(() => productionApi.publishBom(Number(productId)))
  }

  return (
    <div className={tw.page}>
      <div className={tw.pageHeader}>
        <div>
          <h1 className={tw.pageTitle}>کنترل تولید و بهای واقعی</h1>
          <p className={tw.pageSubtitle}>BOM منجمد، رزرو، رهگیری لات مصرف، ضایعات و کالای ساخته‌شده</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={publishBom}>انتشار BOM</Button>
          <Button onClick={() => load(selected?.uuid)}>به‌روزرسانی</Button>
        </div>
      </div>
      {error && <div className={tw.error}>{error}</div>}
      <Card>
        <h2 className="mb-2 font-bold">نسخه‌های BOM منتشرشده</h2>
        <div className="flex flex-wrap gap-2">
          {boms.filter((bom) => bom.status === 'published').map((bom) => (
            <Badge key={bom.uuid}>محصول {bom.product_id} — نسخه {bom.version} ({bom.lines.length} ردیف)</Badge>
          ))}
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          {loading ? <p>در حال دریافت…</p> : !runs.length ? (
            <EmptyState title="اجرای تولیدی ثبت نشده است" />
          ) : runs.map((run) => (
            <button
              type="button"
              key={run.uuid}
              onClick={() => setSelected(run)}
              className="mb-2 flex w-full items-center justify-between rounded-xl border border-slate-200 p-3 text-right"
            >
              <span>سفارش {run.production_order_id} — {run.quantity} عدد</span>
              <Badge>{labels[run.status] || run.status}</Badge>
            </button>
          ))}
        </Card>
        <Card>
          {!selected ? <EmptyState title="یک اجرای تولید را انتخاب کنید" /> : (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {selected.status === 'blocked' && (
                  <Button onClick={() => action(() => productionApi.release(selected.uuid), selected.uuid)}>بررسی مجدد و رزرو</Button>
                )}
                <Button onClick={() => extra(selected)}>مصرف اضافه</Button>
                <Button onClick={() => returnMaterial(selected)}>برگشت متریال</Button>
                <Button onClick={() => scrap(selected)}>ثبت ضایعات</Button>
                {selected.status === 'in_progress' && <Button onClick={() => complete(selected)}>تکمیل و ایجاد لات</Button>}
              </div>
              <section>
                <h3 className="mb-2 font-bold">نیاز و رزرو متریال</h3>
                {selected.requirements.map((req) => (
                  <div key={req.id} className="mb-2 rounded-xl bg-slate-50 p-3">
                    <div>{req.material} — نیاز {req.required_quantity} / کسری {req.shortage_quantity}</div>
                    <div className="mt-2 flex items-center gap-2">
                      <Badge>{req.reservation_status || 'بدون رزرو'}</Badge>
                      {req.reservation_status === 'active' && (
                        <Button onClick={() => action(
                          () => productionApi.consumeRequirement(selected.uuid, req.id, `requirement:${selected.uuid}:${req.id}`),
                          selected.uuid,
                        )}>ثبت مصرف FIFO</Button>
                      )}
                    </div>
                  </div>
                ))}
              </section>
              <section>
                <h3 className="mb-2 font-bold">رهگیری رویداد و لات</h3>
                {selected.events.map((event) => (
                  <div key={event.uuid} className="mb-2 rounded-xl border border-slate-200 p-3">
                    <div>{event.event_type} — مقدار {event.quantity} — بهای {event.total_cost.toLocaleString('fa-IR')}</div>
                    <small className="break-all text-slate-500">{event.uuid}</small>
                    {event.allocations.map((lot) => (
                      <div key={lot.layer_uuid} className="text-xs text-slate-600">
                        لات {lot.layer_uuid}: {lot.quantity} × {lot.unit_cost.toLocaleString('fa-IR')}
                      </div>
                    ))}
                  </div>
                ))}
              </section>
              <div className="rounded-xl bg-emerald-50 p-3">
                مواد {selected.cost_breakdown.actual_material.toLocaleString('fa-IR')} + سربار {selected.cost_breakdown.overhead.toLocaleString('fa-IR')} = {selected.cost_breakdown.total.toLocaleString('fa-IR')}
                {selected.product_lot && <div>لات محصول: {selected.product_lot.lot_number} — نرخ {selected.product_lot.unit_cost.toLocaleString('fa-IR')}</div>}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
