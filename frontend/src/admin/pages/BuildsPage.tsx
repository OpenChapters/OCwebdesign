import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
  queued: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  building: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300',
  complete: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300',
};

const STATUS_OPTIONS = ['', 'draft', 'queued', 'building', 'complete', 'failed'];

export default function BuildsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-builds', search, statusFilter, page],
    queryFn: () => adminApi.buildList({
      search: search || undefined,
      status: statusFilter || undefined,
      page,
    }),
    refetchInterval: 10000,
  });

  const builds = data?.results ?? [];
  const totalPages = data ? Math.ceil(data.count / data.page_size) : 1;

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50">Builds</h1>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            type="search"
            placeholder="Search title or email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-500 dark:text-gray-400 py-8 text-center">Loading…</p>
      ) : (
        <>
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Book</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">User</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Started</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Duration</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">PDF</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400"></th>
                </tr>
              </thead>
              <tbody>
                {builds.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No builds found.</td></tr>
                )}
                {builds.map((b) => {
                  const duration =
                    b.started_at && b.finished_at
                      ? `${Math.round((new Date(b.finished_at).getTime() - new Date(b.started_at).getTime()) / 1000)}s`
                      : '—';
                  return (
                    <tr key={b.id} className="border-b border-gray-100 dark:border-gray-700 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-700">
                      <td className="px-4 py-2 text-gray-900 dark:text-gray-50">{b.book_title}</td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{b.user_email}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                          {b.status}
                        </span>
                        {b.has_error && <span className="ml-1 text-red-500 dark:text-red-400 text-xs" title="Has error">!</span>}
                      </td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                        {b.started_at ? new Date(b.started_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{duration}</td>
                      <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                        {b.pdf_size_mb != null ? `${b.pdf_size_mb} MB` : '—'}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Link
                          to={`/admin-panel/builds/${b.id}`}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          Details
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`text-sm px-3 py-1 rounded ${
                    p === page ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
