import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastContextValue {
  toast: (message: string, type?: Toast['type']) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const colors: Record<string, string> = {
    success: 'bg-green-600',
    error: 'bg-red-600',
    info: 'bg-gray-800',
  };

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container — bottom-center on mobile, bottom-right on md+ */}
      <div
        className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 z-50 flex flex-col gap-2 md:max-w-sm pointer-events-none"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.type === 'error' ? 'alert' : 'status'}
            className={`${colors[t.type]} text-white text-sm px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-[slideIn_0.2s_ease-out] pointer-events-auto`}
            onClick={() => dismiss(t.id)}
          >
            <span className="flex-1">{t.message}</span>
            <button
              className="text-white/60 hover:text-white text-lg leading-none focus:outline-none focus:ring-2 focus:ring-white/60 rounded"
              aria-label="Dismiss notification"
              onClick={(e) => { e.stopPropagation(); dismiss(t.id); }}
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx.toast;
}
