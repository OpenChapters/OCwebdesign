import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { HealthCheck } from '../api';

const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  ok:      { bg: 'bg-green-50', text: 'text-green-800', dot: 'bg-green-500' },
  warning: { bg: 'bg-yellow-50', text: 'text-yellow-800', dot: 'bg-yellow-500' },
  error:   { bg: 'bg-red-50', text: 'text-red-800', dot: 'bg-red-500' },
};

function HealthCard({ name, check }: { name: string; check: HealthCheck }) {
  const style = STATUS_STYLES[check.status] ?? STATUS_STYLES.error;
  return (
    <div className={`${style.bg} border border-gray-200 rounded-lg p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-2.5 h-2.5 rounded-full ${style.dot}`} />
        <h3 className={`text-sm font-semibold ${style.text} capitalize`}>{name.replace('_', ' ')}</h3>
        <span className={`ml-auto text-xs font-medium ${style.text}`}>{check.status}</span>
      </div>
      <dl className="text-xs space-y-1">
        {Object.entries(check)
          .filter(([k]) => k !== 'status')
          .map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt className="text-gray-500">{k.replace(/_/g, ' ')}</dt>
              <dd className={`${style.text} font-mono`}>{v == null ? '—' : String(v)}</dd>
            </div>
          ))}
      </dl>
    </div>
  );
}

export default function SystemPage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['admin-system-health'],
    queryFn: adminApi.systemHealth,
    refetchInterval: 15000,
  });

  const { data: github, isLoading: githubLoading } = useQuery({
    queryKey: ['admin-system-github'],
    queryFn: adminApi.systemGitHub,
  });

  return (
    <div className="p-8 max-w-5xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">System Monitoring</h1>

      {/* Overall status */}
      {health && (
        <div className={`mb-6 px-4 py-3 rounded-lg flex items-center gap-2 ${
          health.overall === 'ok' ? 'bg-green-50 text-green-800'
          : health.overall === 'warning' ? 'bg-yellow-50 text-yellow-800'
          : 'bg-red-50 text-red-800'
        }`}>
          <span className={`w-3 h-3 rounded-full ${
            health.overall === 'ok' ? 'bg-green-500'
            : health.overall === 'warning' ? 'bg-yellow-500'
            : 'bg-red-500'
          }`} />
          <span className="text-sm font-semibold">
            Overall: {health.overall === 'ok' ? 'All systems healthy' : health.overall === 'warning' ? 'Some warnings' : 'Issues detected'}
          </span>
        </div>
      )}

      {/* Health checks */}
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Service Health</h2>
      {healthLoading ? (
        <p className="text-gray-500 py-4">Checking services…</p>
      ) : health ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {Object.entries(health.checks).map(([name, check]) => (
            <HealthCard key={name} name={name} check={check as HealthCheck} />
          ))}
        </div>
      ) : null}

      {/* GitHub token status */}
      <h2 className="text-lg font-semibold text-gray-800 mb-3">GitHub API</h2>
      {githubLoading ? (
        <p className="text-gray-500 py-4">Checking GitHub…</p>
      ) : github ? (
        <div className={`border border-gray-200 rounded-lg p-4 ${
          github.status === 'ok' ? 'bg-green-50' : github.status === 'not_configured' ? 'bg-yellow-50' : 'bg-red-50'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2.5 h-2.5 rounded-full ${
              github.status === 'ok' ? 'bg-green-500' : github.status === 'not_configured' ? 'bg-yellow-500' : 'bg-red-500'
            }`} />
            <span className={`text-sm font-semibold ${
              github.status === 'ok' ? 'text-green-800' : github.status === 'not_configured' ? 'text-yellow-800' : 'text-red-800'
            }`}>
              {github.status === 'ok' ? 'Token valid' : github.status === 'not_configured' ? 'Not configured' : github.detail ?? 'Error'}
            </span>
          </div>
          {github.status === 'ok' && (
            <div className="text-xs text-gray-600 space-y-1">
              <div className="flex justify-between">
                <span>Rate limit</span>
                <span className="font-mono">{github.remaining} / {github.rate_limit}</span>
              </div>
              {github.reset_at && (
                <div className="flex justify-between">
                  <span>Resets at</span>
                  <span className="font-mono">{new Date(github.reset_at).toLocaleTimeString()}</span>
                </div>
              )}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
