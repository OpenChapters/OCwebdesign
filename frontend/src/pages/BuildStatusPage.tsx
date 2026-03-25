import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';

export default function BuildStatusPage() {
  const { id } = useParams<{ id: string }>();
  const bookId = parseInt(id!);

  const { data, isLoading } = useQuery({
    queryKey: ['build-status', bookId],
    queryFn: () => booksApi.getBuildStatus(bookId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'building' ? 3000 : false;
    },
  });

  const status: string = data?.status ?? 'unknown';
  const job = data?.build_job;

  const statusConfig: Record<string, { label: string; color: string; icon: string }> = {
    queued:   { label: 'Queued',   color: 'text-yellow-600', icon: '⏳' },
    building: { label: 'Building', color: 'text-blue-600',   icon: '🔨' },
    complete: { label: 'Complete', color: 'text-green-600',  icon: '✅' },
    failed:   { label: 'Failed',   color: 'text-red-600',    icon: '❌' },
    draft:    { label: 'Draft',    color: 'text-gray-500',   icon: '📝' },
  };
  const cfg = statusConfig[status] ?? { label: status, color: 'text-gray-500', icon: '?' };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/books" className="text-sm text-gray-400 hover:text-gray-600">
          ← My Books
        </Link>
      </div>

      <h1 className="text-2xl font-bold text-gray-900 mb-2">Build Status</h1>

      {isLoading ? (
        <div className="text-gray-500 py-8">Loading…</div>
      ) : (
        <>
          <div className="flex items-center gap-3 mb-6">
            <span className="text-2xl">{cfg.icon}</span>
            <span className={`text-lg font-semibold ${cfg.color}`}>{cfg.label}</span>
            {(status === 'queued' || status === 'building') && (
              <span className="text-sm text-gray-400 animate-pulse">Polling every 3s…</span>
            )}
          </div>

          {job && (
            <div className="space-y-4">
              {job.started_at && (
                <div className="text-sm text-gray-600">
                  <span className="font-medium">Started:</span>{' '}
                  {new Date(job.started_at).toLocaleString()}
                </div>
              )}
              {job.finished_at && (
                <div className="text-sm text-gray-600">
                  <span className="font-medium">Finished:</span>{' '}
                  {new Date(job.finished_at).toLocaleString()}
                </div>
              )}
              {status === 'complete' && job.pdf_path && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-green-800 mb-1">PDF ready</p>
                  <p className="text-xs text-green-700 font-mono break-all">{job.pdf_path}</p>
                </div>
              )}
              {status === 'failed' && job.error_message && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm font-medium text-red-800 mb-1">Error</p>
                  <p className="text-xs text-red-700 font-mono whitespace-pre-wrap">
                    {job.error_message}
                  </p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
