const BASE = '/api';

export interface Mirror {
  id: number;
  name: string;
  url: string;
  status: 'active' | 'dead';
}

export interface Review {
  id: number;
  author: string;
  text: string;
  avatar: string;
  created_at: string;
}

export interface Promo {
  id: number;
  title: string;
  code: string;
  description: string;
  expires_at: string | null;
  active: boolean;
  days: number;
  activations: number;
  promo_type: 'normal' | 'premium' | 'reports';
}

export interface Stats {
  users: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function adminReq(method: string, path: string, body?: unknown, token?: string) {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token || ''}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  stats: () => get<Stats>('/stats'),
  mirrors: () => get<Mirror[]>('/mirrors'),
  reviews: () => get<Review[]>('/reviews'),
  promos: () => get<Promo[]>('/promos'),

  admin: {
    // mirrors
    createMirror: (data: Partial<Mirror>, t: string) => adminReq('POST', '/admin/mirrors', data, t),
    updateMirror: (id: number, data: Partial<Mirror>, t: string) => adminReq('PUT', `/admin/mirrors/${id}`, data, t),
    deleteMirror: (id: number, t: string) => adminReq('DELETE', `/admin/mirrors/${id}`, undefined, t),
    // reviews
    createReview: (data: Partial<Review> & { visible?: boolean }, t: string) => adminReq('POST', '/admin/reviews', data, t),
    updateReview: (id: number, data: Partial<Review> & { visible?: boolean }, t: string) => adminReq('PUT', `/admin/reviews/${id}`, data, t),
    deleteReview: (id: number, t: string) => adminReq('DELETE', `/admin/reviews/${id}`, undefined, t),
    // promos
    createPromo: (data: Partial<Promo>, t: string) => adminReq('POST', '/admin/promos', data, t),
    updatePromo: (id: number, data: Partial<Promo>, t: string) => adminReq('PUT', `/admin/promos/${id}`, data, t),
    deletePromo: (id: number, t: string) => adminReq('DELETE', `/admin/promos/${id}`, undefined, t),
  },
};
