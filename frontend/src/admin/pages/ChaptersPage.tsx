import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';

export default function ChaptersPage() {
  const [search, setSearch] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [updatingThumbs, setUpdatingThumbs] = useState(false);
  const [updatingTOC, setUpdatingTOC] = useState(false);
  const [buildingHtml, setBuildingHtml] = useState(false);
  const [syncOutput, setSyncOutput] = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['admin-chapters', search],
    queryFn: () => adminApi.chapterList({ search: search || undefined }),
  });

  const chapters = data?.results ?? [];

  async function handleSync() {
    if (!confirm('Sync the chapter catalog from GitHub?')) return;
    setSyncing(true);
    setSyncOutput('');
    try {
      const result = await adminApi.chapterSync();
      setSyncOutput(result.output || result.detail);
      queryClient.invalidateQueries({ queryKey: ['admin-chapters'] });
    } catch (err: any) {
      setSyncOutput(err?.response?.data?.output || err?.response?.data?.detail || 'Sync failed.');
    } finally {
      setSyncing(false);
    }
  }

  async function handleUpdateThumbnails() {
    if (!confirm('Check for updated header images and regenerate thumbnails?')) return;
    setUpdatingThumbs(true);
    setSyncOutput('');
    try {
      const result = await adminApi.chapterUpdateThumbnails();
      const lines = [result.detail];
      if (result.updated.length > 0) lines.push(`Updated: ${result.updated.join(', ')}`);
      if (result.errors.length > 0) lines.push(`Errors: ${result.errors.join('; ')}`);
      if (result.skipped.length > 0) lines.push(`Skipped: ${result.skipped.length} chapter(s)`);
      setSyncOutput(lines.join('\n'));
    } catch (err: any) {
      setSyncOutput(err?.response?.data?.detail || 'Thumbnail update failed.');
    } finally {
      setUpdatingThumbs(false);
    }
  }

  async function handleBuildHtml(mode: 'all' | 'stale') {
    const message = mode === 'stale'
      ? 'Build HTML only for chapters whose source has changed since their last HTML build?'
      : 'Rebuild HTML output for ALL published chapters? This may take several minutes.';
    if (!confirm(message)) return;
    setBuildingHtml(true);
    setSyncOutput('');
    try {
      const result = await adminApi.chapterBuildHtml({ mode });
      setSyncOutput(result.detail);
      queryClient.invalidateQueries({ queryKey: ['admin-chapters'] });
    } catch (err: any) {
      setSyncOutput(err?.response?.data?.detail || 'HTML build failed.');
    } finally {
      setBuildingHtml(false);
    }
  }

  async function handleUpdateTOC() {
    if (!confirm('Re-extract section headings from .tex files on GitHub and update TOC?')) return;
    setUpdatingTOC(true);
    setSyncOutput('');
    try {
      const result = await adminApi.chapterUpdateTOC();
      const lines = [result.detail];
      if (result.updated.length > 0) lines.push(`Updated: ${result.updated.join(', ')}`);
      if (result.errors.length > 0) lines.push(`Errors: ${result.errors.join('; ')}`);
      if (result.skipped.length > 0) lines.push(`Skipped: ${result.skipped.length} chapter(s)`);
      setSyncOutput(lines.join('\n'));
      queryClient.invalidateQueries({ queryKey: ['admin-chapters'] });
    } catch (err: any) {
      setSyncOutput(err?.response?.data?.detail || 'TOC update failed.');
    } finally {
      setUpdatingTOC(false);
    }
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Chapters</h1>
        <div className="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search title, chabbr…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => handleBuildHtml('stale')}
            disabled={buildingHtml}
            className="text-sm border border-green-300 text-green-700 px-4 py-2 rounded-lg hover:bg-green-50 disabled:opacity-50"
            title="Build HTML only for chapters whose source has changed"
          >
            {buildingHtml ? 'Building…' : 'Build Stale HTML'}
          </button>
          <button
            onClick={() => handleBuildHtml('all')}
            disabled={buildingHtml}
            className="text-sm border border-green-300 text-green-700 px-4 py-2 rounded-lg hover:bg-green-50 disabled:opacity-50"
            title="Rebuild HTML for every published chapter"
          >
            {buildingHtml ? 'Building…' : 'Rebuild All HTML'}
          </button>
          <button
            onClick={handleUpdateTOC}
            disabled={updatingTOC}
            className="text-sm border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            {updatingTOC ? 'Updating…' : 'Update TOC'}
          </button>
          <button
            onClick={handleUpdateThumbnails}
            disabled={updatingThumbs}
            className="text-sm border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            {updatingThumbs ? 'Updating…' : 'Update Thumbnails'}
          </button>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-50"
          >
            {syncing ? 'Syncing…' : 'Sync from GitHub'}
          </button>
        </div>
      </div>

      {syncOutput && (
        <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-500 uppercase">Sync output</p>
            <button onClick={() => setSyncOutput('')} className="text-xs text-gray-400 hover:text-gray-600">Dismiss</button>
          </div>
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{syncOutput}</pre>
        </div>
      )}

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-2 font-medium text-gray-500">Title</th>
                <th className="px-4 py-2 font-medium text-gray-500">Abbr</th>
                <th className="px-4 py-2 font-medium text-gray-500">Type</th>
                <th className="px-4 py-2 font-medium text-gray-500">Published</th>
                <th className="px-4 py-2 font-medium text-gray-500">Dependencies</th>
                <th className="px-4 py-2 font-medium text-gray-500">Last synced</th>
              </tr>
            </thead>
            <tbody>
              {chapters.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No chapters found.</td></tr>
              )}
              {chapters.map((ch) => (
                <tr key={ch.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-2">
                    <Link to={`/admin-panel/chapters/${ch.id}`} className="text-blue-600 hover:underline">
                      {ch.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-600">{ch.chabbr || '—'}</td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      ch.chapter_type === 'foundational'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-purple-100 text-purple-800'
                    }`}>
                      {ch.chapter_type}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {ch.published ? (
                      <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full">yes</span>
                    ) : (
                      <span className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded-full">no</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {ch.depends_on.length > 0 ? ch.depends_on.join(', ') : '—'}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {new Date(ch.cached_at).toLocaleDateString()}
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
