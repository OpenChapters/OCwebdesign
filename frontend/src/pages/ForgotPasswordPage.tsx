import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post('/api/auth/forgot-password/', { email });
    } catch {
      // Always show success to prevent email enumeration
    }
    setSent(true);
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center px-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-2">Reset password</h1>

        {sent ? (
          <>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
              If an account with that email exists, we've sent a password reset link. Check your inbox.
            </p>
            <p className="text-sm text-gray-400 dark:text-gray-500">
              Didn't receive it? Check your spam folder, or{' '}
              <button onClick={() => setSent(false)} className="text-blue-600 dark:text-blue-400 hover:underline">try again</button>.
            </p>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              Enter your email address and we'll send you a link to reset your password.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="forgot-email" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Email</label>
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
          </>
        )}

        <p className="text-sm text-gray-500 dark:text-gray-400 mt-4 text-center">
          <Link to="/login" className="text-blue-600 dark:text-blue-400 hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
