import { createContext, useContext, useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { themes, ThemeId, DEFAULT_THEME, applyTheme } from './themes';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Manual from './pages/Manual';
import Price from './pages/Price';
import Promo from './pages/Promo';
import FAQ from './pages/FAQ';
import Admin from './pages/Admin';

export type Lang = 'ru' | 'en';

interface AppCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  themeId: ThemeId;
  setThemeId: (id: ThemeId) => void;
}

export const Ctx = createContext<AppCtx>({
  lang: 'ru',
  setLang: () => {},
  themeId: DEFAULT_THEME,
  setThemeId: () => {},
});

export function useLang() {
  return useContext(Ctx);
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => {
    return (localStorage.getItem('brv2-lang') as Lang) || 'ru';
  });

  const [themeId, setThemeIdState] = useState<ThemeId>(() => {
    return (localStorage.getItem('brv2-theme') as ThemeId) || DEFAULT_THEME;
  });

  const setThemeId = (id: ThemeId) => {
    setThemeIdState(id);
    localStorage.setItem('brv2-theme', id);
  };

  const setLangStore = (l: Lang) => {
    setLang(l);
    localStorage.setItem('brv2-lang', l);
  };

  useEffect(() => {
    const theme = themes.find(t => t.id === themeId) || themes[0];
    applyTheme(theme);
  }, [themeId]);

  return (
    <Ctx.Provider value={{ lang, setLang: setLangStore, themeId, setThemeId }}>
      <div className="app-wrap">
        <Header />
        <main className="page-main">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/manual" element={<Manual />} />
            <Route path="/price" element={<Price />} />
            <Route path="/promo" element={<Promo />} />
            <Route path="/faq" element={<FAQ />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </Ctx.Provider>
  );
}
