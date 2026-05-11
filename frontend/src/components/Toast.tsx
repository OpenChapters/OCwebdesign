import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Link } from 'react-router-dom';

type ToastType = 'success' | 'error' | 'info';

interface ToastAction {
  /** Internal SPA route (rendered as a react-router <Link>). */
  to: string;
  /** Button-style label shown inside the toast. */
  label: string;
}

interface Toast {
  id: number;
  message: string;
  type: ToastType;
  action?: ToastAction;
}

interface ToastOptions {
  /** Optional follow-up link inlined in the toast — useful for errors
   *  that point at a remedial page ("Build failed — View details"). */
  action?: ToastAction;
  /** Force-override the auto-dismiss behaviour. Defaults: info/success
   *  dismiss after 4 s; errors stick until the user clicks the close
   *  button or follows the action link. Pass `true` to keep an info
   *  toast sticky, or `false` to make an error self-dismiss. */
  sticky?: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, options?: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, type: ToastType = 'info', options: ToastOptions = {}) => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, message, type, action: options.action }]);

      // Errors stick by default (so the user has time to read them and
      // follow the action link); info/success self-dismiss. Either can
      // be flipped via `sticky`.
      const shouldAutoDismiss =
        options.sticky === true ? false
        : options.sticky === false ? true
        : type !== 'error';

      if (shouldAutoDismiss) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, AUTO_DISMISS_MS);
      }
    },
    [],
  );

  const colors: Record<ToastType, string> = {
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
          >
            <span className="flex-1">{t.message}</span>
            {t.action && (
              <Link
                to={t.action.to}
                onClick={() => dismiss(t.id)}
                className="text-xs font-semibold underline whitespace-nowrap hover:text-white/90 focus:outline-none focus:ring-2 focus:ring-white/60 rounded"
              >
                {t.action.label}
              </Link>
            )}
            <button
              className="text-white/60 hover:text-white text-lg leading-none focus:outline-none focus:ring-2 focus:ring-white/60 rounded"
              aria-label="Dismiss notification"
              onClick={() => dismiss(t.id)}
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
