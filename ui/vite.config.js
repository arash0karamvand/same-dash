import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
// فقط درخواست‌های /api به بک‌اند Django (پورت 8000) proxy می‌شوند تا در حالت
// توسعه مشکل CORS و کوکی session پیش نیاید (same-origin از نگاه مرورگر).
// احراز هویت هم زیر /api/auth است، بنابراین یک قانون proxy کافی است.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss({
      // باینری Lightning CSS در این محیط موجود نیست (مشابه cssMinify: false).
      optimize: false,
    }),
  ],
  // مینیفای CSS غیرفعال است تا به باینری بومی lightningcss یا پکیج esbuild
  // وابسته نباشیم (در این محیط نصب نیستند). خروجی build همچنان کامل و سالم است؛
  // در صورت نیاز به CSS فشرده، کافی است این گزینه حذف/تغییر داده شود.
  build: {
    cssMinify: false,
  },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
