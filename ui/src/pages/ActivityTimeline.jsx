// صفحه تایم‌لاین فعالیت‌ها

import { useEffect, useState } from 'react'
import { activitiesApi } from '../api/client'
import ActivityCard from '../components/ActivityCard'
import { Badge, Button, Card, EmptyState, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { cn, tw } from '../styles/tw'
import Icon from '../components/icons/Icon'

const ACTIVITY_TYPES = [
  { value: 'all', label: 'همه' },
  { value: 'call', label: 'تماس تلفنی' },
  { value: 'email', label: 'ایمیل' },
  { value: 'meeting', label: 'جلسه' },
  { value: 'note', label: 'یادداشت' },
  { value: 'sale', label: 'فروش' },
  { value: 'task_created', label: 'وظیفه ایجاد شد' },
  { value: 'task_completed', label: 'وظیفه انجام شد' },
  { value: 'order_status', label: 'تغییر وضعیت سفارش' },
]

const DATE_RANGES = [
  { value: 'week', label: 'هفته اخیر' },
  { value: 'month', label: 'ماه اخیر' },
  { value: 'all', label: 'همه' },
]

export default function ActivityTimeline() {
  const [activities, setActivities] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({
    type: 'all',
    date_range: 'week',
  })
  const [createModal, setCreateModal] = useState(false)
  const [newActivity, setNewActivity] = useState({
    activity_type: 'note',
    title: '',
    description: '',
  })

  const loadActivities = async (append = false) => {
    try {
      const currentOffset = append ? offset : 0
      if (append) {
        setLoadingMore(true)
      } else {
        setLoading(true)
      }

      const response = await activitiesApi.list({
        type: filters.type,
        date_range: filters.date_range,
        offset: currentOffset,
        limit: PAGE_SIZE,
      })

      if (append) {
        setActivities([...activities, ...response.results])
      } else {
        setActivities(response.results)
      }
      setTotal(response.total)
      setOffset(currentOffset + response.results.length)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    loadActivities()
  }, [filters])

  const handleCreate = async () => {
    try {
      await activitiesApi.create({
        ...newActivity,
        occurred_at: new Date().toISOString(),
      })
      setCreateModal(false)
      setNewActivity({ activity_type: 'note', title: '', description: '' })
      loadActivities()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className={tw.page}>
      {/* Header */}
      <div className={tw.pageHead}>
        <h2 className={tw.pageTitle}>تایم‌لاین فعالیت‌ها</h2>
        <Button onClick={() => setCreateModal(true)}>
          <Icon name="plus" size={16} />
          ثبت فعالیت
        </Button>
      </div>

      {/* Filters */}
      <FilterBar>
        <label className={tw.field}>
          <span className={tw.fieldLabel}>نوع فعالیت</span>
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
            className={tw.searchInput}
          >
            {ACTIVITY_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <label className={tw.field}>
          <span className={tw.fieldLabel}>بازه زمانی</span>
          <select
            value={filters.date_range}
            onChange={(e) => setFilters({ ...filters, date_range: e.target.value })}
            className={tw.searchInput}
          >
            {DATE_RANGES.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      {/* Error */}
      {error && <div className={tw.alert}>{error}</div>}

      {/* Activities list */}
      {loading ? (
        <div className={tw.loading}>در حال بارگذاری...</div>
      ) : activities.length === 0 ? (
        <EmptyState text="فعالیتی ثبت نشده است." />
      ) : (
        <div className="space-y-3">
          {activities.map((activity) => (
            <ActivityCard key={activity.id} activity={activity} />
          ))}

          <LoadMoreButton
            hasMore={offset < total}
            loading={loadingMore}
            onClick={() => loadActivities(true)}
            pageSize={PAGE_SIZE}
          />
        </div>
      )}

      {/* Create modal */}
      <Modal
        title="ثبت فعالیت جدید"
        open={createModal}
        onClose={() => setCreateModal(false)}
      >
        <div className={tw.form}>
          <label className={tw.field}>
            <span className={tw.fieldLabel}>نوع فعالیت</span>
            <select
              value={newActivity.activity_type}
              onChange={(e) =>
                setNewActivity({ ...newActivity, activity_type: e.target.value })
              }
              className={tw.searchInput}
            >
              {ACTIVITY_TYPES.filter((t) => t.value !== 'all').map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>

          <label className={tw.field}>
            <span className={tw.fieldLabel}>عنوان</span>
            <input
              type="text"
              value={newActivity.title}
              onChange={(e) =>
                setNewActivity({ ...newActivity, title: e.target.value })
              }
              className={tw.searchInput}
              placeholder="عنوان فعالیت..."
            />
          </label>

          <label className={tw.field}>
            <span className={tw.fieldLabel}>توضیحات</span>
            <textarea
              value={newActivity.description}
              onChange={(e) =>
                setNewActivity({ ...newActivity, description: e.target.value })
              }
              className={cn(tw.searchInput, 'min-h-[100px] resize-y')}
              placeholder="توضیحات..."
            />
          </label>

          <div className={tw.formActions}>
            <Button onClick={handleCreate} disabled={!newActivity.title}>
              ثبت فعالیت
            </Button>
            <Button variant="ghost" onClick={() => setCreateModal(false)}>
              انصراف
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
