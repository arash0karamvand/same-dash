// صفحه باشگاه مشتریان و سطوح: تعریف بازه و امتیاز هر سطح.
// بازه هر سطح (حداقل/حداکثر خرید) توسط مدیر تعیین می‌شود و سطح مشتری خودکار محاسبه می‌گردد.

import { useEffect, useState } from 'react'
import { levelsApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { formatMoney } from '../utils/format'

const EMPTY_FORM = {
  name: '',
  min_purchase: 0,
  max_purchase: '',
  points: 0,
  color: '#6366f1',
  description: '',
}

export default function Levels() {
  const [levels, setLevels] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)

  const load = async () => {
    setLoading(true)
    try {
      const data = await levelsApi.list()
      setLevels(data.results)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setModalOpen(true)
  }

  const openEdit = (level) => {
    setEditing(level)
    setForm({
      name: level.name,
      min_purchase: level.min_purchase,
      max_purchase: level.max_purchase ?? '',
      points: level.points,
      color: level.color,
      description: level.description,
    })
    setModalOpen(true)
  }

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const save = async (e) => {
    e.preventDefault()
    // max_purchase خالی یعنی سطح بدون سقف (بالاترین سطح).
    const payload = {
      ...form,
      min_purchase: Number(form.min_purchase),
      max_purchase: form.max_purchase === '' ? null : Number(form.max_purchase),
      points: Number(form.points),
    }
    try {
      if (editing) {
        await levelsApi.update(editing.id, payload)
      } else {
        await levelsApi.create(payload)
      }
      setModalOpen(false)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (level) => {
    if (!confirm(`حذف سطح «${level.name}»؟`)) return
    await levelsApi.remove(level.id)
    load()
  }

  return (
    <div className="page">
      <Card title="سطوح باشگاه مشتریان" actions={<Button onClick={openCreate}>+ سطح جدید</Button>}>
        {error && <div className="alert-error">{error}</div>}
        <p className="muted">
          بازه هر سطح را مشخص کنید (مثلاً برنز از ۰ تا ۱۰ میلیون). سطح هر مشتری به‌صورت خودکار بر
          اساس همین بازه‌ها و مجموع خریدش تعیین می‌شود. «حداکثر خرید» را برای بالاترین سطح خالی بگذارید.
        </p>
        {loading ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : levels.length === 0 ? (
          <EmptyState text="سطحی تعریف نشده است." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>سطح</th>
                <th>از (حداقل خرید)</th>
                <th>تا (حداکثر خرید)</th>
                <th>امتیاز</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {levels.map((t) => (
                <tr key={t.id}>
                  <td><Badge color={t.color}>{t.name}</Badge></td>
                  <td>{formatMoney(t.min_purchase)}</td>
                  <td>{t.max_purchase === null ? 'بدون سقف' : formatMoney(t.max_purchase)}</td>
                  <td>{t.points}</td>
                  <td>{t.is_active ? 'فعال' : 'غیرفعال'}</td>
                  <td className="row-actions">
                    <button className="link" onClick={() => openEdit(t)}>ویرایش</button>
                    <button className="link danger" onClick={() => remove(t)}>حذف</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Modal title={editing ? 'ویرایش سطح' : 'سطح جدید'} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className="form">
          <Field label="نام سطح">
            <input value={form.name} onChange={update('name')} placeholder="مثلاً طلایی" required />
          </Field>
          <Field label="حداقل خرید (تومان)">
            <MoneyInput min="0" value={form.min_purchase} onChange={(e) => update('min_purchase')(e)} />
          </Field>
          <Field label="حداکثر خرید (تومان) — خالی = بدون سقف">
            <MoneyInput min="0" value={form.max_purchase} onChange={(e) => update('max_purchase')(e)} placeholder="برای بالاترین سطح خالی بگذارید" />
          </Field>
          <Field label="امتیاز سطح">
            <input className="ltr" type="number" min="0" value={form.points} onChange={update('points')} />
          </Field>
          <Field label="رنگ">
            <input type="color" value={form.color} onChange={update('color')} />
          </Field>
          <Field label="توضیحات">
            <textarea value={form.description} onChange={update('description')} rows={2} />
          </Field>
          <Button type="submit">ذخیره</Button>
        </form>
      </Modal>
    </div>
  )
}
