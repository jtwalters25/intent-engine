// ---------------------------------------------------------------------------
// Multi-platform catalogs, signal configs, and multiplier-based ranking
// ---------------------------------------------------------------------------

// SVG thumbnail generator
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

export type PlatformKey = 'streaming' | 'music' | 'ecommerce' | 'ride_matching' | 'food_delivery';

export interface PlatformItem {
  id: string;
  title: string;
  genre: string;
  rating: string;
  runtime: string;
  tags: string[];
  engagementScore: number;
  emoji: string;
  thumbnail: string;
  // Multiplier-relevant metadata
  maturity: 'kids' | 'family' | 'teen' | 'adult';
  calmScore: number;   // 0-1 how calming/low-energy the content is
  complexity: number;   // 0-1 how complex/cerebral
}

export type SignalKey = 'time' | 'viewer' | 'energy' | 'device' | 'prophecy';

export interface SignalConfig {
  key: SignalKey;
  label: string;
  emoji: string;
  min: number;
  max: number;
  step: number;
  valueLabels: Record<number, string>; // human-friendly labels at key values
}

export type SignalValues = Record<SignalKey, number>;

export interface ScoringBreakdown {
  baseScore: number;
  timeMultiplier: number;
  viewerMultiplier: number;
  energyMultiplier: number;
  deviceMultiplier: number;
  prophecyBoost: number;
  diversityPenalty: number;
  blocked: boolean;
  blockReason?: string;
  finalScore: number;
}

export interface RankedPlatformItem extends PlatformItem {
  breakdown: ScoringBreakdown;
  movement: number;
  status: 'boosted' | 'demoted' | 'blocked' | 'neutral';
}

export type PlatformContextKey = string;

export interface PlatformContext {
  key: PlatformContextKey;
  label: string;
  emoji: string;
  subtitle: string;
  signals: { emoji: string; label: string }[];
  defaults: SignalValues;
}

export interface Platform {
  key: PlatformKey;
  label: string;
  emoji: string;
  catalog: PlatformItem[];
  contexts: Record<string, PlatformContext>;
  contextKeys: string[];
  signalConfigs: SignalConfig[];
}

// ---------------------------------------------------------------------------
// Signal configurations (shared across platforms, labels differ per context)
// ---------------------------------------------------------------------------

const baseSignalConfigs: SignalConfig[] = [
  {
    key: 'time',
    label: 'Time of Day',
    emoji: '🕐',
    min: 0,
    max: 1,
    step: 0.05,
    valueLabels: { 0: 'Late night', 0.25: 'Morning', 0.5: 'Afternoon', 0.75: 'Evening', 1: 'Bedtime' },
  },
  {
    key: 'viewer',
    label: 'Viewer Profile',
    emoji: '👤',
    min: 0,
    max: 1,
    step: 0.05,
    valueLabels: { 0: 'Kids only', 0.25: 'Family', 0.5: 'Teens', 0.75: 'Adult', 1: 'Solo adult' },
  },
  {
    key: 'energy',
    label: 'Energy Intent',
    emoji: '⚡',
    min: 0,
    max: 1,
    step: 0.05,
    valueLabels: { 0: 'Wind down', 0.25: 'Calm', 0.5: 'Neutral', 0.75: 'Engaged', 1: 'High energy' },
  },
  {
    key: 'device',
    label: 'Device',
    emoji: '📱',
    min: 0,
    max: 1,
    step: 0.05,
    valueLabels: { 0: 'Phone', 0.25: 'Tablet', 0.5: 'Laptop', 0.75: 'TV', 1: 'Home theater' },
  },
  {
    key: 'prophecy',
    label: 'Prophecy Schedule',
    emoji: '🔮',
    min: 0,
    max: 1,
    step: 0.05,
    valueLabels: { 0: 'Off', 0.5: 'Moderate', 1: 'Full auto' },
  },
];

// ---------------------------------------------------------------------------
// Streaming catalog (8 items)
// ---------------------------------------------------------------------------

const streamingCatalog: PlatformItem[] = [
  {
    id: 'dark-s3', title: 'Dark Season 3', genre: 'Sci-Fi Thriller', rating: 'TV-MA',
    runtime: '52 min', tags: ['complex', 'tense', 'serialized', 'dark'],
    engagementScore: 0.94, emoji: '⏳', thumbnail: thumb('⏳', '#1a1a2e', '#16213e', 'Dark S3'),
    maturity: 'adult', calmScore: 0.1, complexity: 0.95,
  },
  {
    id: 'outer-range', title: 'Outer Range', genre: 'Sci-Fi Western', rating: 'TV-14',
    runtime: '48 min', tags: ['mystery', 'tense', 'serialized', 'outdoor'],
    engagementScore: 0.91, emoji: '🏜️', thumbnail: thumb('🏜️', '#2d1b00', '#1a3a2a', 'Outer Range'),
    maturity: 'teen', calmScore: 0.25, complexity: 0.7,
  },
  {
    id: 'inception', title: 'Inception', genre: 'Sci-Fi Action', rating: 'PG-13',
    runtime: '148 min', tags: ['complex', 'action', 'long-film', 'cerebral'],
    engagementScore: 0.87, emoji: '🌀', thumbnail: thumb('🌀', '#0f0f23', '#1a1a3e', 'Inception'),
    maturity: 'teen', calmScore: 0.15, complexity: 0.9,
  },
  {
    id: 'the-office', title: 'The Office S1', genre: 'Comedy', rating: 'TV-14',
    runtime: '22 min', tags: ['comedy', 'familiar', 'background-friendly', 'short-episodes'],
    engagementScore: 0.82, emoji: '📎', thumbnail: thumb('📎', '#2a2a1a', '#3a3a2a', 'The Office S1'),
    maturity: 'teen', calmScore: 0.6, complexity: 0.2,
  },
  {
    id: 'merlin', title: 'Merlin Chronicles', genre: 'Fantasy Adventure', rating: 'PG',
    runtime: '95 min', tags: ['adventure', 'family', 'fantasy', 'all-ages'],
    engagementScore: 0.76, emoji: '🧙', thumbnail: thumb('🧙', '#1a0a2e', '#2a1a3e', 'Merlin Chronicles'),
    maturity: 'family', calmScore: 0.35, complexity: 0.4,
  },
  {
    id: 'lion-king', title: 'The Lion King', genre: 'Animation', rating: 'G',
    runtime: '88 min', tags: ['animated', 'family', 'musical', 'all-ages', 'classic'],
    engagementScore: 0.71, emoji: '🦁', thumbnail: thumb('🦁', '#3a2a00', '#2a1a00', 'The Lion King'),
    maturity: 'family', calmScore: 0.5, complexity: 0.2,
  },
  {
    id: 'planet-earth', title: 'Planet Earth III', genre: 'Documentary', rating: 'TV-G',
    runtime: '28 min', tags: ['documentary', 'educational', 'calming', 'nature', 'short-episodes'],
    engagementScore: 0.65, emoji: '🌍', thumbnail: thumb('🌍', '#0a2a1a', '#1a3a2a', 'Planet Earth III'),
    maturity: 'family', calmScore: 0.9, complexity: 0.3,
  },
  {
    id: 'bluey', title: 'Bluey S4', genre: 'Animation', rating: 'TV-Y',
    runtime: '7 min', tags: ['kids', 'animated', 'calming', 'short-episodes', 'soothing', 'G-rated'],
    engagementScore: 0.58, emoji: '🐕', thumbnail: thumb('🐕', '#1a2a3e', '#2a3a4e', 'Bluey S4'),
    maturity: 'kids', calmScore: 0.85, complexity: 0.05,
  },
];

// ---------------------------------------------------------------------------
// Music catalog (8 items)
// ---------------------------------------------------------------------------

const musicCatalog: PlatformItem[] = [
  {
    id: 'sleep-stories', title: 'Sleep Stories Podcast', genre: 'Podcast · Sleep',
    rating: 'E', runtime: '45 min', tags: ['calming', 'sleep', 'narrated', 'long-form'],
    engagementScore: 0.92, emoji: '🌙', thumbnail: thumb('🌙', '#0a0a2e', '#1a1a3e', 'Sleep Stories'),
    maturity: 'family', calmScore: 0.95, complexity: 0.1,
  },
  {
    id: 'deep-focus', title: 'Deep Focus Playlist', genre: 'Playlist · Ambient',
    rating: 'E', runtime: '120 min', tags: ['focus', 'ambient', 'instrumental', 'background-friendly'],
    engagementScore: 0.88, emoji: '🎯', thumbnail: thumb('🎯', '#0a1a2e', '#1a2a3e', 'Deep Focus'),
    maturity: 'family', calmScore: 0.8, complexity: 0.05,
  },
  {
    id: 'morning-jazz', title: 'Morning Jazz Mix', genre: 'Playlist · Jazz',
    rating: 'E', runtime: '90 min', tags: ['jazz', 'morning', 'relaxed', 'background-friendly'],
    engagementScore: 0.85, emoji: '☕', thumbnail: thumb('☕', '#2a1a0a', '#3a2a1a', 'Morning Jazz'),
    maturity: 'family', calmScore: 0.65, complexity: 0.15,
  },
  {
    id: 'true-crime', title: 'True Crime Weekly', genre: 'Podcast · Crime',
    rating: 'M', runtime: '55 min', tags: ['true-crime', 'serialized', 'complex', 'adult'],
    engagementScore: 0.81, emoji: '🔍', thumbnail: thumb('🔍', '#1a0a0a', '#2e1a1a', 'True Crime'),
    maturity: 'adult', calmScore: 0.2, complexity: 0.7,
  },
  {
    id: 'kids-singalong', title: 'Kids Sing-Along', genre: 'Playlist · Children',
    rating: 'E', runtime: '35 min', tags: ['kids', 'singalong', 'upbeat', 'interactive'],
    engagementScore: 0.76, emoji: '🎤', thumbnail: thumb('🎤', '#2a0a2e', '#3a1a3e', 'Sing-Along'),
    maturity: 'kids', calmScore: 0.3, complexity: 0.05,
  },
  {
    id: 'lofi-study', title: 'Lo-Fi Study Beats', genre: 'Playlist · Lo-Fi',
    rating: 'E', runtime: '180 min', tags: ['lofi', 'study', 'ambient', 'background-friendly', 'instrumental'],
    engagementScore: 0.72, emoji: '📚', thumbnail: thumb('📚', '#1a1a0a', '#2a2a1a', 'Lo-Fi Study'),
    maturity: 'family', calmScore: 0.75, complexity: 0.05,
  },
  {
    id: 'pop-hits', title: 'Pop Hits 2024', genre: 'Playlist · Pop',
    rating: 'E', runtime: '60 min', tags: ['pop', 'upbeat', 'high-energy', 'trending'],
    engagementScore: 0.67, emoji: '🎵', thumbnail: thumb('🎵', '#2e0a1a', '#3e1a2a', 'Pop Hits'),
    maturity: 'family', calmScore: 0.15, complexity: 0.1,
  },
  {
    id: 'classical-baby', title: 'Classical for Baby', genre: 'Playlist · Classical',
    rating: 'E', runtime: '60 min', tags: ['classical', 'baby', 'calming', 'soothing', 'instrumental'],
    engagementScore: 0.60, emoji: '🎻', thumbnail: thumb('🎻', '#1a0a1a', '#2a1a2a', 'Classical Baby'),
    maturity: 'kids', calmScore: 0.95, complexity: 0.1,
  },
];

// ---------------------------------------------------------------------------
// E-Commerce catalog (8 items)
// ---------------------------------------------------------------------------

const ecommerceCatalog: PlatformItem[] = [
  {
    id: 'headphones', title: 'Noise-Canceling Headphones', genre: 'Electronics · Audio',
    rating: 'All', runtime: '$349', tags: ['premium', 'tech', 'personal', 'focus'],
    engagementScore: 0.93, emoji: '🎧', thumbnail: thumb('🎧', '#0a0a1e', '#1a1a2e', 'Headphones'),
    maturity: 'adult', calmScore: 0.5, complexity: 0.6,
  },
  {
    id: 'smartwatch', title: 'Smart Watch Pro', genre: 'Electronics · Wearable',
    rating: 'All', runtime: '$299', tags: ['premium', 'tech', 'fitness', 'personal'],
    engagementScore: 0.89, emoji: '⌚', thumbnail: thumb('⌚', '#1a1a0a', '#2a2a1a', 'Smart Watch'),
    maturity: 'adult', calmScore: 0.4, complexity: 0.5,
  },
  {
    id: 'baby-blanket', title: 'Organic Baby Blanket', genre: 'Baby · Bedding',
    rating: 'All', runtime: '$45', tags: ['baby', 'organic', 'comfort', 'calming', 'gift'],
    engagementScore: 0.84, emoji: '🧸', thumbnail: thumb('🧸', '#2a1a1a', '#3a2a2a', 'Baby Blanket'),
    maturity: 'kids', calmScore: 0.9, complexity: 0.05,
  },
  {
    id: 'lego-starwars', title: 'LEGO Star Wars Set', genre: 'Toys · Building',
    rating: 'All', runtime: '$89', tags: ['kids', 'building', 'family', 'interactive', 'gift'],
    engagementScore: 0.80, emoji: '🧱', thumbnail: thumb('🧱', '#1a1a2e', '#2a2a3e', 'LEGO Set'),
    maturity: 'family', calmScore: 0.4, complexity: 0.3,
  },
  {
    id: 'espresso', title: 'Espresso Machine', genre: 'Kitchen · Appliance',
    rating: 'All', runtime: '$499', tags: ['premium', 'kitchen', 'adult', 'morning'],
    engagementScore: 0.75, emoji: '☕', thumbnail: thumb('☕', '#2a1a0a', '#3a2a1a', 'Espresso'),
    maturity: 'adult', calmScore: 0.5, complexity: 0.4,
  },
  {
    id: 'art-kit', title: 'Kids Art Supply Kit', genre: 'Toys · Creative',
    rating: 'All', runtime: '$35', tags: ['kids', 'creative', 'educational', 'family', 'gift'],
    engagementScore: 0.70, emoji: '🎨', thumbnail: thumb('🎨', '#2e1a2e', '#3e2a3e', 'Art Kit'),
    maturity: 'kids', calmScore: 0.55, complexity: 0.15,
  },
  {
    id: 'desk-mat', title: 'Standing Desk Mat', genre: 'Office · Ergonomic',
    rating: 'All', runtime: '$79', tags: ['office', 'ergonomic', 'adult', 'focus'],
    engagementScore: 0.66, emoji: '🖥️', thumbnail: thumb('🖥️', '#0a1a1a', '#1a2a2a', 'Desk Mat'),
    maturity: 'adult', calmScore: 0.5, complexity: 0.2,
  },
  {
    id: 'board-game', title: 'Board Game Collection', genre: 'Games · Family',
    rating: 'All', runtime: '$55', tags: ['family', 'games', 'interactive', 'all-ages', 'gift'],
    engagementScore: 0.59, emoji: '🎲', thumbnail: thumb('🎲', '#1a2a1a', '#2a3a2a', 'Board Games'),
    maturity: 'family', calmScore: 0.45, complexity: 0.25,
  },
];

// ---------------------------------------------------------------------------
// Ride Matching catalog (8 items)
// ---------------------------------------------------------------------------

const rideMatchingCatalog: PlatformItem[] = [
  {
    id: 'uberx', title: 'UberX', genre: 'Standard', rating: '4 min',
    runtime: '$12', tags: ['standard', 'affordable', 'everyday'],
    engagementScore: 0.85, emoji: '🚗', thumbnail: thumb('🚗', '#1a1a2e', '#2a2a3e', 'UberX'),
    maturity: 'family', calmScore: 0.5, complexity: 0.3,
  },
  {
    id: 'comfort', title: 'Uber Comfort', genre: 'Comfort', rating: '6 min',
    runtime: '$18', tags: ['comfort', 'spacious', 'quiet'],
    engagementScore: 0.80, emoji: '🚙', thumbnail: thumb('🚙', '#1a2a1a', '#2a3a2a', 'Comfort'),
    maturity: 'family', calmScore: 0.7, complexity: 0.5,
  },
  {
    id: 'black', title: 'Uber Black', genre: 'Premium', rating: '8 min',
    runtime: '$45', tags: ['premium', 'luxury', 'professional'],
    engagementScore: 0.75, emoji: '🖤', thumbnail: thumb('🖤', '#0a0a0a', '#1a1a1a', 'Uber Black'),
    maturity: 'adult', calmScore: 0.9, complexity: 0.8,
  },
  {
    id: 'pool', title: 'UberX Share', genre: 'Shared', rating: '12 min',
    runtime: '$7', tags: ['budget', 'shared', 'eco'],
    engagementScore: 0.70, emoji: '👥', thumbnail: thumb('👥', '#1a1a3e', '#2a2a4e', 'Pool'),
    maturity: 'family', calmScore: 0.3, complexity: 0.2,
  },
  {
    id: 'green', title: 'Uber Green', genre: 'Eco', rating: '5 min',
    runtime: '$14', tags: ['eco', 'electric', 'sustainable'],
    engagementScore: 0.72, emoji: '🌱', thumbnail: thumb('🌱', '#0a2a0a', '#1a3a1a', 'Green'),
    maturity: 'family', calmScore: 0.6, complexity: 0.4,
  },
  {
    id: 'xl', title: 'UberXL', genre: 'XL', rating: '7 min',
    runtime: '$22', tags: ['spacious', 'group', 'suv'],
    engagementScore: 0.68, emoji: '🚐', thumbnail: thumb('🚐', '#2a1a0a', '#3a2a1a', 'XL'),
    maturity: 'family', calmScore: 0.5, complexity: 0.4,
  },
  {
    id: 'moto', title: 'Uber Moto', genre: 'Moto', rating: '3 min',
    runtime: '$5', tags: ['fast', 'budget', 'solo'],
    engagementScore: 0.60, emoji: '🏍️', thumbnail: thumb('🏍️', '#2e1a0a', '#3e2a1a', 'Moto'),
    maturity: 'adult', calmScore: 0.1, complexity: 0.2,
  },
  {
    id: 'shuttle', title: 'Uber Shuttle', genre: 'Shuttle', rating: '15 min',
    runtime: '$4', tags: ['budget', 'commute', 'scheduled'],
    engagementScore: 0.55, emoji: '🚌', thumbnail: thumb('🚌', '#1a1a0a', '#2a2a1a', 'Shuttle'),
    maturity: 'family', calmScore: 0.4, complexity: 0.1,
  },
];

// ---------------------------------------------------------------------------
// Food Delivery catalog (8 items)
// ---------------------------------------------------------------------------

const foodDeliveryCatalog: PlatformItem[] = [
  {
    id: 'thai-bowl', title: 'Thai Comfort Bowl', genre: 'Thai', rating: '4.6★',
    runtime: '25 min', tags: ['comfort', 'spicy', 'hearty'],
    engagementScore: 0.88, emoji: '🍜', thumbnail: thumb('🍜', '#2a1a0a', '#3a2a1a', 'Thai Bowl'),
    maturity: 'family', calmScore: 0.3, complexity: 0.4,
  },
  {
    id: 'acai-bowl', title: 'Acai Health Bowl', genre: 'Health', rating: '4.8★',
    runtime: '15 min', tags: ['healthy', 'fresh', 'superfood'],
    engagementScore: 0.82, emoji: '🫐', thumbnail: thumb('🫐', '#1a0a2e', '#2a1a3e', 'Acai Bowl'),
    maturity: 'family', calmScore: 0.7, complexity: 0.3,
  },
  {
    id: 'burrito', title: 'Quick Burrito', genre: 'Mexican', rating: '4.3★',
    runtime: '10 min', tags: ['fast', 'filling', 'budget'],
    engagementScore: 0.79, emoji: '🌯', thumbnail: thumb('🌯', '#2a2a0a', '#3a3a1a', 'Burrito'),
    maturity: 'family', calmScore: 0.2, complexity: 0.2,
  },
  {
    id: 'ramen', title: 'Discovery Ramen', genre: 'Japanese', rating: '4.7★',
    runtime: '30 min', tags: ['discovery', 'artisan', 'umami'],
    engagementScore: 0.85, emoji: '🍜', thumbnail: thumb('🍜', '#1a0a0a', '#2e1a1a', 'Ramen'),
    maturity: 'family', calmScore: 0.4, complexity: 0.6,
  },
  {
    id: 'pizza', title: 'Margherita Pizza', genre: 'Italian', rating: '4.5★',
    runtime: '20 min', tags: ['classic', 'comfort', 'family'],
    engagementScore: 0.76, emoji: '🍕', thumbnail: thumb('🍕', '#2e1a0a', '#3e2a1a', 'Pizza'),
    maturity: 'family', calmScore: 0.3, complexity: 0.2,
  },
  {
    id: 'sushi', title: 'Sushi Platter', genre: 'Japanese', rating: '4.9★',
    runtime: '35 min', tags: ['premium', 'fresh', 'date-night'],
    engagementScore: 0.74, emoji: '🍣', thumbnail: thumb('🍣', '#0a1a2e', '#1a2a3e', 'Sushi'),
    maturity: 'adult', calmScore: 0.6, complexity: 0.7,
  },
  {
    id: 'caesar', title: 'Caesar Salad', genre: 'Health', rating: '4.2★',
    runtime: '12 min', tags: ['healthy', 'light', 'quick'],
    engagementScore: 0.65, emoji: '🥗', thumbnail: thumb('🥗', '#0a2a0a', '#1a3a1a', 'Caesar'),
    maturity: 'family', calmScore: 0.8, complexity: 0.1,
  },
  {
    id: 'tacos', title: 'Late Night Tacos', genre: 'Mexican', rating: '4.4★',
    runtime: '18 min', tags: ['late-night', 'comfort', 'indulgent'],
    engagementScore: 0.62, emoji: '🌮', thumbnail: thumb('🌮', '#2a0a1a', '#3a1a2a', 'Tacos'),
    maturity: 'family', calmScore: 0.2, complexity: 0.2,
  },
];

// ---------------------------------------------------------------------------
// Context presets per platform
// ---------------------------------------------------------------------------

const streamingContexts: Record<string, PlatformContext> = {
  bedtime: {
    key: 'bedtime', label: 'Bedtime', emoji: '🌙',
    subtitle: '8:45 PM — winding down for sleep',
    signals: [
      { emoji: '🕐', label: '8:45 PM' }, { emoji: '👶', label: 'Ages 4-7' },
      { emoji: '😴', label: 'Low energy' }, { emoji: '📱', label: 'Tablet' },
    ],
    defaults: { time: 1.0, viewer: 0.0, energy: 0.0, device: 0.25, prophecy: 0.8 },
  },
  'solo-morning': {
    key: 'solo-morning', label: 'Solo Morning', emoji: '☕',
    subtitle: '7:15 AM — adult solo time before the day starts',
    signals: [
      { emoji: '🕐', label: '7:15 AM' }, { emoji: '🧑', label: 'Solo adult' },
      { emoji: '😌', label: 'Relaxed' }, { emoji: '📺', label: 'TV' },
    ],
    defaults: { time: 0.25, viewer: 1.0, energy: 0.5, device: 0.75, prophecy: 0.3 },
  },
  'family-weekend': {
    key: 'family-weekend', label: 'Family Weekend', emoji: '🍿',
    subtitle: 'Saturday 3 PM — whole family together',
    signals: [
      { emoji: '🕐', label: '3:00 PM' }, { emoji: '👨‍👩‍👧‍👦', label: 'Full family' },
      { emoji: '🎉', label: 'High energy' }, { emoji: '📺', label: 'Living room TV' },
    ],
    defaults: { time: 0.5, viewer: 0.25, energy: 0.85, device: 1.0, prophecy: 0.0 },
  },
  'focus-session': {
    key: 'focus-session', label: 'Focus Session', emoji: '🎧',
    subtitle: 'Tuesday 10 AM — background while working',
    signals: [
      { emoji: '🕐', label: '10:00 AM' }, { emoji: '🧑', label: 'Solo adult' },
      { emoji: '🧠', label: 'Focused' }, { emoji: '💻', label: 'Laptop' },
    ],
    defaults: { time: 0.35, viewer: 1.0, energy: 0.3, device: 0.5, prophecy: 0.5 },
  },
};

const musicContexts: Record<string, PlatformContext> = {
  'wind-down': {
    key: 'wind-down', label: 'Wind Down', emoji: '🌙',
    subtitle: '9:30 PM — preparing for sleep',
    signals: [
      { emoji: '🕐', label: '9:30 PM' }, { emoji: '👤', label: 'Personal' },
      { emoji: '😴', label: 'Sleepy' }, { emoji: '📱', label: 'Phone' },
    ],
    defaults: { time: 1.0, viewer: 0.5, energy: 0.0, device: 0.0, prophecy: 0.9 },
  },
  'morning-commute': {
    key: 'morning-commute', label: 'Morning Commute', emoji: '🚗',
    subtitle: '7:45 AM — driving to work',
    signals: [
      { emoji: '🕐', label: '7:45 AM' }, { emoji: '🧑', label: 'Solo' },
      { emoji: '☕', label: 'Waking up' }, { emoji: '🎧', label: 'Headphones' },
    ],
    defaults: { time: 0.25, viewer: 1.0, energy: 0.6, device: 0.0, prophecy: 0.2 },
  },
  'family-play': {
    key: 'family-play', label: 'Family Playtime', emoji: '🎈',
    subtitle: 'Sunday 11 AM — playing with the kids',
    signals: [
      { emoji: '🕐', label: '11:00 AM' }, { emoji: '👨‍👩‍👧', label: 'Family' },
      { emoji: '🎉', label: 'Playful' }, { emoji: '🔊', label: 'Speaker' },
    ],
    defaults: { time: 0.4, viewer: 0.0, energy: 0.9, device: 0.75, prophecy: 0.0 },
  },
  'deep-work': {
    key: 'deep-work', label: 'Deep Work', emoji: '💻',
    subtitle: 'Wednesday 2 PM — coding session',
    signals: [
      { emoji: '🕐', label: '2:00 PM' }, { emoji: '🧑', label: 'Solo' },
      { emoji: '🧠', label: 'Focused' }, { emoji: '🎧', label: 'Headphones' },
    ],
    defaults: { time: 0.45, viewer: 1.0, energy: 0.25, device: 0.0, prophecy: 0.6 },
  },
};

const ecommerceContexts: Record<string, PlatformContext> = {
  'baby-shower': {
    key: 'baby-shower', label: 'Baby Shower Gifts', emoji: '🎁',
    subtitle: 'Shopping for a friend\'s baby shower',
    signals: [
      { emoji: '🎯', label: 'Gift buying' }, { emoji: '👶', label: 'Baby focus' },
      { emoji: '💝', label: 'Sentimental' }, { emoji: '💻', label: 'Laptop' },
    ],
    defaults: { time: 0.5, viewer: 0.0, energy: 0.4, device: 0.5, prophecy: 0.0 },
  },
  'treat-yourself': {
    key: 'treat-yourself', label: 'Treat Yourself', emoji: '✨',
    subtitle: 'Payday splurge — premium picks',
    signals: [
      { emoji: '🎯', label: 'Self-reward' }, { emoji: '🧑', label: 'Personal' },
      { emoji: '💎', label: 'Premium' }, { emoji: '📱', label: 'Phone' },
    ],
    defaults: { time: 0.5, viewer: 1.0, energy: 0.7, device: 0.0, prophecy: 0.3 },
  },
  'family-holiday': {
    key: 'family-holiday', label: 'Family Holiday', emoji: '🎄',
    subtitle: 'Holiday gifts for the whole family',
    signals: [
      { emoji: '🎯', label: 'Gift buying' }, { emoji: '👨‍👩‍👧‍👦', label: 'Family' },
      { emoji: '🎉', label: 'Festive' }, { emoji: '💻', label: 'Laptop' },
    ],
    defaults: { time: 0.5, viewer: 0.25, energy: 0.8, device: 0.5, prophecy: 0.0 },
  },
  'home-office': {
    key: 'home-office', label: 'Home Office Setup', emoji: '🖥️',
    subtitle: 'Optimizing the WFH workspace',
    signals: [
      { emoji: '🎯', label: 'Productivity' }, { emoji: '🧑', label: 'Personal' },
      { emoji: '🧠', label: 'Practical' }, { emoji: '💻', label: 'Laptop' },
    ],
    defaults: { time: 0.35, viewer: 1.0, energy: 0.4, device: 0.5, prophecy: 0.5 },
  },
};

const rideMatchingSignals: SignalConfig[] = [
  {
    key: 'time', label: 'Time of Day', emoji: '🕐', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Late night', 0.25: 'Morning commute', 0.5: 'Midday', 0.75: 'Evening commute', 1: 'Weekend' },
  },
  {
    key: 'viewer', label: 'Rider Profile', emoji: '👤', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Budget rider', 0.25: 'Standard', 0.5: 'Comfort', 0.75: 'Premium', 1: 'Executive' },
  },
  {
    key: 'energy', label: 'Trip Urgency', emoji: '⚡', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'No rush', 0.25: 'Flexible', 0.5: 'Normal', 0.75: 'Hurry', 1: 'ASAP' },
  },
  {
    key: 'device', label: 'Surge Sensitivity', emoji: '💰', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Price insensitive', 0.25: 'Flexible', 0.5: 'Moderate', 0.75: 'Sensitive', 1: 'Very sensitive' },
  },
  {
    key: 'prophecy', label: 'Commute Pattern', emoji: '🔮', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Off', 0.5: 'Learned', 1: 'Full auto' },
  },
];

const foodDeliverySignals: SignalConfig[] = [
  {
    key: 'time', label: 'Meal Time', emoji: '🕐', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Late night', 0.25: 'Breakfast', 0.5: 'Lunch', 0.75: 'Dinner', 1: 'Sunday evening' },
  },
  {
    key: 'viewer', label: 'Dietary Profile', emoji: '🥗', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Health-first', 0.25: 'Balanced', 0.5: 'No preference', 0.75: 'Indulgent', 1: 'Comfort food' },
  },
  {
    key: 'energy', label: 'Hunger Urgency', emoji: '⚡', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Browsing', 0.25: 'Peckish', 0.5: 'Hungry', 0.75: 'Starving', 1: 'Need food NOW' },
  },
  {
    key: 'device', label: 'Price Sensitivity', emoji: '💰', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'No limit', 0.25: 'Flexible', 0.5: 'Moderate', 0.75: 'Budget-conscious', 1: 'Cheapest only' },
  },
  {
    key: 'prophecy', label: 'Meal Routine', emoji: '🔮', min: 0, max: 1, step: 0.05,
    valueLabels: { 0: 'Off', 0.5: 'Learned', 1: 'Full auto' },
  },
];

const rideMatchingContexts: Record<string, PlatformContext> = {
  'morning-commute': {
    key: 'morning-commute', label: 'Morning Commute', emoji: '🌅',
    subtitle: '7:30 AM — weekday commute to office',
    signals: [
      { emoji: '🕐', label: '7:30 AM' }, { emoji: '👤', label: 'Regular rider' },
      { emoji: '⚡', label: 'On schedule' }, { emoji: '💰', label: 'Normal pricing' },
    ],
    defaults: { time: 0.25, viewer: 0.5, energy: 0.6, device: 0.5, prophecy: 0.9 },
  },
  'friday-night': {
    key: 'friday-night', label: 'Friday Night Out', emoji: '🎉',
    subtitle: '10:30 PM — heading out with friends',
    signals: [
      { emoji: '🕐', label: '10:30 PM' }, { emoji: '👤', label: 'Comfort preferred' },
      { emoji: '⚡', label: 'No rush' }, { emoji: '💰', label: 'Surge likely' },
    ],
    defaults: { time: 0.0, viewer: 0.75, energy: 0.3, device: 0.25, prophecy: 0.0 },
  },
  'airport-run': {
    key: 'airport-run', label: 'Airport Run', emoji: '✈️',
    subtitle: '5:00 AM — flight to catch, can\'t be late',
    signals: [
      { emoji: '🕐', label: '5:00 AM' }, { emoji: '👤', label: 'Premium OK' },
      { emoji: '⚡', label: 'ASAP' }, { emoji: '💰', label: 'Price flexible' },
    ],
    defaults: { time: 0.0, viewer: 0.75, energy: 1.0, device: 0.0, prophecy: 0.0 },
  },
  'weekend-errand': {
    key: 'weekend-errand', label: 'Weekend Errand', emoji: '🛒',
    subtitle: 'Saturday 2 PM — quick grocery run',
    signals: [
      { emoji: '🕐', label: '2:00 PM' }, { emoji: '👤', label: 'Budget OK' },
      { emoji: '⚡', label: 'Flexible' }, { emoji: '💰', label: 'Budget-conscious' },
    ],
    defaults: { time: 1.0, viewer: 0.25, energy: 0.3, device: 0.75, prophecy: 0.0 },
  },
};

const foodDeliveryContexts: Record<string, PlatformContext> = {
  'sunday-comfort': {
    key: 'sunday-comfort', label: 'Sunday Comfort', emoji: '🛋️',
    subtitle: 'Sunday 6 PM — cozy evening comfort food',
    signals: [
      { emoji: '🕐', label: '6:00 PM' }, { emoji: '🥗', label: 'Indulgent' },
      { emoji: '⚡', label: 'Relaxed' }, { emoji: '💰', label: 'Flexible' },
    ],
    defaults: { time: 1.0, viewer: 1.0, energy: 0.3, device: 0.25, prophecy: 0.7 },
  },
  'weekday-lunch': {
    key: 'weekday-lunch', label: 'Weekday Lunch', emoji: '💼',
    subtitle: 'Wednesday 12:30 PM — quick work lunch',
    signals: [
      { emoji: '🕐', label: '12:30 PM' }, { emoji: '🥗', label: 'Balanced' },
      { emoji: '⚡', label: 'Hungry' }, { emoji: '💰', label: 'Moderate' },
    ],
    defaults: { time: 0.5, viewer: 0.25, energy: 0.75, device: 0.5, prophecy: 0.3 },
  },
  'healthy-reset': {
    key: 'healthy-reset', label: 'Healthy Reset', emoji: '🥬',
    subtitle: 'Monday 7 PM — new week, healthy start',
    signals: [
      { emoji: '🕐', label: '7:00 PM' }, { emoji: '🥗', label: 'Health-first' },
      { emoji: '⚡', label: 'Normal' }, { emoji: '💰', label: 'Flexible' },
    ],
    defaults: { time: 0.75, viewer: 0.0, energy: 0.5, device: 0.25, prophecy: 0.5 },
  },
  'late-night-craving': {
    key: 'late-night-craving', label: 'Late Night Craving', emoji: '🌙',
    subtitle: 'Friday 11:30 PM — post-movie munchies',
    signals: [
      { emoji: '🕐', label: '11:30 PM' }, { emoji: '🥗', label: 'Comfort food' },
      { emoji: '⚡', label: 'Starving' }, { emoji: '💰', label: 'Whatever' },
    ],
    defaults: { time: 0.0, viewer: 1.0, energy: 0.9, device: 0.0, prophecy: 0.0 },
  },
};

// ---------------------------------------------------------------------------
// Platform definitions
// ---------------------------------------------------------------------------

export const platforms: Record<PlatformKey, Platform> = {
  streaming: {
    key: 'streaming', label: 'Streaming', emoji: '🎬',
    catalog: streamingCatalog,
    contexts: streamingContexts,
    contextKeys: ['bedtime', 'solo-morning', 'family-weekend', 'focus-session'],
    signalConfigs: baseSignalConfigs,
  },
  music: {
    key: 'music', label: 'Music', emoji: '🎵',
    catalog: musicCatalog,
    contexts: musicContexts,
    contextKeys: ['wind-down', 'morning-commute', 'family-play', 'deep-work'],
    signalConfigs: baseSignalConfigs,
  },
  ecommerce: {
    key: 'ecommerce', label: 'E-Commerce', emoji: '🛒',
    catalog: ecommerceCatalog,
    contexts: ecommerceContexts,
    contextKeys: ['baby-shower', 'treat-yourself', 'family-holiday', 'home-office'],
    signalConfigs: baseSignalConfigs,
  },
  ride_matching: {
    key: 'ride_matching', label: 'Ride Matching', emoji: '🚗',
    catalog: rideMatchingCatalog,
    contexts: rideMatchingContexts,
    contextKeys: ['morning-commute', 'friday-night', 'airport-run', 'weekend-errand'],
    signalConfigs: rideMatchingSignals,
  },
  food_delivery: {
    key: 'food_delivery', label: 'Food Delivery', emoji: '🍔',
    catalog: foodDeliveryCatalog,
    contexts: foodDeliveryContexts,
    contextKeys: ['sunday-comfort', 'weekday-lunch', 'healthy-reset', 'late-night-craving'],
    signalConfigs: foodDeliverySignals,
  },
};

export const platformKeys: PlatformKey[] = ['streaming', 'music', 'ecommerce', 'ride_matching', 'food_delivery'];

// ---------------------------------------------------------------------------
// Multiplier-based scoring function
// ---------------------------------------------------------------------------

function computeTimeMultiplier(item: PlatformItem, timeSignal: number): number {
  // High time signal = late/bedtime → prefer calming content
  // Low time signal = morning → prefer energizing content
  if (timeSignal > 0.8) {
    // Bedtime: strongly favor calm content
    return 0.4 + 0.6 * item.calmScore;
  } else if (timeSignal > 0.6) {
    // Evening: slightly favor calm
    return 0.6 + 0.4 * item.calmScore;
  } else if (timeSignal < 0.3) {
    // Morning: favor moderate energy
    return 0.7 + 0.3 * (1 - item.calmScore);
  }
  // Midday: neutral
  return 0.85 + 0.15 * Math.random() * 0; // deterministic 0.85
}

function computeViewerMultiplier(item: PlatformItem, viewerSignal: number): number {
  // 0 = kids, 0.25 = family, 0.5 = teens, 0.75 = adult, 1.0 = solo adult
  if (viewerSignal <= 0.15) {
    // Kids viewer
    if (item.maturity === 'adult') return 0.0; // BLOCKED
    if (item.maturity === 'teen') return 0.2;
    if (item.maturity === 'kids') return 1.2;
    return 0.9; // family
  } else if (viewerSignal <= 0.35) {
    // Family viewer
    if (item.maturity === 'adult') return 0.15;
    if (item.maturity === 'kids') return 0.9;
    return 1.0;
  } else if (viewerSignal >= 0.85) {
    // Solo adult
    if (item.maturity === 'kids') return 0.4;
    if (item.maturity === 'adult') return 1.1;
    return 0.85;
  }
  // Teens or general adult
  if (item.maturity === 'kids') return 0.5;
  return 0.9 + 0.1 * (1 - item.calmScore);
}

function computeEnergyMultiplier(item: PlatformItem, energySignal: number): number {
  // 0 = wind down, 1 = high energy
  // For wind-down: strongly prefer calm content
  // For high energy: prefer stimulating content
  const itemEnergy = 1 - item.calmScore; // flip calmScore to energyScore
  const diff = Math.abs(energySignal - itemEnergy);

  if (energySignal < 0.2) {
    // Wind-down mode: penalize non-calm content heavily
    return 0.3 + 0.7 * item.calmScore;
  } else if (energySignal > 0.8) {
    // High energy: penalize calm content
    return 0.4 + 0.6 * itemEnergy;
  }
  // Moderate: slight preference for matching energy
  return 1.0 - 0.3 * diff;
}

function computeDeviceMultiplier(item: PlatformItem, deviceSignal: number): number {
  // 0 = phone (short form), 1 = home theater (premium long form)
  const runtimeMin = parseInt(item.runtime) || 30;

  if (deviceSignal < 0.3) {
    // Small device: favor short content
    if (runtimeMin <= 15) return 1.1;
    if (runtimeMin > 90) return 0.6;
    return 0.85;
  } else if (deviceSignal > 0.7) {
    // Big screen: favor longer premium content
    if (runtimeMin >= 45) return 1.1;
    if (runtimeMin <= 10) return 0.7;
    return 0.9;
  }
  return 0.9 + 0.1 * (runtimeMin > 20 ? 1 : 0);
}

function computeProphecyBoost(item: PlatformItem, prophecySignal: number, _timeSignal: number): number {
  // Prophecy agent: auto-contextual boost (simulates scheduled preference shifts)
  if (prophecySignal < 0.1) return 1.0; // off
  // Prophecy boosts calm content at high prophecy + late time
  const calmBoost = prophecySignal * item.calmScore * 0.3;
  // Prophecy boosts kids content when viewer is kids
  const kidsBoost = item.maturity === 'kids' ? prophecySignal * 0.15 : 0;
  return 1.0 + calmBoost + kidsBoost;
}

function computeDiversityPenalty(items: { item: PlatformItem; rawScore: number }[]): number[] {
  // Penalize items that are too similar to higher-ranked items (same genre)
  const sorted = [...items].sort((a, b) => b.rawScore - a.rawScore);
  const seenGenres = new Map<string, number>();
  const penalties: Map<string, number> = new Map();

  for (const { item } of sorted) {
    const baseGenre = item.genre.split(' ')[0];
    const count = seenGenres.get(baseGenre) || 0;
    penalties.set(item.id, count > 0 ? -0.05 * count : 0);
    seenGenres.set(baseGenre, count + 1);
  }

  return items.map(({ item }) => penalties.get(item.id) || 0);
}

export function rankWithSignals(
  catalog: PlatformItem[],
  signals: SignalValues,
): RankedPlatformItem[] {
  // Step 1: compute raw scores with breakdowns
  const scoredItems = catalog.map((item) => {
    const timeMultiplier = computeTimeMultiplier(item, signals.time);
    const viewerMultiplier = computeViewerMultiplier(item, signals.viewer);
    const energyMultiplier = computeEnergyMultiplier(item, signals.energy);
    const deviceMultiplier = computeDeviceMultiplier(item, signals.device);
    const prophecyBoost = computeProphecyBoost(item, signals.prophecy, signals.time);

    const blocked = viewerMultiplier === 0.0;
    const rawScore = blocked
      ? 0
      : item.engagementScore * timeMultiplier * viewerMultiplier * energyMultiplier * deviceMultiplier * prophecyBoost;

    return { item, rawScore, timeMultiplier, viewerMultiplier, energyMultiplier, deviceMultiplier, prophecyBoost, blocked };
  });

  // Step 2: diversity penalty
  const diversityPenalties = computeDiversityPenalty(
    scoredItems.map((s) => ({ item: s.item, rawScore: s.rawScore })),
  );

  // Step 3: build breakdowns and final scores
  const withBreakdowns = scoredItems.map((s, i) => {
    const diversityPenalty = diversityPenalties[i];
    const finalScore = Math.max(0, Math.min(1, s.rawScore + diversityPenalty));

    const breakdown: ScoringBreakdown = {
      baseScore: s.item.engagementScore,
      timeMultiplier: Math.round(s.timeMultiplier * 100) / 100,
      viewerMultiplier: Math.round(s.viewerMultiplier * 100) / 100,
      energyMultiplier: Math.round(s.energyMultiplier * 100) / 100,
      deviceMultiplier: Math.round(s.deviceMultiplier * 100) / 100,
      prophecyBoost: Math.round(s.prophecyBoost * 100) / 100,
      diversityPenalty: Math.round(diversityPenalty * 100) / 100,
      blocked: s.blocked,
      blockReason: s.blocked ? 'Content maturity blocked for viewer profile' : undefined,
      finalScore: Math.round(finalScore * 100) / 100,
    };

    return { item: s.item, breakdown, finalScore, originalIndex: i };
  });

  // Step 4: sort by finalScore descending
  withBreakdowns.sort((a, b) => b.finalScore - a.finalScore);

  // Step 5: compute movement + status
  return withBreakdowns.map((entry, newIndex) => {
    const movement = entry.originalIndex - newIndex;
    let status: RankedPlatformItem['status'] = 'neutral';
    if (entry.breakdown.blocked) status = 'blocked';
    else if (movement >= 2) status = 'boosted';
    else if (movement <= -2) status = 'demoted';

    return {
      ...entry.item,
      breakdown: entry.breakdown,
      movement,
      status,
    };
  });
}

// ---------------------------------------------------------------------------
// Helper: get nearest value label for a signal
// ---------------------------------------------------------------------------

export function getSignalLabel(config: SignalConfig, value: number): string {
  const keys = Object.keys(config.valueLabels).map(Number).sort((a, b) => a - b);
  let closest = keys[0];
  let minDist = Math.abs(value - closest);
  for (const k of keys) {
    const dist = Math.abs(value - k);
    if (dist < minDist) {
      closest = k;
      minDist = dist;
    }
  }
  return config.valueLabels[closest];
}
