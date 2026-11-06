// SVG thumbnail generator
export const thumb = (
  emoji: string,
  gradFrom: string,
  gradTo: string,
  label: string,
): string => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="225" viewBox="0 0 400 225">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${gradFrom}"/>
        <stop offset="100%" stop-color="${gradTo}"/>
      </linearGradient>
    </defs>
    <rect width="400" height="225" rx="0" fill="url(#g)"/>
    <text x="200" y="100" font-size="64" text-anchor="middle" dominant-baseline="central">${emoji}</text>
    <text x="200" y="160" font-family="system-ui,sans-serif" font-size="16" font-weight="600" fill="rgba(255,255,255,0.85)" text-anchor="middle">${label}</text>
  </svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
};
