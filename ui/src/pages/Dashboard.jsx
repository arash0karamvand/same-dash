// صفحه داشبورد با ویجت‌های قابل تنظیم

import { useEffect, useState } from 'react'
import { dashboardApi } from '../api/client'
import WidgetGrid from '../components/dashboard/WidgetGrid'
import WidgetConfigModal from '../components/dashboard/WidgetConfigModal'
import { Button } from '../components/ui'
import { cn, tw } from '../styles/tw'
import Icon from '../components/icons/Icon'

export default function Dashboard() {
  const [widgets, setWidgets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [configModal, setConfigModal] = useState(null)

  useEffect(() => {
    loadWidgets()
  }, [])

  const loadWidgets = async () => {
    try {
      setLoading(true)
      const data = await dashboardApi.widgets()
      setWidgets(data)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (config) => {
    try {
      if (config.id) {
        await dashboardApi.updateWidget(config.id, config)
      } else {
        await dashboardApi.createWidget(config)
      }
      loadWidgets()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این ویجت اطمینان دارید؟')) return
    
    try {
      await dashboardApi.deleteWidget(id)
      loadWidgets()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className={tw.page}>
      {/* Header */}
      <div className={tw.pageHead}>
        <h2 className={tw.pageTitle}>داشبورد</h2>
        <div className="flex gap-2">
          <Button onClick={() => setConfigModal('new')}>
            <Icon name="plus" size={16} />
            افزودن ویجت
          </Button>
          <Button variant="ghost" onClick={() => setEditMode(!editMode)}>
            {editMode ? 'اتمام ویرایش' : 'ویرایش'}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && <div className={tw.alert}>{error}</div>}

      {/* Widgets */}
      {loading ? (
        <div className={tw.loading}>در حال بارگذاری...</div>
      ) : widgets.length === 0 ? (
        <div className="text-center py-20 text-muted">
          <Icon name="layout" size={48} className="mx-auto mb-4 opacity-50" />
          <p className="mb-4">هنوز ویجتی اضافه نکرده‌اید.</p>
          <Button onClick={() => setConfigModal('new')}>افزودن اولین ویجت</Button>
        </div>
      ) : (
        <WidgetGrid
          widgets={widgets}
          editMode={editMode}
          onEdit={(w) => setConfigModal(w)}
          onDelete={handleDelete}
        />
      )}

      {/* Config modal */}
      {configModal && (
        <WidgetConfigModal
          widget={configModal === 'new' ? null : configModal}
          open={!!configModal}
          onClose={() => setConfigModal(null)}
          onSave={handleSave}
        />
      )}
    </div>
  )
}
