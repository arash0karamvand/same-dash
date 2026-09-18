// کلید و متن پیش‌فرض راهنمای فعلی — صفحات با زیربخش (مثل تب حسابداری)

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

const PageGuideContext = createContext(null)

export function PageGuideProvider({ children }) {
  const [state, setState] = useState({ key: null, defaultText: '' })

  const setPageGuide = useCallback((key, defaultText = '') => {
    setState({ key: key || null, defaultText: defaultText || '' })
  }, [])

  const clearPageGuide = useCallback(() => {
    setState({ key: null, defaultText: '' })
  }, [])

  const value = useMemo(
    () => ({
      guideKey: state.key,
      guideDefaultText: state.defaultText,
      setPageGuide,
      clearPageGuide,
    }),
    [state.key, state.defaultText, setPageGuide, clearPageGuide],
  )

  return <PageGuideContext.Provider value={value}>{children}</PageGuideContext.Provider>
}

/** ثبت راهنمای صفحه با زیربخش؛ با unmount پاک می‌شود */
export function useRegisterPageGuide(key, defaultText = '') {
  const ctx = useContext(PageGuideContext)
  if (!ctx) throw new Error('useRegisterPageGuide باید داخل PageGuideProvider باشد.')

  useEffect(() => {
    if (!key) return
    ctx.setPageGuide(key, defaultText)
    return () => ctx.clearPageGuide()
    // setPageGuide/clearPageGuide پایدارند
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, defaultText])
}

export function usePageGuideContext() {
  const ctx = useContext(PageGuideContext)
  if (!ctx) throw new Error('usePageGuideContext باید داخل PageGuideProvider باشد.')
  return ctx
}
