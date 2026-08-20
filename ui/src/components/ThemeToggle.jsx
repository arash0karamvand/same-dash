import Icon from './icons/Icon'
import { useTheme } from '../context/ThemeContext'

export default function ThemeToggle({ className = '' }) {
  const { isDark, toggleTheme } = useTheme()

  return (
    <button
      type="button"
      className={`theme-toggle${className ? ` ${className}` : ''}`}
      onClick={toggleTheme}
      aria-label={isDark ? 'فعال‌سازی حالت روشن' : 'فعال‌سازی حالت تاریک'}
      title={isDark ? 'حالت روشن' : 'حالت تاریک'}
    >
      <Icon name={isDark ? 'sun' : 'moon'} size={18} />
    </button>
  )
}
