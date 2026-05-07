import client from './client';
import type { Chapter, Discipline, PaginatedResponse } from '../types';

export const chaptersApi = {
  list: (page = 1, discipline?: string) =>
    client
      .get<PaginatedResponse<Chapter>>('/chapters/', {
        params: { page, ...(discipline ? { discipline } : {}) },
      })
      .then((r) => r.data),

  listAll: async (): Promise<Chapter[]> => {
    const all: Chapter[] = [];
    let page = 1;
    while (true) {
      const resp = await client.get<PaginatedResponse<Chapter>>('/chapters/', {
        params: { page },
      });
      all.push(...resp.data.results);
      if (!resp.data.next) break;
      page += 1;
    }
    return all;
  },

  detail: (id: number) =>
    client.get<Chapter>(`/chapters/${id}/`).then((r) => r.data),

  disciplines: () =>
    client.get<Discipline[]>('/disciplines/').then((r) => r.data),
};
