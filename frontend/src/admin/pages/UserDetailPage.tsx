import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  queued: 'bg-yellow-100 text-yellow-800',
  building: 'bg-blue-100 text-blue-800',
  complete: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
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
    return <div className="p-8 text-gray-500">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link to="/admin-panel/users" className="text-sm text-gray-400 hover:text-gray-600">
        ← All users
      </Link>

      <div className="mt-4 bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{user.email}</h1>
            <p className="text-sm text-gray-500 mt-1">
              Joined {new Date(user.date_joined).toLocaleDateString()}
              {user.last_login && ` · Last login ${new Date(user.last_login).toLocaleDateString()}`}
            </p>
          </div>
          <div className="flex gap-2">
            {user.is_active ? (
              <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">active</span>
            ) : (
              <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded-full">inactive</span>
            )}
            {user.is_staff && (
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">staff</span>
            )}
            {user.is_superuser && (
              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">superuser</span>
            )}
          </div>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            onClick={() => toggleField('is_active')}
            className={`text-xs px-3 py-1.5 rounded font-medium ${
              user.is_active
                ? 'bg-red-50 text-red-700 hover:bg-red-100'
                : 'bg-green-50 text-green-700 hover:bg-green-100'
            }`}
          >
            {user.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button
            onClick={() => toggleField('is_staff')}
            className="text-xs px-3 py-1.5 rounded font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
          >
            {user.is_staff ? 'Revoke staff' : 'Grant staff'}
          </button>
          <button
            onClick={handleDelete}
            className="text-xs px-3 py-1.5 rounded font-medium bg-red-50 text-red-700 hover:bg-red-100"
          >
            Delete user
          </button>
        </div>
      </div>

      {/* User's books */}
      <div className="mt-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Books ({books.length})</h2>
        {books.length === 0 ? (
          <p className="text-sm text-gray-400">This user has no books.</p>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500">Title</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Status</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody>
                {books.map((b) => (
                  <tr key={b.id} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2 text-gray-900">{b.title}</td>
                    <td className="px-4 py-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[b.status] ?? ''}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500">{new Date(b.created_at).toLocaleDateString()}</td>
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
