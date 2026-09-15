import Icon from './icons/Icon'
import { useTheme } from '../context/ThemeContext'
import { cn, tw } from '../styles/tw'

export default function ThemeToggle({ className = '' }) {
  const { isDark, toggleTheme } = useTheme()

  return (
    <button
      type="button"
      className={cn(tw.themeToggle, className)}
      onClick={toggleTheme}
      aria-label={isDark ? 'فعال‌سازی حالت روشن' : 'فعال‌سازی حالت تاریک'}
      title={isDark ? 'حالت روشن' : 'حالت تاریک'}
    >
      <Icon name={isDark ? 'sun' : 'moon'} size={18} />
    </button>
  )
}
