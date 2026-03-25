import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';

export default function LibraryPage() {
  const { data: books = [], isLoading } = useQuery({
    queryKey: ['library'],
    queryFn: booksApi.library,
  });

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Library</h1>
      <p className="text-sm text-gray-500 mb-6">Your completed books are listed here.</p>

      {isLoading && <div className="text-gray-500 py-8 text-center">Loading…</div>}

      {!isLoading && books.length === 0 && (
        <div className="text-center text-gray-400 py-16">
          No completed books yet. Build a book to see it here.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {books.map((book) => (
          <div
            key={book.id}
            className="bg-white border border-gray-200 rounded-lg px-5 py-4 flex items-center gap-4"
          >
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900">{book.title}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                Completed {new Date(book.updated_at).toLocaleDateString()}
              </p>
            </div>
            <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full font-medium">
              complete
            </span>
            <a
              href={`/api/books/${book.id}/build/status/`}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-600 hover:underline"
            >
              View status / PDF path
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
