import client from './client';
import type { FrozenBookPublic } from '../types';

export const frozenApi = {
  // Public read — no auth required. The share token is the sole gate.
  getByToken: (token: string) =>
    client.get<FrozenBookPublic>(`/frozen/${token}/`).then((r) => r.data),
};

export function frozenPdfUrl(token: string): string {
  return `/api/frozen/${token}/pdf/`;
}

export function frozenEpubUrl(token: string): string {
  return `/api/frozen/${token}/epub/`;
}

export function frozenHtmlUrl(token: string): string {
  return `/api/frozen/${token}/html/`;
}
