import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { DashboardData, Worker } from '../api';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  queued: 'bg-yellow-100 text-yellow-800',
  building: 'bg-blue-100 text-blue-800',
  complete: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

function WorkerCard({ worker }: { worker: Worker }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-3">
      <span className="w-2.5 h-2.5 rounded-full bg-green-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{worker.name}</p>
        <p className="text-xs text-gray-500">
          {worker.pool} &middot; concurrency {worker.concurrency}
        </p>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold text-gray-900">{worker.active_tasks}</p>
        <p className="text-xs text-gray-400">active</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-dashboard'],
    queryFn: adminApi.dashboard,
    refetchInterval: 15000,
  });

  const { data: workersData } = useQuery({
    queryKey: ['admin-workers'],
    queryFn: adminApi.workers,
    refetchInterval: 10000,
  });

  if (isLoading || !data) {
    return <div className="p-8 text-gray-500">Loading dashboard…</div>;
  }

  const d = data as DashboardData;
  const workers = workersData?.workers ?? [];
  const totalBooks = d.books.draft + d.books.queued + d.books.building + d.books.complete + d.books.failed;

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Users" value={d.users.total} sub={`+${d.users.new_this_week} this week`} />
        <StatCard label="Chapters" value={d.chapters.published} sub={`${d.chapters.unpublished} unpublished`} />
        <StatCard label="Books" value={totalBooks} sub={`${d.books.complete} complete`} />
        <StatCard label="Builds today" value={d.builds_today.total} sub={`${d.builds_today.success} ok / ${d.builds_today.failed} failed`} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Draft" value={d.books.draft} />
        <StatCard label="Queued" value={d.books.queued} />
        <StatCard label="Building" value={d.books.building} />
        <StatCard label="Failed" value={d.books.failed} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard label="PDFs stored" value={d.storage.pdf_count} sub={`${d.storage.pdf_size_mb} MB`} />
        <StatCard label="Workers online" value={workers.length} sub={workers.length === 0 ? 'No workers detected' : ''} />
        <StatCard label="Active tasks" value={workers.reduce((s, w) => s + w.active_tasks, 0)} />
      </div>

      {/* Workers */}
      {workers.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Workers</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {workers.map((w) => (
              <WorkerCard key={w.name} worker={w} />
            ))}
          </div>
          {workersData?.error && (
            <p className="text-xs text-red-500 mt-2">{workersData.error}</p>
          )}
        </div>
      )}

      {/* Recent builds */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Recent Builds</h2>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-2 font-medium text-gray-500">Book</th>
                <th className="px-4 py-2 font-medium text-gray-500">User</th>
                <th className="px-4 py-2 font-medium text-gray-500">Status</th>
                <th className="px-4 py-2 font-medium text-gray-500">Started</th>
                <th className="px-4 py-2 font-medium text-gray-500">Duration</th>
              </tr>
            </thead>
            <tbody>
              {d.recent_builds.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                    No builds yet.
                  </td>
                </tr>
              )}
              {d.recent_builds.map((b) => {
                const duration =
                  b.started_at && b.finished_at
                    ? `${Math.round((new Date(b.finished_at).getTime() - new Date(b.started_at).getTime()) / 1000)}s`
                    : '—';
                return (
                  <tr key={b.id} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2 text-gray-900">{b.book_title}</td>
                    <td className="px-4 py-2 text-gray-500">{b.user_email}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500">
                      {b.started_at ? new Date(b.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2 text-gray-500">{duration}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
