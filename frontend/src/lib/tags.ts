/** Normalizes like the backend: lowercase, spaces → '-', allowed chars only. */
export const normalizeTag = (s: string) => s.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9.+#-]/g, '').slice(0, 30);
