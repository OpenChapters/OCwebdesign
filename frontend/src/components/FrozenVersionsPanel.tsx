import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import { useToast } from './Toast';
import type { FrozenBook } from '../types';

interface Props {
  bookId: number;
  /** When false, the Freeze button is hidden (book has no completed build yet). */
  canFreeze: boolean;
}

export default function FrozenVersionsPanel({ bookId, canFreeze }: Props) {
  const toast = useToast();
  const qc = useQueryClient();
  const [showFreezeForm, setShowFreezeForm] = useState(false);
  const [label, setLabel] = useState('');

  const { data: frozen = [], isLoading } = useQuery({
    queryKey: ['frozen', bookId],
    queryFn: () => booksApi.listFrozen(bookId),
  });

  const freezeMut = useMutation({
    mutationFn: (lbl: string) => booksApi.freeze(bookId, lbl),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['frozen', bookId] });
      setShowFreezeForm(false);
      setLabel('');
      toast('Frozen. Share URL is ready below.', 'success');
    },
    onError: (e: any) => {
      const msg = e?.response?.data?.detail || 'Freeze failed.';
      toast(msg, 'error');
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => booksApi.deleteFrozen(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['frozen', bookId] });
      toast('Frozen version removed.', 'success');
    },
    onError: () => toast('Could not remove frozen version.', 'error'),
  });

  return (
    <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 mt-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Frozen versions
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Pin this build to a stable share URL students can open without
            logging in. Future rebuilds of this book don&apos;t affect it.
          </p>
        </div>
        {canFreeze && !showFreezeForm && (
          <button
            type="button"
            onClick={() => setShowFreezeForm(true)}
            className="shrink-0 bg-amber-600 text-white text-sm px-3 py-1.5 rounded hover:bg-amber-700"
          >
            Freeze for semester
          </button>
        )}
      </div>

      {showFreezeForm && (
        <form
          className="flex gap-2 mb-3"
          onSubmit={(e) => {
            e.preventDefault();
            freezeMut.mutate(label.trim());
          }}
        >
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label (e.g. Fall 2026)"
            maxLength={200}
            autoFocus
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1.5 text-sm
                       bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100
                       focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
          <button
            type="submit"
            disabled={freezeMut.isPending}
            className="bg-amber-600 text-white text-sm px-3 py-1.5 rounded hover:bg-amber-700 disabled:opacity-50"
          >
            {freezeMut.isPending ? 'Freezing…' : 'Freeze'}
          </button>
          <button
            type="button"
            onClick={() => { setShowFreezeForm(false); setLabel(''); }}
            className="text-sm text-gray-500 dark:text-gray-400 px-2"
          >
            Cancel
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
      ) : frozen.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No frozen versions yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {frozen.map((f) => (
            <FrozenRow key={f.id} frozen={f} onDelete={() => deleteMut.mutate(f.id)} />
          ))}
        </ul>
      )}
    </section>
  );
}

function FrozenRow({ frozen, onDelete }: { frozen: FrozenBook; onDelete: () => void }) {
  const toast = useToast();
  const shareUrl = `${window.location.origin}/frozen/${frozen.share_token}`;

  return (
    <li className="border border-gray-200 dark:border-gray-700 rounded p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {frozen.label || <span className="text-gray-400">Unlabeled</span>}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {new Date(frozen.frozen_at).toLocaleString()}
            {' · '}
            {[
              frozen.has_pdf && 'PDF',
              frozen.has_html && 'HTML',
            ].filter(Boolean).join(' + ') || 'no artifacts'}
            {' · '}
            {frozen.chapter_snapshot.length} chapter
            {frozen.chapter_snapshot.length === 1 ? '' : 's'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (window.confirm('Delete this frozen version? Anyone using the share URL will lose access.')) {
              onDelete();
            }
          }}
          className="shrink-0 text-xs text-red-600 dark:text-red-400 hover:underline"
        >
          Delete
        </button>
      </div>
      <div className="mt-2 flex gap-2 items-center">
        <input
          type="text"
          value={shareUrl}
          readOnly
          onFocus={(e) => e.currentTarget.select()}
          className="flex-1 text-xs font-mono bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded px-2 py-1
                     text-gray-700 dark:text-gray-300"
        />
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(shareUrl);
              toast('Share URL copied.', 'success');
            } catch {
              toast('Copy failed.', 'error');
            }
          }}
          className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-2 py-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          Copy
        </button>
        <a
          href={shareUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700"
        >
          Open
        </a>
      </div>
    </li>
  );
}
