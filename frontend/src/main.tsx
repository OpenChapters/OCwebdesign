// Side-effect import: initializes Sentry from VITE_SENTRY_DSN before
// anything else has a chance to throw. Safe when DSN is unset.
import './sentry';

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sentry } from './sentry';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './components/Toast';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* Wrap the whole tree so any uncaught render error gets captured
        before React unmounts. Falls back to a minimal error page so
        the SPA doesn't show a blank screen. */}
    <Sentry.ErrorBoundary
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
          <div className="max-w-md text-center">
            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              Something went wrong.
            </h1>
            <p className="text-sm text-gray-600 mb-4">
              The page hit an unexpected error. Try reloading; if it
              keeps happening, please file an issue on GitHub.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700"
            >
              Reload
            </button>
          </div>
        </div>
      }
    >
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <ToastProvider>
              <App />
            </ToastProvider>
          </AuthProvider>
        </QueryClientProvider>
      </BrowserRouter>
    </Sentry.ErrorBoundary>
  </React.StrictMode>,
);
