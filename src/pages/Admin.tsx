import { useEffect, useRef, useState } from 'react';
import { api, Mirror, Review, Promo } from '../api';

type Tab = 'mirrors' | 'reviews' | 'promos';
type Phase = 'login' | 'pending' | 'authed';

const TABS: { id: Tab; label: string }[] = [
  { id: 'mirrors', label: '🪞 Зеркала' },
  { id: 'reviews', label: '💬 Отзывы' },
  { id: 'promos', label: '🎁 Промокоды' },
];

function usePersistedAuth() {
  const [token, setTokenState] = useState(() => localStorage.getItem('brv2-admin-token') || '');
  const [loginId, setLoginIdState] = useState<number | null>(() => {
    const v = localStorage.getItem('brv2-admin-lid');
    return v ? Number(v) : null;
  });
  const setToken = (t: string) => { localStorage.setItem('brv2-admin-token', t); setTokenState(t); };
  const setLoginId = (id: number | null) => {
    if (id === null) localStorage.removeItem('brv2-admin-lid');
    else localStorage.setItem('brv2-admin-lid', String(id));
    setLoginIdState(id);
  };
  const clear = () => { setToken(''); setLoginId(null); };
  return { token, loginId, setToken, setLoginId, clear };
}

// ── Mirrors tab ────────────────────────────────────────────────────────────────
function MirrorsTab({ token }: { token: string }) {
  const [list, setList] = useState<Mirror[]>([]);
  const [form, setForm] = useState({ name: '', url: '', status: 'active', sort_order: 0 });
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState('');

  const load = () => api.mirrors().then(setList).catch(() => {});
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      if (editing !== null) await api.admin.updateMirror(editing, form, token);
      else await api.admin.createMirror(form, token);
      setForm({ name: '', url: '', status: 'active', sort_order: 0 });
      setEditing(null); setErr(''); load();
    } catch (e: any) { setErr(e.message || 'Ошибка'); }
  };

  const del = async (id: number) => {
    if (!confirm('Удалить?')) return;
    try { await api.admin.deleteMirror(id, token); load(); } catch {}
  };

  const edit = (m: Mirror) => { setEditing(m.id); setForm({ name: m.name, url: m.url, status: m.status, sort_order: 0 }); };

  return (
    <div className="adm-tab">
      <div className="adm-form">
        <h3>{editing !== null ? 'Редактировать зеркало' : 'Добавить зеркало'}</h3>
        <input placeholder="Название (напр. Зеркало 1)" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        <input placeholder="Ссылка (https://t.me/...)" value={form.url} onChange={e => setForm(f => ({ ...f, url: e.target.value }))} />
        <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
          <option value="active">Активно</option>
          <option value="dead">Не работает</option>
        </select>
        <input type="number" placeholder="Порядок сортировки" value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: Number(e.target.value) }))} />
        {err && <p className="err-msg">{err}</p>}
        <div className="adm-btns">
          <button className="btn-primary sm" onClick={save}>{editing !== null ? 'Сохранить' : 'Добавить'}</button>
          {editing !== null && <button className="btn-ghost sm" onClick={() => { setEditing(null); setForm({ name: '', url: '', status: 'active', sort_order: 0 }); }}>Отмена</button>}
        </div>
      </div>
      <div className="adm-list">
        {list.map(m => (
          <div key={m.id} className="adm-row">
            <span className={`m-dot ${m.status}`} />
            <div className="adm-info">
              <strong>{m.name}</strong>
              <small>{m.url}</small>
            </div>
            <span className={`status-badge ${m.status === 'active' ? 'active' : 'off'}`}>{m.status === 'active' ? 'Активно' : 'Не работает'}</span>
            <div className="adm-actions">
              <button onClick={() => edit(m)}>✏️</button>
              <button onClick={() => del(m.id)}>🗑</button>
            </div>
          </div>
        ))}
        {list.length === 0 && <p className="empty-note">Зеркал нет</p>}
      </div>
    </div>
  );
}

// ── Reviews tab ───────────────────────────────────────────────────────────────
function ReviewsTab({ token }: { token: string }) {
  const [list, setList] = useState<Review[]>([]);
  const [form, setForm] = useState({ author: '', text: '', avatar: '', visible: true });
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState('');

  const load = () => api.reviews().then(setList).catch(() => {});
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      if (editing !== null) await api.admin.updateReview(editing, form, token);
      else await api.admin.createReview(form, token);
      setForm({ author: '', text: '', avatar: '', visible: true });
      setEditing(null); setErr(''); load();
    } catch (e: any) { setErr(e.message || 'Ошибка'); }
  };

  const del = async (id: number) => {
    if (!confirm('Удалить?')) return;
    try { await api.admin.deleteReview(id, token); load(); } catch {}
  };

  const toggleVisible = async (r: Review) => {
    try { await api.admin.updateReview(r.id, { ...r, visible: !r.visible } as any, token); load(); } catch {}
  };

  const edit = (r: Review) => { setEditing(r.id); setForm({ author: r.author, text: r.text, avatar: r.avatar || '', visible: true }); };

  return (
    <div className="adm-tab">
      <div className="adm-form">
        <h3>{editing !== null ? 'Редактировать отзыв' : 'Добавить отзыв'}</h3>
        <input placeholder="Имя автора" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} />
        <textarea placeholder="Текст отзыва" value={form.text} onChange={e => setForm(f => ({ ...f, text: e.target.value }))} rows={4} />
        <input placeholder="Аватар (URL, необязательно)" value={form.avatar} onChange={e => setForm(f => ({ ...f, avatar: e.target.value }))} />
        <label className="chk-label">
          <input type="checkbox" checked={form.visible} onChange={e => setForm(f => ({ ...f, visible: e.target.checked }))} />
          Показывать на сайте
        </label>
        {err && <p className="err-msg">{err}</p>}
        <div className="adm-btns">
          <button className="btn-primary sm" onClick={save}>{editing !== null ? 'Сохранить' : 'Добавить'}</button>
          {editing !== null && <button className="btn-ghost sm" onClick={() => { setEditing(null); setForm({ author: '', text: '', avatar: '', visible: true }); }}>Отмена</button>}
        </div>
      </div>
      <div className="adm-list">
        {list.map(r => (
          <div key={r.id} className="adm-row">
            <div className="adm-info">
              <strong>{r.author}</strong>
              <small>{r.text.slice(0, 80)}{r.text.length > 80 ? '…' : ''}</small>
            </div>
            <div className="adm-actions">
              <button onClick={() => toggleVisible(r)} title="Скрыть/показать">👁</button>
              <button onClick={() => edit(r)}>✏️</button>
              <button onClick={() => del(r.id)}>🗑</button>
            </div>
          </div>
        ))}
        {list.length === 0 && <p className="empty-note">Отзывов нет</p>}
      </div>
    </div>
  );
}

// ── Promos tab ─────────────────────────────────────────────────────────────────
const PROMO_TYPES = [
  { value: 'normal', label: 'Обычный (подписка)' },
  { value: 'premium', label: 'Премиум' },
  { value: 'reports', label: 'Репорты (free_reports)' },
];
const EMPTY_PROMO = { title: '', code: '', description: '', expires_at: '', active: true, days: 7, activations: 100, promo_type: 'normal' };

function PromosTab({ token }: { token: string }) {
  const [list, setList] = useState<Promo[]>([]);
  const [form, setForm] = useState({ ...EMPTY_PROMO });
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState(false);

  const load = () => api.promos().then(setList).catch(() => {});
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim() || !form.code.trim()) { setErr('Заголовок и код обязательны'); return; }
    try {
      const data = { ...form, expires_at: form.expires_at || null, code: form.code.toUpperCase() };
      if (editing !== null) await api.admin.updatePromo(editing, data as any, token);
      else await api.admin.createPromo(data as any, token);
      setForm({ ...EMPTY_PROMO }); setEditing(null); setErr('');
      setSaved(true); setTimeout(() => setSaved(false), 2000); load();
    } catch (e: any) { setErr(e.message || 'Ошибка'); }
  };

  const del = async (id: number) => {
    if (!confirm('Удалить промокод?')) return;
    try { await api.admin.deletePromo(id, token); load(); } catch {}
  };

  const toggleActive = async (p: Promo) => {
    try { await api.admin.updatePromo(p.id, { ...p, active: !p.active } as any, token); load(); } catch {}
  };

  const edit = (p: Promo) => {
    setEditing(p.id);
    setForm({ title: p.title, code: p.code, description: p.description || '', expires_at: p.expires_at ? p.expires_at.slice(0, 10) : '', active: p.active, days: p.days ?? 7, activations: p.activations ?? 100, promo_type: p.promo_type ?? 'normal' });
  };

  const typeLabel = (type: string) => PROMO_TYPES.find(t => t.value === type)?.label ?? type;

  return (
    <div className="adm-tab">
      <div className="adm-form">
        <h3>{editing !== null ? 'Редактировать промокод' : 'Добавить промокод'}</h3>
        <input placeholder="Заголовок (напр. Скидка выходного дня)" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
        <input placeholder="КОД ПРОМОКОДА" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} style={{ fontFamily: 'monospace', letterSpacing: '0.08em' }} />
        <input placeholder="Описание (необязательно)" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.85rem', color: 'var(--text2)' }}>
            Дней подписки
            <input type="number" min={1} max={36500} value={form.days} onChange={e => setForm(f => ({ ...f, days: Math.max(1, Number(e.target.value)) }))} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.85rem', color: 'var(--text2)' }}>
            Активаций
            <input type="number" min={1} max={100000} value={form.activations} onChange={e => setForm(f => ({ ...f, activations: Math.max(1, Number(e.target.value)) }))} />
          </label>
        </div>
        <select value={form.promo_type} onChange={e => setForm(f => ({ ...f, promo_type: e.target.value }))}>
          {PROMO_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <input type="date" value={form.expires_at} onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))} />
        <label className="chk-label">
          <input type="checkbox" checked={form.active} onChange={e => setForm(f => ({ ...f, active: e.target.checked }))} />
          Активен
        </label>
        {err && <p className="err-msg">{err}</p>}
        {saved && <p style={{ color: 'var(--accent2)', fontSize: '0.85rem' }}>✅ Сохранено и синхронизировано с ботом</p>}
        <div className="adm-btns">
          <button className="btn-primary sm" onClick={save}>{editing !== null ? 'Сохранить' : 'Добавить'}</button>
          {editing !== null && <button className="btn-ghost sm" onClick={() => { setEditing(null); setForm({ ...EMPTY_PROMO }); setErr(''); }}>Отмена</button>}
        </div>
      </div>
      <div className="adm-list">
        {list.map(p => (
          <div key={p.id} className="adm-row">
            <div className="adm-info">
              <strong>{p.title}</strong>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <code style={{ fontSize: '0.8rem' }}>{p.code}</code>
                <small style={{ opacity: 0.7 }}>{p.days}д · {p.activations} акт · {typeLabel(p.promo_type)}</small>
              </div>
            </div>
            <span className={`status-badge ${p.active ? 'active' : 'off'}`}>{p.active ? 'Активен' : 'Выкл'}</span>
            <div className="adm-actions">
              <button onClick={() => toggleActive(p)} title="Вкл/Выкл">⚡</button>
              <button onClick={() => edit(p)}>✏️</button>
              <button onClick={() => del(p.id)}>🗑</button>
            </div>
          </div>
        ))}
        {list.length === 0 && <p className="empty-note">Промокодов нет</p>}
      </div>
    </div>
  );
}

// ── Pending screen ─────────────────────────────────────────────────────────────
function PendingScreen({ onCancel }: { onCancel: () => void }) {
  return (
    <div className="page-inner container">
      <div style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center', paddingTop: 48 }}>
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'linear-gradient(135deg, rgba(124,58,255,0.2), rgba(56,189,248,0.1))',
          border: '2px solid rgba(124,58,255,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 28px',
          boxShadow: '0 0 40px rgba(124,58,255,0.3)',
          animation: 'adm-pulse 2s ease-in-out infinite',
        }}>
          <span style={{ fontSize: '2rem' }}>🔐</span>
        </div>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: 12 }}>Ожидание подтверждения</h2>
        <p style={{ color: 'var(--text2)', marginBottom: 32, lineHeight: 1.65 }}>
          Запрос на вход отправлен администратору в Telegram.<br />
          Страница обновится автоматически после подтверждения.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 32 }}>
          {[0, 1, 2].map(i => (
            <div key={i} style={{
              width: 10, height: 10, borderRadius: '50%',
              background: 'var(--accent)',
              animation: `adm-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
            }} />
          ))}
        </div>
        <button className="btn-ghost sm" onClick={onCancel}>Отмена</button>
      </div>
      <style>{`
        @keyframes adm-pulse {
          0%,100% { box-shadow: 0 0 40px rgba(124,58,255,0.3); }
          50% { box-shadow: 0 0 60px rgba(124,58,255,0.6), 0 0 100px rgba(124,58,255,0.2); }
        }
        @keyframes adm-bounce {
          0%,80%,100% { transform: scale(0); opacity: 0.3; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ── Main Admin page ────────────────────────────────────────────────────────────
export default function Admin() {
  const { token, loginId, setToken, setLoginId, clear } = usePersistedAuth();
  const [inputToken, setInputToken] = useState('');
  const [phase, setPhase] = useState<Phase>('login');
  const [tab, setTab] = useState<Tab>('mirrors');
  const [authErr, setAuthErr] = useState('');
  const [attempts, setAttempts] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stop polling helper
  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };

  // Poll check-session endpoint
  const startPolling = (tok: string, lid: number) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/admin/check-session/${lid}`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'confirmed') {
          stopPoll();
          setPhase('authed');
        } else if (data.status === 'blocked') {
          stopPoll();
          clear();
          setPhase('login');
          setAuthErr('Вход заблокирован администратором');
        }
      } catch {}
    }, 3000);
  };

  // Auto-login on mount if we have saved token + login_id that was confirmed
  useEffect(() => {
    if (!token || loginId === null) return;
    // Check if the saved session is still confirmed
    fetch(`/api/admin/check-session/${loginId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async r => {
        if (!r.ok) { clear(); return; }
        const data = await r.json();
        if (data.status === 'confirmed') {
          setPhase('authed');
        } else if (data.status === 'blocked') {
          clear();
          setAuthErr('Вход заблокирован администратором');
        } else if (data.status === 'pending') {
          setPhase('pending');
          startPolling(token, loginId);
        } else {
          clear();
        }
      })
      .catch(() => clear());
    return stopPoll;
  }, []);

  const tryAuth = async () => {
    if (blocked) return;
    if (inputToken.length > 200) { setAuthErr('Недопустимый токен'); return; }
    setAuthErr('');
    try {
      const res = await fetch('/api/admin/ping', {
        headers: { Authorization: `Bearer ${inputToken}` },
      });
      if (res.status === 401) {
        const next = attempts + 1;
        setAttempts(next);
        if (next >= 3) {
          setBlocked(true);
          setAuthErr('Слишком много попыток. Подождите 1 час.');
          setTimeout(() => { setBlocked(false); setAttempts(0); setAuthErr(''); }, 3600000);
        } else {
          setAuthErr(`Неверный пароль (${next}/3)`);
        }
        return;
      }
      if (res.status === 429) { setAuthErr('Слишком много попыток. Попробуйте позже.'); return; }
      if (res.status === 403) { setAuthErr('Ваш IP заблокирован'); return; }
      if (res.status === 202) {
        const data = await res.json();
        setToken(inputToken);
        setLoginId(data.login_id);
        setPhase('pending');
        startPolling(inputToken, data.login_id);
        return;
      }
      setAuthErr('Ошибка сервера');
    } catch {
      setAuthErr('Ошибка подключения');
    }
  };

  const handleCancel = () => {
    stopPoll();
    clear();
    setPhase('login');
    setInputToken('');
    setAuthErr('');
  };

  const handleLogout = () => {
    stopPoll();
    clear();
    setPhase('login');
  };

  if (phase === 'pending') return <PendingScreen onCancel={handleCancel} />;

  if (phase === 'authed') {
    return (
      <div className="page-inner container">
        <div className="page-head adm-head">
          <div>
            <div className="sec-label">🔐 Admin</div>
            <h1>Панель администратора</h1>
          </div>
          <button className="btn-ghost sm" onClick={handleLogout}>Выйти</button>
        </div>
        <div className="adm-tabs">
          {TABS.map(t => (
            <button key={t.id} className={`adm-tab-btn${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'mirrors' && <MirrorsTab token={token} />}
        {tab === 'reviews' && <ReviewsTab token={token} />}
        {tab === 'promos' && <PromosTab token={token} />}
      </div>
    );
  }

  return (
    <div className="page-inner container">
      <div className="page-head">
        <div className="sec-label">🔐</div>
        <h1>Панель администратора</h1>
        <p>Введите пароль для входа</p>
      </div>
      <div className="auth-form">
        <input
          type="password"
          placeholder="Пароль"
          value={inputToken}
          onChange={e => setInputToken(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !blocked && tryAuth()}
          disabled={blocked}
        />
        {authErr && <p className="err-msg">{authErr}</p>}
        <button className="btn-primary" onClick={tryAuth} disabled={blocked}>
          {blocked ? 'Заблокировано' : 'Войти'}
        </button>
      </div>
    </div>
  );
}
