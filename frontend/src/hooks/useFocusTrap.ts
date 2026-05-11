import { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Trap keyboard focus inside the returned ref's container while it is
 * active. Pressing Tab cycles through focusable descendants; Shift+Tab
 * cycles backward; Escape calls `onEscape` (typically the modal's
 * close handler). On unmount, focus is restored to whatever held it
 * before the trap activated.
 *
 * Use on dialogs/modals. The container element must accept a `ref`.
 */
export function useFocusTrap<T extends HTMLElement>(
  active: boolean,
  onEscape?: () => void,
) {
  const containerRef = useRef<T | null>(null);

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    function focusFirst() {
      const nodes = container!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (nodes.length > 0) {
        nodes[0].focus();
      } else {
        container!.setAttribute('tabindex', '-1');
        container!.focus();
      }
    }

    focusFirst();

    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && onEscape) {
        e.stopPropagation();
        onEscape();
        return;
      }
      if (e.key !== 'Tab') return;
      const nodes = Array.from(
        container!.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((n) => !n.hasAttribute('aria-hidden'));
      if (nodes.length === 0) {
        e.preventDefault();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const current = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (current === first || !container!.contains(current)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (current === last || !container!.contains(current)) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
      }
    };
  }, [active, onEscape]);

  return containerRef;
}
