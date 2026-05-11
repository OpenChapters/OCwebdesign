import { useTheme, type ThemeChoice } from '../contexts/ThemeContext';

const OPTIONS: { value: ThemeChoice; label: string; glyph: string }[] = [
  { value: 'light', label: 'Light', glyph: '☀' },
  { value: 'system', label: 'System', glyph: '◐' },
  { value: 'dark', label: 'Dark', glyph: '☾' },
];

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className="inline-flex items-center rounded-full border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-0.5"
    >
      {OPTIONS.map((opt) => {
        const active = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={opt.label}
            title={opt.label}
            onClick={() => setTheme(opt.value)}
            className={
              'w-7 h-7 inline-flex items-center justify-center rounded-full text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ' +
              (active
                ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-gray-50'
                : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100')
            }
          >
            <span aria-hidden="true">{opt.glyph}</span>
          </button>
        );
      })}
    </div>
  );
}
