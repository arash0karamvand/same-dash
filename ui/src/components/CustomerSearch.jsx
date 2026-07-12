import { useEffect, useState } from 'react'
import { customersApi } from '../api/client'
import PersianDateInput from './PersianDateInput'
import { Button, Field } from './ui'
import { formatMoney } from '../utils/format'
import { formatJalali } from '../utils/jalali'

export default function CustomerSearch({ value, onSelect, onCreateNew }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [newPhone, setNewPhone] = useState('')
  const [newAddress, setNewAddress] = useState('')
  const [newBirthday, setNewBirthday] = useState('')

  useEffect(() => {
    if (!value) {
      setQuery('')
      setSelected(null)
      setNewPhone('')
      setNewAddress('')
      setNewBirthday('')
    } else if (value.id) {
      setQuery(value.full_name || '')
      setSelected(value)
    }
  }, [value])

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const data = await customersApi.list(query.trim())
        setResults(data.results.slice(0, 10))
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query])

  const pick = (c) => {
    setSelected(c)
    onSelect(c)
    setQuery(c.full_name)
    setResults([])
    setNewPhone('')
    setNewAddress('')
    setNewBirthday('')
  }

  const addNew = () => {
    const name = query.trim()
    const phone = newPhone.trim()
    const address = newAddress.trim()
    if (!name || !phone || !address) return
    const customer = {
      full_name: name,
      phone,
      address,
      birthday: newBirthday || '',
      id: null,
    }
    onCreateNew(customer)
    setSelected(customer)
  }

  const active = value?.id ? value : selected

  return (
    <div className="customer-search">
      <Field label="مشتری">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelected(null)
            onSelect(null)
          }}
          placeholder="جستجوی نام یا موبایل…"
          autoComplete="off"
        />
      </Field>
      {loading && <p className="muted">در حال جستجو…</p>}
      {results.length > 0 && (
        <ul className="search-dropdown">
          {results.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => pick(c)}>
                {c.full_name} <span className="ltr muted">{c.phone}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {active?.id && (
        <div className="customer-selected-info">
          <p className="muted">
            <strong>{active.full_name}</strong>
          </p>
          <Field label="شماره تماس">
            <input className="ltr" value={active.phone || ''} readOnly disabled />
          </Field>
          <Field label="آدرس">
            <textarea value={active.address || ''} readOnly disabled rows={2} />
          </Field>
          {active.birthday && (
            <Field label="تاریخ تولد">
              <input value={formatJalali(active.birthday.slice(0, 10))} readOnly disabled />
            </Field>
          )}
          {active.wallet_balance > 0 && (
            <p className="muted small">موجودی کیف پول: {formatMoney(active.wallet_balance)}</p>
          )}
        </div>
      )}
      {query.trim() && !loading && results.length === 0 && !active?.id && (
        <div className="customer-new-inline">
          <Field label="شماره تماس">
            <input
              className="ltr"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              placeholder="09xxxxxxxxx"
              required
            />
          </Field>
          <Field label="آدرس">
            <textarea
              value={newAddress}
              onChange={(e) => setNewAddress(e.target.value)}
              placeholder="آدرس کامل مشتری"
              rows={2}
              required
            />
          </Field>
          <Field label="تاریخ تولد">
            <PersianDateInput
              value={newBirthday}
              onChange={setNewBirthday}
            />
            <span className="muted">اختیاری</span>
          </Field>
          <Button
            type="button"
            variant="ghost"
            onClick={addNew}
            disabled={!newPhone.trim() || !newAddress.trim()}
          >
            + ثبت مشتری جدید: «{query.trim()}»
          </Button>
        </div>
      )}
      {active && !active.id && (
        <div className="customer-selected-info">
          <p className="muted small">مشتری جدید (ثبت هنگام فروش)</p>
          <Field label="نام">
            <input value={active.full_name} readOnly disabled />
          </Field>
          <Field label="شماره تماس">
            <input className="ltr" value={active.phone} readOnly disabled />
          </Field>
          <Field label="آدرس">
            <textarea value={active.address || ''} readOnly disabled rows={2} />
          </Field>
          {active.birthday && (
            <Field label="تاریخ تولد">
              <input value={formatJalali(active.birthday.slice(0, 10))} readOnly disabled />
            </Field>
          )}
        </div>
      )}
    </div>
  )
}
