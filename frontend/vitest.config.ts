import { defineConfig, mergeConfig } from 'vitest/config'

import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}', 'worker/**/*.test.ts'],
      css: false,
      coverage: { include: ['src/**/*.{ts,tsx}'], exclude: ['src/components/ui/**', 'src/test/**', 'src/main.tsx'] },
    },
  }),
)
