import { defineConfig } from 'vitest/config';

// Small source-contract tests for the dependency-free browser shell.
export default defineConfig({
  test: {
    environment: 'happy-dom',
    include: ['browser/tests/unit/**/*.test.{js,mjs,ts}'],
    coverage: {
      reporter: ['text', 'lcov'],
      include: ['browser/static/**/*.{js,mjs}'],
    },
  },
});
