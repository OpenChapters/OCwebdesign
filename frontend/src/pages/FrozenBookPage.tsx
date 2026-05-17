import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { frozenApi, frozenPdfUrl, frozenHtmlUrl } from '../api/frozen';

export default function FrozenBookPage() {
  const { token } = useParams<{ token: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['frozen-public', token],
    queryFn: () => frozenApi.getByToken(token!),
    enabled: !!token,
    retry: false,
  });

  if (isLoading) {
    return <div className="max-w-2xl mx-auto px-6 py-16 text-center text-gray-500 dark:text-gray-400">Loading…</div>;
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-50 mb-2">Not found</h1>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          This share link is invalid or the frozen book has been removed.
        </p>
        <Link to="/" className="mt-6 inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline">
          Back to OpenChapters
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="text-xs text-gray-400 dark:text-gray-500 mb-2 uppercase tracking-wide">
        Frozen edition
        {data.label && (
          <>
            <span className="mx-2">·</span>
            <span className="text-gray-600 dark:text-gray-300 normal-case">{data.label}</span>
          </>
        )}
      </div>

      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-50">
        {data.title_snapshot}
      </h1>
      {data.author_snapshot && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          assembled by {data.author_snapshot}
        </p>
      )}
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
        Frozen on {new Date(data.frozen_at).toLocaleDateString()}
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        {data.has_pdf && (
          <a
            href={frozenPdfUrl(token!)}
            className="bg-green-700 text-white text-sm px-4 py-2 rounded hover:bg-green-800"
          >
            Download PDF
          </a>
        )}
        {data.has_html && (
          <a
            href={frozenHtmlUrl(token!)}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700"
          >
            Read Online
          </a>
        )}
      </div>

      <section className="mt-10">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
          Chapters in this edition
        </h2>
        <ol className="border border-gray-200 dark:border-gray-700 rounded-lg divide-y divide-gray-100 dark:divide-gray-700">
          {data.chapter_snapshot.map((ch, i) => (
            <li key={i} className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-gray-900 dark:text-gray-100 truncate">
                  {ch.title}
                </p>
                {ch.chabbr && (
                  <p className="text-xs text-gray-400 dark:text-gray-500 font-mono">
                    {ch.chabbr}
                    {ch.commit_sha && <> · <span title={ch.commit_sha}>{ch.commit_sha.slice(0, 8)}</span></>}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
          Pinned to specific chapter versions. Author updates to upstream
          chapters do not affect this edition.
        </p>
      </section>

      <div className="mt-10 pt-6 border-t border-gray-200 dark:border-gray-700">
        <Link to="/" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          OpenChapters home
        </Link>
      </div>
    </div>
  );
}
