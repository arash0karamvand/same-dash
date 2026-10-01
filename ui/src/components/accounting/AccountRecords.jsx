import { useEffect, useMemo, useState } from 'react'
import Icon from '../icons/Icon'
import PersianDateInput from '../PersianDateInput'
import { accountingApi } from '../../api/client'
import { useConfirm } from '../../context/ConfirmContext'
import { formatDate, formatRial } from '../../utils/format'

const RECORD_PREVIEW = 40

function todayIso() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function parseMoney(value) {
  const normalized = String(value || '')
    .replace(/[۰-۹]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(digit))
    .replace(/[٠-٩]/g, (digit) => '٠١٢٣٤٥٦٧٨٩'.indexOf(digit))
    .replace(/[,،\s]/g, '')
  if (!normalized) return 0
  const amount = Number(normalized)
  if (!Number.isFinite(amount) || amount < 0) return NaN
  return Math.round(amount)
}

function ledgerQuery(level, accountId) {
  if (level === 'detailed') return { detailedId: accountId }
  if (level === 'subsidiary') return { subsidiaryId: accountId }
  return { accountId }
}

function withRunningBalance(lines) {
  let running = 0
  return lines.map((line) => {
    const debit = Number(line.debit || 0)
    const credit = Number(line.credit || 0)
    running += debit - credit
    return { ...line, debit, credit, running }
  })
}

function nodeLine(level, id, debit, credit, description) {
  const body = { debit, credit, description }
  if (level === 'detailed') body.detailed_id = id
  else if (level === 'subsidiary') body.subsidiary_id = id
  else body.account_id = id
  return body
}

function documentLinePayload(row, overrides = {}) {
  const body = {
    debit: overrides.debit != null ? overrides.debit : Number(row.debit || 0),
    credit: overrides.credit != null ? overrides.credit : Number(row.credit || 0),
    description: overrides.description != null ? overrides.description : (row.description || ''),
  }
  if (row.detailed_id) body.detailed_id = row.detailed_id
  else if (row.subsidiary_id) body.subsidiary_id = row.subsidiary_id
  else body.account_id = row.account_id
  return body
}

function postingId(row) {
  return Number(row.detailed_id || row.subsidiary_id || row.account_id || 0)
}

function contraKeyOf(account) {
  return account ? `${account.level}:${account.id}` : ''
}

function amountsFrom(debitText, creditText) {
  const debit = parseMoney(debitText)
  const credit = parseMoney(creditText)
  if (Number.isNaN(debit) || Number.isNaN(credit)) {
    return { error: 'مبلغ نامعتبر است.' }
  }
  if ((debit > 0) === (credit > 0)) {
    return { error: 'دقیقاً یکی از بدهکار یا بستانکار باید مبلغ داشته باشد.' }
  }
  return { debit, credit }
}

export default function AccountRecords({ level, accountId, postableAccounts = [] }) {
  const confirm = useConfirm()
  const [lines, setLines] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [formMode, setFormMode] = useState('')
  const [editing, setEditing] = useState(null)
  const [date, setDate] = useState(todayIso)
  const [description, setDescription] = useState('')
  const [debitText, setDebitText] = useState('')
  const [creditText, setCreditText] = useState('')
  const [contraKey, setContraKey] = useState('')
  const [contraQuery, setContraQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    setShowAll(false)
    accountingApi.detailLedger(ledgerQuery(level, accountId))
      .then((payload) => {
        if (!cancelled) setLines(withRunningBalance(payload?.lines || []))
      })
      .catch((err) => {
        if (!cancelled) {
          setLines([])
          setError(err.message || 'خواندن رکوردها ممکن نشد.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [level, accountId, reloadKey])

  const needsContra = formMode === 'reverse' || (formMode === 'edit' && editing && !editing.can_edit)

  const contraOptions = useMemo(() => {
    const query = contraQuery.trim()
    const selected = postableAccounts.find((row) => contraKeyOf(row) === contraKey)
    const rows = postableAccounts.filter((row) => {
      if (row.level === level && Number(row.id) === Number(accountId)) return false
      if (!query) return true
      return `${row.code || ''} ${row.name || ''}`.includes(query)
    })
    const visible = query ? rows.slice(0, 80) : rows
    if (selected && !visible.some((row) => contraKeyOf(row) === contraKey)) visible.unshift(selected)
    return visible
  }, [postableAccounts, contraQuery, contraKey, level, accountId])

  const resetForm = () => {
    setFormMode('')
    setEditing(null)
    setDate(todayIso())
    setDescription('')
    setDebitText('')
    setCreditText('')
    setContraKey('')
    setContraQuery('')
  }

  const openCreate = () => {
    resetForm()
    setFormMode('create')
    setDate(todayIso())
  }

  const openEdit = (line) => {
    setError('')
    setNotice('')
    setFormMode('edit')
    setEditing(line)
    setDate((line.entry_date || '').slice(0, 10) || todayIso())
    setDescription(line.description || '')
    setDebitText(line.debit ? String(line.debit) : '')
    setCreditText(line.credit ? String(line.credit) : '')
    setContraKey('')
  }

  const selectedContra = postableAccounts.find((row) => contraKeyOf(row) === contraKey)

  const saveRecord = async (event) => {
    event.preventDefault()
    setError('')
    setNotice('')
    const amounts = amountsFrom(debitText, creditText)
    if (amounts.error) {
      setError(amounts.error)
      return
    }
    const text = description.trim()
    if (!date) {
      setError('تاریخ را انتخاب کنید.')
      return
    }
    if (formMode === 'create' && !selectedContra) {
      setError('حساب طرف را انتخاب کنید تا سند دوطرفه ساخته شود.')
      return
    }
    if (formMode === 'create' && Number(selectedContra.id) === Number(accountId)) {
      setError('حساب طرف باید با این حساب فرق داشته باشد.')
      return
    }
    if (needsContra && !selectedContra) {
      setError('برای اصلاح رکورد قطعی، حساب طرف را انتخاب کنید.')
      return
    }
    setBusy(true)
    try {
      if (formMode === 'create') {
        await accountingApi.createDocument({
          entry_date: date,
          description: text,
          lines: [
            nodeLine(level, accountId, amounts.debit, amounts.credit, text),
            nodeLine(selectedContra.level, selectedContra.id, amounts.credit, amounts.debit, text),
          ],
        })
        setNotice('رکورد ثبت شد. مانده از جمع همین رکوردها محاسبه می‌شود.')
      } else if (formMode === 'edit' && editing) {
        const doc = await accountingApi.getDocument(editing.document_code)
        const rows = doc.lines || []
        const current = rows.find((row) => row.id === editing.id)
        if (!current) throw new Error('این ردیف در سند پیدا نشد.')
        if (doc.can_edit && rows.length === 2) {
          await accountingApi.updateDocument(editing.document_code, {
            entry_date: date,
            description: text || doc.description || '',
            document_number: doc.document_number,
            lines: rows.map((row) => (
              row.id === editing.id
                ? documentLinePayload(row, { debit: amounts.debit, credit: amounts.credit, description: text })
                : documentLinePayload(row, { debit: amounts.credit, credit: amounts.debit, description: row.description || text })
            )),
          })
          setNotice('رکورد ویرایش شد.')
        } else {
          if (!selectedContra) {
            setError('این رکورد داخل سند قطعی یا چندخطی است. حساب طرف را انتخاب کنید تا اصلاح با سند جدید ثبت شود.')
            return
          }
          if (Number(selectedContra.id) === postingId(current)) {
            setError('حساب طرف باید با حساب همین رکورد فرق داشته باشد.')
            return
          }
          const oldDebit = Number(current.debit || 0)
          const oldCredit = Number(current.credit || 0)
          if (oldDebit === amounts.debit && oldCredit === amounts.credit) {
            setError('مبلغ رکورد قطعی عوض نشده است. شرح سند قطعی از اینجا تغییر نمی‌کند.')
            return
          }
          const label = `اصلاح رکورد سند ${editing.document_number || editing.document_code}`
          await accountingApi.createDocument({
            entry_date: date,
            description: label,
            lines: [
              documentLinePayload(current, { debit: oldCredit, credit: oldDebit, description: `برگشت ${text || label}` }),
              nodeLine(selectedContra.level, selectedContra.id, oldDebit, oldCredit, `برگشت ${text || label}`),
              documentLinePayload(current, { debit: amounts.debit, credit: amounts.credit, description: text || label }),
              nodeLine(selectedContra.level, selectedContra.id, amounts.credit, amounts.debit, text || label),
            ],
          })
          setNotice(doc.can_edit
            ? 'این سند چندخطی است. اصلاح با سند جدید ثبت شد و ردیف قبلی در لیست می‌ماند.'
            : 'سند قطعی بود. اصلاح با سند جدید ثبت شد و ردیف قبلی در لیست می‌ماند.')
        }
      } else if (formMode === 'reverse' && editing) {
        if (!selectedContra) {
          setError('حساب طرف را انتخاب کنید.')
          return
        }
        const doc = await accountingApi.getDocument(editing.document_code)
        const current = (doc.lines || []).find((row) => row.id === editing.id)
        if (!current) throw new Error('این ردیف در سند پیدا نشد.')
        if (Number(selectedContra.id) === postingId(current)) {
          setError('حساب طرف باید با حساب همین رکورد فرق داشته باشد.')
          return
        }
        const oldDebit = Number(current.debit || editing.debit || 0)
        const oldCredit = Number(current.credit || editing.credit || 0)
        const label = `برگشت رکورد سند ${editing.document_number || editing.document_code}`
        await accountingApi.createDocument({
          entry_date: date,
          description: label,
          lines: [
            documentLinePayload(current, { debit: oldCredit, credit: oldDebit, description: label }),
            nodeLine(selectedContra.level, selectedContra.id, oldDebit, oldCredit, label),
          ],
        })
        setNotice('اثر رکورد با سند اصلاحی صفر شد. ردیف قبلی در لیست می‌ماند.')
      }
      resetForm()
      setReloadKey((value) => value + 1)
    } catch (err) {
      setError(err.message || 'ثبت رکورد ممکن نشد.')
    } finally {
      setBusy(false)
    }
  }

  const removeRecord = async (line) => {
    setError('')
    setNotice('')
    setBusy(true)
    try {
      const doc = await accountingApi.getDocument(line.document_code)
      const rows = doc.lines || []
      if (doc.can_delete && rows.length === 2) {
        setBusy(false)
        const ok = await confirm({
          title: 'حذف رکورد',
          message: 'این رکورد و ردیف طرفش با هم یک سند دوتایی هستند و هر دو حذف می‌شوند.',
          confirmText: 'حذف',
          variant: 'danger',
        })
        if (!ok) return
        setBusy(true)
        await accountingApi.deleteDocument(line.document_code)
        setNotice('سند این رکورد حذف شد.')
        setReloadKey((value) => value + 1)
        return
      }
      if (doc.can_delete && rows.length > 2) {
        const remaining = rows
          .filter((row) => row.id !== line.id)
          .map((row) => documentLinePayload(row))
        const debit = remaining.reduce((sum, row) => sum + Number(row.debit || 0), 0)
        const credit = remaining.reduce((sum, row) => sum + Number(row.credit || 0), 0)
        if (remaining.length >= 2 && debit === credit && debit > 0) {
          setBusy(false)
          const ok = await confirm({
            title: 'حذف ردیف',
            message: 'فقط همین ردیف از سند حذف می‌شود و بقیه ردیف‌ها می‌مانند.',
            confirmText: 'حذف ردیف',
            variant: 'danger',
          })
          if (!ok) return
          setBusy(true)
          await accountingApi.updateDocument(line.document_code, {
            entry_date: doc.entry_date,
            description: doc.description || '',
            document_number: doc.document_number,
            lines: remaining,
          })
          setNotice('ردیف از سند حذف شد.')
          setReloadKey((value) => value + 1)
          return
        }
      }
      setFormMode('reverse')
      setEditing(line)
      setDate(todayIso())
      setDescription(line.description || '')
      setDebitText(line.debit ? String(line.debit) : '')
      setCreditText(line.credit ? String(line.credit) : '')
      setContraKey('')
      setNotice('این رکورد داخل سند قطعی است. حساب طرف را انتخاب کنید تا اثرش با سند اصلاحی صفر شود. ردیف قبلی در لیست می‌ماند.')
    } catch (err) {
      setError(err.message || 'حذف رکورد ممکن نشد.')
    } finally {
      setBusy(false)
    }
  }

  const visible = lines ? (showAll ? lines : lines.slice(0, RECORD_PREVIEW)) : []
  const debitTotal = (lines || []).reduce((sum, line) => sum + line.debit, 0)
  const creditTotal = (lines || []).reduce((sum, line) => sum + line.credit, 0)
  const net = debitTotal - creditTotal

  return (
    <div className="acct-hmap-records">
      <div className="acct-hmap-records-title">
        <strong>{lines ? `${lines.length.toLocaleString('fa-IR')} رکورد` : 'رکوردها'}</strong>
        {lines?.length ? (
          <span>
            مانده از جمع رکوردها: {formatRial(Math.abs(net))} {net > 0 ? 'بد' : net < 0 ? 'بس' : ''}
          </span>
        ) : null}
        <button type="button" className="acct-btn acct-btn--secondary acct-btn--sm" onClick={openCreate} disabled={busy}>
          <Icon name="plus" size={14} />
          رکورد جدید
        </button>
      </div>

      {formMode ? (
        <form className="acct-hmap-record-form" onSubmit={saveRecord}>
          <p className="acct-hmap-record-note">
            {formMode === 'create'
              ? 'رکورد با یک سند دوطرفه ثبت می‌شود: همین حساب و حساب طرف.'
              : formMode === 'reverse'
                ? 'حذف رکورد قطعی، ردیف قبلی را پاک نمی‌کند؛ یک سند برگشت با مبلغ مخالف می‌سازد.'
                : needsContra
                  ? 'این رکورد قطعی است. ذخیره، مبلغ قبلی را برگشت می‌زند و مبلغ جدید را با سند تازه ثبت می‌کند.'
                  : 'اگر سند فقط دو ردیف داشته باشد همین‌جا ویرایش می‌شود. سند چندخطی با حساب طرف اصلاح می‌شود.'}
          </p>
          <label>
            تاریخ
            <PersianDateInput value={date} onChange={setDate} />
          </label>
          <label>
            شرح
            <input className="acct-input" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>
            بدهکار
            <input
              className="acct-input acct-input--numeric"
              inputMode="decimal"
              value={debitText}
              onChange={(event) => setDebitText(event.target.value)}
              disabled={formMode === 'reverse'}
            />
          </label>
          <label>
            بستانکار
            <input
              className="acct-input acct-input--numeric"
              inputMode="decimal"
              value={creditText}
              onChange={(event) => setCreditText(event.target.value)}
              disabled={formMode === 'reverse'}
            />
          </label>
          <label>
            جست‌وجوی حساب طرف
            <input className="acct-input" value={contraQuery} onChange={(event) => setContraQuery(event.target.value)} placeholder="کد یا عنوان" />
          </label>
          <label>
            حساب طرف
            <select
              className="acct-input"
              value={contraKey}
              onChange={(event) => setContraKey(event.target.value)}
              required={formMode !== 'edit' || needsContra}
            >
              <option value="">انتخاب کنید</option>
              {contraOptions.map((row) => (
                <option key={contraKeyOf(row)} value={contraKeyOf(row)}>
                  {row.code} — {row.name}
                </option>
              ))}
            </select>
          </label>
          <div className="acct-hmap-record-actions">
            <button type="submit" className="acct-btn acct-btn--sm" disabled={busy}>
              {formMode === 'reverse' ? 'ثبت برگشت' : 'ذخیره'}
            </button>
            <button type="button" className="acct-btn acct-btn--secondary acct-btn--sm" onClick={resetForm} disabled={busy}>
              انصراف
            </button>
          </div>
        </form>
      ) : null}

      {error ? <p className="acct-hmap-record-error">{error}</p> : null}
      {notice ? <p className="acct-hmap-record-note">{notice}</p> : null}
      {loading ? <p className="acct-hmap-empty">در حال خواندن رکوردها…</p> : null}
      {!loading && lines && !lines.length ? <p className="acct-hmap-empty">رکوردی برای این حساب ثبت نشده.</p> : null}

      {!loading && lines?.length ? (
        <>
          <div className="acct-hmap-record acct-hmap-record-head" aria-hidden="true">
            <span>تاریخ</span>
            <span>سند</span>
            <span>شرح</span>
            <span>بدهکار</span>
            <span>بستانکار</span>
            <span>مانده</span>
            <span />
          </div>
          {visible.map((line) => (
            <div key={line.id} className="acct-hmap-record">
              <span data-label="تاریخ">{formatDate(line.entry_date)}</span>
              <span className="acct-number" data-label="سند">{line.document_number || line.document_code || '—'}</span>
              <span className="acct-hmap-record-desc" data-label="شرح">{line.description || '—'}</span>
              <strong data-label="بدهکار" className={line.debit ? 'acct-number acct-debit' : 'acct-number'}>{line.debit ? formatRial(line.debit) : '—'}</strong>
              <strong data-label="بستانکار" className={line.credit ? 'acct-number acct-credit' : 'acct-number'}>{line.credit ? formatRial(line.credit) : '—'}</strong>
              <span className="acct-number" data-label="مانده">
                {formatRial(Math.abs(line.running))} {line.running > 0 ? 'بد' : line.running < 0 ? 'بس' : ''}
              </span>
              <span className="acct-hmap-record-actions">
                <button type="button" className="acct-btn acct-btn--sm" aria-label="ویرایش رکورد" disabled={busy} onClick={() => openEdit(line)}>
                  <Icon name="pencil" size={14} />
                </button>
                <button type="button" className="acct-btn acct-btn--sm" aria-label="حذف رکورد" disabled={busy} onClick={() => removeRecord(line)}>
                  <Icon name="trash" size={14} />
                </button>
              </span>
            </div>
          ))}
          {lines.length > RECORD_PREVIEW && !showAll ? (
            <button type="button" className="acct-btn acct-btn--secondary acct-btn--sm" onClick={() => setShowAll(true)}>
              نمایش {(lines.length - RECORD_PREVIEW).toLocaleString('fa-IR')} رکورد دیگر
            </button>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
