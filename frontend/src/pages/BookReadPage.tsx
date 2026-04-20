import { useParams, Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';

export default function BookReadPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const bookId = parseInt(id!);

  // Deep-link support: ?node=node-2.html#anchor.
  // Default to index.html (the lwarp TOC landing page) so readers
  // start at the full contents list rather than the first chapter.
  const searchParams = new URLSearchParams(location.search);
  const node = searchParams.get('node') || 'index.html';
  const anchor = location.hash || '';

  const { data: book, isLoading } = useQuery({
    queryKey: ['book', bookId],
    queryFn: () => booksApi.detail(bookId),
  });

  // Iframe requests cannot send the Authorization header, so mint a
  // short-lived signed token to carry in the query string.
  const { data: token } = useQuery({
    queryKey: ['book-html-token', bookId],
    queryFn: () => booksApi.htmlAccessToken(bookId),
    enabled: Boolean(book?.has_html),
    staleTime: 3 * 60 * 60 * 1000, // refresh before the 4-hour token expires
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (!book || !book.html_built_at) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-gray-500 mb-4">HTML version not available for this book.</p>
          <Link to="/library" className="text-blue-600 hover:underline text-sm">
            Back to library
          </Link>
        </div>
      </div>
    );
  }

  const iframeSrc = token
    ? `/api/books/${id}/html/${node}?t=${encodeURIComponent(token)}${anchor}`
    : '';

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-4 shrink-0">
        <Link to="/library" className="text-sm text-gray-500 hover:text-gray-700">
          &larr; Library
        </Link>
        <h1 className="text-sm font-semibold text-gray-900 truncate">{book.title}</h1>
      </div>

      {iframeSrc ? (
        <iframe
          src={iframeSrc}
          title={book.title}
          style={{ width: '100%', height: 'calc(100vh - 48px)', border: 'none' }}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Preparing viewer…
        </div>
      )}
    </div>
  );
}
