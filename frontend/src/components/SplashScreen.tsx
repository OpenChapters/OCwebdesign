import { useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useSiteConfig } from '../hooks/useSiteConfig';
import { useFocusTrap } from '../hooks/useFocusTrap';

const SESSION_KEY = 'oc.splashSeen';
const DISABLED_KEY = 'oc.splashDisabled';
const LANDING_PATHS = new Set(['/', '/chapters']);

export default function SplashScreen() {
  const { data: config } = useSiteConfig();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isPreview = searchParams.get('splash') === 'preview';

  const [visible, setVisible] = useState(false);
  const [closing, setClosing] = useState(false);
  const [dontShow, setDontShow] = useState(false);

  const shouldRender = useMemo(() => {
    if (!config?.splash_enabled) return false;
    if (!LANDING_PATHS.has(location.pathname)) return false;
    if (isPreview) return true;
    try {
      if (localStorage.getItem(DISABLED_KEY) === '1') return false;
      if (sessionStorage.getItem(SESSION_KEY) === '1') return false;
    } catch {
      // Storage blocked (e.g. strict private mode) — fall through and show.
    }
    return true;
  }, [config, location.pathname, isPreview]);

  useEffect(() => {
    if (shouldRender) {
      setVisible(true);
      setClosing(false);
    }
  }, [shouldRender]);

  const handleDismiss = useMemo(
    () => () => {
      if (!isPreview) {
        try {
          sessionStorage.setItem(SESSION_KEY, '1');
          if (dontShow) localStorage.setItem(DISABLED_KEY, '1');
        } catch {
          // Ignore storage errors — UI still dismisses.
        }
      }
      setClosing(true);
      window.setTimeout(() => setVisible(false), 300);
    },
    [dontShow, isPreview],
  );

  useEffect(() => {
    if (!visible || closing) return;
    const duration = config?.splash_duration_ms ?? 10000;
    const t = window.setTimeout(handleDismiss, duration);
    return () => window.clearTimeout(t);
  }, [visible, closing, config?.splash_duration_ms, handleDismiss]);

  const containerRef = useFocusTrap<HTMLDivElement>(visible && !closing, handleDismiss);

  if (!visible) return null;

  const imageUrl = config?.splash_image_url || '/splash-placeholder.svg';
  const caption = config?.splash_caption || '';
  const isSvg = imageUrl.split('?')[0].toLowerCase().endsWith('.svg');

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to OpenChapters"
      onClick={handleDismiss}
      className={
        'fixed inset-0 z-50 flex items-center justify-center bg-black ' +
        'transition-opacity duration-300 cursor-pointer ' +
        (closing ? 'opacity-0 pointer-events-none' : 'opacity-100')
      }
    >
      {isSvg ? (
        // Safari renders CSS-animated SVGs poorly via <img> — frames persist
        // as artifacts. <object> embeds the SVG as a live document so the
        // animations run cleanly. pointer-events: none keeps the overlay's
        // click-to-dismiss behavior intact. Scaling/cropping is handled by
        // the SVG's own preserveAspectRatio="slice", so no object-fit needed.
        <object
          type="image/svg+xml"
          data={imageUrl}
          aria-label=""
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
      ) : (
        <img
          src={imageUrl}
          alt=""
          className="absolute inset-0 w-full h-full object-cover select-none"
          draggable={false}
        />
      )}

      {caption && (
        <p
          className="absolute left-1/2 -translate-x-1/2 bottom-28 max-w-2xl px-6 text-center
                     text-white text-lg drop-shadow"
        >
          {caption}
        </p>
      )}

      {/* "Don't show again" — stopPropagation so clicking it doesn't dismiss */}
      <label
        onClick={(e) => e.stopPropagation()}
        className="absolute bottom-6 left-6 flex items-center gap-2 text-white text-sm
                   bg-black/40 backdrop-blur px-3 py-2 rounded cursor-pointer
                   hover:bg-black/60 transition-colors"
      >
        <input
          type="checkbox"
          checked={dontShow}
          onChange={(e) => setDontShow(e.target.checked)}
          className="cursor-pointer"
        />
        Don&apos;t show this again
      </label>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          handleDismiss();
        }}
        className="absolute bottom-6 right-6 text-white text-sm font-medium
                   bg-black/40 backdrop-blur px-4 py-2 rounded
                   hover:bg-black/60 transition-colors
                   focus:outline-none focus:ring-2 focus:ring-white"
      >
        Skip &rsaquo;
      </button>

      {isPreview && (
        <span
          className="absolute top-4 right-4 px-2 py-1 text-xs font-medium
                     bg-amber-500 text-amber-950 rounded"
        >
          Preview mode
        </span>
      )}
    </div>
  );
}
