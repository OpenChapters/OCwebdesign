import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import { useToast } from '../components/Toast';
import { SkeletonTable } from '../components/Skeleton';

export default function LibraryPage() {
  const toast = useToast();
  const { data: books = [], isLoading } = useQuery({
    queryKey: ['library'],
    queryFn: booksApi.library,
  });

  async function handleDownloadPDF(bookId: number) {
    try {
      await booksApi.downloadPDF(bookId);
    } catch {
      toast('Download failed.', 'error');
    }
  }

  async function handleDownloadHTML(bookId: number) {
    try {
      await booksApi.downloadHtmlZip(bookId);
    } catch {
      toast('Download failed.', 'error');
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Library</h1>
      <p className="text-sm text-gray-500 mb-6">Your completed books are listed here.</p>

      {isLoading && <SkeletonTable rows={3} cols={3} />}

      {!isLoading && books.length === 0 && (
        <div className="text-center py-16">
          <p className="text-4xl mb-3">📖</p>
          <p className="text-lg font-semibold text-gray-700 mb-1">Your library is empty</p>
          <p className="text-sm text-gray-400 mb-4">Completed books will appear here after you build them.</p>
          <Link
            to="/chapters"
            className="inline-block bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700"
          >
            Browse chapters
          </Link>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {books.map((book) => (
          <div
            key={book.id}
            className="bg-white border border-gray-200 rounded-lg px-5 py-4 flex items-center gap-4 flex-wrap"
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
            <Link
              to={`/books/${book.id}/status`}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Build info
            </Link>
            {book.has_pdf && (
              <button
                onClick={() => handleDownloadPDF(book.id)}
                className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
              >
                Download PDF
              </button>
            )}
            {book.has_html && (
              <>
                <Link
                  to={`/books/${book.id}/read`}
                  className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded hover:bg-indigo-700"
                >
                  View Online
                </Link>
                <button
                  onClick={() => handleDownloadHTML(book.id)}
                  className="text-xs bg-gray-700 text-white px-3 py-1.5 rounded hover:bg-gray-800"
                >
                  Download HTML
                </button>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
