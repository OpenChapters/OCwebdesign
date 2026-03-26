import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { adminApi } from '../api';

export default function AnalyticsPage() {
  const { data: buildData } = useQuery({
    queryKey: ['admin-analytics-builds'],
    queryFn: () => adminApi.analyticsBuilds(30),
  });

  const { data: chapterData } = useQuery({
    queryKey: ['admin-analytics-chapters'],
    queryFn: adminApi.analyticsChapters,
  });

  const { data: userData } = useQuery({
    queryKey: ['admin-analytics-users'],
    queryFn: () => adminApi.analyticsUsers(90),
  });

  const builds = (buildData ?? []).map((d) => ({
    ...d,
    date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }));

  const chapters = chapterData ?? [];

  const users = (userData ?? []).map((d) => ({
    ...d,
    date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }));

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Analytics</h1>

      {/* Builds per day */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Builds per day (last 30 days)</h2>
        {builds.length === 0 ? (
          <p className="text-sm text-gray-400">No build data yet.</p>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={builds}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="success" name="Success" fill="#22c55e" stackId="a" />
                <Bar dataKey="failed" name="Failed" fill="#ef4444" stackId="a" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* Most popular chapters */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Most included chapters</h2>
        {chapters.length === 0 ? (
          <p className="text-sm text-gray-400">No data yet.</p>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={Math.max(200, chapters.length * 32)}>
              <BarChart data={chapters} layout="vertical" margin={{ left: 140 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="title"
                  tick={{ fontSize: 11 }}
                  width={130}
                />
                <Tooltip />
                <Bar dataKey="count" name="Inclusions" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* User registrations */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">User registrations (last 90 days)</h2>
        {users.length === 0 ? (
          <p className="text-sm text-gray-400">No registration data yet.</p>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={users}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" name="Registrations" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
    </div>
  );
}
