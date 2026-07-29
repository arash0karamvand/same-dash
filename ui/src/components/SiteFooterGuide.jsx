// راهنمای فوتر — مشاهده برای همه؛ ویرایش با دبل‌کلیک فقط مدیر سیستم

import { useMemo, useState } from 'react'
import { configApi } from '../api/client'
import { resolvePageGuideText } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { usePageGuideContext } from '../context/PageGuideContext'
import { isSystemAdmin } from '../utils/permissions'
import { Button, Modal } from './ui'

export default function SiteFooterGuide({ pageKey }) {
  const { user } = useAuth()
  const { config, refresh } = useConfig()
  const { guideKey, guideDefaultText } = usePageGuideContext()
  const admin = isSystemAdmin(user)
  const code = guideKey || pageKey
  const savedGuides = config.page_guides || {}

  const displayText = useMemo(
    () => resolvePageGuideText(code, savedGuides) || guideDefaultText.trim(),
    [code, savedGuides, guideDefaultText],
  )

  const [editOpen, setEditOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (!displayText && !admin) return null

  const openEditor = () => {
    if (!admin) return
    const initial = resolvePageGuideText(code, savedGuides) || guideDefaultText
    setDraft(initial)
    setError('')
    setEditOpen(true)
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await configApi.savePageGuide(code, draft)
      await refresh()
      setEditOpen(false)
    } catch (err) {
      setError(err.message || 'خطا در ذخیره')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <footer
        className={`site-footer-guide${admin ? ' site-footer-guide-editable' : ''}`}
        aria-label="راهنمای صفحه"
        onDoubleClick={openEditor}
        title={admin ? 'دوبار کلیک برای ویرایش راهنما (فقط مدیر سیستم)' : undefined}
      >
        <span className="site-footer-guide-label">راهنما</span>
        <p className="site-footer-guide-text">
          {displayText || (admin ? 'برای افزودن توضیحات، دوبار کلیک کنید.' : '')}
        </p>
      </footer>

      <Modal title="ویرایش راهنمای صفحه" open={editOpen} onClose={() => setEditOpen(false)}>
        <form onSubmit={save} className="form">
          <p className="muted small">این متن در فوتر برای همه کاربران نمایش داده می‌شود.</p>
          <label className="field">
            <span className="field-label">توضیحات و راهنما</span>
            <textarea
              rows={6}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="راهنمای استفاده از این بخش…"
            />
          </label>
          {error && <div className="alert-error">{error}</div>}
          <div className="form-actions-row">
            <Button type="button" variant="ghost" onClick={() => setEditOpen(false)}>
              انصراف
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'در حال ذخیره…' : 'ذخیره'}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  )
}
