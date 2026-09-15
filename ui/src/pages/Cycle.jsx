// چرخه سفارش — فقط مدیر سیستم

import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi, cycleApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, Modal } from '../components/ui'
import { isSystemAdmin } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_WAREHOUSE = { code: '', label: '', branch: '', sort_order: 0, is_active: true }

const FIXED_KEYS = ['branch_supervisor', 'shop_crm_monitor', 'crm']
const ROUTE_KEYS = ['factory', 'warehouse', 'customer_pickup', 'merchant']

function slotByKey(slots, key) {
  return slots.find((s) => s.step_key === key)
}

function AssigneeFields({ slot, users, ranks, onChange }) {
  if (!slot) return null
  const type = slot.assignee_type || ''
  return (
    <div className="cycle-assignee">
      <Select
        value={type}
        onChange={(value) => onChange({
          ...slot,
          assignee_type: value,
          user_id: value === 'user' ? slot.user_id : null,
          org_rank_id: value === 'rank' ? slot.org_rank_id : null,
        })}
        options={[
          { value: '', label: slot.requires_assignee ? 'انتخاب کنید…' : 'بدون تخصیص' },
          { value: 'user', label: 'کاربر' },
          { value: 'rank', label: 'مقام' },
        ]}
      />
      {type === 'user' && (
        <Select
          value={slot.user_id ? String(slot.user_id) : ''}
          onChange={(value) => onChange({ ...slot, user_id: value ? Number(value) : null, org_rank_id: null })}
          options={[{ value: '', label: 'کاربر…' }, ...users]}
        />
      )}
      {type === 'rank' && (
        <Select
          value={slot.org_rank_id ? String(slot.org_rank_id) : ''}
          onChange={(value) => onChange({ ...slot, org_rank_id: value ? Number(value) : null, user_id: null })}
          options={[{ value: '', label: 'مقام…' }, ...ranks]}
        />
      )}
    </div>
  )
}

export default function Cycle() {
  const { user } = useAuth()
  const { branches } = useConfig()
  const [cycle, setCycle] = useState(null)
  const [slots, setSlots] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [users, setUsers] = useState([])
  const [ranks, setRanks] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [whModal, setWhModal] = useState(false)
  const [whForm, setWhForm] = useState(EMPTY_WAREHOUSE)
  const [selectedWh, setSelectedWh] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cfg, userList, rankList] = await Promise.all([
        cycleApi.get(),
        authApi.users({ limit: 300, active: '1' }),
        authApi.orgRanks(),
      ])
      setCycle(cfg)
      setSlots(cfg.slots || [])
      setWarehouses(cfg.warehouses || [])
      setUsers((userList.results || []).map((u) => ({
        value: String(u.id),
        label: u.full_name || u.username,
      })))
      setRanks((rankList.results || rankList || []).map((r) => ({
        value: String(r.id),
        label: r.name,
      })))
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const updateSlot = (key, next) => {
    setSlots((prev) => prev.map((s) => (s.step_key === key ? { ...s, ...next } : s)))
  }

  const save = async () => {
    setSaving(true)
    setError('')
    setInfo('')
    try {
      const cfg = await cycleApi.save({ name: cycle?.name || 'چرخه فروش', slots })
      setCycle(cfg)
      setSlots(cfg.slots || [])
      setWarehouses(cfg.warehouses || [])
      setInfo('چرخه ذخیره شد.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const saveWarehouse = async (e) => {
    e.preventDefault()
    try {
      if (selectedWh) {
        await cycleApi.updateWarehouse(selectedWh.id, whForm)
        setInfo('انبار به‌روز شد.')
      } else {
        await cycleApi.createWarehouse(whForm)
        setInfo('انبار جدید ساخته شد.')
      }
      setWhModal(false)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const branchOptions = useMemo(
    () => [{ value: '', label: 'بدون شعبه' }, ...(branches || []).map((b) => ({ value: b.code, label: b.label }))],
    [branches],
  )

  if (!isSystemAdmin(user)) {
    return (
      <div className={fromLegacy('page')}>
        <Card title="چرخه">
          <div className={fromLegacy('alert-error')}>فقط مدیر سیستم به این بخش دسترسی دارد.</div>
        </Card>
      </div>
    )
  }

  const monitor = slotByKey(slots, 'shop_crm_monitor')
  const supervisor = slotByKey(slots, 'fulfillment_supervisor')

  return (
    <div className={fromLegacy('page cycle-page')}>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-info')}>{info}</div>}

      <div className={fromLegacy('page-head')}>
        <div>
          <h1>چرخه سفارش</h1>
          <p className={fromLegacy('muted')}>مسیر فروش تا ارسال را ماژولار تنظیم کنید. ناظر فقط مشاهده می‌کند.</p>
        </div>
        <Button type="button" onClick={save} disabled={saving || loading}>
          {saving ? 'در حال ذخیره…' : 'ذخیره چرخه'}
        </Button>
      </div>

      {loading ? (
        <p className={fromLegacy('muted loading')}>در حال بارگذاری…</p>
      ) : (
        <>
          <div className="cycle-map">
            {FIXED_KEYS.map((key) => {
              const slot = slotByKey(slots, key)
              if (!slot) return null
              return (
                <Card key={key} title={slot.label} className="cycle-node">
                  {key === 'shop_crm_monitor' && (
                    <p className={fromLegacy('muted small')}>بین فروشگاه و CRM نظارت می‌کند؛ سفارش را متوقف نمی‌کند.</p>
                  )}
                  <AssigneeFields slot={slot} users={users} ranks={ranks} onChange={(next) => updateSlot(key, next)} />
                </Card>
              )
            })}
            <div className="cycle-arrow">بعد از CRM</div>
            <div className="cycle-routes">
              {ROUTE_KEYS.map((key) => {
                const slot = slotByKey(slots, key)
                if (!slot) return null
                return (
                  <Card key={key} title={slot.label} className={`cycle-route ${slot.is_enabled ? 'is-on' : 'is-off'}`}>
                    <label className="cycle-toggle">
                      <input
                        type="checkbox"
                        checked={Boolean(slot.is_enabled)}
                        onChange={(e) => updateSlot(key, { is_enabled: e.target.checked })}
                      />
                      {slot.is_enabled ? 'روشن' : 'خاموش'}
                    </label>
                    <AssigneeFields slot={slot} users={users} ranks={ranks} onChange={(next) => updateSlot(key, next)} />
                  </Card>
                )
              })}
            </div>
            {supervisor && (
              <Card title={supervisor.label} className="cycle-node">
                <p className={fromLegacy('muted small')}>روی هر چهار مسیر نظارت دارد؛ سفارش را متوقف نمی‌کند.</p>
                <AssigneeFields
                  slot={supervisor}
                  users={users}
                  ranks={ranks}
                  onChange={(next) => updateSlot('fulfillment_supervisor', next)}
                />
              </Card>
            )}
          </div>

          {monitor?.requires_assignee && !monitor.user_id && !monitor.org_rank_id && (
            <div className={fromLegacy('alert-error')}>ناظر فروشگاه و CRM باید مقام یا کاربر داشته باشد.</div>
          )}

          <Card title="انبارها">
            <p className={fromLegacy('muted')} style={{ marginBottom: 12 }}>
              برای مسیر انبار، انبار جدا از شعبه تعریف می‌شود. هنگام تایید CRM می‌توان انبار یا شعبه را انتخاب کرد.
            </p>
            <div className={fromLegacy('form-actions')} style={{ marginBottom: 12 }}>
              <Button type="button" onClick={() => { setSelectedWh(null); setWhForm(EMPTY_WAREHOUSE); setWhModal(true) }}>
                انبار جدید
              </Button>
            </div>
            {warehouses.length === 0 ? (
              <EmptyState text="هنوز انباری تعریف نشده" />
            ) : (
              <div className={fromLegacy('table-wrap')}>
                <table className={fromLegacy('table')}>
                  <thead>
                    <tr>
                      <th>کد</th>
                      <th>نام</th>
                      <th>شعبه</th>
                      <th>وضعیت</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {warehouses.map((w) => (
                      <tr key={w.id}>
                        <td className={fromLegacy('ltr')}>{w.code}</td>
                        <td>{w.label}</td>
                        <td>{w.branch_label || '—'}</td>
                        <td>
                          <Badge color={w.is_active ? 'var(--success)' : 'var(--muted)'}>
                            {w.is_active ? 'فعال' : 'غیرفعال'}
                          </Badge>
                        </td>
                        <td>
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => {
                              setSelectedWh(w)
                              setWhForm({
                                code: w.code,
                                label: w.label,
                                branch: w.branch || '',
                                sort_order: w.sort_order || 0,
                                is_active: w.is_active,
                              })
                              setWhModal(true)
                            }}
                          >
                            ویرایش
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      <Modal title={selectedWh ? 'ویرایش انبار' : 'انبار جدید'} open={whModal} onClose={() => setWhModal(false)}>
        <form onSubmit={saveWarehouse} className={fromLegacy('form')}>
          <Field label="کد">
            <input
              value={whForm.code}
              onChange={(e) => setWhForm({ ...whForm, code: e.target.value })}
              required
              disabled={Boolean(selectedWh)}
            />
          </Field>
          <Field label="نام">
            <input
              value={whForm.label}
              onChange={(e) => setWhForm({ ...whForm, label: e.target.value })}
              required
            />
          </Field>
          <Field label="شعبه مرتبط (اختیاری)">
            <Select
              value={whForm.branch}
              onChange={(value) => setWhForm({ ...whForm, branch: value })}
              options={branchOptions}
            />
          </Field>
          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={() => setWhModal(false)}>انصراف</Button>
            <Button type="submit">{selectedWh ? 'ذخیره' : 'ایجاد'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
