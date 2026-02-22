import { Show } from '@/contexts/WizardContext';

// ---------------------------------------------------------------------------
// Thumbnail generator — consistent themed gradient cards with emoji icons
// ---------------------------------------------------------------------------

const thumb = (
  emoji: string,
  gradFrom: string,
  gradTo: string,
  label: string,
): string => {
  // Encode an inline SVG as a data URI — no external dependencies
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
// Show catalog
// ---------------------------------------------------------------------------

export const mockShows: Show[] = [
  // ── Calm / Bedtime ─────────────────────────────────────────────────────
  {
    id: '1',
    title: 'Sleepy Ocean',
    description: 'Gentle underwater adventures with soft narration and calming visuals. Perfect for winding down before sleep.',
    thumbnail: thumb('🌊', '#1a1a4e', '#2d3a8c', 'Sleepy Ocean'),
    badges: ['Low Energy', 'Ages 4-7'],
    reasons: [
      'Calm pacing — gentle transitions, no jarring sounds',
      'Age-appropriate themes for ages 4-7',
      'Supports emotional regulation',
      'No cliffhangers or anxiety-inducing plots',
    ],
    category: 'bedtime',
    energyLevel: 'low',
    ageRange: '4-7',
    learningFocus: ['emotional'],
  },
  {
    id: '2',
    title: 'Whisper Woods',
    description: 'Friendly forest animals share quiet stories and soft songs in a magical woodland setting.',
    thumbnail: thumb('🌲', '#1a3a2a', '#2d6b4a', 'Whisper Woods'),
    badges: ['Low Energy', 'Ages 3-6'],
    reasons: [
      'Soft, melodic soundtrack promotes relaxation',
      'Short 10-minute episodes',
      'Gentle storylines with peaceful resolutions',
      'Encourages mindfulness and appreciation of nature',
    ],
    category: 'bedtime',
    energyLevel: 'low',
    ageRange: '3-6',
    learningFocus: ['emotional', 'literacy'],
  },
  {
    id: '3',
    title: 'Moonbeam Meditations',
    description: 'Guided breathing exercises and calming visualizations designed for young children.',
    thumbnail: thumb('🌙', '#2a1a4e', '#5a3a8c', 'Moonbeam Meditations'),
    badges: ['Low Energy', 'Ages 4-8'],
    reasons: [
      'Teaches healthy relaxation techniques',
      'Soft visuals with minimal movement',
      'Narrated by soothing voices',
      'Helps establish healthy bedtime routines',
    ],
    category: 'bedtime',
    energyLevel: 'low',
    ageRange: '4-8',
    learningFocus: ['emotional'],
  },

  // ── STEM / Science ─────────────────────────────────────────────────────
  {
    id: '4',
    title: 'Cosmic Explorers',
    description: 'Join young astronauts on incredible journeys through space, learning about planets, stars, and the universe.',
    thumbnail: thumb('🚀', '#0a1628', '#1a3a6b', 'Cosmic Explorers'),
    badges: ['Medium Energy', 'Ages 5-8'],
    reasons: [
      'Age-appropriate science concepts',
      'Encourages curiosity and wonder',
      'Accurate but accessible astronomy facts',
      'Promotes critical thinking',
    ],
    category: 'science',
    energyLevel: 'medium',
    ageRange: '5-8',
    learningFocus: ['stem'],
  },
  {
    id: '5',
    title: 'Little Lab',
    description: 'Fun experiments and discoveries with curious characters who love asking "why?" and finding out how things work.',
    thumbnail: thumb('🧪', '#1a3a3a', '#2d8c8c', 'Little Lab'),
    badges: ['Medium Energy', 'Ages 4-7'],
    reasons: [
      'Hands-on experiments kids can try at home',
      'Teaches scientific method basics',
      'Celebrates curiosity and questions',
      'Gender-diverse scientist characters',
    ],
    category: 'science',
    energyLevel: 'medium',
    ageRange: '4-7',
    learningFocus: ['stem'],
  },
  {
    id: '6',
    title: 'Number Ninjas',
    description: 'Math becomes an adventure as kids solve puzzles, count treasures, and discover patterns in everyday life.',
    thumbnail: thumb('🔢', '#1a2a3a', '#3a6a8c', 'Number Ninjas'),
    badges: ['Medium Energy', 'Ages 5-7'],
    reasons: [
      'Makes math fun and accessible',
      'Grade-aligned content for K-2',
      'Problem-solving focus',
      'Celebrates mistakes as learning opportunities',
    ],
    category: 'science',
    energyLevel: 'medium',
    ageRange: '5-7',
    learningFocus: ['stem'],
  },

  // ── Emotional Intelligence ─────────────────────────────────────────────
  {
    id: '7',
    title: 'Feelings Friends',
    description: 'A diverse group of friends learn to understand, express, and manage their emotions together.',
    thumbnail: thumb('💛', '#3a1a2a', '#8c3a5a', 'Feelings Friends'),
    badges: ['Low Energy', 'Ages 4-7'],
    reasons: [
      'Teaches emotional vocabulary',
      'Models healthy conflict resolution',
      'Diverse characters and family structures',
      'Supports social-emotional learning',
    ],
    category: 'emotional',
    energyLevel: 'low',
    ageRange: '4-7',
    learningFocus: ['emotional', 'social'],
  },
  {
    id: '8',
    title: 'Kindness Kingdom',
    description: 'Stories about empathy, sharing, and caring for others in a magical kingdom where kindness is the greatest power.',
    thumbnail: thumb('👑', '#3a2a1a', '#8c6a3a', 'Kindness Kingdom'),
    badges: ['Low Energy', 'Ages 3-6'],
    reasons: [
      'Promotes prosocial behavior',
      'Simple moral lessons without preaching',
      'Encourages perspective-taking',
      'Celebrates acts of kindness',
    ],
    category: 'emotional',
    energyLevel: 'low',
    ageRange: '3-6',
    learningFocus: ['emotional', 'social'],
  },
  {
    id: '9',
    title: 'Brave Little Me',
    description: 'A shy bunny learns to face fears, try new things, and discover inner courage with the help of loving friends.',
    thumbnail: thumb('🐰', '#2a1a3a', '#6a3a8c', 'Brave Little Me'),
    badges: ['Low Energy', 'Ages 4-6'],
    reasons: [
      'Normalizes fear and anxiety',
      'Shows gradual, realistic progress',
      'Celebrates small victories',
      'Models supportive friendships',
    ],
    category: 'emotional',
    energyLevel: 'low',
    ageRange: '4-6',
    learningFocus: ['emotional'],
  },

  // ── Social Skills ──────────────────────────────────────────────────────
  {
    id: '10',
    title: 'Playground Pals',
    description: 'Learn the art of making friends, taking turns, and navigating social situations on the playground.',
    thumbnail: thumb('🤝', '#2a3a1a', '#6a8c3a', 'Playground Pals'),
    badges: ['Medium Energy', 'Ages 4-7'],
    reasons: [
      'Teaches turn-taking and sharing',
      'Models inclusive play',
      'Shows different personality types',
      'Addresses common social challenges',
    ],
    category: 'social',
    energyLevel: 'medium',
    ageRange: '4-7',
    learningFocus: ['social'],
  },
  {
    id: '11',
    title: 'Team Builders',
    description: 'A group of friends tackle challenges by working together, learning that teamwork makes dreams work.',
    thumbnail: thumb('🏗️', '#1a2a2a', '#3a6a6a', 'Team Builders'),
    badges: ['Medium Energy', 'Ages 5-8'],
    reasons: [
      'Emphasizes collaboration over competition',
      'Shows different strengths contributing to success',
      'Models effective communication',
      'Celebrates group achievements',
    ],
    category: 'social',
    energyLevel: 'medium',
    ageRange: '5-8',
    learningFocus: ['social'],
  },

  // ── Literacy ───────────────────────────────────────────────────────────
  {
    id: '12',
    title: 'Story Sprouts',
    description: 'Animated tales that bring classic stories to life while building vocabulary and comprehension skills.',
    thumbnail: thumb('📖', '#2a1a3a', '#6a4a8c', 'Story Sprouts'),
    badges: ['Low Energy', 'Ages 4-7'],
    reasons: [
      'Builds vocabulary through context',
      'Encourages love of stories and books',
      'Highlights story structure elements',
      'Includes diverse authors and characters',
    ],
    category: 'literacy',
    energyLevel: 'low',
    ageRange: '4-7',
    learningFocus: ['literacy'],
  },
  {
    id: '13',
    title: 'Letter Land',
    description: 'Phonics adventures where letters come alive to teach reading fundamentals in fun, memorable ways.',
    thumbnail: thumb('🔤', '#1a1a3a', '#4a4a8c', 'Letter Land'),
    badges: ['Medium Energy', 'Ages 3-6'],
    reasons: [
      'Evidence-based phonics instruction',
      'Multi-sensory learning approach',
      'Repetition without boredom',
      'Celebrates reading milestones',
    ],
    category: 'literacy',
    energyLevel: 'medium',
    ageRange: '3-6',
    learningFocus: ['literacy'],
  },

  // ── Just for Fun ───────────────────────────────────────────────────────
  {
    id: '14',
    title: 'Giggle Galaxy',
    description: 'Pure silliness and laughter with wacky characters and absurd adventures that make kids (and parents) laugh out loud.',
    thumbnail: thumb('😂', '#3a1a1a', '#8c3a3a', 'Giggle Galaxy'),
    badges: ['High Energy', 'Ages 4-8'],
    reasons: [
      'Pure entertainment and joy',
      'Age-appropriate humor',
      'No hidden lessons — just fun!',
      'Great for mood-boosting',
    ],
    category: 'fun',
    energyLevel: 'high',
    ageRange: '4-8',
    learningFocus: ['fun'],
  },
  {
    id: '15',
    title: 'Dance Party Animals',
    description: 'Get up and move! Interactive dance and movement show featuring animal friends and catchy songs.',
    thumbnail: thumb('💃', '#3a2a1a', '#8c5a2a', 'Dance Party Animals'),
    badges: ['High Energy', 'Ages 3-7'],
    reasons: [
      'Promotes physical activity',
      'Interactive — encourages participation',
      'Catchy but not annoying music',
      'Gross motor skill development',
    ],
    category: 'fun',
    energyLevel: 'high',
    ageRange: '3-7',
    learningFocus: ['fun'],
  },
  {
    id: '16',
    title: 'Silly Chefs',
    description: 'Cooking shows for kids featuring easy recipes, food facts, and plenty of kitchen chaos and laughs.',
    thumbnail: thumb('👨‍🍳', '#2a1a1a', '#6a3a3a', 'Silly Chefs'),
    badges: ['Medium Energy', 'Ages 5-9'],
    reasons: [
      'Inspires interest in cooking',
      'Simple recipes families can try together',
      'Teaches kitchen safety basics',
      'Fun without being overstimulating',
    ],
    category: 'fun',
    energyLevel: 'medium',
    ageRange: '5-9',
    learningFocus: ['fun', 'stem'],
  },
];

export const childProfiles = [
  {
    id: '1',
    name: 'Emma',
    age: 6,
    avatar: '👧🏾',
  },
  {
    id: '2',
    name: 'Lucas',
    age: 4,
    avatar: '👦🏼',
  },
  {
    id: '3',
    name: 'Sophia',
    age: 8,
    avatar: '👧🏽',
  },
];
