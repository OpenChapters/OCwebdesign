import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import client from '../api/client';

interface SearchResult {
  chapter_id: number;
  chapter_title: string;
  chabbr: string;
  discipline: { name: string; color_primary: string } | null;
  section_title: string;
  snippet: string;
  read_url: string;
}

interface SearchResponse {
  results: SearchResult[];
  count: number;
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const urlQuery = params.get('q') ?? '';
  const [query, setQuery] = useState(urlQuery);
  const [debouncedQuery, setDebouncedQuery] = useState(urlQuery);

  // Debounce the query to avoid hammering the API on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
      if (query) {
        setParams({ q: query });
      } else {
        setParams({});
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, setParams]);

  const { data, isLoading } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () =>
      client
        .get<SearchResponse>('/chapters/search/', {
          params: { q: debouncedQuery, limit: 50 },
        })
        .then((r) => r.data),
    enabled: debouncedQuery.length >= 2,
  });

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-6">Search Chapters</h1>

      <label htmlFor="full-text-search" className="sr-only">
        Search across all published chapter content
      </label>
      <input
        id="full-text-search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search chapter content…"
        autoFocus
        className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
        Searches across all published chapters with HTML output. Supports phrases in quotes and OR/AND operators.
      </p>

      <div className="mt-6">
        {debouncedQuery.length < 2 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">Type at least 2 characters to search.</p>
        ) : isLoading ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Searching…</p>
        ) : !data || data.count === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">No matches for "{debouncedQuery}".</p>
        ) : (
          <>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
              {data.count} result{data.count === 1 ? '' : 's'}
            </p>
            <ul className="space-y-4">
              {data.results.map((r, i) => (
                <li key={i} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-sm transition-shadow">
                  <Link to={r.read_url} className="block">
                    <div className="flex items-center gap-2 mb-1 text-xs">
                      <span className="font-mono text-gray-500 dark:text-gray-400">{r.chabbr}</span>
                      {r.discipline && (
                        <span
                          className="px-1.5 py-0.5 rounded text-white"
                          style={{ backgroundColor: r.discipline.color_primary }}
                        >
                          {r.discipline.name}
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-50 hover:text-blue-600 dark:hover:text-blue-400">
                      {r.chapter_title}
                      {r.section_title && (
                        <span className="text-gray-500 dark:text-gray-400 font-normal"> — {r.section_title}</span>
                      )}
                    </h3>
                    <p
                      className="text-xs text-gray-600 dark:text-gray-300 mt-1 leading-relaxed [&>mark]:bg-yellow-100 dark:[&>mark]:bg-yellow-700/60 [&>mark]:text-gray-900 dark:[&>mark]:text-yellow-50 [&>mark]:font-semibold"
                      dangerouslySetInnerHTML={{ __html: r.snippet || '' }}
                    />
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
