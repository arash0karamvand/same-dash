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
import { todayIso } from '../utils/jalali'

const EMPTY_COMPOSE = {
  target: '',
  kind: 'ticket',
  title: '',
  body: '',
  grade: 3,
  sale_id: null,
  invoice_number: '',
  customer_name: '',
  leave_pay_type: 'paid',
  leave_duration: 'days',
  start_date: todayIso(),
  end_date: todayIso(),
  hours: '',
  mission_dest_kind: 'branch',
  mission_dest_code: '',
  mission_dest_label: '',
}

const MISSION_DEST_OPTIONS = [
  { value: 'branch', label: 'شعبه' },
  { value: 'warehouse', label: 'انبار' },
  { value: 'factory', label: 'کارخانه' },
  { value: 'outside', label: 'خارج از شرکت' },
]

function kindBadgeLabel(kind) {
  if (kind === 'responsibility') return 'مسئولیت'
  if (kind === 'ticket') return 'تیکت'
  if (kind === 'leave') return 'مرخصی'
  if (kind === 'mission') return 'ماموریت'
  return ''
}

function dispatchSummary(payload) {
  if (!payload) return ''
  if (payload.kind === 'leave') {
    const pay = payload.pay_type === 'unpaid' ? 'بدون حقوق' : 'با حقوق'
    if (payload.duration_unit === 'hours') {
      return `${pay} — ${payload.hours} ساعت`
    }
    if (payload.start_date && payload.end_date && payload.start_date !== payload.end_date) {
      return `${pay} — از ${formatDate(payload.start_date)} تا ${formatDate(payload.end_date)}`
    }
    return `${pay} — ${formatDate(payload.start_date || payload.end_date)}`
  }
  if (payload.kind === 'mission') {
    const dest = payload.dest_label || ''
    const when = payload.start_date && payload.end_date && payload.start_date !== payload.end_date
      ? ` از ${formatDate(payload.start_date)} تا ${formatDate(payload.end_date)}`
      : payload.start_date ? ` — ${formatDate(payload.start_date)}` : ''
    if (payload.dest_kind === 'outside') return `خارج از شرکت${dest ? ` — ${dest}` : ''}${when}`
    if (payload.dest_kind === 'factory') return `کارخانه${when}`
    if (payload.dest_kind === 'warehouse') return `انبار ${dest}${when}`
    if (payload.dest_kind === 'branch') return `شعبه ${dest}${when}`
    return `${dest}${when}`.trim()
  }
  return ''
}

export default function Notifications() {
  useRegisterPageGuide('notifications', PAGE_GUIDE_DEFAULTS.notifications || 'اعلان‌های بخش‌هایی که به آن‌ها دسترسی دارید.')
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  const { ticketGrades, branchOptions, stockLocations, attendanceSettings } = useConfig()
  const grades = ticketGrades.grades || []
  const defaultGrade = ticketGrades.default_grade || 3
  const [items, setItems] = useState([])
  const [sections, setSections] = useState([])
  const [recipients, setRecipients] = useState([])
  const [departments, setDepartments] = useState([])
  const [canSendLeaveMission, setCanSendLeaveMission] = useState(false)
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
  const [earlyShipDraft, setEarlyShipDraft] = useState({})
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
      setCanSendLeaveMission(Boolean(people.can_send_leave_mission))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [section, box])

  useEffect(() => { load() }, [load])

  const recipientOptions = useMemo(() => {
    const peopleOpts = recipients.map((person) => ({
      value: `user:${person.id}`,
      label: person.full_name,
      hint: person.hint || (person.department_label && person.role_label
        ? `${person.department_label} / ${person.role_label}`
        : person.department_label || ''),
    }))
    if (compose.kind === 'leave' || compose.kind === 'mission') {
      return peopleOpts
    }
    const deptOpts = departments.map((item) => ({
      value: `dept:${item.id}`,
      label: item.label,
      hint: 'دپارتمان',
    }))
    return [...deptOpts, ...peopleOpts]
  }, [departments, recipients, compose.kind])

  const warehouseOptions = useMemo(
    () => (stockLocations || [])
      .filter((item) => item.kind === 'warehouse')
      .map((item) => ({
        value: String(item.warehouse_id),
        label: item.label,
      })),
    [stockLocations],
  )

  const workDayHours = attendanceSettings?.work_day_hours

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

  const saveEarlyShipDate = async (item) => {
    const noteId = item.notification_id
    const allowedDate = earlyShipDraft[noteId] || item.payload?.early_ship_allowed_date || todayIso()
    setBusyId(noteId)
    try {
      const data = await notificationsApi.act(noteId, {
        action: 'set_early_ship_date',
        allowed_date: allowedDate,
      })
      setThreads((prev) => ({ ...prev, [noteId]: data }))
      setInfo('تاریخ مجاز ارسال ثبت شد.')
      await load()
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
      if (compose.kind === 'leave' || compose.kind === 'mission') {
        payload.start_date = compose.start_date
        payload.end_date = compose.kind === 'leave' && compose.leave_duration === 'hours'
          ? compose.start_date
          : compose.end_date
        if (compose.kind === 'leave') {
          payload.pay_type = compose.leave_pay_type
          payload.duration_unit = compose.leave_duration
          if (compose.leave_duration === 'hours') payload.hours = Number(compose.hours)
        } else {
          payload.dest_kind = compose.mission_dest_kind
          payload.dest_code = compose.mission_dest_code
          payload.dest_label = compose.mission_dest_label
        }
      } else if (compose.kind === 'ticket') {
        payload.sale_id = compose.sale_id
      } else if (compose.sale_id) {
        payload.sale_id = compose.sale_id
      }
      const sentKind = compose.kind
      await notificationsApi.send(payload)
      const infoByKind = {
        responsibility: 'مسئولیت ارسال شد.',
        ticket: 'تیکت ارسال شد.',
        leave: 'مرخصی ثبت و ارسال شد.',
        mission: 'ماموریت ثبت و ارسال شد.',
      }
      setInfo(infoByKind[sentKind] || 'ارسال شد.')
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
              const kindLabel = kindBadgeLabel(kind)
              const summary = dispatchSummary(item.payload)
              const status = item.status || item.payload?.status
              const statusLabel = status === 'closed' || status === 'done' ? 'بسته' : kindLabel && (kind === 'ticket' || kind === 'responsibility') ? 'باز' : ''
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
                  {summary && <p className={fromLegacy('muted small')}>{summary}</p>}
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
                      {thread.can_set_early_ship_date && (
                        <div className="ticket-reply">
                          <Field label="تاریخ مجاز ارسال زودتر از موعد">
                            <PersianDateInput
                              value={earlyShipDraft[item.notification_id] || thread.payload?.early_ship_allowed_date || ''}
                              onChange={(value) => setEarlyShipDraft((prev) => ({ ...prev, [item.notification_id]: value }))}
                              placeholder="انتخاب تاریخ"
                            />
                          </Field>
                          <Button type="button" disabled={busy} onClick={() => saveEarlyShipDate(item)}>
                            ثبت تاریخ ارسال
                          </Button>
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

      <Card title={canSendLeaveMission ? 'ارسال اعلان' : 'ارسال تیکت یا مسئولیت'}>
        <p className={fromLegacy('muted small')} style={{ marginBottom: 12 }}>
          {canSendLeaveMission
            ? 'تیکت باید به فاکتور وصل شود. مرخصی و ماموریت فقط به یک نفر ارسال می‌شود و همان لحظه در حضور ثبت می‌گردد.'
            : 'تیکت باید به فاکتور وصل شود. گیرنده می‌تواند یک نفر یا یک دپارتمان باشد؛ اولین بازکننده تیکت دپارتمانی مالک گفتگو می‌شود.'}
        </p>
        <form className={fromLegacy('form')} onSubmit={sendMessage}>
          <Field label="گیرنده">
            <Select
              value={compose.target}
              onChange={(value) => setCompose({ ...compose, target: value })}
              placeholder={compose.kind === 'leave' || compose.kind === 'mission' ? 'فرد' : 'فرد یا دپارتمان'}
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
              {canSendLeaveMission && (
                <>
                  <label>
                    <input
                      type="radio"
                      name="note-kind"
                      checked={compose.kind === 'leave'}
                      onChange={() => setCompose({
                        ...compose,
                        kind: 'leave',
                        target: compose.target.startsWith('dept:') ? '' : compose.target,
                        sale_id: null,
                        invoice_number: '',
                        customer_name: '',
                      })}
                    />
                    مرخصی
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="note-kind"
                      checked={compose.kind === 'mission'}
                      onChange={() => setCompose({
                        ...compose,
                        kind: 'mission',
                        target: compose.target.startsWith('dept:') ? '' : compose.target,
                        sale_id: null,
                        invoice_number: '',
                        customer_name: '',
                      })}
                    />
                    ماموریت
                  </label>
                </>
              )}
            </div>
          </Field>
          {compose.kind === 'leave' && (
            <>
              <Field label="نوع مرخصی">
                <div className="org-kind-toggle">
                  <label>
                    <input
                      type="radio"
                      name="leave-pay"
                      checked={compose.leave_pay_type === 'paid'}
                      onChange={() => setCompose({ ...compose, leave_pay_type: 'paid' })}
                    />
                    با حقوق
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="leave-pay"
                      checked={compose.leave_pay_type === 'unpaid'}
                      onChange={() => setCompose({ ...compose, leave_pay_type: 'unpaid' })}
                    />
                    بدون حقوق
                  </label>
                </div>
              </Field>
              <Field label="مدت">
                <div className="org-kind-toggle">
                  <label>
                    <input
                      type="radio"
                      name="leave-duration"
                      checked={compose.leave_duration === 'days'}
                      onChange={() => setCompose({ ...compose, leave_duration: 'days' })}
                    />
                    روزانه
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="leave-duration"
                      checked={compose.leave_duration === 'hours'}
                      onChange={() => setCompose({ ...compose, leave_duration: 'hours' })}
                    />
                    ساعتی
                  </label>
                </div>
              </Field>
              {compose.leave_duration === 'hours' ? (
                <>
                  <Field label="تاریخ">
                    <PersianDateInput
                      value={compose.start_date}
                      onChange={(value) => setCompose({ ...compose, start_date: value })}
                      required
                    />
                  </Field>
                  <Field label={workDayHours ? `ساعت (حداکثر ${workDayHours})` : 'ساعت'}>
                    <input
                      className={fromLegacy('ltr')}
                      type="number"
                      min="0.5"
                      step="0.5"
                      max={workDayHours || undefined}
                      value={compose.hours}
                      onChange={(e) => setCompose({ ...compose, hours: e.target.value })}
                      required
                    />
                  </Field>
                  {!workDayHours && (
                    <p className={fromLegacy('muted small')}>
                      برای مرخصی ساعتی ابتدا ساعت کاری سراسری را در تنظیمات سایت تعیین کنید.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <Field label="از تاریخ">
                    <PersianDateInput
                      value={compose.start_date}
                      onChange={(value) => setCompose({ ...compose, start_date: value })}
                      required
                    />
                  </Field>
                  <Field label="تا تاریخ">
                    <PersianDateInput
                      value={compose.end_date}
                      onChange={(value) => setCompose({ ...compose, end_date: value })}
                      required
                    />
                  </Field>
                </>
              )}
            </>
          )}
          {compose.kind === 'mission' && (
            <>
              <Field label="مقصد">
                <Select
                  value={compose.mission_dest_kind}
                  onChange={(value) => setCompose({
                    ...compose,
                    mission_dest_kind: value,
                    mission_dest_code: '',
                    mission_dest_label: value === 'factory' ? 'کارخانه' : '',
                  })}
                  options={MISSION_DEST_OPTIONS}
                />
              </Field>
              {compose.mission_dest_kind === 'branch' && (
                <Field label="شعبه">
                  <Select
                    value={compose.mission_dest_code}
                    onChange={(value) => setCompose({ ...compose, mission_dest_code: value })}
                    options={branchOptions}
                    placeholder="انتخاب شعبه"
                    required
                  />
                </Field>
              )}
              {compose.mission_dest_kind === 'warehouse' && (
                <Field label="انبار">
                  <Select
                    value={compose.mission_dest_code}
                    onChange={(value) => setCompose({ ...compose, mission_dest_code: value })}
                    options={warehouseOptions}
                    placeholder="انتخاب انبار"
                    required
                  />
                </Field>
              )}
              {compose.mission_dest_kind === 'outside' && (
                <Field label="محل">
                  <input
                    value={compose.mission_dest_label}
                    onChange={(e) => setCompose({ ...compose, mission_dest_label: e.target.value })}
                    required
                    maxLength={160}
                    placeholder="مثلاً دفتر مشتری"
                  />
                </Field>
              )}
              <Field label="از تاریخ">
                <PersianDateInput
                  value={compose.start_date}
                  onChange={(value) => setCompose({ ...compose, start_date: value })}
                  required
                />
              </Field>
              <Field label="تا تاریخ">
                <PersianDateInput
                  value={compose.end_date}
                  onChange={(value) => setCompose({ ...compose, end_date: value })}
                  required
                />
              </Field>
            </>
          )}
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
          <Field label={compose.kind === 'leave' || compose.kind === 'mission' ? 'عنوان (اختیاری)' : 'عنوان'}>
            <input
              value={compose.title}
              onChange={(e) => setCompose({ ...compose, title: e.target.value })}
              required={compose.kind !== 'leave' && compose.kind !== 'mission'}
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
          {(compose.kind === 'ticket' || compose.kind === 'responsibility') && (
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
          )}
          <Button
            type="submit"
            disabled={
              sending
              || (compose.kind === 'ticket' && !compose.sale_id)
              || ((compose.kind === 'leave' || compose.kind === 'mission') && !compose.target.startsWith('user:'))
              || (compose.kind === 'leave' && compose.leave_duration === 'hours' && !workDayHours)
            }
          >
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
