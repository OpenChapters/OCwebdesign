import type { BuildStep } from '../types';

const STATUS_ICON: Record<BuildStep['status'], { glyph: string; cls: string; aria: string }> = {
  pending:   { glyph: '○', cls: 'text-gray-300',     aria: 'Pending' },
  running:   { glyph: '◐', cls: 'text-blue-600 dark:text-blue-400 animate-pulse', aria: 'Running' },
  succeeded: { glyph: '✓', cls: 'text-emerald-600 dark:text-emerald-400', aria: 'Succeeded' },
  failed:    { glyph: '✗', cls: 'text-red-600 dark:text-red-400',     aria: 'Failed' },
  skipped:   { glyph: '–', cls: 'text-gray-400 dark:text-gray-500',    aria: 'Skipped' },
};

function durationText(started: string | null, finished: string | null): string {
  if (!started || !finished) return '';
  const ms = new Date(finished).getTime() - new Date(started).getTime();
  if (ms < 0) return '';
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 100) / 10;
  if (s < 90) return `${s} s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s - m * 60);
  return `${m} min ${r} s`;
}

export default function BuildStepsList({ steps }: { steps: BuildStep[] }) {
  if (steps.length === 0) {
    return (
      <p className="text-sm text-gray-400 dark:text-gray-500 italic">
        No progress recorded yet — the build is still spinning up.
      </p>
    );
  }
  const sorted = [...steps].sort((a, b) => a.order - b.order);
  return (
    <ol className="space-y-2">
      {sorted.map((step) => {
        const icon = STATUS_ICON[step.status];
        const duration = durationText(step.started_at, step.finished_at);
        return (
          <li
            key={step.order}
            className={`flex gap-3 items-start border rounded-md px-3 py-2 ${
              step.status === 'failed'
                ? 'border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40'
                : step.status === 'running'
                  ? 'border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40'
                  : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
            }`}
          >
            <span
              className={`shrink-0 mt-0.5 text-base ${icon.cls}`}
              role="img"
              aria-label={icon.aria}
            >
              {icon.glyph}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-medium text-gray-900 dark:text-gray-50">{step.label}</span>
                {step.detail && (
                  <span className="text-xs text-gray-500 dark:text-gray-400 truncate">{step.detail}</span>
                )}
              </div>
              {duration && (
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{duration}</p>
              )}
              {step.status === 'failed' && step.log_tail && (
                <details className="mt-2">
                  <summary className="text-xs text-red-700 dark:text-red-300 cursor-pointer hover:underline">
                    Show log
                  </summary>
                  <pre className="mt-1 text-xs text-red-900 dark:text-red-200 font-mono whitespace-pre-wrap bg-white dark:bg-gray-800 border border-red-200 dark:border-red-900 rounded p-2 max-h-64 overflow-y-auto">
                    {step.log_tail}
                  </pre>
                </details>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Compact summary for the build button / editor header: the currently
 * running step (if any), else the last completed step. Returns null
 * when there are no steps to show.
 */
export function currentStepSummary(steps: BuildStep[]): { label: string; detail: string; order: number; total: number } | null {
  if (steps.length === 0) return null;
  const sorted = [...steps].sort((a, b) => a.order - b.order);
  const running = sorted.find((s) => s.status === 'running');
  const last = sorted[sorted.length - 1];
  const step = running ?? last;
  return {
    label: step.label,
    detail: step.detail,
    order: step.order + 1,
    total: sorted.length,
  };
}
