import { useCallback, useEffect, useMemo, useState } from 'react'
import { notificationsApi, salesApi } from '../api/client'
import InvoiceModal from '../components/InvoiceModal'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field } from '../components/ui'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { fromLegacy } from '../styles/tw.js'
import { formatDate, formatMoney } from '../utils/format'
import { isSystemAdmin } from '../utils/permissions'

const EMPTY_COMPOSE = {
  target: '',
  kind: 'ticket',
  title: '',
  body: '',
  grade: 3,
  sale_id: null,
  invoice_number: '',
  customer_name: '',
}

export default function Notifications() {
  useRegisterPageGuide('notifications', PAGE_GUIDE_DEFAULTS.notifications || 'اعلان‌های بخش‌هایی که به آن‌ها دسترسی دارید.')
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  const { ticketGrades } = useConfig()
  const grades = ticketGrades.grades || []
  const defaultGrade = ticketGrades.default_grade || 3
  const [items, setItems] = useState([])
  const [sections, setSections] = useState([])
  const [recipients, setRecipients] = useState([])
  const [departments, setDepartments] = useState([])
  const [section, setSection] = useState('')
  const [box, setBox] = useState('inbox')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [sending, setSending] = useState(false)
  const [compose, setCompose] = useState({ ...EMPTY_COMPOSE, grade: defaultGrade })
  const [invoices, setInvoices] = useState([])
  const [invoiceSearch, setInvoiceSearch] = useState('')
  const [invoiceDate, setInvoiceDate] = useState('')
  const [invoiceLoading, setInvoiceLoading] = useState(false)
  const [threads, setThreads] = useState({})
  const [replyDraft, setReplyDraft] = useState({})
  const [invoiceSale, setInvoiceSale] = useState(null)

  useEffect(() => {
    setCompose((prev) => ({ ...prev, grade: defaultGrade }))
  }, [defaultGrade])

  const loadInvoices = useCallback(async () => {
    setInvoiceLoading(true)
    try {
      const params = new URLSearchParams()
      if (invoiceSearch.trim()) params.set('search', invoiceSearch.trim())
      if (invoiceDate) params.set('date', invoiceDate)
      params.set('limit', '10')
      const data = await notificationsApi.invoices(params.toString())
      setInvoices(data.results || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setInvoiceLoading(false)
    }
  }, [invoiceSearch, invoiceDate])

  useEffect(() => {
    if (compose.kind !== 'ticket') return undefined
    loadInvoices()
    return undefined
  }, [compose.kind, loadInvoices])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (box === 'sent') params.set('box', 'sent')
      else if (box === 'all') params.set('box', 'all')
      else if (section) params.set('section', section)
      const [data, people] = await Promise.all([
        notificationsApi.list(params.toString()),
        notificationsApi.recipients(),
      ])
      setItems(data.results || [])
      setSections(data.sections || [])
      setRecipients(people.results || [])
      setDepartments(people.departments || [])
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [section, box])

  useEffect(() => { load() }, [load])

  const recipientOptions = useMemo(() => {
    const deptOpts = departments.map((item) => ({
      value: `dept:${item.id}`,
      label: item.label,
      hint: 'دپارتمان',
    }))
    const peopleOpts = recipients.map((person) => ({
      value: `user:${person.id}`,
      label: person.full_name,
      hint: person.hint || (person.department_label && person.role_label
        ? `${person.department_label} / ${person.role_label}`
        : person.department_label || ''),
    }))
    return [...deptOpts, ...peopleOpts]
  }, [departments, recipients])

  const markRead = async (item) => {
    if (!item.id || item.box !== 'inbox') return
    setBusyId(item.notification_id || item.id)
    try {
      await notificationsApi.markRead(item.id, !item.is_read ? true : false)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const act = async (item) => {
    setBusyId(item.notification_id || item.id)
    try {
      await notificationsApi.act(item.id)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const toggleTicket = async (item, action) => {
    setBusyId(item.notification_id)
    try {
      const data = await notificationsApi.act(item.notification_id, { action })
      setThreads((prev) => ({ ...prev, [item.notification_id]: data }))
      setInfo(action === 'close' ? 'تیکت بسته شد.' : 'تیکت دوباره باز شد.')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const openThread = async (item) => {
    const noteId = item.notification_id
    if (threads[noteId]?.messages) {
      setThreads((prev) => {
        const next = { ...prev }
        delete next[noteId]
        return next
      })
      return
    }
    setBusyId(noteId)
    try {
      const data = await notificationsApi.get(noteId)
      setThreads((prev) => ({ ...prev, [noteId]: data }))
      setError('')
      if (item.payload?.to_department && data.payload?.claimed_by_id) {
        await load()
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const sendReply = async (item) => {
    const noteId = item.notification_id
    const body = (replyDraft[noteId] || '').trim()
    if (!body) return
    setBusyId(noteId)
    try {
      await notificationsApi.reply(noteId, { body })
      const data = await notificationsApi.get(noteId)
      setThreads((prev) => ({ ...prev, [noteId]: data }))
      setReplyDraft((prev) => ({ ...prev, [noteId]: '' }))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const openInvoice = async (saleId) => {
    if (!saleId) return
    setBusyId(`inv-${saleId}`)
    try {
      const sale = await salesApi.get(saleId)
      setInvoiceSale(sale)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const pickInvoice = (row) => {
    setCompose((prev) => ({
      ...prev,
      sale_id: row.id,
      invoice_number: row.invoice_number,
      customer_name: row.customer_name,
    }))
  }

  const sendMessage = async (event) => {
    event.preventDefault()
    setSending(true)
    try {
      const target = compose.target || ''
      const payload = {
        kind: compose.kind,
        title: compose.title,
        body: compose.body,
        grade: compose.grade,
      }
      if (target.startsWith('dept:')) {
        payload.to_department = target.slice(5)
      } else if (target.startsWith('user:')) {
        payload.to_user_id = Number(target.slice(5))
      }
      if (compose.kind === 'ticket') {
        payload.sale_id = compose.sale_id
      } else if (compose.sale_id) {
        payload.sale_id = compose.sale_id
      }
      const sentKind = compose.kind
      await notificationsApi.send(payload)
      setInfo(sentKind === 'responsibility' ? 'مسئولیت ارسال شد.' : 'تیکت ارسال شد.')
      setCompose({ ...EMPTY_COMPOSE, grade: defaultGrade })
      setError('')
      if (sentKind === 'ticket' && box !== 'sent') {
        setBox('sent')
      } else {
        await load()
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  const boxes = [
    { id: 'inbox', label: 'دریافتی' },
    { id: 'sent', label: 'ارسالی' },
    ...(admin ? [{ id: 'all', label: 'گفتگوها' }] : []),
  ]

  return (
    <div className={fromLegacy('page')}>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-info')}>{info}</div>}

      <Card
        title="اعلان‌ها"
        actions={(
          box === 'inbox' ? (
            <Button type="button" variant="ghost" onClick={() => notificationsApi.readAll().then(load)}>
              همه خوانده شود
            </Button>
          ) : null
        )}
      >
        <div className={fromLegacy('branch-tabs')}>
          {boxes.map((item) => (
            <button
              key={item.id}
              type="button"
              className={fromLegacy(`branch-tab ${box === item.id ? 'active' : ''}`)}
              onClick={() => { setBox(item.id); setSection('') }}
            >
              {item.label}
            </button>
          ))}
        </div>
        {box === 'inbox' && (
          <div className={fromLegacy('branch-tabs')}>
            <button type="button" className={fromLegacy(`branch-tab ${!section ? 'active' : ''}`)} onClick={() => setSection('')}>همه</button>
            {sections.map((item) => (
              <button
                key={item.id}
                type="button"
                className={fromLegacy(`branch-tab ${section === item.id ? 'active' : ''}`)}
                onClick={() => setSection(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
        {loading ? (
          <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
        ) : items.length === 0 ? (
          <EmptyState text="اعلانی نیست." />
        ) : (
          <div className="notification-list">
            {items.map((item) => {
              const ticketColor = item.payload?.color
              const kind = item.payload?.kind
              const kindLabel = kind === 'responsibility' ? 'مسئولیت' : kind === 'ticket' ? 'تیکت' : ''
              const status = item.status || item.payload?.status
              const statusLabel = status === 'closed' || status === 'done' ? 'بسته' : kindLabel ? 'باز' : ''
              const thread = threads[item.notification_id]
              const busy = busyId === item.notification_id || busyId === item.id
              return (
                <article
                  key={`${item.box}-${item.id}-${item.notification_id}`}
                  className={`notification-card${item.is_read ? '' : ' is-unread'}${ticketColor ? ' has-ticket-color' : ''}`}
                  style={ticketColor ? { '--ticket-color': ticketColor } : undefined}
                >
                  <div className="notification-card-head">
                    <strong>{item.title}</strong>
                    <div className="notification-card-badges">
                      {kindLabel && <Badge color={ticketColor || 'var(--accent)'}>{kindLabel}</Badge>}
                      {statusLabel && <Badge color={status === 'closed' || status === 'done' ? '#94a3b8' : 'var(--accent)'}>{statusLabel}</Badge>}
                      <Badge color={item.is_read ? '#94a3b8' : 'var(--accent)'}>{item.section_label}</Badge>
                    </div>
                  </div>
                  {(item.parties || item.created_by) && (
                    <p className={fromLegacy('muted small')}>
                      {item.parties || `از طرف ${item.created_by}`}
                    </p>
                  )}
                  {(item.invoice_number || item.sale_id) && (
                    <p className={fromLegacy('muted small')}>
                      <button
                        type="button"
                        className={fromLegacy('link')}
                        onClick={() => openInvoice(item.sale_id)}
                        disabled={busyId === `inv-${item.sale_id}`}
                      >
                        فاکتور {item.invoice_number || item.sale_id}
                      </button>
                      {item.customer_name ? ` — ${item.customer_name}` : ''}
                    </p>
                  )}
                  {item.body && <p className={fromLegacy('muted')}>{item.body}</p>}
                  <div className="notification-card-actions">
                    {item.box === 'inbox' && (
                      <button type="button" className={fromLegacy('link')} disabled={busy} onClick={() => markRead(item)}>
                        {item.is_read ? 'نخوانده' : 'خوانده شد'}
                      </button>
                    )}
                    {item.action_type === 'approve_branch_switch' && !item.resolved && (
                      <Button type="button" disabled={busy} onClick={() => act(item)}>
                        تایید تغییر شعبه
                      </Button>
                    )}
                    {item.action_type === 'org_responsibility' && !item.resolved && item.box === 'inbox' && (
                      <Button type="button" disabled={busy} onClick={() => act(item)}>
                        انجام شد
                      </Button>
                    )}
                    {item.action_type === 'org_ticket' && (
                      <button type="button" className={fromLegacy('link')} disabled={busy} onClick={() => openThread(item)}>
                        {thread?.messages ? 'بستن گفتگو' : 'گفتگو'}
                      </button>
                    )}
                    {item.action_type === 'org_ticket' && (thread?.can_close ?? item.can_close) && (
                      <Button type="button" disabled={busy} onClick={() => toggleTicket(item, 'close')}>
                        بستن تیکت
                      </Button>
                    )}
                    {item.action_type === 'org_ticket' && (thread?.can_reopen ?? item.can_reopen) && (
                      <Button type="button" variant="ghost" disabled={busy} onClick={() => toggleTicket(item, 'reopen')}>
                        باز کردن
                      </Button>
                    )}
                    {item.resolved && item.action_type === 'org_responsibility' && (
                      <span className={fromLegacy('muted small')}>انجام شد</span>
                    )}
                  </div>
                  {thread?.messages && (
                    <div className="ticket-thread">
                      {thread.messages.map((message, index) => (
                        <div key={message.id || `initial-${index}`} className="ticket-message">
                          <strong>{message.author_name}</strong>
                          <span className={fromLegacy('muted small')}>{formatDate(message.created_at)}</span>
                          <p>{message.body}</p>
                        </div>
                      ))}
                      {thread.can_reply && (
                        <div className="ticket-reply">
                          <textarea
                            rows={2}
                            value={replyDraft[item.notification_id] || ''}
                            onChange={(e) => setReplyDraft((prev) => ({ ...prev, [item.notification_id]: e.target.value }))}
                            placeholder="پاسخ…"
                          />
                          <Button type="button" disabled={busy} onClick={() => sendReply(item)}>ارسال پاسخ</Button>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </Card>

      <Card title="ارسال تیکت یا مسئولیت">
        <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
          تیکت باید به فاکتور وصل شود. گیرنده می‌تواند یک نفر یا یک دپارتمان باشد؛ اولین بازکننده تیکت دپارتمانی مالک گفتگو می‌شود.
        </p>
        <form className={fromLegacy('form')} onSubmit={sendMessage}>
          <Field label="گیرنده">
            <Select
              value={compose.target}
              onChange={(value) => setCompose({ ...compose, target: value })}
              placeholder="فرد یا دپارتمان"
              required
              options={recipientOptions}
            />
          </Field>
          <Field label="نوع">
            <div className="org-kind-toggle">
              <label>
                <input
                  type="radio"
                  name="note-kind"
                  checked={compose.kind === 'ticket'}
                  onChange={() => setCompose({ ...compose, kind: 'ticket' })}
                />
                تیکت
              </label>
              <label>
                <input
                  type="radio"
                  name="note-kind"
                  checked={compose.kind === 'responsibility'}
                  onChange={() => setCompose({ ...compose, kind: 'responsibility' })}
                />
                مسئولیت
              </label>
            </div>
          </Field>
          {compose.kind === 'ticket' && (
            <Field label="فاکتور">
              {compose.sale_id ? (
                <div className="invoice-picker-selected">
                  <span>
                    {compose.invoice_number}
                    {compose.customer_name ? ` — ${compose.customer_name}` : ''}
                  </span>
                  <button
                    type="button"
                    className={fromLegacy('link')}
                    onClick={() => setCompose({ ...compose, sale_id: null, invoice_number: '', customer_name: '' })}
                  >
                    تغییر
                  </button>
                </div>
              ) : (
                <div className="invoice-picker">
                  <div className="invoice-picker-filters">
                    <input
                      value={invoiceSearch}
                      onChange={(e) => setInvoiceSearch(e.target.value)}
                      placeholder="شماره فاکتور"
                    />
                    <PersianDateInput
                      value={invoiceDate}
                      onChange={setInvoiceDate}
                      onClear={() => setInvoiceDate('')}
                      placeholder="تاریخ"
                    />
                  </div>
                  {invoiceLoading ? (
                    <p className={fromLegacy('muted small')}>در حال جستجو…</p>
                  ) : invoices.length === 0 ? (
                    <p className={fromLegacy('muted small')}>فاکتوری در دسترس نیست.</p>
                  ) : (
                    <div className="invoice-picker-list">
                      {invoices.map((row) => (
                        <button
                          key={row.id}
                          type="button"
                          className="invoice-picker-item"
                          onClick={() => pickInvoice(row)}
                        >
                          <strong>{row.invoice_number}</strong>
                          <span>{row.customer_name}</span>
                          <span className={fromLegacy('muted small')}>{formatDate(row.sold_at)} — {formatMoney(row.amount)}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Field>
          )}
          <Field label="عنوان">
            <input
              value={compose.title}
              onChange={(e) => setCompose({ ...compose, title: e.target.value })}
              required
              maxLength={160}
            />
          </Field>
          <Field label="متن">
            <textarea
              rows={3}
              value={compose.body}
              onChange={(e) => setCompose({ ...compose, body: e.target.value })}
            />
          </Field>
          <Field label="رنگ">
            <div className="ticket-grade-swatches">
              {grades.map((item) => (
                <button
                  key={item.grade}
                  type="button"
                  className={`ticket-grade-swatch${compose.grade === item.grade ? ' is-selected' : ''}`}
                  style={{ background: item.color }}
                  title={item.label}
                  aria-label={item.label}
                  onClick={() => setCompose({ ...compose, grade: item.grade })}
                />
              ))}
            </div>
          </Field>
          <Button type="submit" disabled={sending || (compose.kind === 'ticket' && !compose.sale_id)}>
            {sending ? 'در حال ارسال…' : 'ارسال'}
          </Button>
        </form>
      </Card>

      <InvoiceModal
        sale={invoiceSale}
        open={Boolean(invoiceSale)}
        onClose={() => setInvoiceSale(null)}
      />
    </div>
  )
}
