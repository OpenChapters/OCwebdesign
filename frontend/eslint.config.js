import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'vite.config.ts'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // The React 19-era hooks plugin flags every setState-in-effect as
      // an error. Real bugs exist there, but the codebase has many
      // pre-existing patterns that work fine — keep them visible as
      // warnings rather than blocking the build.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/set-state-in-render': 'warn',
      // We hit `any` in a few places where third-party SDK shapes are
      // genuinely dynamic (Turnstile widget, Sentry global). Downgrade
      // rather than disable so it stays visible.
      '@typescript-eslint/no-explicit-any': 'warn',
      // `_`-prefixed args/vars are an opt-out for known-unused params.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
);
