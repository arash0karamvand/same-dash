// صفحه پیامک: ارسال دستی، تبریک تولد خودکار، تاریخچه

import { useCallback, useEffect, useState } from 'react'
import { customersApi, levelsApi, smsApi } from '../api/client'
import ReminderCampaigns from '../components/ReminderCampaigns'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate } from '../utils/format'
import { CURRENCY_UNIT, PERCENT_UNIT } from '../config/money'
import { formatJalali, toPersianDigits } from '../utils/jalali'
import { hasPermission } from '../utils/permissions'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useRegisterPageGuide } from '../context/PageGuideContext'

const STATUS_COLORS = {
  sent: '#10b981',
  pending: '#f59e0b',
  failed: '#ef4444',
  mock_sent: '#6366f1',
  pending_provider_config: '#94a3b8',
  birthday: '#ec4899',
  order_placed: '#3b82f6',
  discount: '#f97316',
  welcome: '#8b5cf6',
  level_up: '#14b8a6',
}

function formatTimeFa(hhmm) {
  if (!hhmm) return '—'
  const [h, m] = hhmm.split(':')
  return `${toPersianDigits(h)}:${toPersianDigits(m)}`
}

export default function Sms() {
  useRegisterPageGuide('sms', PAGE_GUIDE_DEFAULTS.sms)
  const { user } = useAuth()
  const confirm = useConfirm()
  const canSend = hasPermission(user, 'send_sms')
  const canViewLogs = hasPermission(user, 'view_sms_logs')
  const canManageBirthday = hasPermission(user, 'manage_birthday_sms')
  const canManageReminders = hasPermission(user, 'manage_reminders')
  const canManageClub = hasPermission(user, 'manage_sms_club')
  const [tab, setTab] = useState(canManageClub ? 'club' : canManageBirthday ? 'birthday' : 'logs')

  const [messages, setMessages] = useState([])
  const [customers, setCustomers] = useState([])
  const [levels, setLevels] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState({ target: 'single', customer_id: '', level_id: '', message: '' })

  const [birthdaySettings, setBirthdaySettings] = useState(null)
  const [preview, setPreview] = useState(null)
  const [birthdaySaving, setBirthdaySaving] = useState(false)
  const [settingsForm, setSettingsForm] = useState({
    is_enabled: false,
    message_template: '',
    shop_name: '',
    send_time: '10:00',
  })

  const [clubSettings, setClubSettings] = useState(null)
  const [clubForm, setClubForm] = useState({
    shop_name: '',
    auto_order_placed: true,
    auto_welcome: true,
    auto_level_up: true,
    order_placed_template: '',
    welcome_template: '',
    level_up_template: '',
    discount_template: '',
    default_discount_type: 'amount',
    default_discount_value: 0,
  })
  const [clubSaving, setClubSaving] = useState(false)
  const [discountForm, setDiscountForm] = useState({
    target: 'single',
    customer_id: '',
    level_id: '',
    discount_type: 'amount',
    discount_value: '',
    message_template: '',
  })
  const [discountPreview, setDiscountPreview] = useState('')
  const [discountSending, setDiscountSending] = useState(false)

  const loadLogs = async () => {
    try {
      const msgData = await smsApi.list()
      setMessages(msgData.results)
    } catch (e) {
      setError(e.message)
    }
  }

  const loadBirthday = useCallback(async (auto = true) => {
    if (!canManageBirthday) return
    try {
      const [settings, prev] = await Promise.all([
        smsApi.birthdaySettings(),
        smsApi.birthdayPreview(auto),
      ])
      setBirthdaySettings(settings)
      setSettingsForm({
        is_enabled: settings.is_enabled,
        message_template: settings.message_template,
        shop_name: settings.shop_name,
        send_time: settings.send_time,
      })
      setPreview(prev)
      if (prev.auto_result?.successful) {
        setInfo(`ارسال خودکار تبریک تولد: ${prev.auto_result.successful} پیامک`)
        loadLogs()
      }
    } catch (e) {
      setError(e.message)
    }
  }, [canManageBirthday])

  const loadClub = useCallback(async () => {
    if (!canManageClub) return
    try {
      const settings = await smsApi.clubSettings()
      setClubSettings(settings)
      setClubForm({
        shop_name: settings.shop_name,
        auto_order_placed: settings.auto_order_placed,
        auto_welcome: settings.auto_welcome,
        auto_level_up: settings.auto_level_up,
        order_placed_template: settings.order_placed_template,
        welcome_template: settings.welcome_template,
        level_up_template: settings.level_up_template,
        discount_template: settings.discount_template,
        default_discount_type: settings.default_discount_type,
        default_discount_value: settings.default_discount_value,
      })
      setDiscountForm((prev) => ({
        ...prev,
        discount_type: settings.default_discount_type,
        discount_value: String(settings.default_discount_value || ''),
        message_template: settings.discount_template,
      }))
    } catch (e) {
      setError(e.message)
    }
  }, [canManageClub])

  const load = async () => {
    setLoading(true)
    try {
      const tasks = []
      if (canViewLogs) tasks.push(loadLogs())
      if (canSend) {
        tasks.push(
          customersApi.list().then((d) => setCustomers(d.results)),
          levelsApi.list().then((d) => setLevels(d.results)),
        )
      }
      if (canManageBirthday) tasks.push(loadBirthday(true))
      if (canManageClub) tasks.push(loadClub())
      await Promise.all(tasks)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [canSend])

  useEffect(() => {
    if (!canManageBirthday || tab !== 'birthday' || !settingsForm.is_enabled) return
    const timer = setInterval(() => loadBirthday(true), 60000)
    return () => clearInterval(timer)
  }, [canManageBirthday, tab, settingsForm.is_enabled, loadBirthday])

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const send = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')
    try {
      let result
      if (form.target === 'single') {
        result = await smsApi.send({ message: form.message, customer_id: form.customer_id })
      } else if (form.target === 'level') {
        result = await smsApi.sendToLevel({ message: form.message, level_id: form.level_id })
      } else {
        result = await smsApi.sendToAll({ message: form.message })
      }
      setInfo(`نتیجه: ${result.successful} موفق، ${result.failed} ناموفق، ${result.skipped} ردشده`)
      setModalOpen(false)
      setForm({ target: 'single', customer_id: '', level_id: '', message: '' })
      loadLogs()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveBirthdaySettings = async (e) => {
    e.preventDefault()
    setBirthdaySaving(true)
    setError('')
    try {
      await smsApi.updateBirthdaySettings(settingsForm)
      setInfo('تنظیمات تبریک تولد ذخیره شد.')
      await loadBirthday(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setBirthdaySaving(false)
    }
  }

  const excludeFromBirthday = async (customerId) => {
    try {
      await smsApi.birthdayExclude(customerId)
      await loadBirthday(false)
    } catch (e) {
      setError(e.message)
    }
  }

  const restoreToBirthday = async (customerId) => {
    try {
      await smsApi.birthdayUnexclude(customerId)
      await loadBirthday(false)
    } catch (e) {
      setError(e.message)
    }
  }

  const sendBirthdayNow = async () => {
    if (!await confirm({
      title: 'ارسال پیامک تولد',
      message: 'پیامک تبریک تولد برای مشتریان واجد شرایط همین الان ارسال شود؟',
      confirmText: 'بله، ارسال شود',
      variant: 'warning',
    })) return
    try {
      const result = await smsApi.birthdaySend(true)
      setInfo(`ارسال تولد: ${result.successful} موفق، ${result.failed} ناموفق`)
      await loadBirthday(false)
      loadLogs()
    } catch (e) {
      setError(e.message)
    }
  }

  const insertVar = (v) => {
    setSettingsForm((prev) => ({
      ...prev,
      message_template: `${prev.message_template}{${v}}`,
    }))
  }

  const insertClubVar = (field, v) => {
    setClubForm((prev) => ({
      ...prev,
      [field]: `${prev[field]}{${v}}`,
    }))
  }

  const saveClubSettings = async (e) => {
    e.preventDefault()
    setClubSaving(true)
    setError('')
    try {
      await smsApi.updateClubSettings(clubForm)
      setInfo('تنظیمات باشگاه مشتریان ذخیره شد.')
      await loadClub()
    } catch (err) {
      setError(err.message)
    } finally {
      setClubSaving(false)
    }
  }

  const refreshDiscountPreview = async () => {
    if (discountForm.target !== 'single' || !discountForm.customer_id || !discountForm.discount_value) {
      setDiscountPreview('')
      return
    }
    try {
      const data = await smsApi.discountPreview(
        discountForm.customer_id,
        discountForm.discount_type,
        discountForm.discount_value,
      )
      setDiscountPreview(data.message)
    } catch {
      setDiscountPreview('')
    }
  }

  useEffect(() => {
    if (tab === 'discount') refreshDiscountPreview()
  }, [
    tab,
    discountForm.customer_id,
    discountForm.discount_type,
    discountForm.discount_value,
    discountForm.target,
  ])

  const sendDiscount = async (e) => {
    e.preventDefault()
    setDiscountSending(true)
    setError('')
    setInfo('')
    try {
      const payload = {
        target: discountForm.target,
        discount_type: discountForm.discount_type,
        discount_value: Number(discountForm.discount_value),
        message_template: discountForm.message_template || undefined,
      }
      if (discountForm.target === 'single') payload.customer_id = discountForm.customer_id
      if (discountForm.target === 'level') payload.level_id = discountForm.level_id
      const result = await smsApi.sendDiscount(payload)
      setInfo(`تخفیف ویژه: ${result.successful} موفق، ${result.failed} ناموفق`)
      if (canViewLogs) loadLogs()
    } catch (err) {
      setError(err.message)
    } finally {
      setDiscountSending(false)
    }
  }

  const smsTypeColor = (type) => STATUS_COLORS[type] || '#94a3b8'

  const activeRecipients = preview?.recipients?.filter((r) => !r.already_sent) || []
  const sendTimeLabel = formatTimeFa(preview?.send_time || settingsForm.send_time)

  return (
    <div className="page sms-page">
      <div className="sms-tabs">
        {canManageClub && (
          <button
            type="button"
            className={`sms-tab ${tab === 'club' ? 'active' : ''}`}
            onClick={() => setTab('club')}
          >
            🏅 باشگاه
          </button>
        )}
        {canManageClub && (
          <button
            type="button"
            className={`sms-tab ${tab === 'discount' ? 'active' : ''}`}
            onClick={() => setTab('discount')}
          >
            🎁 تخفیف ویژه
          </button>
        )}
        {canManageBirthday && (
          <button
            type="button"
            className={`sms-tab ${tab === 'birthday' ? 'active' : ''}`}
            onClick={() => setTab('birthday')}
          >
            🎂 تبریک تولد
          </button>
        )}
        {canManageReminders && (
          <button
            type="button"
            className={`sms-tab ${tab === 'reminders' ? 'active' : ''}`}
            onClick={() => setTab('reminders')}
          >
            🔔 یادآوری باشگاه
          </button>
        )}
        {canViewLogs && (
          <button
            type="button"
            className={`sms-tab ${tab === 'logs' ? 'active' : ''}`}
            onClick={() => setTab('logs')}
          >
            📜 تاریخچه
          </button>
        )}
        {canSend && (tab === 'logs' || !canViewLogs) && (
          <Button className="sms-tab-action" onClick={() => setModalOpen(true)}>
            + ارسال پیامک
          </Button>
        )}
      </div>

      {error && <div className="alert-error">{error}</div>}
      {info && <div className="alert-info">{info}</div>}

      {tab === 'club' && canManageClub && (
        <div className="sms-birthday-grid">
          <Card title="پیامک‌های خودکار باشگاه">
            <form onSubmit={saveClubSettings} className="form">
              <Field label="نام فروشگاه">
                <input
                  value={clubForm.shop_name}
                  onChange={(e) => setClubForm({ ...clubForm, shop_name: e.target.value })}
                />
              </Field>

              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={clubForm.auto_order_placed}
                  onChange={(e) => setClubForm({ ...clubForm, auto_order_placed: e.target.checked })}
                />
                <span>ارسال خودکار پس از ثبت سفارش</span>
              </label>
              <Field label="قالب ثبت سفارش">
                <div className="template-vars">
                  {['name', 'amount', 'invoice', 'shop_name'].map((v) => (
                    <button
                      key={v}
                      type="button"
                      className="var-chip"
                      onClick={() => insertClubVar('order_placed_template', v)}
                    >
                      {`{${v}}`}
                    </button>
                  ))}
                </div>
                <textarea
                  rows={3}
                  value={clubForm.order_placed_template}
                  onChange={(e) => setClubForm({ ...clubForm, order_placed_template: e.target.value })}
                />
              </Field>

              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={clubForm.auto_welcome}
                  onChange={(e) => setClubForm({ ...clubForm, auto_welcome: e.target.checked })}
                />
                <span>ارسال خودکار خوش‌آمدگویی (مشتری جدید)</span>
              </label>
              <Field label="قالب خوش‌آمدگویی">
                <textarea
                  rows={2}
                  value={clubForm.welcome_template}
                  onChange={(e) => setClubForm({ ...clubForm, welcome_template: e.target.value })}
                />
              </Field>

              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={clubForm.auto_level_up}
                  onChange={(e) => setClubForm({ ...clubForm, auto_level_up: e.target.checked })}
                />
                <span>ارسال خودکار ارتقای سطح</span>
              </label>
              <Field label="قالب ارتقای سطح">
                <textarea
                  rows={2}
                  value={clubForm.level_up_template}
                  onChange={(e) => setClubForm({ ...clubForm, level_up_template: e.target.value })}
                />
              </Field>

              <Field label="قالب پیش‌فرض تخفیف ویژه">
                <div className="template-vars">
                  {['name', 'discount_label', 'shop_name'].map((v) => (
                    <button
                      key={v}
                      type="button"
                      className="var-chip"
                      onClick={() => insertClubVar('discount_template', v)}
                    >
                      {`{${v}}`}
                    </button>
                  ))}
                </div>
                <textarea
                  rows={3}
                  value={clubForm.discount_template}
                  onChange={(e) => setClubForm({ ...clubForm, discount_template: e.target.value })}
                />
              </Field>

              <div className="form-row">
                <Field label="نوع تخفیف پیش‌فرض">
                  <Select
                    value={clubForm.default_discount_type}
                    onChange={(v) => setClubForm({ ...clubForm, default_discount_type: v })}
                    options={[
                      { value: 'amount', label: `مبلغ (${CURRENCY_UNIT})` },
                      { value: 'percent', label: 'درصد' },
                    ]}
                  />
                </Field>
                <Field label="مقدار پیش‌فرض">
                  <MoneyInput
                    min="0"
                    unit={clubForm.default_discount_type === 'percent' ? PERCENT_UNIT : CURRENCY_UNIT}
                    value={clubForm.default_discount_value}
                    onChange={(e) =>
                      setClubForm({ ...clubForm, default_discount_value: e.target.value })
                    }
                  />
                </Field>
              </div>

              <Button type="submit" disabled={clubSaving}>
                {clubSaving ? 'در حال ذخیره…' : 'ذخیره تنظیمات باشگاه'}
              </Button>
            </form>
          </Card>

        </div>
      )}

      {tab === 'discount' && canManageClub && (
        <Card title="ارسال تخفیف ویژه (دستی)">
          <form onSubmit={sendDiscount} className="form">
            <Field label="گیرندگان">
              <Select
                value={discountForm.target}
                onChange={(v) => setDiscountForm({ ...discountForm, target: v })}
                options={[
                  { value: 'single', label: 'یک مشتری' },
                  { value: 'level', label: 'یک سطح باشگاه' },
                  { value: 'all', label: 'همه مشتریان فعال' },
                ]}
              />
            </Field>

            {discountForm.target === 'single' && (
              <Field label="مشتری">
                <Select
                  value={discountForm.customer_id}
                  onChange={(v) => setDiscountForm({ ...discountForm, customer_id: v })}
                  options={customers.map((c) => ({ value: String(c.id), label: `${c.full_name} (${c.phone})` }))}
                  placeholder="— انتخاب مشتری —"
                  required
                />
              </Field>
            )}

            {discountForm.target === 'level' && (
              <Field label="سطح">
                <Select
                  value={discountForm.level_id}
                  onChange={(v) => setDiscountForm({ ...discountForm, level_id: v })}
                  options={levels.map((t) => ({ value: String(t.id), label: t.name }))}
                  placeholder="— انتخاب سطح —"
                  required
                />
              </Field>
            )}

            <div className="form-row">
              <Field label="نوع تخفیف">
                <Select
                  value={discountForm.discount_type}
                  onChange={(v) => setDiscountForm({ ...discountForm, discount_type: v })}
                  options={[
                    { value: 'amount', label: `مبلغ (${CURRENCY_UNIT})` },
                    { value: 'percent', label: 'درصد' },
                  ]}
                />
              </Field>
              <Field label="مقدار تخفیف">
                <MoneyInput
                  min="1"
                  unit={discountForm.discount_type === 'percent' ? PERCENT_UNIT : CURRENCY_UNIT}
                  value={discountForm.discount_value}
                  onChange={(e) =>
                    setDiscountForm({ ...discountForm, discount_value: e.target.value })
                  }
                  required
                />
              </Field>
            </div>

            <Field label="متن پیام (اختیاری — خالی = قالب پیش‌فرض)">
              <textarea
                rows={4}
                value={discountForm.message_template}
                onChange={(e) =>
                  setDiscountForm({ ...discountForm, message_template: e.target.value })
                }
              />
            </Field>

            {discountPreview && discountForm.target === 'single' && (
              <div className="birthday-preview-msg muted">
                <strong>پیش‌نمایش:</strong> {discountPreview}
              </div>
            )}

            <Button type="submit" disabled={discountSending}>
              {discountSending ? 'در حال ارسال…' : 'ارسال تخفیف ویژه'}
            </Button>
          </form>
        </Card>
      )}

      {tab === 'birthday' && canManageBirthday && (
        <div className="sms-birthday-grid">
          <Card title="تنظیمات تبریک تولد">
            <form onSubmit={saveBirthdaySettings} className="form">
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={settingsForm.is_enabled}
                  onChange={(e) =>
                    setSettingsForm({ ...settingsForm, is_enabled: e.target.checked })
                  }
                />
                <span>ارسال خودکار فعال باشد</span>
              </label>

              <Field label="نام فروشگاه در پیام">
                <input
                  value={settingsForm.shop_name}
                  onChange={(e) => setSettingsForm({ ...settingsForm, shop_name: e.target.value })}
                />
              </Field>

              <Field label="ساعت ارسال روزانه">
                <input
                  className="ltr"
                  type="time"
                  value={settingsForm.send_time}
                  onChange={(e) => setSettingsForm({ ...settingsForm, send_time: e.target.value })}
                />
              </Field>

              <Field label="متن پیام (قابل شخصی‌سازی)">
                <div className="template-vars">
                  {(birthdaySettings?.template_vars || ['name', 'shop_name', 'phone']).map((v) => (
                    <button key={v} type="button" className="var-chip" onClick={() => insertVar(v)}>
                      {`{${v}}`}
                    </button>
                  ))}
                </div>
                <textarea
                  rows={4}
                  value={settingsForm.message_template}
                  onChange={(e) =>
                    setSettingsForm({ ...settingsForm, message_template: e.target.value })
                  }
                  required
                />
              </Field>

              <Button type="submit" disabled={birthdaySaving}>
                {birthdaySaving ? 'در حال ذخیره…' : 'ذخیره تنظیمات'}
              </Button>
            </form>
          </Card>

          <Card
            title="لیست ارسال امروز"
            actions={
              preview?.will_send_count > 0 ? (
                <Button variant="ghost" type="button" onClick={sendBirthdayNow}>
                  ارسال الان
                </Button>
              ) : null
            }
          >
            {loading ? (
              <div className="loading">در حال بارگذاری…</div>
            ) : (
              <>
                <div className={`birthday-schedule-banner ${settingsForm.is_enabled ? 'on' : 'off'}`}>
                  {settingsForm.is_enabled ? (
                    preview?.will_send_count > 0 ? (
                      <>
                        <strong>{toPersianDigits(preview.will_send_count)} مشتری</strong> امروز ساعت{' '}
                        <strong>{sendTimeLabel}</strong> پیامک تبریک دریافت می‌کنند.
                      </>
                    ) : (
                      <>امروز مشتری با تولد در لیست ارسال نیست (یا همه حذف/ارسال شده‌اند).</>
                    )
                  ) : (
                    <>ارسال خودکار غیرفعال است — فقط با «ارسال الان» یا فعال‌سازی تنظیمات.</>
                  )}
                  {preview?.send_due && settingsForm.is_enabled && (
                    <p className="muted">زمان ارسال رسیده — در صورت باز بودن صفحه، خودکار ارسال می‌شود.</p>
                  )}
                </div>

                {activeRecipients.length === 0 ? (
                  <EmptyState text="مشتری در صف ارسال امروز نیست." />
                ) : (
                  <div className="birthday-recipient-list">
                    {activeRecipients.map((r) => (
                      <div key={r.customer_id} className="birthday-recipient-card">
                        <div className="birthday-recipient-head">
                          <div>
                            <strong>{r.full_name}</strong>
                            <span className="ltr muted"> — {r.phone}</span>
                          </div>
                          <button
                            type="button"
                            className="link danger"
                            onClick={() => excludeFromBirthday(r.customer_id)}
                          >
                            حذف از لیست
                          </button>
                        </div>
                        <p className="muted birthday-preview-msg">{r.preview_message}</p>
                        <span className="muted">
                          تولد: {formatJalali(r.birthday)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {preview?.excluded?.length > 0 && (
                  <div className="birthday-excluded-section">
                    <h4>حذف‌شده از ارسال امروز ({toPersianDigits(preview.excluded.length)})</h4>
                    {preview.excluded.map((r) => (
                      <div key={r.customer_id} className="birthday-excluded-row">
                        <span>{r.full_name}</span>
                        <button
                          type="button"
                          className="link"
                          onClick={() => restoreToBirthday(r.customer_id)}
                        >
                          بازگرداندن
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      )}

      {tab === 'reminders' && canManageReminders && <ReminderCampaigns />}

      {!canManageBirthday && !canViewLogs && canSend && (
        <Card title="ارسال پیامک">
          <p className="muted">از دکمه زیر برای ارسال پیامک به مشتریان استفاده کنید.</p>
          <Button onClick={() => setModalOpen(true)}>+ ارسال پیامک</Button>
        </Card>
      )}

      {(tab === 'logs' || !canManageBirthday) && canViewLogs && (
        <Card title="تاریخچه پیامک‌ها">
          <p className="muted">
            درگاه پیش‌فرض شبیه‌سازی است. بدون SMS_API_KEY، وضعیت mock_sent ثبت می‌شود.
          </p>
          {loading ? (
            <div className="loading">در حال بارگذاری…</div>
          ) : messages.length === 0 ? (
            <EmptyState text="پیامکی ثبت نشده است." />
          ) : (
            <>
              <div className="table-wrap sms-table-desktop">
                <table className="table">
                  <thead>
                    <tr>
                      <th>شماره</th>
                      <th>نوع</th>
                      <th>متن</th>
                      <th>وضعیت</th>
                      <th>ارسال‌کننده</th>
                      <th>تاریخ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {messages.map((m) => (
                      <tr key={m.id}>
                        <td className="ltr">{m.phone_number}</td>
                        <td>
                          <Badge color={smsTypeColor(m.sms_type)}>{m.sms_type_display}</Badge>
                        </td>
                        <td className="text-cell">{m.message}</td>
                        <td>
                          <Badge color={STATUS_COLORS[m.status]}>{m.status_display}</Badge>
                        </td>
                        <td>{m.created_by || '—'}</td>
                        <td>{formatDate(m.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="sms-cards-mobile">
                {messages.map((m) => (
                  <div key={m.id} className="sms-log-card">
                    <div className="sms-log-card-head">
                      <span className="ltr">{m.phone_number}</span>
                      <Badge color={STATUS_COLORS[m.status]}>{m.status_display}</Badge>
                    </div>
                    <p>{m.message}</p>
                    <div className="sms-log-card-meta">
                      <Badge color={smsTypeColor(m.sms_type)}>{m.sms_type_display}</Badge>
                      <span className="muted">{formatDate(m.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {canSend && (
        <Modal title="ارسال پیامک" open={modalOpen} onClose={() => setModalOpen(false)}>
          <form onSubmit={send} className="form">
            <Field label="گیرندگان">
              <Select
                value={form.target}
                onChange={(v) => setForm({ ...form, target: v })}
                options={[
                  { value: 'single', label: 'یک مشتری' },
                  { value: 'level', label: 'مشتریان فعال یک سطح' },
                  { value: 'all', label: 'همه مشتریان فعال' },
                ]}
              />
            </Field>

            {form.target === 'single' && (
              <Field label="مشتری">
                <Select
                  value={form.customer_id}
                  onChange={(v) => setForm({ ...form, customer_id: v })}
                  options={customers.map((c) => ({ value: String(c.id), label: `${c.full_name} (${c.phone})` }))}
                  placeholder="— انتخاب مشتری —"
                  required
                />
              </Field>
            )}

            {form.target === 'level' && (
              <Field label="سطح">
                <Select
                  value={form.level_id}
                  onChange={(v) => setForm({ ...form, level_id: v })}
                  options={levels.map((t) => ({ value: String(t.id), label: t.name }))}
                  placeholder="— انتخاب سطح —"
                  required
                />
              </Field>
            )}

            <Field label="متن پیامک">
              <textarea value={form.message} onChange={update('message')} rows={4} required />
            </Field>
            <Button type="submit">ارسال</Button>
          </form>
        </Modal>
      )}
    </div>
  )
}
