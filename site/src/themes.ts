export type ThemeId = 'blue-purple' | 'dark' | 'light' | 'blue-black' | 'blue-white' | 'pink-purple';

export interface Theme {
  id: ThemeId;
  name: { ru: string; en: string };
  preview: [string, string]; // two colors for swatch
  vars: Record<string, string>;
}

export const themes: Theme[] = [
  {
    id: 'blue-purple',
    name: { ru: 'Сине-фиолетовая', en: 'Blue-Purple' },
    preview: ['#818cf8', '#0e0a1f'],
    vars: {
      '--bg':         '#0e0a1f',
      '--bg2':        '#14102c',
      '--bg3':        '#1c1838',
      '--surface':    '#1c1838',
      '--border':     '#2e2a50',
      '--text':       '#e8e6ff',
      '--text2':      '#8b87c0',
      '--accent':     '#818cf8',
      '--accent2':    '#a5b4fc',
      '--accent-dim': 'rgba(129,140,248,0.13)',
      '--badge-bg':   'rgba(129,140,248,0.10)',
      '--badge-text': '#a5b4fc',
      '--pulse':      '#818cf8',
      '--card-hover': '#201c3e',
    },
  },
  {
    id: 'dark',
    name: { ru: 'Тёмная', en: 'Dark' },
    preview: ['#7c3aed', '#0d0d0d'],
    vars: {
      '--bg':         '#0d0d0d',
      '--bg2':        '#141414',
      '--bg3':        '#1a1a1a',
      '--surface':    '#1a1a1a',
      '--border':     '#2a2a2a',
      '--text':       '#f0f0f0',
      '--text2':      '#888',
      '--accent':     '#7c3aed',
      '--accent2':    '#a78bfa',
      '--accent-dim': 'rgba(124,58,237,0.12)',
      '--badge-bg':   'rgba(124,58,237,0.10)',
      '--badge-text': '#a78bfa',
      '--pulse':      '#7c3aed',
      '--card-hover': '#1f1f1f',
    },
  },
  {
    id: 'light',
    name: { ru: 'Светлая', en: 'Light' },
    preview: ['#7c3aed', '#ffffff'],
    vars: {
      '--bg':         '#f8f8fc',
      '--bg2':        '#ffffff',
      '--bg3':        '#f0eef8',
      '--surface':    '#ffffff',
      '--border':     '#e2e0f0',
      '--text':       '#1a1a2e',
      '--text2':      '#6b6987',
      '--accent':     '#7c3aed',
      '--accent2':    '#6d28d9',
      '--accent-dim': 'rgba(124,58,237,0.08)',
      '--badge-bg':   'rgba(124,58,237,0.08)',
      '--badge-text': '#7c3aed',
      '--pulse':      '#7c3aed',
      '--card-hover': '#f4f2ff',
    },
  },
  {
    id: 'blue-black',
    name: { ru: 'Сине-чёрная', en: 'Blue-Black' },
    preview: ['#3b82f6', '#080d1a'],
    vars: {
      '--bg':         '#080d1a',
      '--bg2':        '#0e1628',
      '--bg3':        '#131e34',
      '--surface':    '#131e34',
      '--border':     '#1e2f50',
      '--text':       '#ddeeff',
      '--text2':      '#6b8aaa',
      '--accent':     '#3b82f6',
      '--accent2':    '#60a5fa',
      '--accent-dim': 'rgba(59,130,246,0.13)',
      '--badge-bg':   'rgba(59,130,246,0.10)',
      '--badge-text': '#60a5fa',
      '--pulse':      '#3b82f6',
      '--card-hover': '#152240',
    },
  },
  {
    id: 'blue-white',
    name: { ru: 'Сине-белая', en: 'Blue-White' },
    preview: ['#2563eb', '#f0f4ff'],
    vars: {
      '--bg':         '#f0f4ff',
      '--bg2':        '#ffffff',
      '--bg3':        '#e8eeff',
      '--surface':    '#ffffff',
      '--border':     '#c7d2fe',
      '--text':       '#1e1b4b',
      '--text2':      '#5b6a9a',
      '--accent':     '#2563eb',
      '--accent2':    '#1d4ed8',
      '--accent-dim': 'rgba(37,99,235,0.08)',
      '--badge-bg':   'rgba(37,99,235,0.08)',
      '--badge-text': '#2563eb',
      '--pulse':      '#2563eb',
      '--card-hover': '#e0e8ff',
    },
  },
  {
    id: 'pink-purple',
    name: { ru: 'Розово-фиолетовая', en: 'Pink-Purple' },
    preview: ['#e879f9', '#120b1a'],
    vars: {
      '--bg':         '#120b1a',
      '--bg2':        '#1a1024',
      '--bg3':        '#22152e',
      '--surface':    '#22152e',
      '--border':     '#38204a',
      '--text':       '#f5e6ff',
      '--text2':      '#a87bbf',
      '--accent':     '#e879f9',
      '--accent2':    '#f0abfc',
      '--accent-dim': 'rgba(232,121,249,0.13)',
      '--badge-bg':   'rgba(232,121,249,0.10)',
      '--badge-text': '#f0abfc',
      '--pulse':      '#e879f9',
      '--card-hover': '#2a1838',
    },
  },
];

export const DEFAULT_THEME: ThemeId = 'blue-black';

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
  root.setAttribute('data-theme', theme.id);
}
