import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  queued: 'bg-yellow-100 text-yellow-800',
  building: 'bg-blue-100 text-blue-800',
  complete: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
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
        <h1 className="text-2xl font-bold text-gray-900">Builds</h1>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <>
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500">Book</th>
                  <th className="px-4 py-2 font-medium text-gray-500">User</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Status</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Started</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Duration</th>
                  <th className="px-4 py-2 font-medium text-gray-500">PDF</th>
                  <th className="px-4 py-2 font-medium text-gray-500"></th>
                </tr>
              </thead>
              <tbody>
                {builds.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No builds found.</td></tr>
                )}
                {builds.map((b) => {
                  const duration =
                    b.started_at && b.finished_at
                      ? `${Math.round((new Date(b.finished_at).getTime() - new Date(b.started_at).getTime()) / 1000)}s`
                      : '—';
                  return (
                    <tr key={b.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-2 text-gray-900">{b.book_title}</td>
                      <td className="px-4 py-2 text-gray-500">{b.user_email}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                          {b.status}
                        </span>
                        {b.has_error && <span className="ml-1 text-red-500 text-xs" title="Has error">!</span>}
                      </td>
                      <td className="px-4 py-2 text-gray-500">
                        {b.started_at ? new Date(b.started_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{duration}</td>
                      <td className="px-4 py-2 text-gray-500">
                        {b.pdf_size_mb != null ? `${b.pdf_size_mb} MB` : '—'}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Link
                          to={`/admin-panel/builds/${b.id}`}
                          className="text-xs text-blue-600 hover:underline"
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
                    p === page ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
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
