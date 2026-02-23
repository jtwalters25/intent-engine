// ---------------------------------------------------------------------------
// Demo page data: catalog, contexts, and ranking logic
// ---------------------------------------------------------------------------

// SVG thumbnail generator (same pattern as mockShows.ts)
const thumb = (
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DemoItem {
  id: string;
  title: string;
  genre: string;
  rating: string;
  runtime: string;
  tags: string[];
  engagementScore: number;
  emoji: string;
  thumbnail: string;
}

export type ContextKey = 'bedtime' | 'solo-morning' | 'family-weekend' | 'focus-session';

export interface DemoContext {
  key: ContextKey;
  label: string;
  emoji: string;
  subtitle: string;
  signals: { emoji: string; label: string }[];
}

export interface RankedDemoItem extends DemoItem {
  intentScore: number;
  reason: string;
  movement: number; // positive = moved up, negative = moved down
  status: 'boosted' | 'demoted' | 'blocked' | 'neutral';
}

// ---------------------------------------------------------------------------
// 8-item catalog (engagement-score order)
// ---------------------------------------------------------------------------

export const catalog: DemoItem[] = [
  {
    id: 'dark-s3',
    title: 'Dark Season 3',
    genre: 'Sci-Fi Thriller',
    rating: 'TV-MA',
    runtime: '52 min',
    tags: ['complex', 'tense', 'serialized', 'dark'],
    engagementScore: 0.94,
    emoji: '⏳',
    thumbnail: thumb('⏳', '#1a1a2e', '#16213e', 'Dark S3'),
  },
  {
    id: 'outer-range',
    title: 'Outer Range',
    genre: 'Sci-Fi Western',
    rating: 'TV-14',
    runtime: '48 min',
    tags: ['mystery', 'tense', 'serialized', 'outdoor'],
    engagementScore: 0.91,
    emoji: '🏜️',
    thumbnail: thumb('🏜️', '#2d1b00', '#1a3a2a', 'Outer Range'),
  },
  {
    id: 'inception',
    title: 'Inception',
    genre: 'Sci-Fi Action',
    rating: 'PG-13',
    runtime: '148 min',
    tags: ['complex', 'action', 'long-film', 'cerebral'],
    engagementScore: 0.87,
    emoji: '🌀',
    thumbnail: thumb('🌀', '#0f0f23', '#1a1a3e', 'Inception'),
  },
  {
    id: 'the-office',
    title: 'The Office S1',
    genre: 'Comedy',
    rating: 'TV-14',
    runtime: '22 min',
    tags: ['comedy', 'familiar', 'background-friendly', 'short-episodes'],
    engagementScore: 0.82,
    emoji: '📎',
    thumbnail: thumb('📎', '#2a2a1a', '#3a3a2a', 'The Office S1'),
  },
  {
    id: 'merlin',
    title: 'Merlin Chronicles',
    genre: 'Fantasy Adventure',
    rating: 'PG',
    runtime: '95 min',
    tags: ['adventure', 'family', 'fantasy', 'all-ages'],
    engagementScore: 0.76,
    emoji: '🧙',
    thumbnail: thumb('🧙', '#1a0a2e', '#2a1a3e', 'Merlin Chronicles'),
  },
  {
    id: 'lion-king',
    title: 'The Lion King',
    genre: 'Animation',
    rating: 'G',
    runtime: '88 min',
    tags: ['animated', 'family', 'musical', 'all-ages', 'classic'],
    engagementScore: 0.71,
    emoji: '🦁',
    thumbnail: thumb('🦁', '#3a2a00', '#2a1a00', 'The Lion King'),
  },
  {
    id: 'planet-earth',
    title: 'Planet Earth III',
    genre: 'Documentary',
    rating: 'TV-G',
    runtime: '28 min',
    tags: ['documentary', 'educational', 'calming', 'nature', 'short-episodes'],
    engagementScore: 0.65,
    emoji: '🌍',
    thumbnail: thumb('🌍', '#0a2a1a', '#1a3a2a', 'Planet Earth III'),
  },
  {
    id: 'bluey',
    title: 'Bluey S4',
    genre: 'Animation',
    rating: 'TV-Y',
    runtime: '7 min',
    tags: ['kids', 'animated', 'calming', 'short-episodes', 'soothing', 'G-rated'],
    engagementScore: 0.58,
    emoji: '🐕',
    thumbnail: thumb('🐕', '#1a2a3e', '#2a3a4e', 'Bluey S4'),
  },
];

// ---------------------------------------------------------------------------
// 4 context presets
// ---------------------------------------------------------------------------

export const contexts: Record<ContextKey, DemoContext> = {
  bedtime: {
    key: 'bedtime',
    label: 'Bedtime',
    emoji: '🌙',
    subtitle: '8:45 PM — winding down for sleep',
    signals: [
      { emoji: '🕐', label: '8:45 PM' },
      { emoji: '👶', label: 'Ages 4-7' },
      { emoji: '😴', label: 'Low energy' },
      { emoji: '📱', label: 'Tablet' },
      { emoji: '⏱️', label: '15 min left' },
    ],
  },
  'solo-morning': {
    key: 'solo-morning',
    label: 'Solo Morning',
    emoji: '☕',
    subtitle: '7:15 AM — adult solo time before the day starts',
    signals: [
      { emoji: '🕐', label: '7:15 AM' },
      { emoji: '🧑', label: 'Solo adult' },
      { emoji: '😌', label: 'Relaxed' },
      { emoji: '📺', label: 'TV' },
      { emoji: '⏱️', label: '45 min' },
    ],
  },
  'family-weekend': {
    key: 'family-weekend',
    label: 'Family Weekend',
    emoji: '🍿',
    subtitle: 'Saturday 3 PM — whole family together',
    signals: [
      { emoji: '🕐', label: '3:00 PM' },
      { emoji: '👨‍👩‍👧‍👦', label: 'Full family' },
      { emoji: '🎉', label: 'High energy' },
      { emoji: '📺', label: 'Living room TV' },
      { emoji: '⏱️', label: '2 hours' },
    ],
  },
  'focus-session': {
    key: 'focus-session',
    label: 'Focus Session',
    emoji: '🎧',
    subtitle: 'Tuesday 10 AM — background while working',
    signals: [
      { emoji: '🕐', label: '10:00 AM' },
      { emoji: '🧑', label: 'Solo adult' },
      { emoji: '🧠', label: 'Focused' },
      { emoji: '💻', label: 'Laptop' },
      { emoji: '⏱️', label: '60 min' },
    ],
  },
};

// ---------------------------------------------------------------------------
// Ranking logic — pure function, no side effects
// ---------------------------------------------------------------------------

type ScoringRule = {
  test: (item: DemoItem) => boolean;
  score: number;
  reason: string;
};

const contextRules: Record<ContextKey, ScoringRule[]> = {
  bedtime: [
    { test: (i) => i.rating === 'TV-MA', score: 0, reason: 'TV-MA blocked at bedtime' },
    { test: (i) => ['G', 'TV-Y', 'TV-G'].includes(i.rating), score: 0.35, reason: 'Age-appropriate rating' },
    { test: (i) => i.tags.includes('calming') || i.tags.includes('soothing'), score: 0.3, reason: 'Calming content' },
    { test: (i) => parseInt(i.runtime) <= 10, score: 0.25, reason: 'Very short runtime' },
    { test: (i) => parseInt(i.runtime) <= 30, score: 0.1, reason: 'Moderate runtime' },
    { test: (i) => i.tags.includes('tense') || i.tags.includes('complex'), score: -0.3, reason: 'Too stimulating' },
    { test: (i) => i.rating === 'TV-14' || i.rating === 'PG-13', score: -0.15, reason: 'Rating not ideal for bedtime' },
    { test: (i) => i.tags.includes('kids'), score: 0.15, reason: 'Kid-friendly content' },
  ],
  'solo-morning': [
    { test: (i) => i.tags.includes('familiar'), score: 0.25, reason: 'Familiar comfort pick' },
    { test: (i) => i.tags.includes('background-friendly'), score: 0.2, reason: 'Good background viewing' },
    { test: (i) => i.tags.includes('complex') || i.tags.includes('cerebral'), score: 0.2, reason: 'Engaging for solo viewing' },
    { test: (i) => i.tags.includes('serialized'), score: 0.15, reason: 'Serialized — easy to continue' },
    { test: (i) => parseInt(i.runtime) >= 20 && parseInt(i.runtime) <= 55, score: 0.1, reason: 'Fits morning window' },
    { test: (i) => i.tags.includes('kids') && !i.tags.includes('complex'), score: -0.25, reason: 'Kids-only — not for solo adult' },
    { test: (i) => parseInt(i.runtime) > 120, score: -0.1, reason: 'Too long for morning session' },
  ],
  'family-weekend': [
    { test: (i) => ['G', 'PG', 'TV-Y', 'TV-G'].includes(i.rating), score: 0.25, reason: 'Family-safe rating' },
    { test: (i) => i.tags.includes('comedy') || i.tags.includes('adventure'), score: 0.2, reason: 'Fun genre for group viewing' },
    { test: (i) => i.tags.includes('all-ages') || i.tags.includes('family'), score: 0.25, reason: 'All-ages appeal' },
    { test: (i) => i.tags.includes('animated') || i.tags.includes('musical'), score: 0.15, reason: 'Crowd-pleasing format' },
    { test: (i) => i.rating === 'TV-MA', score: -0.4, reason: 'Not family-appropriate' },
    { test: (i) => i.tags.includes('dark') || i.tags.includes('tense'), score: -0.2, reason: 'Too intense for mixed ages' },
    { test: (i) => i.tags.includes('complex') && !i.tags.includes('family'), score: -0.1, reason: 'Too niche for group' },
  ],
  'focus-session': [
    { test: (i) => i.tags.includes('documentary') || i.tags.includes('educational'), score: 0.35, reason: 'Documentary — ideal focus companion' },
    { test: (i) => i.tags.includes('short-episodes'), score: 0.2, reason: 'Short episodes = natural breakpoints' },
    { test: (i) => i.tags.includes('nature') || i.tags.includes('calming'), score: 0.15, reason: 'Non-distracting ambiance' },
    { test: (i) => i.tags.includes('background-friendly'), score: 0.15, reason: 'Background-friendly format' },
    { test: (i) => parseInt(i.runtime) > 90, score: -0.2, reason: 'Long runtime — too absorbing' },
    { test: (i) => i.tags.includes('serialized') || i.tags.includes('complex'), score: -0.15, reason: 'Plot-heavy — too distracting' },
    { test: (i) => i.tags.includes('action'), score: -0.1, reason: 'Action sequences pull focus' },
    { test: (i) => i.tags.includes('kids'), score: -0.05, reason: 'Kids content — less relevant' },
  ],
};

export function rankForContext(items: DemoItem[], contextKey: ContextKey): RankedDemoItem[] {
  const rules = contextRules[contextKey];

  const scored = items.map((item, originalIndex) => {
    const firedReasons: string[] = [];
    let intentScore = item.engagementScore;
    let blocked = false;

    for (const rule of rules) {
      if (rule.test(item)) {
        if (rule.score === 0 && intentScore > 0) {
          blocked = true;
          intentScore = 0;
          firedReasons.push(rule.reason);
        } else {
          intentScore += rule.score;
          firedReasons.push(rule.reason);
        }
      }
    }

    intentScore = Math.max(0, Math.min(1, intentScore));

    return {
      ...item,
      intentScore: Math.round(intentScore * 100) / 100,
      reason: firedReasons.join(' · ') || 'No adjustments',
      originalIndex,
      blocked,
    };
  });

  // Sort by intentScore descending
  scored.sort((a, b) => b.intentScore - a.intentScore);

  return scored.map((item, newIndex) => {
    const movement = item.originalIndex - newIndex; // positive = moved up
    let status: RankedDemoItem['status'] = 'neutral';
    if (item.blocked) status = 'blocked';
    else if (movement >= 2) status = 'boosted';
    else if (movement <= -2) status = 'demoted';

    return {
      id: item.id,
      title: item.title,
      genre: item.genre,
      rating: item.rating,
      runtime: item.runtime,
      tags: item.tags,
      engagementScore: item.engagementScore,
      emoji: item.emoji,
      thumbnail: item.thumbnail,
      intentScore: item.intentScore,
      reason: item.reason,
      movement,
      status,
    };
  });
}
