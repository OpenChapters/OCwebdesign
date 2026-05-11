import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
  queued: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200',
  building: 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300',
  complete: 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300',
};

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const userId = parseInt(id!);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ['admin-user', userId],
    queryFn: () => adminApi.userDetail(userId),
  });

  const { data: books = [] } = useQuery({
    queryKey: ['admin-user-books', userId],
    queryFn: () => adminApi.userBooks(userId),
  });

  async function toggleField(field: 'is_active' | 'is_staff') {
    if (!user) return;
    const newVal = !user[field];
    const label = field === 'is_active' ? (newVal ? 'activate' : 'deactivate') : (newVal ? 'grant staff' : 'revoke staff');
    if (!confirm(`Are you sure you want to ${label} this user?`)) return;
    await adminApi.userUpdate(userId, { [field]: newVal });
    queryClient.invalidateQueries({ queryKey: ['admin-user', userId] });
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to permanently delete this user and all their data?')) return;
    if (!confirm('This action cannot be undone. Delete this user?')) return;
    try {
      await adminApi.userDelete(userId);
      navigate('/admin-panel/users');
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Could not delete user.');
    }
  }

  if (isLoading || !user) {
    return <div className="p-8 text-gray-500 dark:text-gray-400">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link to="/admin-panel/users" className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
        ← All users
      </Link>

      <div className="mt-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50">{user.email}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Joined {new Date(user.date_joined).toLocaleDateString()}
              {user.last_login && ` · Last login ${new Date(user.last_login).toLocaleDateString()}`}
            </p>
          </div>
          <div className="flex gap-2">
            {user.is_active ? (
              <span className="text-xs bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 px-2 py-1 rounded-full">active</span>
            ) : (
              <span className="text-xs bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 px-2 py-1 rounded-full">inactive</span>
            )}
            {user.is_staff && (
              <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 px-2 py-1 rounded-full">staff</span>
            )}
            {user.is_superuser && (
              <span className="text-xs bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300 px-2 py-1 rounded-full">superuser</span>
            )}
          </div>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={() => toggleField('is_active')}
            className={`text-xs px-3 py-1.5 rounded font-medium ${
              user.is_active
                ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40'
                : 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/40'
            }`}
          >
            {user.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button
            onClick={() => toggleField('is_staff')}
            className="text-xs px-3 py-1.5 rounded font-medium bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40"
          >
            {user.is_staff ? 'Revoke staff' : 'Grant staff'}
          </button>
          <button
            onClick={handleDelete}
            className="text-xs px-3 py-1.5 rounded font-medium bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40"
          >
            Delete user
          </button>
        </div>
      </div>

      {/* User's books */}
      <div className="mt-6">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">Books ({books.length})</h2>
        {books.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">This user has no books.</p>
        ) : (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Title</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Status</th>
                  <th className="px-4 py-2 font-medium text-gray-500 dark:text-gray-400">Created</th>
                </tr>
              </thead>
              <tbody>
                {books.map((b) => (
                  <tr key={b.id} className="border-b border-gray-100 dark:border-gray-700 last:border-0">
                    <td className="px-4 py-2 text-gray-900 dark:text-gray-50">{b.title}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{new Date(b.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
