import { ICON_PATHS, ICON_VIEWBOX } from './paths'

const DEFAULT_SIZE = 20

export default function Icon({ name, size = DEFAULT_SIZE, className = '', title, ...props }) {
  const path = ICON_PATHS[name]
  if (!path) {
    return (
      <span
        className={`icon icon--missing ${className}`.trim()}
        style={{ width: size, height: size, display: 'inline-flex' }}
        aria-hidden={!title}
        title={title}
        {...props}
      />
    )
  }

  return (
    <svg
      className={`icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox={ICON_VIEWBOX}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden={!title}
      role={title ? 'img' : undefined}
      {...props}
    >
      {title && <title>{title}</title>}
      <path
        d={path}
        stroke="currentColor"
        strokeWidth="16"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
