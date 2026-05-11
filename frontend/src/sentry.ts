/**
 * Sentry / error-tracking init. No-op when VITE_SENTRY_DSN is unset
 * (CI, fresh local dev, anonymous self-hosters who haven't signed up
 * for a tracker yet). Works with sentry.io, self-hosted Sentry, or
 * GlitchTip — any DSN-compatible endpoint.
 *
 * Imported once at the top of main.tsx; the SDK is bundled regardless,
 * but its runtime side-effects are gated by the DSN check.
 */
import * as Sentry from '@sentry/react';

const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

if (dsn) {
  Sentry.init({
    dsn,
    environment: (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined)
      ?? import.meta.env.MODE,
    release: import.meta.env.VITE_SENTRY_RELEASE as string | undefined,
    // Tracing / replays are off by default — they cost a separate quota
    // and aren't necessary for crash visibility. An operator can opt in
    // by exporting VITE_SENTRY_TRACES_SAMPLE_RATE.
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    // Don't ship PII unless explicitly requested.
    sendDefaultPii: false,
  });
}

export { Sentry };
