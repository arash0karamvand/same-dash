// صفحه باشگاه مشتریان و سطوح: تعریف بازه و امتیاز هر سطح.
// بازه هر سطح (حداقل/حداکثر خرید) توسط مدیر تعیین می‌شود و سطح مشتری خودکار محاسبه می‌گردد.

import { useEffect, useState } from 'react'
import { levelsApi } from '../api/client'
import { useConfirm } from '../context/ConfirmContext'
import MoneyInput from '../components/MoneyInput'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { formatMoney } from '../utils/format'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_FORM = {
  name: '',
  min_purchase: 0,
  max_purchase: '',
  points: 0,
  color: 'var(--accent)',
  description: '',
}

export default function Levels() {
  const confirm = useConfirm()
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
    if (!await confirm({
      title: 'حذف سطح',
      message: `حذف سطح «${level.name}»؟`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    await levelsApi.remove(level.id)
    load()
  }

  return (
    <div className={fromLegacy("page")}>
      <Card title="سطوح باشگاه مشتریان" actions={<Button onClick={openCreate}>+ سطح جدید</Button>}>
        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        <p className={fromLegacy("muted")}>
          بازه هر سطح را مشخص کنید (مثلاً برنز از ۰ تا ۱۰ میلیون). سطح هر مشتری به‌صورت خودکار بر
          اساس همین بازه‌ها و مجموع خریدش تعیین می‌شود. «حداکثر خرید» را برای بالاترین سطح خالی بگذارید.
        </p>
        {loading ? (
          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
        ) : levels.length === 0 ? (
          <EmptyState text="سطحی تعریف نشده است." />
        ) : (
          <>
            <div className={fromLegacy("table-wrap levels-table-desktop")}>
              <table className={fromLegacy("table")}>
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
                      <td className={fromLegacy("row-actions")}>
                        <button className={fromLegacy("link")} onClick={() => openEdit(t)}>ویرایش</button>
                        <button className={fromLegacy("link danger")} onClick={() => remove(t)}>حذف</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={fromLegacy("levels-cards-mobile")}>
              {levels.map((t) => (
                <div key={t.id} className={fromLegacy("m-card")}>
                  <div className={fromLegacy("m-card-head")}>
                    <Badge color={t.color}>{t.name}</Badge>
                    <span className={fromLegacy("muted")}>{t.is_active ? 'فعال' : 'غیرفعال'}</span>
                  </div>
                  <div className={fromLegacy("m-card-grid")}>
                    <div><span className={fromLegacy("muted")}>حداقل خرید</span>{formatMoney(t.min_purchase)}</div>
                    <div><span className={fromLegacy("muted")}>حداکثر خرید</span>{t.max_purchase === null ? 'بدون سقف' : formatMoney(t.max_purchase)}</div>
                    <div><span className={fromLegacy("muted")}>امتیاز</span>{t.points}</div>
                  </div>
                  <div className={fromLegacy("m-card-actions")}>
                    <button type="button" className={fromLegacy("link")} onClick={() => openEdit(t)}>ویرایش</button>
                    <button type="button" className={fromLegacy("link danger")} onClick={() => remove(t)}>حذف</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      <Modal title={editing ? 'ویرایش سطح' : 'سطح جدید'} open={modalOpen} onClose={() => setModalOpen(false)}>
        <form onSubmit={save} className={fromLegacy("form")}>
          <Field label="نام سطح">
            <input value={form.name} onChange={update('name')} placeholder="مثلاً طلایی" required />
          </Field>
          <Field label="حداقل خرید (ریال)">
            <MoneyInput min="0" value={form.min_purchase} onChange={(e) => update('min_purchase')(e)} />
          </Field>
          <Field label="حداکثر خرید (ریال) — خالی = بدون سقف">
            <MoneyInput min="0" value={form.max_purchase} onChange={(e) => update('max_purchase')(e)} placeholder="برای بالاترین سطح خالی بگذارید" />
          </Field>
          <Field label="امتیاز سطح">
            <input className={fromLegacy("ltr")} type="number" min="0" value={form.points} onChange={update('points')} />
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
