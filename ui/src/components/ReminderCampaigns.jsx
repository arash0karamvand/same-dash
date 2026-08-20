// کمپین یادآوری دوره‌ای باشگاه — فقط مدیر

import { useCallback, useEffect, useState } from 'react'
import { levelsApi, smsApi } from '../api/client'
import { useConfirm } from '../context/ConfirmContext'
import { Button, Card, EmptyState, Field, Modal } from '../components/ui'

const EMPTY = {
  name: '',
  interval_months: 3,
  is_enabled: true,
  shop_name: 'سام اکسون',
  message_template: '{name} عزیز، {shop_name} دلتنگ شماست! کد باشگاه: {code} — سطح: {level}',
  level_ids: [],
  min_months_since_purchase: '',
}

export default function ReminderCampaigns() {
  const confirm = useConfirm()
  const [campaigns, setCampaigns] = useState([])
  const [levels, setLevels] = useState([])
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cData, lData, pData] = await Promise.all([
        smsApi.reminderList(),
        levelsApi.list(),
        smsApi.reminderPreview(false),
      ])
      setCampaigns(cData.results || [])
      setLevels(lData.results || [])
      setPreview(pData)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY)
    setModalOpen(true)
  }

  const openEdit = (c) => {
    setEditing(c)
    setForm({
      name: c.name,
      interval_months: c.interval_months,
      is_enabled: c.is_enabled,
      shop_name: c.shop_name,
      message_template: c.message_template,
      level_ids: c.level_ids || [],
      min_months_since_purchase: c.min_months_since_purchase || '',
    })
    setModalOpen(true)
  }

  const toggleLevel = (id) => {
    setForm((f) => ({
      ...f,
      level_ids: f.level_ids.includes(id) ? f.level_ids.filter((x) => x !== id) : [...f.level_ids, id],
    }))
  }

  const save = async (e) => {
    e.preventDefault()
    try {
      const payload = {
        ...form,
        min_months_since_purchase: form.min_months_since_purchase ? Number(form.min_months_since_purchase) : null,
      }
      if (editing) {
        await smsApi.updateReminder(editing.id, payload)
        setInfo('کمپین به‌روز شد.')
      } else {
        await smsApi.createReminder(payload)
        setInfo('کمپین ساخته شد.')
      }
      setModalOpen(false)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const sendNow = async (id, force = false) => {
    try {
      const r = await smsApi.sendReminder(id, force)
      setInfo(`ارسال: ${r.successful} موفق، ${r.failed} ناموفق`)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (id) => {
    if (!await confirm({
      title: 'حذف کمپین',
      message: 'این کمپین حذف شود؟',
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await smsApi.deleteReminder(id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <p className="muted">در حال بارگذاری یادآوری‌ها…</p>

  return (
    <div className="reminder-section">
      {error && <div className="alert-error">{error}</div>}
      {info && <div className="alert-info">{info}</div>}

      <Card title="یادآوری دوره‌ای باشگاه" actions={<Button onClick={openCreate}>+ کمپین جدید</Button>}>
        <p className="muted">
          هر چند ماه یک‌بار به مشتریان (بر اساس سطح باشگاه) پیام یادآوری ارسال می‌شود. فقط مدیر سیستم.
        </p>

        {campaigns.length === 0 ? (
          <EmptyState message="کمپینی تعریف نشده" />
        ) : (
          <div className="reminder-list">
            {campaigns.map((c) => {
              const prev = preview?.campaigns?.find((p) => p.id === c.id)
              return (
                <div key={c.id} className="reminder-item">
                  <div>
                    <strong>{c.name}</strong>
                    <span className="muted"> — هر {c.interval_months} ماه</span>
                    {!c.is_enabled && <span className="badge-muted"> غیرفعال</span>}
                    <div className="muted small">
                      سطوح: {c.levels?.length ? c.levels.map((l) => l.name).join('، ') : 'همه'}
                      {prev && ` — ${prev.will_send_count} نفر در صف ارسال`}
                    </div>
                  </div>
                  <div className="reminder-actions">
                    <button type="button" className="link" onClick={() => openEdit(c)}>ویرایش</button>
                    <button type="button" className="link link-success" onClick={() => sendNow(c.id)}>ارسال الان</button>
                    <button type="button" className="link danger" onClick={() => remove(c.id)}>حذف</button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'ویرایش کمپین' : 'کمپین یادآوری'}>
        <form onSubmit={save} className="form-grid">
          <Field label="نام کمپین"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
          <Field label="هر چند ماه">
            <input type="number" min={1} max={24} value={form.interval_months} onChange={(e) => setForm({ ...form, interval_months: Number(e.target.value) })} />
          </Field>
          <Field label="نام فروشگاه"><input value={form.shop_name} onChange={(e) => setForm({ ...form, shop_name: e.target.value })} /></Field>
          <Field label="حداقل ماه بدون خرید (اختیاری)">
            <input type="number" min={0} value={form.min_months_since_purchase} onChange={(e) => setForm({ ...form, min_months_since_purchase: e.target.value })} placeholder="خالی = همه" />
          </Field>
          <Field label="متن پیام">
            <textarea rows={3} value={form.message_template} onChange={(e) => setForm({ ...form, message_template: e.target.value })} />
            <span className="muted small">متغیرها: {'{name}'} {'{shop_name}'} {'{code}'} {'{level}'} {'{phone}'}</span>
          </Field>
          <div>
            <div className="field-label">سطوح باشگاه (خالی = همه)</div>
            <div className="level-check-grid">
              {levels.map((l) => (
                <label key={l.id} className="checkbox-row">
                  <input type="checkbox" checked={form.level_ids.includes(l.id)} onChange={() => toggleLevel(l.id)} />
                  {l.name}
                </label>
              ))}
            </div>
          </div>
          <label className="checkbox-row">
            <input type="checkbox" checked={form.is_enabled} onChange={(e) => setForm({ ...form, is_enabled: e.target.checked })} />
            فعال
          </label>
          <div className="form-actions">
            <Button type="submit">ذخیره</Button>
            <Button type="button" variant="ghost" onClick={() => setModalOpen(false)}>انصراف</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
