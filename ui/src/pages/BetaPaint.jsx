import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaPaintApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useBetaSaleSources } from '../hooks/useBetaSaleSources'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'
import { BETA_PAINT_KIND, BETA_PAINT_STAGE, useBetaOptions } from '../hooks/useBetaOptions'

const EMPTY = {
  sale_id: '',
  product_name: '',
  kind: '',
  color_name: '',
  stage: '',
  progress: '0',
  qc_issue: '',
  note: '',
}

export default function BetaPaint() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const betaOptions = useBetaOptions()
  const { saleOptions, applySale } = useBetaSaleSources()
  const canManage = hasPermission(user, 'manage_beta_paint')
  const [stats, setStats] = useState({ by_stage: {}, by_kind: {} })
  const [orders, setOrders] = useState([])
  const [kind, setKind] = useState('')
  const [stage, setStage] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [advanceItem, setAdvanceItem] = useState(null)
  const [advanceNote, setAdvanceNote] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const kindOpts = useMemo(() => betaOptions(BETA_PAINT_KIND, stats.kinds), [betaOptions, stats.kinds])
  const stageOpts = useMemo(() => betaOptions(BETA_PAINT_STAGE, stats.stages), [betaOptions, stats.stages])
  const finalStage = stats.final_stage || (stageOpts.length ? stageOpts[stageOpts.length - 1].value : '')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, list] = await Promise.all([
        betaPaintApi.stats(),
        betaPaintApi.list({ kind, stage, search: search.trim(), limit: 200 }),
      ])
      setStats(s || { by_stage: {}, by_kind: {} })
      setOrders(list.results || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [kind, stage, search])

  useEffect(() => { load() }, [load])

  const grouped = useMemo(() => {
    const map = {}
    for (const st of stageOpts) map[st.value] = []
    for (const order of orders) {
      if (!map[order.stage]) map[order.stage] = []
      map[order.stage].push(order)
    }
    return map
  }, [orders, stageOpts])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, kind: kindOpts[0]?.value || '', stage: stageOpts[0]?.value || '' })
    setModalOpen(true)
  }

  const openEdit = (order) => {
    setEditing(order)
    setForm({
      sale_id: order.sale_id ? String(order.sale_id) : '',
      product_name: order.product_name || '',
      kind: order.kind || '',
      color_name: order.color_name || '',
      stage: order.stage || '',
      progress: String(order.progress ?? 0),
      qc_issue: order.qc_issue || '',
      note: '',
    })
    setModalOpen(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const payload = {
        ...form,
        sale_id: form.sale_id ? Number(form.sale_id) : null,
        progress: Number(form.progress || 0),
      }
      if (editing) await betaPaintApi.update(editing.id, payload)
      else await betaPaintApi.create(payload)
      setModalOpen(false)
      setEditing(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeOrder = async (order) => {
    if (!(await confirm({ title: 'حذف سفارش رنگ', message: `${order.code} حذف شود؟` }))) return
    try {
      await betaPaintApi.remove(order.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const submitAdvance = async () => {
    if (!advanceItem) return
    setBusyId(advanceItem.id)
    try {
      await betaPaintApi.advance(advanceItem.id, advanceNote.trim() || undefined)
      setAdvanceItem(null)
      setAdvanceNote('')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const renderOrderActions = (order) => {
    if (!canManage) return null
    return (
      <div className={fromLegacy('row')}>
        {order.stage !== finalStage && (
          <Button variant="ghost" disabled={busyId === order.id} onClick={() => { setAdvanceItem(order); setAdvanceNote('') }}>
            مرحله بعد
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={() => openEdit(order)}>ویرایش</Button>
        <Button variant="ghost" size="sm" onClick={() => removeOrder(order)}>حذف</Button>
      </div>
    )
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>واحد رنگ و پلی‌استر مبلمان (بتا)</h1>
          <p className={fromLegacy('muted')}>
            مستقر در کارخانه — جریان ۸گانه خط رنگ، تعمیرات، برگشتی‌های QC و ارتقای مرحله
          </p>
        </div>
        {canManage && (
          <Button onClick={openCreate}>+ ثبت سفارش کلاف رنگ</Button>
        )}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <div className={fromLegacy('stat-grid')}>
        <StatCard label="کلاف‌های در جریان خط" value={stats.total ?? 0} />
        {kindOpts.map((opt) => (
          <StatCard
            key={opt.value}
            label={opt.label}
            value={stats.by_kind?.[opt.value] ?? 0}
            accent={opt.meta?.color}
          />
        ))}
      </div>

      <div className={fromLegacy('workflow-filter-bar')}>
        <span className={fromLegacy('workflow-filter-label')}>فیلتر سفارشات خط:</span>
        <div className={fromLegacy('workflow-filter-tabs')}>
          <button type="button" className={fromLegacy(`workflow-filter-tab ${kind === '' ? 'active' : ''}`)} onClick={() => setKind('')}>همه موارد</button>
          {kindOpts.map((opt) => (
            <button key={opt.value} type="button" className={fromLegacy(`workflow-filter-tab ${kind === opt.value ? 'active' : ''}`)} onClick={() => setKind(opt.value)}>{opt.label}</button>
          ))}
        </div>
      </div>

      <FilterBar>
        <Field label="جستجو">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجوی کد، محصول، فام رنگ…" />
        </Field>
        <Field label="مرحله خط">
          <Select value={stage} onChange={setStage} options={[{ value: '', label: 'همه مراحل' }, ...stageOpts]} />
        </Field>
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : orders.length === 0 ? (
        <EmptyState text="سفارش رنگی مطابق فیلتر یافت نشد." />
      ) : (
        <div className={fromLegacy('frame-list')}>
          {stageOpts.map((st, idx) => (
            <Card key={st.value} title={`${idx + 1}. ${st.label}`} actions={<Badge>{(grouped[st.value] || []).length}</Badge>}>
              {(grouped[st.value] || []).length === 0 ? (
                <p className={fromLegacy('muted small')}>کلافی در این مرحله نیست</p>
              ) : (
                (grouped[st.value] || []).map((order) => (
                  <div key={order.id} className={fromLegacy('frame-row')}>
                    <div>
                      <strong>{order.product_name}</strong>
                      <div className={fromLegacy('muted small')}>
                        [{order.code}] • {order.color_name || 'فام تعریف‌نشده'} • {order.kind_display}
                      </div>
                      {order.qc_issue && <p className={fromLegacy('small')}>ایراد QC: {order.qc_issue}</p>}
                      <p className={fromLegacy('muted small')}>پیشرفت: {order.progress}٪</p>
                      {(order.notes_log || []).length > 0 && (
                        <p className={fromLegacy('muted small')}>آخرین یادداشت: {order.notes_log[order.notes_log.length - 1]?.text || '—'}</p>
                      )}
                    </div>
                    {renderOrderActions(order)}
                  </div>
                ))
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal title={editing ? `ویرایش ${editing.code}` : 'ثبت سفارش کلاف رنگ'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null) }} wide>
        <Field label="سفارش کارخانه">
          <Select value={form.sale_id} onChange={(v) => setForm(applySale(v, form))} options={saleOptions} />
        </Field>
        <Field label="نام محصول">
          <input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} />
        </Field>
        <Field label="نوع سفارش">
          <Select value={form.kind} onChange={(v) => setForm({ ...form, kind: v })} options={kindOpts} />
        </Field>
        <Field label="فام رنگ">
          <input list="beta-paint-colors" value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} />
          <datalist id="beta-paint-colors">
            {(stats.color_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="مرحله">
          <Select value={form.stage} onChange={(v) => setForm({ ...form, stage: v })} options={stageOpts} />
        </Field>
        <Field label="پیشرفت (٪)">
          <input className={fromLegacy('ltr')} type="number" min="0" max="100" value={form.progress} onChange={(e) => setForm({ ...form, progress: e.target.value })} />
        </Field>
        <Field label="ایراد QC">
          <textarea rows={3} value={form.qc_issue} onChange={(e) => setForm({ ...form, qc_issue: e.target.value })} />
        </Field>
        <Field label="یادداشت">
          <textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder={editing ? 'به لاگ یادداشت‌ها اضافه می‌شود' : 'یادداشت اولیه'} />
        </Field>
        {editing && (editing.notes_log || []).length > 0 && (
          <Field label="لاگ یادداشت‌ها">
            <div className={fromLegacy('muted small')}>
              {(editing.notes_log || []).slice(-5).map((entry, i) => (
                <div key={i}>{entry.at ? `${entry.at}: ` : ''}{entry.text}</div>
              ))}
            </div>
          </Field>
        )}
        <Button disabled={saving} onClick={save}>{editing ? 'ذخیره تغییرات' : 'ثبت سفارش'}</Button>
      </Modal>

      <Modal title={advanceItem ? `ارتقای مرحله — ${advanceItem.code}` : 'ارتقای مرحله'} open={Boolean(advanceItem)} onClose={() => setAdvanceItem(null)}>
        <Field label="یادداشت مرحله (اختیاری)">
          <textarea rows={3} value={advanceNote} onChange={(e) => setAdvanceNote(e.target.value)} placeholder="توضیح کوتاه برای لاگ خط رنگ…" />
        </Field>
        <Button disabled={busyId === advanceItem?.id} onClick={submitAdvance}>تایید و مرحله بعد</Button>
      </Modal>
    </div>
  )
}
