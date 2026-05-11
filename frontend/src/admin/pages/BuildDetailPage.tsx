import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
  queued: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  building: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300',
  complete: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300',
};

export default function BuildDetailPage() {
  const { id } = useParams<{ id: string }>();
  const buildId = parseInt(id!);
  const queryClient = useQueryClient();

  const { data: build, isLoading } = useQuery({
    queryKey: ['admin-build', buildId],
    queryFn: () => adminApi.buildDetail(buildId),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'queued' || s === 'building' ? 3000 : false;
    },
  });

  async function handleCancel() {
    if (!confirm('Cancel this build?')) return;
    try {
      await adminApi.buildCancel(buildId);
      queryClient.invalidateQueries({ queryKey: ['admin-build', buildId] });
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Cancel failed.');
    }
  }

  async function handleRetry() {
    if (!confirm('Re-queue this build?')) return;
    try {
      await adminApi.buildRetry(buildId);
      queryClient.invalidateQueries({ queryKey: ['admin-build', buildId] });
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Retry failed.');
    }
  }

  async function handleDownload() {
    try {
      await adminApi.buildDownload(buildId);
    } catch {
      alert('Download failed.');
    }
  }

  if (isLoading || !build) {
    return <div className="p-8 text-gray-500 dark:text-gray-400">Loading…</div>;
  }

  const duration =
    build.started_at && build.finished_at
      ? `${Math.round((new Date(build.finished_at).getTime() - new Date(build.started_at).getTime()) / 1000)}s`
      : null;

  return (
    <div className="p-8 max-w-5xl">
      <Link to="/admin-panel/builds" className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
        ← All builds
      </Link>

      <div className="mt-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50">{build.book_title}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Build #{build.id} · {build.user_email}
            </p>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_COLORS[build.status] ?? ''}`}>
            {build.status}
          </span>
        </div>

        {/* Metadata */}
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-gray-500 dark:text-gray-400">Started</p>
            <p className="text-gray-900 dark:text-gray-50">{build.started_at ? new Date(build.started_at).toLocaleString() : '—'}</p>
          </div>
          <div>
            <p className="text-gray-500 dark:text-gray-400">Finished</p>
            <p className="text-gray-900 dark:text-gray-50">{build.finished_at ? new Date(build.finished_at).toLocaleString() : '—'}</p>
          </div>
          <div>
            <p className="text-gray-500 dark:text-gray-400">Duration</p>
            <p className="text-gray-900 dark:text-gray-50">{duration ?? '—'}</p>
          </div>
          <div>
            <p className="text-gray-500 dark:text-gray-400">Celery task</p>
            <p className="text-gray-900 dark:text-gray-50 font-mono text-xs truncate" title={build.celery_task_id}>
              {build.celery_task_id || '—'}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-5 flex gap-3">
          {(build.status === 'queued' || build.status === 'building') && (
            <button
              onClick={handleCancel}
              className="text-xs px-3 py-1.5 rounded font-medium bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
            >
              Cancel build
            </button>
          )}
          {(build.status === 'failed' || build.status === 'complete') && (
            <button
              onClick={handleRetry}
              className="text-xs px-3 py-1.5 rounded font-medium bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40"
            >
              Retry build
            </button>
          )}
          {build.status === 'complete' && build.pdf_path && (
            <button
              onClick={handleDownload}
              className="text-xs px-3 py-1.5 rounded font-medium bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/40"
            >
              Download PDF
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {build.error_message && (
        <div className="mt-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-4">
          <p className="text-sm font-medium text-red-800 dark:text-red-300 mb-1">Error</p>
          <pre className="text-xs text-red-700 dark:text-red-300 whitespace-pre-wrap font-mono">{build.error_message}</pre>
        </div>
      )}

      {/* Build log */}
      {build.log_output && (
        <div className="mt-4">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-2">Build Log</h2>
          <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
            <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
              {build.log_output}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
