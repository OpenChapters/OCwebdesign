import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import type { ExampleDifficulty } from '../types';

const DIFFICULTY_LABEL: Record<ExampleDifficulty, string> = {
  introductory: 'Introductory',
  standard: 'Standard',
  advanced: 'Advanced',
};

const DIFFICULTY_BADGE: Record<ExampleDifficulty, string> = {
  introductory: 'bg-emerald-100 text-emerald-800',
  standard: 'bg-blue-100 text-blue-800',
  advanced: 'bg-amber-100 text-amber-800',
};

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n) + '…' : s;
}

interface Props {
  bookId: number;
  onClose: () => void;
  onSaved: (excluded: number[]) => void;
}

export default function ExampleSelectionModal({ bookId, onClose, onSaved }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['examples-available', bookId],
    queryFn: () => booksApi.getExamplesAvailable(bookId),
    staleTime: 0,
  });

  const [excluded, setExcluded] = useState<Set<number>>(new Set());
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data && !initialized) {
      setExcluded(new Set(data.excluded_example_ids ?? []));
      setInitialized(true);
    }
  }, [data, initialized]);

  const groups = data?.groups ?? [];
  const totalExamples = useMemo(
    () => groups.reduce((sum, g) => sum + g.examples.length, 0),
    [groups],
  );
  const selectedCount = totalExamples - excluded.size;

  function toggleOne(id: number) {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setGroupSelected(ids: number[], select: boolean) {
    setExcluded((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (select) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      // Prune ids that no longer correspond to a known example in this book;
      // this keeps the stored list tidy after the user opens the picker.
      const knownIds = new Set<number>();
      for (const g of groups) for (const ex of g.examples) knownIds.add(ex.id);
      const pruned = [...excluded].filter((id) => knownIds.has(id));
      await booksApi.update(bookId, { excluded_example_ids: pruned });
      onSaved(pruned);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Customize examples</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Uncheck any examples you don't want in this build. Selections are
              saved on the book and reused on every future build until changed.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none px-1"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading && <p className="text-gray-500 text-sm py-8 text-center">Loading…</p>}
          {error && (
            <p className="text-red-600 text-sm py-8 text-center">
              Failed to load examples.
            </p>
          )}
          {!isLoading && !error && groups.length === 0 && (
            <p className="text-gray-500 text-sm py-8 text-center">
              No published examples are tagged to any chapter in this book.
            </p>
          )}

          {groups.map((g) => {
            const ids = g.examples.map((e) => e.id);
            const allSelected = ids.every((id) => !excluded.has(id));
            const noneSelected = ids.every((id) => excluded.has(id));
            return (
              <div key={g.chapter.id} className="mb-6">
                <div className="flex items-baseline justify-between mb-2">
                  <h3 className="text-sm font-semibold text-gray-800">
                    {g.chapter.title}{' '}
                    {g.chapter.chabbr && (
                      <span className="font-mono text-xs text-gray-500">
                        ({g.chapter.chabbr})
                      </span>
                    )}
                  </h3>
                  <div className="flex gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => setGroupSelected(ids, true)}
                      disabled={allSelected}
                      className="text-blue-600 hover:text-blue-800 disabled:text-gray-300 disabled:cursor-default"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={() => setGroupSelected(ids, false)}
                      disabled={noneSelected}
                      className="text-blue-600 hover:text-blue-800 disabled:text-gray-300 disabled:cursor-default"
                    >
                      Deselect all
                    </button>
                  </div>
                </div>
                <ul className="space-y-2">
                  {g.examples.map((ex) => {
                    const checked = !excluded.has(ex.id);
                    return (
                      <li
                        key={ex.id}
                        className={`flex gap-3 border rounded-md p-3 ${
                          checked ? 'border-gray-200 bg-white' : 'border-gray-200 bg-gray-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleOne(ex.id)}
                          className="mt-1 shrink-0"
                          id={`ex-${ex.id}`}
                        />
                        <label
                          htmlFor={`ex-${ex.id}`}
                          className="flex-1 cursor-pointer"
                        >
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span
                              className={`text-xs font-medium px-2 py-0.5 rounded-full ${DIFFICULTY_BADGE[ex.difficulty]}`}
                            >
                              {DIFFICULTY_LABEL[ex.difficulty]}
                            </span>
                            {ex.chapter_chabbrs.map((ch) => (
                              <span
                                key={ch}
                                className="text-xs font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
                              >
                                {ch}
                              </span>
                            ))}
                            <span className="text-xs text-gray-400 ml-auto">
                              by {ex.author_display}
                            </span>
                            <a
                              href={`/examples/${ex.id}`}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-xs text-blue-600 hover:text-blue-800"
                              title="Open in a new tab"
                            >
                              Open ↗
                            </a>
                          </div>
                          <pre className="font-mono text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">
                            {truncate(ex.statement_tex, 240)}
                          </pre>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>

        <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
          <p className="text-xs text-gray-500">
            {totalExamples > 0
              ? `${selectedCount} of ${totalExamples} included`
              : ''}
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              disabled={saving}
              className="text-sm border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || isLoading || !!error}
              className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40"
            >
              {saving ? 'Saving…' : 'Save selection'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
