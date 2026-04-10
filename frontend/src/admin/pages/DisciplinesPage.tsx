import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, type AdminDiscipline } from '../api';

export default function DisciplinesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AdminDiscipline | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: '',
    slug: '',
    description: '',
    github_repo: '',
    github_src_path: 'src',
    color_primary: '#2563eb',
    order: 0,
    published: true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const { data: disciplines = [], isLoading } = useQuery({
    queryKey: ['admin-disciplines'],
    queryFn: () => adminApi.disciplineList(),
  });

  function openCreate() {
    setEditing(null);
    setForm({
      name: '',
      slug: '',
      description: '',
      github_repo: '',
      github_src_path: 'src',
      color_primary: '#2563eb',
      order: disciplines.length,
      published: true,
    });
    setCreating(true);
    setError('');
  }

  function openEdit(disc: AdminDiscipline) {
    setCreating(false);
    setForm({
      name: disc.name,
      slug: disc.slug,
      description: disc.description,
      github_repo: disc.github_repo,
      github_src_path: disc.github_src_path,
      color_primary: disc.color_primary,
      order: disc.order,
      published: disc.published,
    });
    setEditing(disc);
    setError('');
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setError('');
  }

  function slugify(name: string) {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
  }

  async function handleSave() {
    setSaving(true);
    setError('');
    try {
      if (creating) {
        await adminApi.disciplineCreate(form);
      } else if (editing) {
        await adminApi.disciplineUpdate(editing.id, form);
      }
      queryClient.invalidateQueries({ queryKey: ['admin-disciplines'] });
      closeForm();
    } catch (err: any) {
      const detail = err?.response?.data;
      if (detail && typeof detail === 'object') {
        const msgs = Object.entries(detail).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        setError(msgs.join('; '));
      } else {
        setError('Failed to save discipline.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(disc: AdminDiscipline) {
    if (!confirm(`Delete discipline "${disc.name}"? Chapters in this discipline will become unassigned.`)) return;
    try {
      await adminApi.disciplineDelete(disc.id);
      queryClient.invalidateQueries({ queryKey: ['admin-disciplines'] });
      if (editing?.id === disc.id) closeForm();
    } catch {
      alert('Failed to delete discipline.');
    }
  }

  const showForm = creating || editing !== null;

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Disciplines</h1>
        <button
          onClick={openCreate}
          className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900"
        >
          + New Discipline
        </button>
      </div>

      {showForm && (
        <div className="mb-6 bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">
            {creating ? 'Create Discipline' : `Edit: ${editing!.name}`}
          </h2>
          {error && (
            <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => {
                  const name = e.target.value;
                  setForm((f) => ({
                    ...f,
                    name,
                    ...(creating ? { slug: slugify(name) } : {}),
                  }));
                }}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Slug</label>
              <input
                type="text"
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">GitHub Repo</label>
              <input
                type="text"
                value={form.github_repo}
                onChange={(e) => setForm((f) => ({ ...f, github_repo: e.target.value }))}
                placeholder="OpenChapters/OpenChapters"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Source Path</label>
              <input
                type="text"
                value={form.github_src_path}
                onChange={(e) => setForm((f) => ({ ...f, github_src_path: e.target.value }))}
                placeholder="src"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={form.color_primary}
                  onChange={(e) => setForm((f) => ({ ...f, color_primary: e.target.value }))}
                  className="h-9 w-12 rounded border border-gray-300 cursor-pointer"
                />
                <input
                  type="text"
                  value={form.color_primary}
                  onChange={(e) => setForm((f) => ({ ...f, color_primary: e.target.value }))}
                  className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Display Order</label>
              <input
                type="number"
                value={form.order}
                onChange={(e) => setForm((f) => ({ ...f, order: parseInt(e.target.value) || 0 }))}
                className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-center gap-2 col-span-2">
              <input
                type="checkbox"
                id="disc-published"
                checked={form.published}
                onChange={(e) => setForm((f) => ({ ...f, published: e.target.checked }))}
                className="rounded border-gray-300"
              />
              <label htmlFor="disc-published" className="text-sm text-gray-700">Published</label>
            </div>
          </div>
          <div className="flex items-center gap-3 mt-5">
            <button
              onClick={handleSave}
              disabled={saving || !form.name || !form.slug}
              className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : creating ? 'Create' : 'Save Changes'}
            </button>
            <button
              onClick={closeForm}
              className="text-sm text-gray-600 px-4 py-2 rounded-lg hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-2 font-medium text-gray-500 w-8">Order</th>
                <th className="px-4 py-2 font-medium text-gray-500">Color</th>
                <th className="px-4 py-2 font-medium text-gray-500">Name</th>
                <th className="px-4 py-2 font-medium text-gray-500">Slug</th>
                <th className="px-4 py-2 font-medium text-gray-500">Repo</th>
                <th className="px-4 py-2 font-medium text-gray-500">Chapters</th>
                <th className="px-4 py-2 font-medium text-gray-500">Published</th>
                <th className="px-4 py-2 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {disciplines.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No disciplines found.</td></tr>
              )}
              {disciplines.map((disc) => (
                <tr key={disc.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500">{disc.order}</td>
                  <td className="px-4 py-2">
                    <span
                      className="inline-block w-5 h-5 rounded border border-gray-200"
                      style={{ backgroundColor: disc.color_primary }}
                      title={disc.color_primary}
                    />
                  </td>
                  <td className="px-4 py-2 font-medium text-gray-900">{disc.name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-600">{disc.slug}</td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-600">{disc.github_repo}</td>
                  <td className="px-4 py-2 text-gray-600">{disc.chapter_count}</td>
                  <td className="px-4 py-2">
                    {disc.published ? (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">yes</span>
                    ) : (
                      <span className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded-full">no</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEdit(disc)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(disc)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
