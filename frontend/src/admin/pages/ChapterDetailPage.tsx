import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { AdminChapterUpdatePayload } from '../api';

export default function ChapterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const chapterId = parseInt(id!);
  const queryClient = useQueryClient();

  const { data: chapter, isLoading } = useQuery({
    queryKey: ['admin-chapter', chapterId],
    queryFn: () => adminApi.chapterDetail(chapterId),
  });

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<AdminChapterUpdatePayload>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (chapter) {
      setForm({
        published: chapter.published,
        reviewer_name: chapter.reviewer_name,
        reviewed_at: chapter.reviewed_at,
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
    return <div className="p-8 text-gray-500 dark:text-gray-400">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link to="/admin-panel/chapters" className="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300">
        ← All chapters
      </Link>

      <div className="mt-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-50">{chapter.title}</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {chapter.chabbr && <span className="font-mono">{chapter.chabbr}</span>}
              {chapter.chabbr && ' · '}
              {chapter.chapter_subdir}
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${
              chapter.chapter_type === 'foundational' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300' : 'bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300'
            }`}>
              {chapter.chapter_type}
            </span>
            {chapter.published ? (
              <span className="text-xs bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 px-2 py-1 rounded-full">published</span>
            ) : (
              <span className="text-xs bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 px-2 py-1 rounded-full">unpublished</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="mt-4 flex gap-3">
          <button
            onClick={togglePublished}
            className={`text-xs px-3 py-1.5 rounded font-medium ${
              chapter.published
                ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/40'
                : 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300 hover:bg-green-100 dark:hover:bg-green-900/40'
            }`}
          >
            {chapter.published ? 'Unpublish' : 'Publish'}
          </button>
          <button
            onClick={() => setEditing(!editing)}
            className="text-xs px-3 py-1.5 rounded font-medium bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40"
          >
            {editing ? 'Cancel editing' : 'Edit metadata'}
          </button>
          <a
            href={chapter.github_edit_url}
            target="_blank"
            rel="noopener noreferrer"
            title="Open chapter.json in the GitHub web editor. Submit your change as a PR; the next sync will pick it up."
            className="text-xs px-3 py-1.5 rounded font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            ✏ Edit chapter.json on GitHub
          </a>
        </div>

        {/* Edit form — admin-curation fields only. Title, description,
            keywords, type, authors, TOC, dependencies and cover live in
            chapter.json on GitHub; edit them there via PR. */}
        {editing && (
          <div className="mt-6 space-y-4 border-t border-gray-200 dark:border-gray-700 pt-4">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Title, authors, description, keywords, TOC and other content
              metadata are owned by the author and live in <code className="font-mono">chapter.json</code>.
              Edit them on GitHub (links in the Details panel below) and merge
              the PR; the next sync will pick them up.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Reviewer Name</label>
                <input
                  value={form.reviewer_name ?? ''}
                  onChange={(e) => setForm({ ...form, reviewer_name: e.target.value })}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Review Date</label>
                <input
                  type="date"
                  value={form.reviewed_at ? new Date(form.reviewed_at).toISOString().slice(0, 10) : ''}
                  onChange={(e) => setForm({ ...form, reviewed_at: e.target.value ? new Date(e.target.value + 'T00:00:00Z').toISOString() : null })}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
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
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Table of Contents</h2>
          {chapter.toc.length > 0 ? (
            <ol className="list-decimal list-inside text-sm text-gray-600 dark:text-gray-300 space-y-1">
              {chapter.toc.map((item, i) => <li key={i}>{item}</li>)}
            </ol>
          ) : (
            <p className="text-sm text-gray-400 dark:text-gray-500">No TOC entries.</p>
          )}
        </div>

        {/* Metadata */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">Details</h2>
          <dl className="text-sm space-y-2">
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Authors</dt>
              <dd className="text-gray-900 dark:text-gray-50">
                {chapter.authors.length > 0
                  ? chapter.authors.map((name, i) => {
                      const url = chapter.author_urls?.[name];
                      return (
                        <span key={name}>
                          {i > 0 && ', '}
                          {url ? (
                            <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">{name}</a>
                          ) : name}
                        </span>
                      );
                    })
                  : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Dependencies</dt>
              <dd className="text-gray-900 dark:text-gray-50 font-mono text-xs">{chapter.depends_on.join(', ') || 'None'}</dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Entry file</dt>
              <dd className="text-gray-900 dark:text-gray-50 font-mono text-xs">{chapter.latex_entry_file}</dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">GitHub path</dt>
              <dd className="text-gray-900 dark:text-gray-50 font-mono text-xs">{chapter.github_repo}/{chapter.chapter_subdir}</dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Reviewer</dt>
              <dd className="text-gray-900 dark:text-gray-50">
                {chapter.reviewer_name || '—'}
                {chapter.reviewed_at && ` (${new Date(chapter.reviewed_at).toLocaleDateString()})`}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 dark:text-gray-400">Last synced</dt>
              <dd className="text-gray-900 dark:text-gray-50">{new Date(chapter.cached_at).toLocaleString()}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
