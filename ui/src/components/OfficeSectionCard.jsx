import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { Card } from './ui'
import RecordFilterPanel from './RecordFilterPanel'

/**
 * یک بخش اداری: فیلتر زنده + (اختیاری) محتوای لیست/عملیات در همان کارت.
 */
export default function OfficeSectionCard({
  section,
  actions = null,
  children = null,
  onFiltersChange,
  className = '',
}) {
  const {
    scope,
    lockModel,
    initialFilters = {},
    pageGuideKey,
    title,
    resultLimit = 30,
    liveSearch = true,
    compact = true,
    hideFilterResults = false,
  } = section

  const guideKey = pageGuideKey || null
  const guideText = guideKey ? (PAGE_GUIDE_DEFAULTS[guideKey] || '') : ''
  useRegisterPageGuide(guideKey, guideText)

  return (
    <Card title={title} actions={actions} className={`office-unified-section ${className}`.trim()}>
      <RecordFilterPanel
        scope={scope}
        lockModel={lockModel}
        compact={compact}
        liveSearch={liveSearch}
        initialFilters={initialFilters}
        resultLimit={resultLimit}
        hideResults={hideFilterResults}
        onFiltersChange={onFiltersChange}
        unified
      />
      {children && <div className="office-section-body">{children}</div>}
    </Card>
  )
}
