import { useCallback, useEffect, useMemo, useState } from 'react'
import { betaAssemblyApi, betaClearanceApi, betaCushionApi, betaFoamApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { useBetaSaleSources } from '../hooks/useBetaSaleSources'
import { parseRoute } from '../utils/routing'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const PIPELINES = {
  'factory-foam': {
    title: 'واحد اسفنج',
    api: betaFoamApi,
    managePerm: 'manage_beta_foam',
    nameField: 'foam_name',
    nameLabel: 'دستور اسفنج',
    createLabel: '+ ثبت کار اسفنج',
  },
  'factory-cushion': {
    title: 'واحد کوسن',
    api: betaCushionApi,
    managePerm: 'manage_beta_cushion',
    nameField: 'cushion_name',
    nameLabel: 'دستور کوسن',
    createLabel: '+ ثبت کار کوسن',
  },
  'factory-assembly': {
    title: 'مونتاژ',
    api: betaAssemblyApi,
    managePerm: 'manage_beta_assembly',
    nameField: 'assembly_name',
    nameLabel: 'شرح مونتاژ',
    createLabel: '+ ثبت کار مونتاژ',
  },
  'factory-clearance': {
    title: 'ترخیص',
    api: betaClearanceApi,
    managePerm: 'manage_beta_clearance',
    nameField: 'destination',
    nameLabel: 'مقصد',
    createLabel: '+ ثبت ترخیص',
  },
}

const EMPTY = { sale_id: '', product_name: '', name: '', stage: '', progress: '0', note: '' }

export default function BetaPipelineJobs() {
  const { page } = parseRoute()
  const meta = PIPELINES[page] || PIPELINES['factory-foam']
  const { user } = useAuth()
  const confirm = useConfirm()
  const { saleOptions, applySale } = useBetaSaleSources()
  const canManage = hasPermission(user, meta.managePerm)
  useRegisterPageGuide(page, PAGE_GUIDE_DEFAULTS[page])

  const [stats, setStats] = useState({ by_stage: {}, stages: [] })
  const [jobs, setJobs] = useState([])
  const [stage, setStage] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const stageOpts = useMemo(() => stats.stages || [], [stats.stages])
  const finalStage = stats.final_stage || (stageOpts.length ? stageOpts[stageOpts.length - 1].value : '')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, list] = await Promise.all([
        meta.api.stats(),
        meta.api.list({ stage, search: search.trim(), limit: 200 }),
      ])
      setStats(s || { by_stage: {}, stages: [] })
      setJobs(list.results || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [meta.api, stage, search])

  useEffect(() => { load() }, [load])

  const grouped = useMemo(() => {
    const map = {}
    for (const st of stageOpts) map[st.value] = []
    for (const job of jobs) {
      if (!map[job.stage]) map[job.stage] = []
      map[job.stage].push(job)
    }
    return map
  }, [jobs, stageOpts])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, stage: stageOpts[0]?.value || '' })
    setModalOpen(true)
  }

  const openEdit = (job) => {
    setEditing(job)
    setForm({
      sale_id: job.sale_id ? String(job.sale_id) : '',
      product_name: job.product_name || '',
      name: job[meta.nameField] || '',
      stage: job.stage || '',
      progress: String(job.progress ?? 0),
      note: '',
    })
    setModalOpen(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const payload = {
        sale_id: form.sale_id ? Number(form.sale_id) : null,
        product_name: form.product_name,
        [meta.nameField]: form.name,
        stage: form.stage,
        progress: Number(form.progress || 0),
        note: form.note,
      }
      if (editing) await meta.api.update(editing.id, payload)
      else await meta.api.create(payload)
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
    if (!(await confirm({ title: 'حذف کار', message: `${job.code} حذف شود؟` }))) return
    try {
      await meta.api.remove(job.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const advance = async (job) => {
    setBusyId(job.id)
    try {
      await meta.api.advance(job.id)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>{meta.title}</h1>
          <p className={fromLegacy('muted')}>کارهای ساخته‌شده از دست کار محصول هنگام دریافت سفارش کارخانه</p>
        </div>
        {canManage && <Button onClick={openCreate}>{meta.createLabel}</Button>}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <div className={fromLegacy('stat-grid')}>
        <StatCard label="کل کارها" value={stats.total ?? 0} />
        {stageOpts.map((opt) => (
          <StatCard key={opt.value} label={opt.label} value={stats.by_stage?.[opt.value] ?? 0} />
        ))}
      </div>

      <FilterBar>
        <Field label="جستجو">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="کد، محصول یا دستور…" />
        </Field>
        <Field label="مرحله">
          <Select value={stage} onChange={setStage} options={[{ value: '', label: 'همه مراحل' }, ...stageOpts]} />
        </Field>
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : jobs.length === 0 ? (
        <EmptyState text="کاری مطابق فیلتر یافت نشد." />
      ) : (
        <div className={fromLegacy('frame-list')}>
          {stageOpts.map((st, idx) => (
            <Card key={st.value} title={`${idx + 1}. ${st.label}`} actions={<Badge>{(grouped[st.value] || []).length}</Badge>}>
              {(grouped[st.value] || []).length === 0 ? (
                <p className={fromLegacy('muted small')}>کاری در این مرحله نیست</p>
              ) : (
                (grouped[st.value] || []).map((job) => (
                  <div key={job.id} className={fromLegacy('frame-row')}>
                    <div>
                      <strong>{job.product_name}</strong>
                      <div className={fromLegacy('muted small')}>
                        [{job.code}] • {job[meta.nameField] || 'بدون دستور'} • پیشرفت {job.progress}٪
                      </div>
                    </div>
                    {canManage && (
                      <div className={fromLegacy('row')}>
                        {job.stage !== finalStage && (
                          <Button variant="ghost" disabled={busyId === job.id} onClick={() => advance(job)}>مرحله بعد</Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => openEdit(job)}>ویرایش</Button>
                        <Button variant="ghost" size="sm" onClick={() => removeJob(job)}>حذف</Button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal title={editing ? `ویرایش ${editing.code}` : meta.createLabel} open={modalOpen} onClose={() => setModalOpen(false)}>
        <Field label="سفارش کارخانه">
          <Select value={form.sale_id} onChange={(v) => setForm(applySale(v, form))} options={saleOptions} />
        </Field>
        <Field label="نام محصول">
          <input value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} />
        </Field>
        <Field label={meta.nameLabel}>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="مرحله">
          <Select value={form.stage} onChange={(v) => setForm({ ...form, stage: v })} options={stageOpts} />
        </Field>
        <Field label="پیشرفت (٪)">
          <input className={fromLegacy('ltr')} type="number" min="0" max="100" value={form.progress} onChange={(e) => setForm({ ...form, progress: e.target.value })} />
        </Field>
        <Field label="یادداشت">
          <textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </Field>
        <Button disabled={saving} onClick={save}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>
      </Modal>
    </div>
  )
}
