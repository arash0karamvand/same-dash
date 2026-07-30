import { useEffect, useRef, useState } from 'react'
import { customersApi } from '../api/client'
import PersianDateInput from './PersianDateInput'
import JcalPanel from './JcalPanel'
import { Button, Field } from './ui'
import { formatMoney } from '../utils/format'
import { formatJalali } from '../utils/jalali'

export default function CustomerSearch({ value, onSelect, onCreateNew }) {
  const anchorRef = useRef(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [newPhone, setNewPhone] = useState('')
  const [newAddress, setNewAddress] = useState('')
  const [newBirthday, setNewBirthday] = useState('')
  const [newName, setNewName] = useState('')
  const [registerOpen, setRegisterOpen] = useState(false)

  useEffect(() => {
    if (!value) {
      setQuery('')
      setSelected(null)
      setNewPhone('')
      setNewAddress('')
      setNewBirthday('')
      setNewName('')
      setRegisterOpen(false)
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
    setRegisterOpen(false)
  }

  const openRegister = () => {
    setNewName(query.trim())
    setRegisterOpen(true)
    setResults([])
  }

  const addNew = () => {
    const name = newName.trim()
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
    setRegisterOpen(false)
  }

  const active = value?.id ? value : selected
  const [dropdownOpen, setDropdownOpen] = useState(false)

  useEffect(() => {
    if (results.length > 0 && !registerOpen) {
      setDropdownOpen(true)
    } else {
      setDropdownOpen(false)
    }
  }, [results, registerOpen])

  return (
    <div className="customer-search">
      <Field label="مشتری">
        <div className="customer-search-anchor" ref={anchorRef}>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelected(null)
              onSelect(null)
              setRegisterOpen(false)
            }}
            onFocus={() => {
              if (results.length > 0 && !registerOpen) setDropdownOpen(true)
            }}
            placeholder="جستجوی نام یا موبایل…"
            autoComplete="off"
          />
        </div>
      </Field>
      {loading && <p className="muted">در حال جستجو…</p>}
      <JcalPanel
        open={dropdownOpen}
        onClose={() => setDropdownOpen(false)}
        anchorRef={anchorRef}
        variant="menu"
        ariaLabel="نتایج جستجوی مشتری"
      >
        <ul className="search-dropdown">
          {results.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => pick(c)}>
                {c.full_name} <span className="ltr muted">{c.phone}</span>
              </button>
            </li>
          ))}
          <li className="search-dropdown-divider" aria-hidden />
          <li>
            <button type="button" className="search-dropdown-new" onClick={openRegister}>
              + ثبت مشتری جدید
            </button>
          </li>
        </ul>
      </JcalPanel>
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
      {query.trim() && !loading && results.length === 0 && !active?.id && !registerOpen && (
        <div className="customer-new-inline">
          <p className="muted small">مشتری با این مشخصات یافت نشد.</p>
          <Button type="button" variant="ghost" onClick={openRegister}>
            + ثبت مشتری جدید
          </Button>
        </div>
      )}
      {registerOpen && !active?.id && (
        <div className="customer-new-inline">
          <p className="muted small">ثبت مشتری جدید (همراه با ثبت فروش)</p>
          <Field label="نام">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="نام و نام خانوادگی"
              required
            />
          </Field>
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
          <div className="customer-new-inline-actions">
            <Button
              type="button"
              onClick={addNew}
              disabled={!newName.trim() || !newPhone.trim() || !newAddress.trim()}
            >
              تأیید مشتری
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setRegisterOpen(false)
                setNewPhone('')
                setNewAddress('')
                setNewBirthday('')
              }}
            >
              انصراف
            </Button>
          </div>
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
