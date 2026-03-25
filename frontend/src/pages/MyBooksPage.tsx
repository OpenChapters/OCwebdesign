import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { booksApi } from '../api/books';

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

      {isLoading && <div className="text-gray-500 py-8 text-center">Loading…</div>}

      {!isLoading && books.length === 0 && (
        <div className="text-center text-gray-400 py-16">
          No books yet. Create one to get started.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {books.map((book) => (
          <div
            key={book.id}
            className="bg-white border border-gray-200 rounded-lg px-5 py-4 flex items-center gap-4"
          >
            <div className="flex-1 min-w-0">
              <Link
                to={`/books/${book.id}`}
                className="font-semibold text-gray-900 hover:text-blue-600"
              >
                {book.title}
              </Link>
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(book.created_at).toLocaleDateString()}
              </p>
            </div>
            <span
              className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[book.status] ?? STATUS_COLORS.draft}`}
            >
              {book.status}
            </span>
            {book.status === 'complete' && (
              <Link
                to="/library"
                className="text-xs text-blue-600 hover:underline"
              >
                Download
              </Link>
            )}
            {(book.status === 'queued' || book.status === 'building') && (
              <Link
                to={`/books/${book.id}/status`}
                className="text-xs text-blue-600 hover:underline"
              >
                Status
              </Link>
            )}
            <button
              onClick={() => handleDelete(book.id)}
              className="text-xs text-gray-400 hover:text-red-500"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
