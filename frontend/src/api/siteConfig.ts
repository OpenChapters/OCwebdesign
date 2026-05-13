import client from './client';
import type { PublicSettings } from '../types';

export const siteConfigApi = {
  get: () =>
    client.get<PublicSettings>('/settings/public/').then((r) => r.data),
};
