import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-green-100 text-green-800',
  update: 'bg-blue-100 text-blue-800',
  delete: 'bg-red-100 text-red-800',
  cancel: 'bg-yellow-100 text-yellow-800',
  retry: 'bg-purple-100 text-purple-800',
};

function actionColor(action: string) {
  for (const [key, cls] of Object.entries(ACTION_COLORS)) {
    if (action.includes(key)) return cls;
  }
  return 'bg-gray-100 text-gray-700';
}

export default function AuditLogPage() {
  const [actionFilter, setActionFilter] = useState('');
  const [targetFilter, setTargetFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-audit', actionFilter, targetFilter, userFilter, page],
    queryFn: () => adminApi.auditLog({
      action: actionFilter || undefined,
      target_type: targetFilter || undefined,
      user: userFilter || undefined,
      page,
    }),
  });

  const entries = data?.results ?? [];
  const totalPages = data ? Math.ceil(data.count / data.page_size) : 1;

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Audit Log</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter by action…"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={targetFilter}
          onChange={(e) => { setTargetFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All targets</option>
          <option value="User">User</option>
          <option value="Chapter">Chapter</option>
          <option value="BuildJob">BuildJob</option>
          <option value="SiteSetting">SiteSetting</option>
        </select>
        <input
          type="text"
          placeholder="Filter by user email…"
          value={userFilter}
          onChange={(e) => { setUserFilter(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <>
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500">Time</th>
                  <th className="px-4 py-2 font-medium text-gray-500">User</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Action</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Target</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Details</th>
                  <th className="px-4 py-2 font-medium text-gray-500">IP</th>
                </tr>
              </thead>
              <tbody>
                {entries.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No audit entries found.</td></tr>
                )}
                {entries.map((e) => (
                  <tr key={e.id} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap text-xs">
                      {new Date(e.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-gray-700">{e.user_email ?? '—'}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${actionColor(e.action)}`}>
                        {e.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600 text-xs">
                      {e.target_type}{e.target_id != null ? ` #${e.target_id}` : ''}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate" title={JSON.stringify(e.detail)}>
                      {Object.keys(e.detail).length > 0 ? JSON.stringify(e.detail) : '—'}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-400 font-mono">{e.ip_address ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => i + 1).map((p) => (
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
