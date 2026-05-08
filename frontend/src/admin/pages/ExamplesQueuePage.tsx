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

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Worked examples</h1>
      <p className="text-sm text-gray-600 mb-6">
        Review submitted examples before they appear publicly.
      </p>

      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`text-sm px-4 py-2 border-b-2 -mb-px transition ${
              tab === t.value
                ? 'border-blue-600 text-blue-700 font-medium'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-gray-500 py-12 text-center">Loading…</p>}

      {!isLoading && items.length === 0 && (
        <p className="text-gray-400 py-12 text-center">No examples in this state.</p>
      )}

      <div className="space-y-3">
        {items.map((ex) => (
          <div key={ex.id} className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                  <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">
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
                      className="text-xs font-mono bg-blue-50 text-blue-800 px-2 py-0.5 rounded"
                    >
                      {ch.chabbr}
                      {ex.primary_chapter.id === ch.id && '*'}
                    </span>
                  ))}
                </div>
              </div>
              <Link
                to={`/examples/${ex.id}`}
                className="text-xs text-blue-600 hover:underline shrink-0"
              >
                Open detail →
              </Link>
            </div>

            <pre className="font-mono text-xs text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 border border-gray-200 rounded p-2 max-h-32 overflow-y-auto">
              {ex.statement_tex.length > 400
                ? ex.statement_tex.slice(0, 400) + '…'
                : ex.statement_tex}
            </pre>

            {tab === 'rejected' && ex.rejection_reason && (
              <p className="mt-2 text-xs text-red-700">
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
                      className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
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
                      className="text-xs text-gray-600 hover:bg-gray-100 px-2 py-1 rounded"
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
                      className="text-xs text-red-600 border border-red-200 px-3 py-1.5 rounded hover:bg-red-50"
                    >
                      Reject…
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
