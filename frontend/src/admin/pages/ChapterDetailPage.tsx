import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { AdminChapter } from '../api';

export default function ChapterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const chapterId = parseInt(id!);
  const queryClient = useQueryClient();

  const { data: chapter, isLoading } = useQuery({
    queryKey: ['admin-chapter', chapterId],
    queryFn: () => adminApi.chapterDetail(chapterId),
  });

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<AdminChapter>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (chapter) {
      setForm({
        title: chapter.title,
        description: chapter.description,
        chapter_type: chapter.chapter_type,
        keywords: chapter.keywords,
        published: chapter.published,
      });
    }
  }, [chapter?.id]);

  async function handleSave() {
    setSaving(true);
    try {
      await adminApi.chapterUpdate(chapterId, form);
      queryClient.invalidateQueries({ queryKey: ['admin-chapter', chapterId] });
      setEditing(false);
    } catch {
      alert('Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }

  async function togglePublished() {
    if (!chapter) return;
    const action = chapter.published ? 'unpublish' : 'publish';
    if (!confirm(`Are you sure you want to ${action} "${chapter.title}"?`)) return;
    await adminApi.chapterUpdate(chapterId, { published: !chapter.published });
    queryClient.invalidateQueries({ queryKey: ['admin-chapter', chapterId] });
  }

  if (isLoading || !chapter) {
    return <div className="p-8 text-gray-500">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link to="/admin-panel/chapters" className="text-sm text-gray-400 hover:text-gray-600">
        ← All chapters
      </Link>

      <div className="mt-4 bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{chapter.title}</h1>
            <p className="text-sm text-gray-500 mt-1">
              {chapter.chabbr && <span className="font-mono">{chapter.chabbr}</span>}
              {chapter.chabbr && ' · '}
              {chapter.chapter_subdir}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${
              chapter.chapter_type === 'foundational' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
            }`}>
              {chapter.chapter_type}
            </span>
            {chapter.published ? (
              <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">published</span>
            ) : (
              <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded-full">unpublished</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="mt-4 flex gap-3">
          <button
            onClick={togglePublished}
            className={`text-xs px-3 py-1.5 rounded font-medium ${
              chapter.published
                ? 'bg-red-50 text-red-700 hover:bg-red-100'
                : 'bg-green-50 text-green-700 hover:bg-green-100'
            }`}
          >
            {chapter.published ? 'Unpublish' : 'Publish'}
          </button>
          <button
            onClick={() => setEditing(!editing)}
            className="text-xs px-3 py-1.5 rounded font-medium bg-blue-50 text-blue-700 hover:bg-blue-100"
          >
            {editing ? 'Cancel editing' : 'Edit metadata'}
          </button>
        </div>

        {/* Edit form */}
        {editing && (
          <div className="mt-6 space-y-4 border-t border-gray-200 pt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input
                value={form.title ?? ''}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={form.description ?? ''}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                rows={4}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={form.chapter_type ?? 'topical'}
                onChange={(e) => setForm({ ...form, chapter_type: e.target.value as any })}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="topical">Topical</option>
                <option value="foundational">Foundational</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Keywords <span className="text-gray-400 font-normal">(comma-separated)</span>
              </label>
              <input
                value={(form.keywords ?? []).join(', ')}
                onChange={(e) => setForm({ ...form, keywords: e.target.value.split(',').map((k) => k.trim()).filter(Boolean) })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        )}
      </div>

      {/* Info panels */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* TOC */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Table of Contents</h2>
          {chapter.toc.length > 0 ? (
            <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1">
              {chapter.toc.map((item, i) => <li key={i}>{item}</li>)}
            </ol>
          ) : (
            <p className="text-sm text-gray-400">No TOC entries.</p>
          )}
        </div>

        {/* Metadata */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Details</h2>
          <dl className="text-sm space-y-2">
            <div>
              <dt className="text-gray-500">Authors</dt>
              <dd className="text-gray-900">{chapter.authors.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Dependencies</dt>
              <dd className="text-gray-900 font-mono text-xs">{chapter.depends_on.join(', ') || 'None'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Entry file</dt>
              <dd className="text-gray-900 font-mono text-xs">{chapter.latex_entry_file}</dd>
            </div>
            <div>
              <dt className="text-gray-500">GitHub path</dt>
              <dd className="text-gray-900 font-mono text-xs">{chapter.github_repo}/{chapter.chapter_subdir}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Last synced</dt>
              <dd className="text-gray-900">{new Date(chapter.cached_at).toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
