import client from './client';
import type { Book, BookListItem, BuildFormat } from '../types';

export const booksApi = {
  list: () =>
    client.get('/books/').then((r) => (Array.isArray(r.data) ? r.data : r.data.results ?? []) as BookListItem[]),

  detail: (id: number) => client.get<Book>(`/books/${id}/`).then((r) => r.data),

  create: (title: string) =>
    client.post<Book>('/books/', { title }).then((r) => r.data),

  update: (id: number, data: { title?: string; doi?: string }) =>
    client.patch<Book>(`/books/${id}/`, data).then((r) => r.data),

  delete: (id: number) => client.delete(`/books/${id}/`),

  // Parts
  addPart: (bookId: number, data: { title: string; order: number }) =>
    client.post(`/books/${bookId}/parts/`, data).then((r) => r.data),

  updatePart: (bookId: number, partId: number, data: { title?: string }) =>
    client.patch(`/books/${bookId}/parts/${partId}/`, data).then((r) => r.data),

  deletePart: (bookId: number, partId: number) =>
    client.delete(`/books/${bookId}/parts/${partId}/`),

  reorderParts: (bookId: number, order: number[]) =>
    client.patch(`/books/${bookId}/parts/reorder/`, { order }),

  // Chapters within parts
  addChapter: (bookId: number, partId: number, data: { chapter_id: number; order: number }) =>
    client.post(`/books/${bookId}/parts/${partId}/chapters/`, data).then((r) => r.data),

  removeChapter: (bookId: number, partId: number, bcId: number) =>
    client.delete(`/books/${bookId}/parts/${partId}/chapters/${bcId}/`),

  reorderChapters: (bookId: number, partId: number, order: number[]) =>
    client.patch(`/books/${bookId}/parts/${partId}/chapters/reorder/`, { order }),

  // Build
  triggerBuild: (bookId: number, format: BuildFormat = 'pdf') =>
    client.post(`/books/${bookId}/build/`, { format }).then((r) => r.data),

  getBuildStatus: (bookId: number) =>
    client.get(`/books/${bookId}/build/status/`).then((r) => r.data),

  // Cover image
  uploadCover: (bookId: number, file: File) => {
    const form = new FormData();
    form.append('cover_image', file);
    return client.post(`/books/${bookId}/cover/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
  removeCover: (bookId: number) =>
    client.delete(`/books/${bookId}/cover/`).then((r) => r.data),

  // Download
  downloadPDF: (bookId: number) =>
    client.get(`/books/${bookId}/download/`, { responseType: 'blob' }).then((r) => {
      const disposition = r.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `book_${bookId}.pdf`;
      const url = window.URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }),

  htmlAccessToken: (bookId: number) =>
    client.get<{ token: string }>(`/books/${bookId}/html-token/`).then((r) => r.data.token),

  downloadHtmlZip: (bookId: number) =>
    client.get(`/books/${bookId}/download-html/`, { responseType: 'blob' }).then((r) => {
      const disposition = r.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `book_${bookId}.zip`;
      const url = window.URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }),

  // Library
  library: () =>
    client.get('/library/').then((r) => (Array.isArray(r.data) ? r.data : r.data.results ?? []) as BookListItem[]),
};
