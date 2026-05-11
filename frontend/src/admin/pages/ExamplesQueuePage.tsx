import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { examplesApi } from '../../api/examples';
import { useToast } from '../../components/Toast';
import type { ExampleStatus } from '../../types';

const STATUS_TABS: { value: ExampleStatus; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'published', label: 'Published' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'draft', label: 'Drafts' },
];

export default function ExamplesQueuePage() {
  const [tab, setTab] = useState<ExampleStatus>('pending');
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['admin-examples', tab],
    queryFn: () => examplesApi.adminQueue(tab),
  });

  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const approveMut = useMutation({
    mutationFn: (id: number) => examplesApi.adminApprove(id),
    onSuccess: () => {
      toast('Approved.', 'success');
      queryClient.invalidateQueries({ queryKey: ['admin-examples'] });
    },
    onError: () => toast('Could not approve.', 'error'),
  });

  const rejectMut = useMutation({
    mutationFn: (id: number) => examplesApi.adminReject(id, rejectReason),
    onSuccess: () => {
      toast('Rejected.', 'success');
      setRejectId(null);
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['admin-examples'] });
    },
    onError: () => toast('Could not reject.', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => examplesApi.adminDelete(id),
    onSuccess: () => {
      toast('Example deleted.', 'success');
      queryClient.invalidateQueries({ queryKey: ['admin-examples'] });
    },
    onError: () => toast('Could not delete.', 'error'),
  });

  function handleDelete(id: number) {
    if (confirm('Permanently delete this example, including any attached figures and the preview PDF? This cannot be undone.')) {
      deleteMut.mutate(id);
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50">Worked examples</h1>
        <Link
          to="/admin-panel/examples/import"
          className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900"
        >
          Batch import…
        </Link>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-300 mb-6">
        Review submitted examples before they appear publicly.
      </p>

      <div className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`text-sm px-4 py-2 border-b-2 -mb-px transition ${
              tab === t.value
                ? 'border-blue-600 text-blue-700 dark:text-blue-300 font-medium'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-gray-500 dark:text-gray-400 py-12 text-center">Loading…</p>}

      {!isLoading && items.length === 0 && (
        <p className="text-gray-400 dark:text-gray-500 py-12 text-center">No examples in this state.</p>
      )}

      <div className="space-y-3">
        {items.map((ex) => (
          <div key={ex.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-1">
                  <span className="font-mono bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">
                    #{ex.id}
                  </span>
                  <span>·</span>
                  <span>by {ex.author_display}</span>
                  <span>·</span>
                  <span>{new Date(ex.created_at).toLocaleDateString()}</span>
                  <span>·</span>
                  <span className="font-medium">{ex.difficulty}</span>
                </div>
                <div className="flex flex-wrap gap-1 mb-2">
                  {ex.chapters.map((ch) => (
                    <span
                      key={ch.id}
                      className="text-xs font-mono bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 px-2 py-0.5 rounded"
                    >
                      {ch.chabbr}
                      {ex.primary_chapter.id === ch.id && '*'}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <Link
                  to={`/examples/${ex.id}`}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Open detail →
                </Link>
                {ex.preview_pdf_url && (
                  <a
                    href={ex.preview_pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-amber-700 dark:text-amber-300 hover:underline"
                  >
                    Open preview PDF ↗
                  </a>
                )}
                {ex.preview_build_log && (
                  <span className="text-xs text-red-600 dark:text-red-400">build failed</span>
                )}
              </div>
            </div>

            <pre className="font-mono text-xs text-gray-700 dark:text-gray-200 whitespace-pre-wrap leading-relaxed bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-2 max-h-32 overflow-y-auto">
              {ex.statement_tex.length > 400
                ? ex.statement_tex.slice(0, 400) + '…'
                : ex.statement_tex}
            </pre>

            {tab === 'rejected' && ex.rejection_reason && (
              <p className="mt-2 text-xs text-red-700 dark:text-red-300">
                <span className="font-semibold">Rejected:</span> {ex.rejection_reason}
              </p>
            )}

            {tab === 'pending' && (
              <div className="mt-3 flex flex-wrap gap-2 items-center">
                {rejectId === ex.id ? (
                  <div className="flex-1 flex gap-2 items-center">
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason for rejection"
                      className="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
                    />
                    <button
                      onClick={() => rejectMut.mutate(ex.id)}
                      disabled={!rejectReason.trim() || rejectMut.isPending}
                      className="text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 disabled:opacity-50"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => { setRejectId(null); setRejectReason(''); }}
                      className="text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 px-2 py-1 rounded"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      onClick={() => approveMut.mutate(ex.id)}
                      disabled={approveMut.isPending}
                      className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded hover:bg-emerald-700 disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => { setRejectId(ex.id); setRejectReason(''); }}
                      className="text-xs text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900 px-3 py-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/40"
                    >
                      Reject…
                    </button>
                    <button
                      onClick={() => handleDelete(ex.id)}
                      disabled={deleteMut.isPending}
                      className="text-xs text-red-700 dark:text-red-300 border border-red-300 dark:border-red-900 px-3 py-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/40 disabled:opacity-50 ml-auto"
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>
            )}

            {tab !== 'pending' && (
              <div className="mt-3 flex justify-end">
                <button
                  onClick={() => handleDelete(ex.id)}
                  disabled={deleteMut.isPending}
                  className="text-xs text-red-700 dark:text-red-300 border border-red-300 dark:border-red-900 px-3 py-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/40 disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
