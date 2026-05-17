import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import { useToast } from '../components/Toast';
import BuildStepsList from '../components/BuildStepsList';
import FrozenVersionsPanel from '../components/FrozenVersionsPanel';
import type { BuildJob } from '../types';

export default function BuildStatusPage() {
  const toast = useToast();
  const { id } = useParams<{ id: string }>();
  const bookId = parseInt(id!);

  const { data: bookData } = useQuery({
    queryKey: ['book', bookId],
    queryFn: () => booksApi.detail(bookId),
  });

  const { data, isLoading } = useQuery({
    queryKey: ['build-status', bookId],
    queryFn: () => booksApi.getBuildStatus(bookId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'building' ? 3000 : false;
    },
  });

  const bookTitle = bookData?.title ?? '';
  const status: string = data?.status ?? 'unknown';
  const job: BuildJob | undefined = data?.build_job;

  const hasPdf = Boolean(bookData?.has_pdf);
  const hasHtml = Boolean(bookData?.has_html);
  const canFreeze = status === 'complete' && (hasPdf || hasHtml);

  const statusConfig: Record<string, { label: string; color: string; icon: string }> = {
    queued:   { label: 'Queued',   color: 'text-yellow-600 dark:text-yellow-400', icon: '⏳' },
    building: { label: 'Building', color: 'text-blue-600 dark:text-blue-400',   icon: '🔨' },
    complete: { label: 'Complete', color: 'text-green-600 dark:text-green-400',  icon: '✅' },
    failed:   { label: 'Failed',   color: 'text-red-600 dark:text-red-400',    icon: '❌' },
    draft:    { label: 'Draft',    color: 'text-gray-500 dark:text-gray-400',   icon: '📝' },
  };
  const cfg = statusConfig[status] ?? { label: status, color: 'text-gray-500 dark:text-gray-400', icon: '?' };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/books" className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
          ← My Books
        </Link>
      </div>

      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-1">Build Status</h1>
      {bookTitle && <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">{bookTitle}</p>}

      {isLoading ? (
        <div className="text-gray-500 dark:text-gray-400 py-8">Loading…</div>
      ) : (
        <>
          <div className="flex items-center gap-3 mb-6">
            <span className="text-2xl">{cfg.icon}</span>
            <span className={`text-lg font-semibold ${cfg.color}`}>{cfg.label}</span>
            {(status === 'queued' || status === 'building') && (
              <span className="text-sm text-gray-400 dark:text-gray-500 animate-pulse">Polling every 3s…</span>
            )}
          </div>

          {job && (
            <div className="space-y-4">
              {job.started_at && (
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Started:</span>{' '}
                  {new Date(job.started_at).toLocaleString()}
                </div>
              )}
              {job.finished_at && (
                <div className="text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Finished:</span>{' '}
                  {new Date(job.finished_at).toLocaleString()}
                </div>
              )}
              {job.steps && job.steps.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                    Pipeline
                  </p>
                  <BuildStepsList steps={job.steps} />
                </div>
              )}
              {status === 'complete' && (hasPdf || hasHtml) && (
                <div className="bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 rounded-lg p-4 flex items-center gap-3 flex-wrap">
                  <p className="text-sm font-medium text-green-800 dark:text-green-200 flex-1">
                    {hasPdf && hasHtml
                      ? 'PDF and HTML ready'
                      : hasHtml
                        ? 'HTML ready'
                        : job?.preview_structure
                          ? 'Structure preview ready (TOC + chapter titles only)'
                          : 'PDF ready'}
                  </p>
                  {hasPdf && (
                    <button
                      onClick={async () => {
                        try { await booksApi.downloadPDF(bookId); }
                        catch { toast('Download failed.', 'error'); }
                      }}
                      className="bg-green-700 text-white text-sm px-4 py-2 rounded hover:bg-green-800"
                    >
                      Download PDF
                    </button>
                  )}
                  {hasHtml && (
                    <>
                      <Link
                        to={`/books/${bookId}/read`}
                        className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700"
                      >
                        View Online
                      </Link>
                      <button
                        onClick={async () => {
                          try { await booksApi.downloadHtmlZip(bookId); }
                          catch { toast('Download failed.', 'error'); }
                        }}
                        className="bg-gray-700 text-white text-sm px-4 py-2 rounded hover:bg-gray-800"
                      >
                        Download HTML
                      </button>
                    </>
                  )}
                </div>
              )}

              <FrozenVersionsPanel bookId={bookId} canFreeze={canFreeze} />
              {status === 'failed' && job.error_message && (
                <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg p-4">
                  <p className="text-sm font-medium text-red-800 dark:text-red-300 mb-1">Error</p>
                  <p className="text-xs text-red-700 dark:text-red-300 font-mono whitespace-pre-wrap">
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