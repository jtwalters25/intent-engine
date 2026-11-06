import type { PlatformItem } from '@/data/demoPlatforms';

// Poster colors come from each item's existing thumbnail gradient, brightened for
// large tiles, so every vertical gets posters without new data fields.

function hexToHsl(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s, l];
}

export function posterTone(item: PlatformItem): string {
  const svg = decodeURIComponent(item.thumbnail);
  const stops = [...svg.matchAll(/stop-color="(#[0-9a-fA-F]{6})"/g)].map((m) => m[1]);
  if (stops.length < 2) return 'linear-gradient(160deg, hsl(230 12% 34%), hsl(230 12% 12%))';
  const [h1, s1] = hexToHsl(stops[0]);
  const [h2, s2] = hexToHsl(stops[1]);
  const sat = (s: number) => Math.round(Math.max(s, 0.42) * 100);
  return `linear-gradient(160deg, hsl(${Math.round(h1)} ${sat(s1)}% 44%), hsl(${Math.round(h2)} ${sat(s2)}% 15%))`;
}
