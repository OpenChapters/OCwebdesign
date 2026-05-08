import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import { useToast } from '../components/Toast';
import { SkeletonTable } from '../components/Skeleton';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  queued: 'bg-yellow-100 text-yellow-800',
  building: 'bg-blue-100 text-blue-800',
  complete: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

export default function MyBooksPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [newTitle, setNewTitle] = useState('');
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const { data: books = [], isLoading } = useQuery({
    queryKey: ['books'],
    queryFn: booksApi.list,
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const book = await booksApi.create(newTitle.trim());
      queryClient.invalidateQueries({ queryKey: ['books'] });
      navigate(`/books/${book.id}`);
    } finally {
      setCreating(false);
      setNewTitle('');
      setShowForm(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Delete this book?')) return;
    await booksApi.delete(id);
    queryClient.invalidateQueries({ queryKey: ['books'] });
  }

  async function handleDownloadPDF(id: number) {
    try {
      await booksApi.downloadPDF(id);
    } catch {
      toast('Download failed.', 'error');
    }
  }

  async function handleDownloadHTML(id: number) {
    try {
      await booksApi.downloadHtmlZip(id);
    } catch {
      toast('Download failed.', 'error');
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">My Books</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          + New Book
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="flex gap-2 mb-6">
          <input
            type="text"
            placeholder="Book title"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            autoFocus
            required
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={creating}
            className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? 'Creating…' : 'Create'}
          </button>
          <button
            type="button"
            onClick={() => setShowForm(false)}
            className="text-sm text-gray-500 px-3 py-2"
          >
            Cancel
          </button>
        </form>
      )}

      {isLoading && <SkeletonTable rows={3} cols={4} />}

      {!isLoading && books.length === 0 && (
        <div className="text-center py-16">
          <p className="text-4xl mb-3">📚</p>
          <p className="text-lg font-semibold text-gray-700 mb-1">No books yet</p>
          <p className="text-sm text-gray-400 mb-4">Create your first book to start assembling chapters into a custom textbook.</p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700"
          >
            + Create your first book
          </button>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {books.map((book) => {
          const isActive = book.status === 'queued' || book.status === 'building';
          const isComplete = book.status === 'complete';
          return (
            <div
              key={book.id}
              className="bg-white border border-gray-200 rounded-lg px-5 py-4 flex items-center gap-3 flex-wrap"
            >
              <div className="flex-1 min-w-[180px]">
                <Link
                  to={`/books/${book.id}`}
                  className="font-semibold text-gray-900 hover:text-blue-600"
                >
                  {book.title}
                </Link>
                <p className="text-xs text-gray-400 mt-0.5">
                  Updated {new Date(book.updated_at).toLocaleDateString()}
                </p>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[book.status] ?? STATUS_COLORS.draft}`}
              >
                {book.status}
              </span>
              {isComplete && book.has_html && (
                <Link
                  to={`/books/${book.id}/read`}
                  className="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded hover:bg-indigo-700"
                >
                  View Online
                </Link>
              )}
              {isComplete && book.has_pdf && (
                <button
                  onClick={() => handleDownloadPDF(book.id)}
                  className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
                >
                  Download PDF
                </button>
              )}
              {isComplete && book.has_html && (
                <button
                  onClick={() => handleDownloadHTML(book.id)}
                  className="text-xs bg-gray-700 text-white px-3 py-1.5 rounded hover:bg-gray-800"
                >
                  Download HTML
                </button>
              )}
              {(isActive || isComplete || book.status === 'failed') && (
                <Link
                  to={`/books/${book.id}/status`}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Build info
                </Link>
              )}
              {!isActive && (
                <button
                  onClick={() => handleDelete(book.id)}
                  className="text-xs text-gray-400 hover:text-red-500"
                >
                  Delete
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
