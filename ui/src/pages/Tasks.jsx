// صفحه مدیریت وظایف

import { useEffect, useMemo, useState } from 'react'
import { tasksApi } from '../api/client'
import TaskCard from '../components/TaskCard'
import { Button, EmptyState, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { cn, tw } from '../styles/tw'
import Icon from '../components/icons/Icon'

const PRIORITY_OPTIONS = [
  { value: 'all', label: 'همه' },
  { value: 'urgent', label: 'فوری' },
  { value: 'high', label: 'زیاد' },
  { value: 'medium', label: 'متوسط' },
  { value: 'low', label: 'کم' },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'همه' },
  { value: 'todo', label: 'انجام نشده' },
  { value: 'in_progress', label: 'در حال انجام' },
  { value: 'completed', label: 'انجام شده' },
]

export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({
    status: 'todo',
    priority: 'all',
  })
  const [createModal, setCreateModal] = useState(false)
  const [editModal, setEditModal] = useState(null)
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
  })

  const loadTasks = async (append = false) => {
    try {
      const currentOffset = append ? offset : 0
      if (append) {
        setLoadingMore(true)
      } else {
        setLoading(true)
      }

      const response = await tasksApi.list({
        status: filters.status,
        priority: filters.priority,
        offset: currentOffset,
        limit: PAGE_SIZE,
      })

      if (append) {
        setTasks([...tasks, ...response.results])
      } else {
        setTasks(response.results)
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
    loadTasks()
  }, [filters])

  // Group tasks: pinned first
  const groupedTasks = useMemo(() => {
    const pinned = tasks.filter((t) => t.pinned)
    const unpinned = tasks.filter((t) => !t.pinned)
    return { pinned, unpinned }
  }, [tasks])

  const handleCreate = async () => {
    try {
      await tasksApi.create(newTask)
      setCreateModal(false)
      setNewTask({ title: '', description: '', priority: 'medium', due_date: '' })
      loadTasks()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleComplete = async (taskId) => {
    try {
      await tasksApi.complete(taskId)
      loadTasks()
    } catch (e) {
      setError(e.message)
    }
  }

  const handlePin = async (taskId, pinned) => {
    try {
      await tasksApi.pin(taskId, pinned)
      loadTasks()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleUpdate = async (task) => {
    setEditModal(task)
  }

  const handleSaveEdit = async () => {
    try {
      await tasksApi.update(editModal.id, {
        title: editModal.title,
        description: editModal.description,
        priority: editModal.priority,
        due_date: editModal.due_date,
      })
      setEditModal(null)
      loadTasks()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className={tw.page}>
      {/* Header */}
      <div className={tw.pageHead}>
        <h2 className={tw.pageTitle}>وظایف من</h2>
        <Button onClick={() => setCreateModal(true)}>
          <Icon name="plus" size={16} />
          وظیفه جدید
        </Button>
      </div>

      {/* Filters */}
      <FilterBar>
        <label className={tw.field}>
          <span className={tw.fieldLabel}>وضعیت</span>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className={tw.searchInput}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
              </option>
            ))}
          </select>
        </label>

        <label className={tw.field}>
          <span className={tw.fieldLabel}>اولویت</span>
          <select
            value={filters.priority}
            onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
            className={tw.searchInput}
          >
            {PRIORITY_OPTIONS.map((priority) => (
              <option key={priority.value} value={priority.value}>
                {priority.label}
              </option>
            ))}
          </select>
        </label>
      </FilterBar>

      {/* Error */}
      {error && <div className={tw.alert}>{error}</div>}

      {/* Tasks list */}
      {loading ? (
        <div className={tw.loading}>در حال بارگذاری...</div>
      ) : tasks.length === 0 ? (
        <EmptyState text="وظیفه‌ای وجود ندارد." />
      ) : (
        <>
          {/* Pinned tasks */}
          {groupedTasks.pinned.length > 0 && (
            <section className="mb-5">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted">
                پین شده ({groupedTasks.pinned.length})
              </h3>
              <div className="space-y-2">
                {groupedTasks.pinned.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onComplete={handleComplete}
                    onPin={handlePin}
                    onUpdate={handleUpdate}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Regular tasks */}
          {groupedTasks.unpinned.length > 0 && (
            <div className="space-y-2">
              {groupedTasks.unpinned.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onComplete={handleComplete}
                  onPin={handlePin}
                  onUpdate={handleUpdate}
                />
              ))}
            </div>
          )}

          <LoadMoreButton
            hasMore={offset < total}
            loading={loadingMore}
            onClick={() => loadTasks(true)}
            pageSize={PAGE_SIZE}
          />
        </>
      )}

      {/* Create modal */}
      <Modal
        title="وظیفه جدید"
        open={createModal}
        onClose={() => setCreateModal(false)}
      >
        <div className={tw.form}>
          <label className={tw.field}>
            <span className={tw.fieldLabel}>عنوان</span>
            <input
              type="text"
              value={newTask.title}
              onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
              className={tw.searchInput}
              placeholder="عنوان وظیفه..."
            />
          </label>

          <label className={tw.field}>
            <span className={tw.fieldLabel}>توضیحات</span>
            <textarea
              value={newTask.description}
              onChange={(e) =>
                setNewTask({ ...newTask, description: e.target.value })
              }
              className={cn(tw.searchInput, 'min-h-[100px] resize-y')}
              placeholder="توضیحات..."
            />
          </label>

          <label className={tw.field}>
            <span className={tw.fieldLabel}>اولویت</span>
            <select
              value={newTask.priority}
              onChange={(e) => setNewTask({ ...newTask, priority: e.target.value })}
              className={tw.searchInput}
            >
              <option value="low">کم</option>
              <option value="medium">متوسط</option>
              <option value="high">زیاد</option>
              <option value="urgent">فوری</option>
            </select>
          </label>

          <label className={tw.field}>
            <span className={tw.fieldLabel}>سررسید</span>
            <input
              type="datetime-local"
              value={newTask.due_date}
              onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
              className={tw.searchInput}
            />
          </label>

          <div className={tw.formActions}>
            <Button onClick={handleCreate} disabled={!newTask.title}>
              ایجاد وظیفه
            </Button>
            <Button variant="ghost" onClick={() => setCreateModal(false)}>
              انصراف
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit modal */}
      {editModal && (
        <Modal
          title="ویرایش وظیفه"
          open={!!editModal}
          onClose={() => setEditModal(null)}
        >
          <div className={tw.form}>
            <label className={tw.field}>
              <span className={tw.fieldLabel}>عنوان</span>
              <input
                type="text"
                value={editModal.title}
                onChange={(e) =>
                  setEditModal({ ...editModal, title: e.target.value })
                }
                className={tw.searchInput}
              />
            </label>

            <label className={tw.field}>
              <span className={tw.fieldLabel}>توضیحات</span>
              <textarea
                value={editModal.description}
                onChange={(e) =>
                  setEditModal({ ...editModal, description: e.target.value })
                }
                className={cn(tw.searchInput, 'min-h-[100px] resize-y')}
              />
            </label>

            <label className={tw.field}>
              <span className={tw.fieldLabel}>اولویت</span>
              <select
                value={editModal.priority}
                onChange={(e) =>
                  setEditModal({ ...editModal, priority: e.target.value })
                }
                className={tw.searchInput}
              >
                <option value="low">کم</option>
                <option value="medium">متوسط</option>
                <option value="high">زیاد</option>
                <option value="urgent">فوری</option>
              </select>
            </label>

            <label className={tw.field}>
              <span className={tw.fieldLabel}>سررسید</span>
              <input
                type="datetime-local"
                value={editModal.due_date || ''}
                onChange={(e) =>
                  setEditModal({ ...editModal, due_date: e.target.value })
                }
                className={tw.searchInput}
              />
            </label>

            <div className={tw.formActions}>
              <Button onClick={handleSaveEdit}>ذخیره</Button>
              <Button variant="ghost" onClick={() => setEditModal(null)}>
                انصراف
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
