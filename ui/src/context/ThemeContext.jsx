import { createContext, useCallback, useContext, useEffect, useMemo } from 'react'

import { usePersistedState } from '../hooks/usePersistedState'



const ThemeContext = createContext(null)



const THEME_KEY = 'ui-theme'

const META_THEME = {

  dark: '#07070A',

  light: '#E8E8EC',

}



function applyTheme(theme) {

  const root = document.documentElement

  root.setAttribute('data-theme', theme)

  root.style.colorScheme = theme



  const meta = document.querySelector('meta[name="theme-color"]')

  if (meta) meta.setAttribute('content', META_THEME[theme] || META_THEME.dark)

}



function applyAccessibilityPrefs() {

  const root = document.documentElement

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const reducedTransparency = window.matchMedia('(prefers-reduced-transparency: reduce)').matches

  root.setAttribute('data-reduced-motion', reducedMotion ? 'true' : 'false')

  root.setAttribute('data-reduced-transparency', reducedTransparency ? 'true' : 'false')

}



export function ThemeProvider({ children }) {

  const [theme, setTheme] = usePersistedState(THEME_KEY, 'dark')



  useEffect(() => {

    applyTheme(theme === 'light' ? 'light' : 'dark')

  }, [theme])



  useEffect(() => {

    applyAccessibilityPrefs()

    const motionMq = window.matchMedia('(prefers-reduced-motion: reduce)')

    const transparencyMq = window.matchMedia('(prefers-reduced-transparency: reduce)')

    const onChange = () => applyAccessibilityPrefs()

    motionMq.addEventListener('change', onChange)

    transparencyMq.addEventListener('change', onChange)

    return () => {

      motionMq.removeEventListener('change', onChange)

      transparencyMq.removeEventListener('change', onChange)

    }

  }, [])



  const toggleTheme = useCallback(() => {

    setTheme((t) => (t === 'light' ? 'dark' : 'light'))

  }, [setTheme])



  const value = useMemo(

    () => ({

      theme: theme === 'light' ? 'light' : 'dark',

      isDark: theme !== 'light',

      setTheme,

      toggleTheme,

    }),

    [theme, setTheme, toggleTheme],

  )



  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>

}



export function useTheme() {

  const ctx = useContext(ThemeContext)

  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')

  return ctx

}

