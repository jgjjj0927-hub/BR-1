const BASE = 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg';

function toCodepoint(emoji: string): string {
  return [...emoji]
    .map(c => c.codePointAt(0)!.toString(16))
    .filter(cp => cp !== 'fe0f')
    .join('-');
}

export function Emoji({ v, size = '1.2em', className }: { v: string; size?: string; className?: string }) {
  const cp = toCodepoint(v);
  return (
    <img
      src={`${BASE}/${cp}.svg`}
      alt={v}
      draggable={false}
      className={className}
      style={{ width: size, height: size, display: 'inline-block', verticalAlign: '-0.18em' }}
    />
  );
}
