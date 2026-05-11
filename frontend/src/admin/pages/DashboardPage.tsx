import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { DashboardData, Worker } from '../api';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-gray-50 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
  queued: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  building: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300',
  complete: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300',
};

function WorkerCard({ worker }: { worker: Worker }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex items-center gap-3">
      <span className="w-2.5 h-2.5 rounded-full bg-green-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-gray-50 truncate">{worker.name}</p>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {worker.pool} &middot; concurrency {worker.concurrency}
        </p>
      </div>
      <div className="text-right">
        <p className="text-sm font-semibold text-gray-900 dark:text-gray-50">{worker.active_tasks}</p>
        <p className="text-xs text-gray-400 dark:text-gray-500">active</p>
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
    return <div className="p-8 text-gray-500 dark:text-gray-400">Loading dashboard…</div>;
  }

  const d = data as DashboardData;
  const workers = workersData?.workers ?? [];
  const totalBooks = d.books.draft + d.books.queued + d.books.building + d.books.complete + d.books.failed;

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-6">Dashboard</h1>

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
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">Workers</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {workers.map((w) => (
              <WorkerCard key={w.name} worker={w} />
            ))}
          </div>
          {workersData?.error && (
            <p className="text-xs text-red-500 dark:text-red-400 mt-2">{workersData.error}</p>
          )}
        </div>
      )}

      {/* Recent builds */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">Recent Builds</h2>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Book</th>
                <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">User</th>
                <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Started</th>
                <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Duration</th>
              </tr>
            </thead>
            <tbody>
              {d.recent_builds.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-400 dark:text-gray-500">
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
                  <tr key={b.id} className="border-b border-gray-100 dark:border-gray-700 last:border-0">
                    <td className="px-4 py-2 text-gray-900 dark:text-gray-50">{b.book_title}</td>
                    <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{b.user_email}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                      {b.started_at ? new Date(b.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{duration}</td>
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
