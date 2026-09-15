const ICON_FILES = import.meta.glob('../../assets/icons/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
})

function parseIcon(raw) {
  const source = String(raw)
  const viewBox = /viewBox="([^"]+)"/.exec(source)?.[1] || '0 0 256 256'
  const inner = source
    .replace(/<\?xml[^>]*>/i, '')
    .replace(/<!DOCTYPE[^>]*>/i, '')
    .replace(/<svg[^>]*>/i, '')
    .replace(/<\/svg>/i, '')
    .trim()
  return { viewBox, inner }
}

const ICONS = Object.fromEntries(
  Object.entries(ICON_FILES).map(([path, raw]) => {
    const name = path.split('/').pop().replace(/\.svg$/i, '')
    return [name, parseIcon(raw)]
  }),
)

const DEFAULT_SIZE = 20

export default function Icon({ name, size = DEFAULT_SIZE, className = '', title, ...props }) {
  const icon = ICONS[name]
  if (!icon) {
    return (
      <span
        className={['inline-flex shrink-0 items-center justify-center align-middle rounded bg-surface-2', className].filter(Boolean).join(' ')}
        style={{ width: size, height: size, display: 'inline-flex' }}
        aria-hidden={!title}
        title={title}
        {...props}
      />
    )
  }

  return (
    <svg
      className={['inline-flex shrink-0 items-center justify-center align-middle', className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox={icon.viewBox}
      fill="currentColor"
      aria-hidden={!title}
      role={title ? 'img' : undefined}
      {...props}
    >
      {title && <title>{title}</title>}
      <g dangerouslySetInnerHTML={{ __html: icon.inner }} />
    </svg>
  )
}
