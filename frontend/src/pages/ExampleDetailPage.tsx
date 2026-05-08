import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { examplesApi } from '../api/examples';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../components/Toast';
import type { ExampleDetail, ExampleDifficulty, ExampleStatus } from '../types';

const DIFFICULTY_LABEL: Record<ExampleDifficulty, string> = {
  introductory: 'Introductory',
  standard: 'Standard',
  advanced: 'Advanced',
};

const STATUS_BADGE: Record<ExampleStatus, string> = {
  draft: 'bg-gray-100 text-gray-700',
  pending: 'bg-amber-100 text-amber-800',
  published: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-700',
};

const STATUS_LABEL: Record<ExampleStatus, string> = {
  draft: 'Draft',
  pending: 'Pending review',
  published: 'Published',
  rejected: 'Rejected',
};

async function fetchExample(id: number, isAuthenticated: boolean): Promise<ExampleDetail> {
  // Public endpoint only returns PUBLISHED. If 404 and authenticated,
  // fall back to /manage/ which returns own non-published.
  try {
    return await examplesApi.detail(id);
  } catch (err: any) {
    if (err?.response?.status === 404 && isAuthenticated) {
      return await examplesApi.manage(id);
    }
    throw err;
  }
}

export default function ExampleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const exampleId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isAuthenticated, isStaff } = useAuth();
  const [showSolution, setShowSolution] = useState(true);

  const { data: example, isLoading, error } = useQuery({
    queryKey: ['example', exampleId],
    queryFn: () => fetchExample(exampleId, isAuthenticated),
    enabled: !Number.isNaN(exampleId),
  });

  const submitMut = useMutation({
    mutationFn: () => examplesApi.submit(exampleId),
    onSuccess: () => {
      toast('Submitted for review.', 'success');
      queryClient.invalidateQueries({ queryKey: ['example', exampleId] });
    },
    onError: (err: any) => {
      toast(err?.response?.data?.detail || 'Could not submit.', 'error');
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => examplesApi.remove(exampleId),
    onSuccess: () => {
      toast('Draft deleted.', 'success');
      navigate('/examples');
    },
    onError: () => toast('Could not delete.', 'error'),
  });

  const approveMut = useMutation({
    mutationFn: () => examplesApi.adminApprove(exampleId),
    onSuccess: () => {
      toast('Approved and published.', 'success');
      queryClient.invalidateQueries({ queryKey: ['example', exampleId] });
    },
    onError: () => toast('Could not approve.', 'error'),
  });

  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const rejectMut = useMutation({
    mutationFn: () => examplesApi.adminReject(exampleId, rejectReason),
    onSuccess: () => {
      toast('Rejected.', 'success');
      setShowReject(false);
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['example', exampleId] });
    },
    onError: () => toast('Could not reject.', 'error'),
  });

  if (isLoading) return <div className="max-w-4xl mx-auto px-6 py-8 text-gray-500">Loading…</div>;
  if (error || !example) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8 text-center">
        <p className="text-lg text-gray-700 mb-1">Example not found</p>
        <Link to="/examples" className="text-sm text-blue-600 hover:underline">
          Back to examples
        </Link>
      </div>
    );
  }

  const isOwn = example.status !== 'published'; // /manage/ would only return own
  const canEdit = isOwn && (example.status === 'draft' || example.status === 'rejected');
  const canSubmit = canEdit;
  const canDelete = isOwn && example.status === 'draft';

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <Link to="/examples" className="text-sm text-blue-600 hover:underline">
        ← Back to examples
      </Link>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_BADGE[example.status]}`}>
          {STATUS_LABEL[example.status]}
        </span>
        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
          {DIFFICULTY_LABEL[example.difficulty]}
        </span>
        {example.chapters.map((ch) => (
          <Link
            key={ch.id}
            to={`/chapters/${ch.id}`}
            className="text-xs font-mono bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-0.5 rounded"
          >
            {ch.chabbr}
            {example.primary_chapter.id === ch.id && (
              <span className="ml-1 text-gray-400">(primary)</span>
            )}
          </Link>
        ))}
      </div>

      <h1 className="mt-3 text-xl font-bold text-gray-900">
        Example #{example.id}
      </h1>
      <p className="text-sm text-gray-500">by {example.author_display}</p>

      {example.status === 'rejected' && example.rejection_reason && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-red-800 uppercase tracking-wide mb-1">
            Rejection reason
          </p>
          <p className="text-sm text-red-900 whitespace-pre-wrap">{example.rejection_reason}</p>
        </div>
      )}

      {example.preview_pdf_url && (
        <div className="mt-4">
          <a
            href={example.preview_pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm bg-amber-600 text-white px-4 py-2 rounded-lg hover:bg-amber-700"
          >
            Open preview PDF ↗
          </a>
        </div>
      )}

      {/* Build log only ever surfaces here for the author/admin paths
          (the public detail endpoint is reached only for PUBLISHED). */}
      {example.preview_build_log && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-red-800 uppercase tracking-wide mb-1">
            Last preview build failed
          </p>
          <pre className="font-mono text-xs text-red-900 bg-red-50 border border-red-200 rounded-lg p-3 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
            {example.preview_build_log}
          </pre>
        </div>
      )}

      <section className="mt-6">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
          Statement
        </h2>
        <pre className="font-mono text-sm bg-gray-50 border border-gray-200 rounded-lg p-4 whitespace-pre-wrap leading-relaxed">
          {example.statement_tex}
        </pre>
      </section>

      <section className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Solution
          </h2>
          <button
            onClick={() => setShowSolution((s) => !s)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showSolution ? 'Hide' : 'Show'}
          </button>
        </div>
        {showSolution ? (
          <pre className="font-mono text-sm bg-gray-50 border border-gray-200 rounded-lg p-4 whitespace-pre-wrap leading-relaxed">
            {example.solution_tex}
          </pre>
        ) : (
          <p className="text-sm text-gray-400 italic px-4 py-3 bg-gray-50 border border-dashed border-gray-200 rounded-lg">
            Solution hidden. Click "Show" to reveal.
          </p>
        )}
      </section>

      <p className="mt-6 text-xs text-gray-400">
        License: {example.license}
      </p>

      {/* Author actions */}
      {(canEdit || canSubmit || canDelete) && (
        <div className="mt-6 flex flex-wrap gap-2 border-t border-gray-200 pt-4">
          {canEdit && (
            <Link
              to={`/examples/${example.id}/edit`}
              className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900"
            >
              Edit
            </Link>
          )}
          {canSubmit && (
            <button
              onClick={() => submitMut.mutate()}
              disabled={submitMut.isPending}
              className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {submitMut.isPending ? 'Submitting…' : 'Submit for review'}
            </button>
          )}
          {canDelete && (
            <button
              onClick={() => {
                if (confirm('Delete this draft? This cannot be undone.')) {
                  deleteMut.mutate();
                }
              }}
              disabled={deleteMut.isPending}
              className="text-sm text-red-600 border border-red-200 px-4 py-2 rounded-lg hover:bg-red-50 disabled:opacity-50"
            >
              Delete draft
            </button>
          )}
        </div>
      )}

      {/* Admin actions */}
      {isStaff && example.status === 'pending' && (
        <div className="mt-6 border-t border-gray-200 pt-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Admin review
          </p>
          {!showReject ? (
            <div className="flex gap-2">
              <button
                onClick={() => approveMut.mutate()}
                disabled={approveMut.isPending}
                className="text-sm bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 disabled:opacity-50"
              >
                {approveMut.isPending ? 'Approving…' : 'Approve & publish'}
              </button>
              <button
                onClick={() => setShowReject(true)}
                className="text-sm text-red-600 border border-red-200 px-4 py-2 rounded-lg hover:bg-red-50"
              >
                Reject…
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Reason for rejection (visible to author)"
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => rejectMut.mutate()}
                  disabled={rejectMut.isPending || !rejectReason.trim()}
                  className="text-sm bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  {rejectMut.isPending ? 'Rejecting…' : 'Confirm rejection'}
                </button>
                <button
                  onClick={() => { setShowReject(false); setRejectReason(''); }}
                  className="text-sm text-gray-600 px-4 py-2 rounded-lg hover:bg-gray-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
