import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { chaptersApi } from '../api/chapters';

export default function CatalogPage() {
  const [selectedDiscipline, setSelectedDiscipline] = useState('');

  const { data: disciplines = [] } = useQuery({
    queryKey: ['disciplines'],
    queryFn: () => chaptersApi.disciplines(),
    staleTime: 300_000,
  });

  const { data: chapters = [], isLoading } = useQuery({
    queryKey: ['catalog-all'],
    queryFn: () => chaptersApi.listAll(),
    staleTime: 60_000,
  });

  const filtered = selectedDiscipline
    ? chapters.filter((c) => c.discipline?.slug === selectedDiscipline)
    : chapters;

  return (
    <div className="p-4 sm:p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Chapter catalog</h1>
        <p className="text-sm text-gray-600">
          All published chapters in the OpenChapters collection. Useful as a reference
          when planning a new contribution. Download the CSV for offline use.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <label htmlFor="catalog-discipline" className="sr-only">
            Filter by discipline
          </label>
          <select
            id="catalog-discipline"
            value={selectedDiscipline}
            onChange={(e) => setSelectedDiscipline(e.target.value)}
            className="w-full sm:w-auto border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All disciplines</option>
            {disciplines.map((d) => (
              <option key={d.id} value={d.slug}>{d.name}</option>
            ))}
          </select>
        </div>
        <a
          href="/api/chapters/catalog.csv"
          download
          className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 text-center"
        >
          Download CSV
        </a>
      </div>

      {isLoading ? (
        <p className="text-gray-500 py-8 text-center">Loading…</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="px-4 py-2 font-medium text-gray-500">Title</th>
                <th className="px-4 py-2 font-medium text-gray-500">Abbr</th>
                <th className="px-4 py-2 font-medium text-gray-500">Discipline</th>
                <th className="px-4 py-2 font-medium text-gray-500">Type</th>
                <th className="px-4 py-2 font-medium text-gray-500">Authors</th>
                <th className="px-4 py-2 font-medium text-gray-500">Last updated</th>
                <th className="px-4 py-2 font-medium text-gray-500 text-right">Examples</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                    No chapters.
                  </td>
                </tr>
              )}
              {filtered.map((c) => (
                <tr key={c.id} className="border-b border-gray-100 last:border-0">
                  <td className="px-4 py-2 text-gray-900">{c.title}</td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-600">
                    {c.chabbr || '—'}
                  </td>
                  <td className="px-4 py-2 text-gray-700">
                    {c.discipline?.name || '—'}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      c.chapter_type === 'foundational'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-purple-100 text-purple-800'
                    }`}>
                      {c.chapter_type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-600">
                    {c.authors.length > 0 ? c.authors.join('; ') : '—'}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {c.last_updated ? new Date(c.last_updated).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-700 text-right tabular-nums">
                    {c.examples_count > 0 ? (
                      <Link
                        to={`/examples?chapter=${c.chabbr}`}
                        className="text-blue-600 hover:underline"
                      >
                        {c.examples_count}
                      </Link>
                    ) : (
                      <span className="text-gray-300">0</span>
                    )}
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
