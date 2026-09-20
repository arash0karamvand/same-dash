// گزینه‌های واحدهای بتا — همه از تنظیمات داینامیک (LookupOption) خوانده می‌شوند.

import { useCallback } from 'react'
import { useConfig } from '../context/ConfigContext'

export const BETA_WORKSHOP_KIND = 'beta_workshop_kind'
export const BETA_CARPENTRY_KIND = 'beta_carpentry_kind'
export const BETA_CARPENTRY_STATUS = 'beta_carpentry_status'
export const BETA_PAINT_KIND = 'beta_paint_kind'
export const BETA_PAINT_STAGE = 'beta_paint_stage'
export const BETA_UPHOLSTERY_STAGE = 'beta_upholstery_stage'
export const BETA_QC_STATUS = 'beta_qc_status'
export const BETA_QC_GRADE = 'beta_qc_grade'

export function useBetaOptions() {
  const { choices } = useConfig()

  // fallback فهرستی است که خود API برمی‌گرداند؛ تا قبل از رسیدن تنظیمات، فرم خالی نماند.
  return useCallback(
    (category, fallback = []) => {
      const fromConfig = choices(category)
      return fromConfig.length ? fromConfig : fallback
    },
    [choices],
  )
}
