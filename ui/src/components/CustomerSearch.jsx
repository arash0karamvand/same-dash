import { useEffect, useState } from 'react'
import { customersApi } from '../api/client'
import { Button, Field } from './ui'
import { formatMoney } from '../utils/format'

export default function CustomerSearch({ value, onSelect, onCreateNew }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)

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
  }

  const addNew = () => {
    const name = query.trim()
    if (!name) return
    onCreateNew({ full_name: name, phone: '', email: '' })
    setSelected({ full_name: name, id: null })
  }

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
      {query.trim() && !loading && results.length === 0 && !selected && (
        <Button type="button" variant="ghost" onClick={addNew}>
          + ثبت مشتری جدید: «{query.trim()}»
        </Button>
      )}
      {value?.full_name && (
        <p className="muted">
          انتخاب: {value.full_name}
          {value.wallet_balance > 0 && (
            <span> — موجودی: {formatMoney(value.wallet_balance)}</span>
          )}
        </p>
      )}
    </div>
  )
}
