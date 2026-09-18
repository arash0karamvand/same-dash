import { useCallback, useEffect, useMemo, useState } from 'react'
import { rfmApi } from '../api/client'
import Select from './Select'
import MoneyInput from './MoneyInput'
import { Badge, Button, Card, EmptyState, Field, Modal } from './ui'
import { useConfirm } from '../context/ConfirmContext'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const REDEEM_OPTIONS = [
  { value: 'auto_each_sale', label: 'هر فاکتور از مبلغ کم شود' },
  { value: 'wallet_credit', label: 'شارژ یک‌باره کیف پول' },
  { value: 'manual', label: 'بدون مصرف خودکار' },
]

const EMPTY_PROGRAM = {
  name: '',
  is_active: true,
  sort_order: 0,
  description: '',
  earn_percent: '5',
  base_usable_percent: '30',
  redeem_mode: 'manual',
  segment_ids: [],
  unlock_steps: [],
  preview_last: '10000000',
  preview_invoice: '11000000',
  preview_balance: '1000000',
}

function emptyStep() {
  return { extra_purchase_percent: '10', extra_usable_percent: '20' }
}

function previewUsable(form) {
  const base = Number(form.base_usable_percent) || 0
  const last = Number(form.preview_last) || 0
  const invoice = Number(form.preview_invoice) || 0
  const balance = Number(form.preview_balance) || 0
  let extra = 0
  if (last > 0 && invoice > last) {
    const growth = ((invoice - last) / last) * 100
    const matched = (form.unlock_steps || [])
      .map((step) => ({
        purchase: Number(step.extra_purchase_percent) || 0,
        usable: Number(step.extra_usable_percent) || 0,
      }))
      .filter((step) => growth >= step.purchase)
      .sort((a, b) => b.purchase - a.purchase)[0]
    extra = matched ? matched.usable : 0
  }
  const usablePct = Math.max(0, Math.min(100, base + extra))
  return {
    usablePct,
    usableAmount: Math.round((balance * usablePct) / 100),
  }
}

export default function RfmCashback({ canManage, segments = [] }) {
  const confirm = useConfirm()
  const [programs, setPrograms] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_PROGRAM)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await rfmApi.cashbackPrograms()
      setPrograms(data.results || [])
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const segmentOptions = useMemo(
    () => segments.map((item) => ({ value: String(item.id), label: item.name })),
    [segments],
  )

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY_PROGRAM, sort_order: programs.length, unlock_steps: [] })
    setModalOpen(true)
  }

  const openEdit = (program) => {
    setEditing(program)
    setForm({
      name: program.name,
      is_active: program.is_active,
      sort_order: program.sort_order || 0,
      description: program.description || '',
      earn_percent: String(program.earn_percent ?? 0),
      base_usable_percent: String(program.base_usable_percent ?? 0),
      redeem_mode: program.redeem_mode || 'manual',
      segment_ids: (program.segment_ids || []).map(String),
      unlock_steps: (program.unlock_steps || []).map((step) => ({
        extra_purchase_percent: String(step.extra_purchase_percent),
        extra_usable_percent: String(step.extra_usable_percent),
      })),
      preview_last: '10000000',
      preview_invoice: '11000000',
      preview_balance: '1000000',
    })
    setModalOpen(true)
  }

  const payload = () => ({
    name: form.name,
    is_active: form.is_active,
    sort_order: Number(form.sort_order || 0),
    description: form.description,
    earn_percent: Number(form.earn_percent || 0),
    base_usable_percent: Number(form.base_usable_percent || 0),
    redeem_mode: form.redeem_mode,
    segment_ids: form.segment_ids.map(Number),
    unlock_steps: (form.unlock_steps || []).map((step) => ({
      extra_purchase_percent: Number(step.extra_purchase_percent || 0),
      extra_usable_percent: Number(step.extra_usable_percent || 0),
    })),
  })

  const save = async (e) => {
    e.preventDefault()
    try {
      if (editing) await rfmApi.updateCashbackProgram(editing.id, payload())
      else await rfmApi.createCashbackProgram(payload())
      setModalOpen(false)
      await load()
      setInfo('برنامه کش‌بک ذخیره شد.')
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (program) => {
    if (!await confirm({
      title: 'حذف برنامه',
      message: `برنامه «${program.name}» حذف شود؟ مانده کش‌بک مشتریان پاک نمی‌شود.`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    await rfmApi.removeCashbackProgram(program.id)
    await load()
  }

  const preview = previewUsable(form)
  const redeemLabel = (mode) => REDEEM_OPTIONS.find((item) => item.value === mode)?.label || mode

  if (loading) return <div className={fromLegacy('loading')}>در حال بارگذاری…</div>

  return (
    <>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-info')}>{info}</div>}
      <Card
        title="برنامه‌های کش‌بک"
        actions={canManage ? <Button type="button" onClick={openCreate}>برنامه جدید</Button> : null}
      >
        <p className={fromLegacy('muted')}>
          هر برنامه می‌تواند یک یا چند بخش RFM را هدف بگیرد. اگر بخشی انتخاب نشود برای همه مشتریان است.
          وقتی چند برنامه جور شوند، اولویت کمتر برنده است.
        </p>
        {programs.length === 0 ? (
          <EmptyState text="برنامه‌ای نیست. یک برنامه با درصد کسب، سقف مصرف و پله اپسل بسازید." />
        ) : (
          <div className={fromLegacy('table-wrap')} style={{ marginTop: 12 }}>
            <table>
              <thead>
                <tr>
                  <th>برنامه</th>
                  <th>کسب</th>
                  <th>قابل‌استفاده</th>
                  <th>مصرف</th>
                  <th>بخش‌ها</th>
                  <th>پله‌ها</th>
                  {canManage && <th />}
                </tr>
              </thead>
              <tbody>
                {programs.map((program) => (
                  <tr key={program.id}>
                    <td>
                      {program.name}
                      {!program.is_active && <Badge>غیرفعال</Badge>}
                    </td>
                    <td>{toPersianDigits(program.earn_percent)}٪</td>
                    <td>{toPersianDigits(program.base_usable_percent)}٪</td>
                    <td>{redeemLabel(program.redeem_mode)}</td>
                    <td>
                      {(program.segment_ids || []).length
                        ? segments
                          .filter((item) => program.segment_ids.includes(item.id))
                          .map((item) => item.name)
                          .join('، ')
                        : 'همه'}
                    </td>
                    <td>{toPersianDigits((program.unlock_steps || []).length)}</td>
                    {canManage && (
                      <td>
                        <Button variant="ghost" onClick={() => openEdit(program)}>ویرایش</Button>
                        <Button variant="ghost" onClick={() => remove(program)}>حذف</Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal title={editing ? 'ویرایش برنامه کش‌بک' : 'برنامه جدید'} open={modalOpen} onClose={() => setModalOpen(false)} wide>
        <form onSubmit={save} className={fromLegacy('form')}>
          <Field label="نام برنامه">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="اولویت (عدد کمتر = زودتر)">
            <input
              className={fromLegacy('ltr')}
              type="number"
              min="0"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value || 0) })}
            />
          </Field>
          <Field label="درصد کسب از مبلغ پرداخت‌شده">
            <MoneyInput
              unit="درصد"
              min="0"
              max="100"
              step="0.5"
              value={form.earn_percent}
              onChange={(e) => setForm({ ...form, earn_percent: e.target.value })}
            />
          </Field>
          <Field label="درصد پایه قابل‌استفاده از مانده">
            <MoneyInput
              unit="درصد"
              min="0"
              max="100"
              step="0.5"
              value={form.base_usable_percent}
              onChange={(e) => setForm({ ...form, base_usable_percent: e.target.value })}
            />
          </Field>
          <Field label="حالت مصرف">
            <Select
              value={form.redeem_mode}
              onChange={(redeem_mode) => setForm({ ...form, redeem_mode })}
              options={REDEEM_OPTIONS}
              label="حالت مصرف"
            />
          </Field>
          <Field label="بخش‌های RFM (خالی = همه)">
            <div className="rfm-score-row">
              {segmentOptions.map((opt) => {
                const checked = form.segment_ids.includes(opt.value)
                return (
                  <label key={opt.value} className="rfm-score-chip">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const next = checked
                          ? form.segment_ids.filter((id) => id !== opt.value)
                          : [...form.segment_ids, opt.value]
                        setForm({ ...form, segment_ids: next })
                      }}
                    />
                    {opt.label}
                  </label>
                )
              })}
            </div>
          </Field>
          <Field label="توضیح">
            <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <label className="rfm-score-chip">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            برنامه فعال باشد
          </label>

          <div className="rfm-cashback-steps">
            <div className="rfm-cashback-steps-head">
              <strong>پله‌های اپسل فاکتور</strong>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setForm({ ...form, unlock_steps: [...form.unlock_steps, emptyStep()] })}
              >
                پله جدید
              </Button>
            </div>
            <p className={fromLegacy('muted')}>
              اگر این فاکتور از آخرین خرید بیشتر باشد، درصد بیشتری از مانده آزاد می‌شود. بالاترین پلهٔ مطابق اعمال می‌گردد.
            </p>
            {form.unlock_steps.length === 0 ? (
              <p className={fromLegacy('muted')}>بدون پله؛ فقط درصد پایه قابل‌استفاده است.</p>
            ) : form.unlock_steps.map((step, index) => (
              <div key={index} className="rfm-cashback-step-row">
                <Field label="اگر چند درصد بیشتر بخرد">
                  <MoneyInput
                    unit="درصد"
                    min="0"
                    max="100"
                    step="0.5"
                    value={step.extra_purchase_percent}
                    onChange={(e) => {
                      const unlock_steps = form.unlock_steps.map((item, i) => (
                        i === index ? { ...item, extra_purchase_percent: e.target.value } : item
                      ))
                      setForm({ ...form, unlock_steps })
                    }}
                  />
                </Field>
                <Field label="چند درصد بیشتر از کش‌بک آزاد شود">
                  <MoneyInput
                    unit="درصد"
                    min="0"
                    max="100"
                    step="0.5"
                    value={step.extra_usable_percent}
                    onChange={(e) => {
                      const unlock_steps = form.unlock_steps.map((item, i) => (
                        i === index ? { ...item, extra_usable_percent: e.target.value } : item
                      ))
                      setForm({ ...form, unlock_steps })
                    }}
                  />
                </Field>
                <button
                  type="button"
                  className={fromLegacy('link')}
                  onClick={() => setForm({
                    ...form,
                    unlock_steps: form.unlock_steps.filter((_, i) => i !== index),
                  })}
                >
                  حذف
                </button>
              </div>
            ))}
          </div>

          <div className="rfm-cashback-preview">
            <strong>پیش‌نمایش سقف مصرف</strong>
            <div className="rfm-cashback-step-row">
              <Field label="آخرین خرید">
                <MoneyInput min="0" value={form.preview_last} onChange={(e) => setForm({ ...form, preview_last: e.target.value })} />
              </Field>
              <Field label="فاکتور جاری">
                <MoneyInput min="0" value={form.preview_invoice} onChange={(e) => setForm({ ...form, preview_invoice: e.target.value })} />
              </Field>
              <Field label="مانده کش‌بک">
                <MoneyInput min="0" value={form.preview_balance} onChange={(e) => setForm({ ...form, preview_balance: e.target.value })} />
              </Field>
            </div>
            <p>
              قابل‌استفاده: {toPersianDigits(preview.usablePct)}٪ = {formatMoney(preview.usableAmount)}
            </p>
          </div>

          <Button type="submit">ذخیره برنامه</Button>
        </form>
      </Modal>
    </>
  )
}
