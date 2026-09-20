import { useCallback, useEffect, useState } from 'react'
import { betaFabricApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatMoney } from '../utils/format'
import { formatJalali, todayIso } from '../utils/jalali'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_ROLL = {
  code: '',
  color_name: '',
  company: '',
  fabric_type: '',
  country: '',
  unit_cost: '',
  meters: '',
  image_url: '',
  min_meters: '',
}

const EMPTY_DISPATCH = {
  roll_id: '',
  destination: '',
  meters: '',
  sent_date: todayIso(),
}

// فهرست‌های فیلتر از مقادیر موجود در انبار ساخته می‌شوند.
const toOptions = (allLabel, values) => [
  { value: '', label: allLabel },
  ...(values || []).map((v) => ({ value: v, label: v })),
]

export default function BetaFabric() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasPermission(user, 'manage_beta_fabric')
  const [tab, setTab] = useState('stock')
  const [stats, setStats] = useState({})
  const [rolls, setRolls] = useState([])
  const [dispatches, setDispatches] = useState([])
  const [needs, setNeeds] = useState([])
  const [search, setSearch] = useState('')
  const [company, setCompany] = useState('')
  const [fabricType, setFabricType] = useState('')
  const [country, setCountry] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rollModal, setRollModal] = useState(false)
  const [dispatchModal, setDispatchModal] = useState(false)
  const [editingRoll, setEditingRoll] = useState(null)
  const [rollForm, setRollForm] = useState(EMPTY_ROLL)
  const [dispatchForm, setDispatchForm] = useState(EMPTY_DISPATCH)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, r, d, n] = await Promise.all([
        betaFabricApi.stats(),
        betaFabricApi.rolls({ search: search.trim(), company, fabric_type: fabricType, country, limit: 100 }),
        betaFabricApi.dispatches({ limit: 100 }),
        betaFabricApi.needs({ limit: 100 }),
      ])
      setStats(s || {})
      setRolls(r.results || [])
      setDispatches(d.results || [])
      setNeeds(n.results || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search, company, fabricType, country])

  useEffect(() => { load() }, [load])

  const openCreateRoll = () => {
    setEditingRoll(null)
    setRollForm(EMPTY_ROLL)
    setRollModal(true)
  }

  const openEditRoll = (roll) => {
    setEditingRoll(roll)
    setRollForm({
      code: roll.code || '',
      color_name: roll.color_name || '',
      company: roll.company || '',
      fabric_type: roll.fabric_type || '',
      country: roll.country || '',
      unit_cost: String(roll.unit_cost || ''),
      meters: String(roll.meters ?? ''),
      image_url: roll.image_url || '',
      min_meters: String(roll.min_meters ?? ''),
    })
    setRollModal(true)
  }

  const saveRoll = async () => {
    setSaving(true)
    try {
      if (editingRoll) await betaFabricApi.updateRoll(editingRoll.id, rollForm)
      else await betaFabricApi.createRoll(rollForm)
      setRollModal(false)
      setEditingRoll(null)
      setRollForm(EMPTY_ROLL)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeRoll = async (roll) => {
    if (!(await confirm({ title: 'حذف طاقه پارچه', message: `${roll.code} حذف شود؟` }))) return
    try {
      await betaFabricApi.removeRoll(roll.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveDispatch = async () => {
    setSaving(true)
    try {
      await betaFabricApi.createDispatch({ ...dispatchForm, roll_id: Number(dispatchForm.roll_id) })
      setDispatchModal(false)
      setDispatchForm({ ...EMPTY_DISPATCH, sent_date: todayIso() })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>انبار پارچه و کالیته‌ها (بتا)</h1>
          <p className={fromLegacy('muted')}>
            کالیته‌ها، جنس، کشور سازنده، قیمت، تصاویر و حواله‌های برش کارگاه‌های اقماری
          </p>
        </div>
        {canManage && (
          <div className={fromLegacy('row')}>
            <Button variant="ghost" onClick={() => { setDispatchForm({ ...EMPTY_DISPATCH, sent_date: todayIso(), roll_id: rolls[0] ? String(rolls[0].id) : '' }); setDispatchModal(true) }}>صدور حواله خروج</Button>
            <Button onClick={openCreateRoll}>+ ثبت کالیته / طاقه جدید</Button>
          </div>
        )}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <div className={fromLegacy('stat-grid')}>
        <StatCard label="مجموع متراژ پارچه" value={`${stats.meters ?? 0}`} hint="متر طول" />
        <StatCard label="ارزش کل موجودی" value={formatMoney(stats.value || 0)} />
        <StatCard label="شرکت‌ها و تنوع کالیته" value={stats.companies ?? 0} hint={`${stats.rolls ?? 0} طاقه`} />
        <StatCard label="کالیته‌های در مرز اتمام" value={stats.low_stock ?? 0} accent="var(--warning)" />
      </div>

      <div className={fromLegacy('workflow-filter-tabs')}>
        <button type="button" className={fromLegacy(`workflow-filter-tab ${tab === 'stock' ? 'active' : ''}`)} onClick={() => setTab('stock')}>موجودی طاقه‌ها و کالیته‌ها ({stats.rolls ?? 0})</button>
        <button type="button" className={fromLegacy(`workflow-filter-tab ${tab === 'needs' ? 'active' : ''}`)} onClick={() => setTab('needs')}>نیاز خط تولید ({stats.needs_total ?? needs.length})</button>
        <button type="button" className={fromLegacy(`workflow-filter-tab ${tab === 'out' ? 'active' : ''}`)} onClick={() => setTab('out')}>تاریخچه حواله‌های خروج ({stats.dispatches ?? 0})</button>
      </div>

      {tab === 'stock' && (
        <>
          <FilterBar>
            <Field label="جستجو">
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجوی کد، رنگ، شرکت یا جنس…" />
            </Field>
            <Field label="شرکت / برند">
              <Select value={company} onChange={setCompany} options={toOptions('همه شرکت‌ها', stats.company_options)} />
            </Field>
            <Field label="جنس پارچه">
              <Select value={fabricType} onChange={setFabricType} options={toOptions('همه جنس‌ها', stats.fabric_type_options)} />
            </Field>
            <Field label="کشور سازنده">
              <Select value={country} onChange={setCountry} options={toOptions('همه کشورها', stats.country_options)} />
            </Field>
          </FilterBar>
          <Card>
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : rolls.length === 0 ? (
              <EmptyState text="طاقه پارچه‌ای مطابق فیلتر یافت نشد. با دکمه «ثبت کالیته / طاقه جدید» پارچه وارد انبار کنید." />
            ) : (
              <div className={fromLegacy('table-wrap')}>
                <table className={fromLegacy('data-table')}>
                  <thead>
                    <tr>
                      <th>تصویر</th>
                      <th>کد پارچه</th>
                      <th>رنگ</th>
                      <th>شرکت / برند</th>
                      <th>جنس</th>
                      <th>کشور</th>
                      <th>متراژ</th>
                      <th>بهای خرید</th>
                      <th>ارزش</th>
                      <th>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rolls.map((roll) => (
                      <tr key={roll.id} className={roll.low_stock ? fromLegacy('row-highlight') : undefined}>
                        <td>
                          {roll.image_url ? (
                            <a href={roll.image_url} target="_blank" rel="noreferrer">
                              <img src={roll.image_url} alt={roll.code} style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }} />
                            </a>
                          ) : '—'}
                        </td>
                        <td>
                          {roll.code}
                          {roll.low_stock && <Badge color="var(--warning)" style={{ marginInlineStart: 6 }}>کمبود</Badge>}
                        </td>
                        <td>{roll.color_name || '—'}</td>
                        <td>{roll.company || '—'}</td>
                        <td>{roll.fabric_type || '—'}</td>
                        <td>{roll.country || '—'}</td>
                        <td>{roll.meters} متر{roll.min_meters > 0 && <div className={fromLegacy('muted small')}>حداقل: {roll.min_meters}</div>}</td>
                        <td>{formatMoney(roll.unit_cost)}</td>
                        <td>{formatMoney(roll.value)}</td>
                        <td>
                          {canManage && (
                            <>
                              <Button variant="ghost" size="sm" onClick={() => openEditRoll(roll)}>ویرایش</Button>
                              <Button variant="ghost" size="sm" onClick={() => removeRoll(roll)}>حذف</Button>
                            </>
                          )}
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

      {tab === 'needs' && (
        <Card>
          {needs.length === 0 ? (
            <EmptyState text="نیاز پارچه‌ای از سفارش‌های دریافتی ثبت نشده." />
          ) : (
            <div className={fromLegacy('table-wrap')}>
              <table className={fromLegacy('data-table')}>
                <thead>
                  <tr>
                    <th>کد</th>
                    <th>محصول</th>
                    <th>دستور</th>
                    <th>رنگ</th>
                    <th>متراژ</th>
                    <th>وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {needs.map((need) => (
                    <tr key={need.id}>
                      <td>{need.code}</td>
                      <td>{need.product_name}</td>
                      <td>{need.recipe_name || '—'}</td>
                      <td>{need.color_name || '—'}</td>
                      <td>{need.meters} متر</td>
                      <td>
                        {canManage ? (
                          <Select
                            value={need.status}
                            onChange={async (status) => {
                              try {
                                await betaFabricApi.updateNeed(need.id, { status })
                                await load()
                              } catch (err) {
                                setError(err.message)
                              }
                            }}
                            options={[
                              { value: 'pending', label: 'نیاز ثبت‌شده' },
                              { value: 'reserved', label: 'رزرو شده' },
                              { value: 'issued', label: 'حواله شده' },
                            ]}
                          />
                        ) : (need.status_display || need.status)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === 'out' && (
        <Card>
          {dispatches.length === 0 ? (
            <EmptyState text="حواله خروجی ثبت نشده" />
          ) : (
            <div className={fromLegacy('table-wrap')}>
              <table className={fromLegacy('data-table')}>
                <thead>
                  <tr>
                    <th>شماره حواله</th>
                    <th>کد پارچه</th>
                    <th>کارگاه مقصد</th>
                    <th>متراژ ارسالی</th>
                    <th>تاریخ ارسال</th>
                  </tr>
                </thead>
                <tbody>
                  {dispatches.map((d) => (
                    <tr key={d.id}>
                      <td>{d.code}</td>
                      <td>{d.roll_code}</td>
                      <td>{d.destination}</td>
                      <td>{d.meters} متر</td>
                      <td>{d.sent_date ? formatJalali(d.sent_date) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Modal title={editingRoll ? `ویرایش ${editingRoll.code}` : 'ثبت کالیته / طاقه جدید'} open={rollModal} onClose={() => { setRollModal(false); setEditingRoll(null) }} wide>
        <Field label="کد پارچه">
          <input value={rollForm.code} onChange={(e) => setRollForm({ ...rollForm, code: e.target.value })} placeholder="خالی بماند تا خودکار ساخته شود" />
        </Field>
        <Field label="رنگ">
          <input value={rollForm.color_name} onChange={(e) => setRollForm({ ...rollForm, color_name: e.target.value })} />
        </Field>
        <Field label="شرکت / برند">
          <input list="beta-fabric-companies" value={rollForm.company} onChange={(e) => setRollForm({ ...rollForm, company: e.target.value })} />
          <datalist id="beta-fabric-companies">
            {(stats.company_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="جنس پارچه">
          <input list="beta-fabric-types" value={rollForm.fabric_type} onChange={(e) => setRollForm({ ...rollForm, fabric_type: e.target.value })} />
          <datalist id="beta-fabric-types">
            {(stats.fabric_type_options || []).map((t) => <option key={t} value={t} />)}
          </datalist>
        </Field>
        <Field label="کشور سازنده">
          <input list="beta-fabric-countries" value={rollForm.country} onChange={(e) => setRollForm({ ...rollForm, country: e.target.value })} />
          <datalist id="beta-fabric-countries">
            {(stats.country_options || []).map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="بهای خرید هر متر">
          <MoneyInput value={rollForm.unit_cost} onChange={(e) => setRollForm({ ...rollForm, unit_cost: e.target.value })} />
        </Field>
        <Field label="متراژ">
          <input className={fromLegacy('ltr')} type="number" min="0" step="0.01" value={rollForm.meters} onChange={(e) => setRollForm({ ...rollForm, meters: e.target.value })} />
        </Field>
        <Field label="حداقل موجودی">
          <input className={fromLegacy('ltr')} type="number" min="0" step="0.01" value={rollForm.min_meters} onChange={(e) => setRollForm({ ...rollForm, min_meters: e.target.value })} />
        </Field>
        <Field label="آدرس تصویر">
          <input value={rollForm.image_url} onChange={(e) => setRollForm({ ...rollForm, image_url: e.target.value })} placeholder="https://…" />
        </Field>
        <Button disabled={saving} onClick={saveRoll}>{editingRoll ? 'ذخیره تغییرات' : 'ورود به انبار'}</Button>
      </Modal>

      <Modal title="صدور حواله خروج" open={dispatchModal} onClose={() => setDispatchModal(false)}>
        <Field label="طاقه / کالیته">
          <Select
            value={dispatchForm.roll_id}
            onChange={(v) => setDispatchForm({ ...dispatchForm, roll_id: v })}
            options={rolls.map((r) => ({ value: String(r.id), label: `${r.code} — ${r.meters} متر` }))}
          />
        </Field>
        <Field label="کارگاه مقصد (پیمانکار)">
          <input
            list="beta-fabric-destinations"
            value={dispatchForm.destination}
            onChange={(e) => setDispatchForm({ ...dispatchForm, destination: e.target.value })}
          />
          <datalist id="beta-fabric-destinations">
            {(stats.destination_options || []).map((d) => <option key={d} value={d} />)}
          </datalist>
        </Field>
        <Field label="متراژ ارسالی">
          <input className={fromLegacy('ltr')} type="number" min="0.001" step="0.01" value={dispatchForm.meters} onChange={(e) => setDispatchForm({ ...dispatchForm, meters: e.target.value })} />
        </Field>
        <Field label="تاریخ ارسال">
          <PersianDateInput value={dispatchForm.sent_date} onChange={(v) => setDispatchForm({ ...dispatchForm, sent_date: v })} />
        </Field>
        <Button disabled={saving} onClick={saveDispatch}>صدور حواله</Button>
      </Modal>
    </div>
  )
}
