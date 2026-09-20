import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaUpholsteryApi } from '../api/client'
import { BetaChipNav, BetaSegmentNav } from '../components/BetaSegmentNav'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useBetaSaleSources } from '../hooks/useBetaSaleSources'
import { formatJalali, toPersianDigits } from '../utils/jalali'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'
import { BETA_UPHOLSTERY_STAGE, useBetaOptions } from '../hooks/useBetaOptions'

const EMPTY = {
  sale_id: '',
  order_ref: '',
  product_name: '',
  foam_material: '',
  craftsman: '',
  stage: '',
  progress: '0',
  due_date: '',
}

export default function BetaUpholstery() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const betaOptions = useBetaOptions()
  const { saleOptions, applySale } = useBetaSaleSources()
  const canManage = hasPermission(user, 'manage_beta_upholstery')
  const [stats, setStats] = useState({ by_stage: {} })
  const [jobs, setJobs] = useState([])
  const [listTotal, setListTotal] = useState(0)
  const [view, setView] = useState('pipeline')
  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const stages = useMemo(() => betaOptions(BETA_UPHOLSTERY_STAGE, stats.stages), [betaOptions, stats.stages])
  const finalStage = stats.final_stage || stages[stages.length - 1]?.value || ''

  const stageCount = useCallback((code) => stats.by_stage?.[code] ?? 0, [stats.by_stage])

  const stageChipItems = useMemo(() => [
    { key: '', label: 'همه مراحل', count: stats.total ?? 0 },
    ...stages.map((opt) => ({
      key: opt.value,
      label: opt.label,
      count: stageCount(opt.value),
      accent: opt.meta?.color,
    })),
  ], [stages, stats.total, stageCount])

  const viewItems = useMemo(() => [
    { key: 'pipeline', label: 'خط تولید', count: stats.total ?? 0, hint: 'رکورد در دیتابیس' },
    { key: 'table', label: 'فهرست جدولی', count: listTotal ?? stats.total ?? 0, hint: stage ? 'با فیلتر مرحله' : 'همه رکوردها' },
  ], [stats.total, listTotal, stage])

  const grouped = useMemo(() => {
    const map = {}
    for (const s of stages) map[s.value] = []
    for (const job of jobs) {
      if (!map[job.stage]) map[job.stage] = []
      map[job.stage].push(job)
    }
    return map
  }, [jobs, stages])

  const visibleStages = useMemo(() => {
    if (!stage) return stages
    return stages.filter((s) => s.value === stage)
  }, [stages, stage])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const searchTrim = search.trim()
    try {
      const [s, list] = await Promise.all([
        betaUpholsteryApi.stats({ search: searchTrim }),
        betaUpholsteryApi.list({
          search: searchTrim,
          stage,
          limit: view === 'pipeline' && !stage ? 500 : 100,
        }),
      ])
      setStats(s || { by_stage: {} })
      setJobs(list.results || [])
      setListTotal(list.total ?? 0)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search, stage, view])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, stage: stages[0]?.value || '' })
    setModalOpen(true)
  }

  const openEdit = (job) => {
    setEditing(job)
    setForm({
      sale_id: job.sale_id ? String(job.sale_id) : '',
      order_ref: job.order_ref || '',
      product_name: job.product_name || '',
      foam_material: job.foam_material || '',
      craftsman: job.craftsman || '',
      stage: job.stage || '',
      progress: String(job.progress ?? 0),
      due_date: job.due_date || '',
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
      if (editing) await betaUpholsteryApi.update(editing.id, payload)
      else await betaUpholsteryApi.create(payload)
      setModalOpen(false)
      setEditing(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeJob = async (job) => {
    if (!(await confirm({ title: 'حذف کار رویه‌کوبی', message: `${job.code} حذف شود؟` }))) return
    try {
      await betaUpholsteryApi.remove(job.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const advance = async (job) => {
    setBusyId(job.id)
    try {
      await betaUpholsteryApi.advance(job.id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const renderJobActions = (job) => {
    if (!canManage) return null
    return (
      <div className={fromLegacy('row')}>
        {!(job.is_done || job.stage === finalStage) && (
          <Button variant="ghost" disabled={busyId === job.id} onClick={() => advance(job)}>مرحله بعد ←</Button>
        )}
        {(job.is_done || job.stage === finalStage) && <Badge color="var(--success)">آماده QC</Badge>}
        <Button variant="ghost" size="sm" onClick={() => openEdit(job)}>ویرایش</Button>
        <Button variant="ghost" size="sm" onClick={() => removeJob(job)}>حذف</Button>
      </div>
    )
  }

  const renderJobRow = (job) => (
    <tr key={job.id}>
      <td>{job.code}<div className={fromLegacy('muted small')}>{job.order_ref || '—'}</div></td>
      <td>{job.product_name}</td>
      <td>{job.foam_material || '—'}</td>
      <td>{job.craftsman || '—'}</td>
      <td><Badge color={stages.find((s) => s.value === job.stage)?.meta?.color}>{job.stage_display}</Badge></td>
      <td>
        {job.progress}٪
        <div className={fromLegacy('uph-progress-bar')}>
          <div className={fromLegacy('uph-progress-fill')} style={{ width: `${job.progress || 0}%` }} />
        </div>
      </td>
      <td>{job.due_date ? formatJalali(job.due_date) : '—'}</td>
      <td>{renderJobActions(job)}</td>
    </tr>
  )

  const renderJobCard = (job) => (
    <div key={job.id} className={fromLegacy('frame-row')}>
      <div>
        <strong>{job.product_name}</strong>
        <div className={fromLegacy('muted small')}>
          [{job.code}] • {job.order_ref || 'بدون سفارش'} • {job.craftsman || 'بدون استادکار'}
        </div>
        <div className={fromLegacy('muted small')}>
          فوم: {job.foam_material || '—'} • موعد: {job.due_date ? formatJalali(job.due_date) : '—'}
        </div>
        <div className={fromLegacy('uph-progress-bar')} style={{ maxWidth: 180 }}>
          <div className={fromLegacy('uph-progress-fill')} style={{ width: `${job.progress || 0}%` }} />
        </div>
        <span className={fromLegacy('muted small')}>پیشرفت: {job.progress}٪</span>
      </div>
      {renderJobActions(job)}
    </div>
  )

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>واحد رویه‌کوبی و مونتاژ نهایی (بتا)</h1>
          <p className={fromLegacy('muted')}>
            مرحله پایانی خط ساخت: تسمه‌کشی، فنربندی، فوم سرد، لمسه‌کاری و ارسال به QC
          </p>
        </div>
        {canManage && (
          <Button onClick={openCreate}>+ ثبت کار رویه‌کوبی</Button>
        )}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <div className={fromLegacy('stat-grid')}>
        <StatCard label="کل کارهای رویه‌کوبی" value={stats.total ?? 0} active={stage === ''} onClick={() => setStage('')} />
        <StatCard label="در حال مونتاژ و لمسه" value={stats.assembling ?? 0} accent="var(--warning)" />
        <StatCard
          label="آماده بازرسی QC"
          value={stats.ready_for_qc ?? 0}
          accent="var(--success)"
          active={stage === finalStage}
          onClick={() => finalStage && setStage(finalStage)}
        />
      </div>

      <BetaSegmentNav label="نمای صفحه" value={view} onChange={setView} items={viewItems} />

      <div className={fromLegacy('beta-stage-pipeline')} role="tablist" aria-label="مراحل فنی">
        {stages.map((opt, idx) => (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={stage === opt.value}
            className={fromLegacy(`beta-stage-step ${stage === opt.value ? 'active' : ''}`)}
            onClick={() => setStage(stage === opt.value ? '' : opt.value)}
          >
            <span className={fromLegacy('beta-stage-step-num')}>{idx + 1}</span>
            <span className={fromLegacy('beta-stage-step-label')}>{opt.label}</span>
            <span className={fromLegacy('beta-stage-step-count')}>{stageCount(opt.value)}</span>
          </button>
        ))}
      </div>

      <BetaChipNav label="فیلتر مرحله" value={stage} onChange={setStage} items={stageChipItems} />

      <FilterBar>
        <Field label="جستجو">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجوی سفارش، مدل، استادکار…" />
        </Field>
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : jobs.length === 0 ? (
        <EmptyState text="کاری در این مرحله نیست" />
      ) : view === 'pipeline' ? (
        <div className={fromLegacy('frame-list')}>
          {visibleStages.map((s, idx) => (
            <Card key={s.value} title={`${idx + 1}. ${s.label}`} actions={<Badge color={s.meta?.color}>{stageCount(s.value)}</Badge>}>
              {stageCount(s.value) === 0 ? (
                <p className={fromLegacy('muted small')}>کاری در این مرحله نیست</p>
              ) : (
                <>
                  {(grouped[s.value] || []).map(renderJobCard)}
                  {stageCount(s.value) > (grouped[s.value] || []).length && (
                    <p className={fromLegacy('muted small')}>
                      نمایش {(grouped[s.value] || []).length} از {toPersianDigits(stageCount(s.value))} رکورد این مرحله
                    </p>
                  )}
                </>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Card
          title="فهرست کارهای رویه‌کوبی"
          actions={listTotal > 0 && (
            <span className={fromLegacy('muted small')}>{toPersianDigits(listTotal)} رکورد</span>
          )}
        >
          <div className={fromLegacy('table-wrap')}>
            <table className={fromLegacy('data-table')}>
              <thead>
                <tr>
                  <th>شناسه و شماره سفارش</th>
                  <th>مدل مبلمان</th>
                  <th>متریال فوم و نشیمن</th>
                  <th>استادکار</th>
                  <th>مرحله فنی</th>
                  <th>پیشرفت</th>
                  <th>موعد تحویل</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>{jobs.map(renderJobRow)}</tbody>
            </table>
          </div>
          {listTotal > jobs.length && (
            <p className={fromLegacy('muted small')}>
              نمایش {toPersianDigits(jobs.length)} از {toPersianDigits(listTotal)} رکورد
            </p>
          )}
        </Card>
      )}

      <Modal title={editing ? `ویرایش ${editing.code}` : 'ثبت کار رویه‌کوبی'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null) }} wide>
        <Field label="سفارش کارخانه">
          <Select value={form.sale_id} onChange={(v) => setForm(applySale(v, form))} options={saleOptions} />
        </Field>
        <Field label="شماره سفارش">
          <input value={form.order_ref} onChange={(e) => setForm({ ...form, order_ref: e.target.value })} />
        </Field>
        <Field label="مدل مبلمان">
          <input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} />
        </Field>
        <Field label="متریال فوم و نشیمن">
          <input list="beta-uph-foams" value={form.foam_material} onChange={(e) => setForm({ ...form, foam_material: e.target.value })} />
          <datalist id="beta-uph-foams">
            {(stats.foam_options || []).map((f) => <option key={f} value={f} />)}
          </datalist>
        </Field>
        <Field label="استادکار رویه‌کوب">
          <input list="beta-uph-craftsmen" value={form.craftsman} onChange={(e) => setForm({ ...form, craftsman: e.target.value })} />
          <datalist id="beta-uph-craftsmen">
            {(stats.craftsman_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="مرحله فنی">
          <Select value={form.stage} onChange={(v) => setForm({ ...form, stage: v })} options={stages} />
        </Field>
        <Field label="پیشرفت">
          <input className={fromLegacy('ltr')} type="number" min="0" max="100" value={form.progress} onChange={(e) => setForm({ ...form, progress: e.target.value })} />
        </Field>
        <Field label="موعد تحویل">
          <PersianDateInput value={form.due_date} onChange={(v) => setForm({ ...form, due_date: v })} />
        </Field>
        <Button disabled={saving} onClick={save}>{editing ? 'ذخیره تغییرات' : 'ثبت کار'}</Button>
      </Modal>
    </div>
  )
}
