import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newIsStaff, setNewIsStaff] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', search, page],
    queryFn: () => adminApi.userList({ search: search || undefined, page }),
  });

  const users = data?.results ?? [];
  const totalPages = data ? Math.ceil(data.count / 50) : 1;

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError('');
    setCreating(true);
    try {
      await adminApi.userCreate({ email: newEmail, password: newPassword, is_staff: newIsStaff });
      setShowAddForm(false);
      setNewEmail('');
      setNewPassword('');
      setNewIsStaff(false);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.email) setCreateError(data.email.join(' '));
      else if (data?.password) setCreateError(data.password.join(' '));
      else setCreateError('Failed to create user.');
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(userId: number, email: string) {
    if (!confirm(`Delete user "${email}" and all their data?`)) return;
    if (!confirm('This action cannot be undone. Are you sure?')) return;
    try {
      await adminApi.userDelete(userId);
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    } catch (err: any) {
      alert(err?.response?.data?.detail ?? 'Could not delete user.');
    }
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <div className="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search by email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            + Add User
          </button>
        </div>
      </div>

      {/* Add user form */}
      {showAddForm && (
        <form onSubmit={handleCreate} className="mb-6 bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Create new user</h2>
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-gray-500 mb-1">Password (min 8)</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700 pb-1">
              <input
                type="checkbox"
                checked={newIsStaff}
                onChange={(e) => setNewIsStaff(e.target.checked)}
                className="rounded"
              />
              Staff
            </label>
            <button
              type="submit"
              disabled={creating}
              className="text-sm bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => { setShowAddForm(false); setCreateError(''); }}
              className="text-sm text-gray-500 px-3 py-2"
            >
              Cancel
            </button>
          </div>
          {createError && <p className="text-sm text-red-600 mt-2">{createError}</p>}
        </form>
      )}

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <>
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-left">
                  <th className="px-4 py-2 font-medium text-gray-500">Email</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Joined</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Books</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Last login</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Role</th>
                  <th className="px-4 py-2 font-medium text-gray-500">Status</th>
                  <th className="px-4 py-2 font-medium text-gray-500"></th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No users found.</td></tr>
                )}
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <Link to={`/admin-panel/users/${u.id}`} className="text-blue-600 hover:underline">
                        {u.email}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-gray-500">{new Date(u.date_joined).toLocaleDateString()}</td>
                    <td className="px-4 py-2 text-gray-700">{u.book_count}</td>
                    <td className="px-4 py-2 text-gray-500">
                      {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-2">
                      {u.is_superuser ? (
                        <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">superuser</span>
                      ) : u.is_staff ? (
                        <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">staff</span>
                      ) : (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">user</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      {u.is_active ? (
                        <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">active</span>
                      ) : (
                        <span className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded-full">inactive</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => handleDelete(u.id, u.email)}
                        className="text-xs text-gray-400 hover:text-red-500"
                        title="Delete user"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
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
