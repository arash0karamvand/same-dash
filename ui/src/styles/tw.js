/**
 * Tailwind CSS class name utility
 */

export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

export default cn;
