import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { examplesApi } from '../api/examples';
import MathText from './MathText';
import type { ExampleStatus, ExampleVersion } from '../types';

const STATUS_LABEL: Record<ExampleStatus, string> = {
  draft: 'Draft',
  pending: 'Pending review',
  published: 'Published',
  rejected: 'Rejected',
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function VersionRow({ v }: { v: ExampleVersion }) {
  const [open, setOpen] = useState(false);
  const editor = v.editor_display ?? 'Unknown';
  return (
    <li className="border border-gray-200 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md"
      >
        <span className="text-xs font-mono text-gray-500 dark:text-gray-400 shrink-0">
          v{v.version_no}
        </span>
        <span className="text-sm text-gray-700 dark:text-gray-200 flex-1 min-w-0 truncate">
          {editor}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0 hidden sm:inline">
          {formatDate(v.created_at)}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 space-y-3 text-sm">
          <p className="text-xs text-gray-400 dark:text-gray-500 sm:hidden">
            {formatDate(v.created_at)}
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200">
              {STATUS_LABEL[v.snapshot.status] ?? v.snapshot.status}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300">
              {v.snapshot.difficulty}
            </span>
            {v.snapshot.primary_chapter_chabbr && (
              <span className="font-mono px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200">
                {v.snapshot.primary_chapter_chabbr}
                <span className="ml-1 text-gray-400 dark:text-gray-500">(primary)</span>
              </span>
            )}
            {v.snapshot.chapters_chabbrs
              .filter((c) => c !== v.snapshot.primary_chapter_chabbr)
              .map((c) => (
                <span
                  key={c}
                  className="font-mono px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200"
                >
                  {c}
                </span>
              ))}
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
              Statement
            </p>
            <MathText
              source={v.snapshot.statement_tex}
              className="text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md p-3"
            />
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
              Solution
            </p>
            <MathText
              source={v.snapshot.solution_tex}
              className="text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md p-3"
            />
          </div>
        </div>
      )}
    </li>
  );
}

export default function ExampleVersionHistory({ exampleId }: { exampleId: number }) {
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ['example-versions', exampleId],
    queryFn: () => examplesApi.versions(exampleId),
    enabled: expanded,
  });

  return (
    <section className="mt-6 border-t border-gray-200 dark:border-gray-700 pt-4">
      <button
        type="button"
        onClick={() => setExpanded((s) => !s)}
        aria-expanded={expanded}
        className="flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide hover:text-gray-700 dark:hover:text-gray-200"
      >
        <span aria-hidden="true">{expanded ? '▾' : '▸'}</span>
        Revision history
        {data && data.length > 0 && (
          <span className="text-gray-400 dark:text-gray-500 normal-case font-normal tracking-normal">
            ({data.length})
          </span>
        )}
      </button>
      {expanded && (
        <div className="mt-3">
          {isLoading && (
            <p className="text-sm text-gray-400 dark:text-gray-500 italic">Loading history…</p>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">Could not load history.</p>
          )}
          {data && data.length === 0 && (
            <p className="text-sm text-gray-400 dark:text-gray-500 italic">
              No prior versions — this example has not been edited yet.
            </p>
          )}
          {data && data.length > 0 && (
            <ul className="space-y-2">
              {data.map((v) => (
                <VersionRow key={v.version_no} v={v} />
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
