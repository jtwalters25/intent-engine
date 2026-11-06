// ---------------------------------------------------------------------------
// Expanded demo catalogs with familiar titles.
//
// SAMPLE DATA. Titles, ratings, and runtimes are real-world facts; engagement
// scores, calm/complexity scores, and stimulation profiles are illustrative
// estimates for the demo, not measurements or claims about any title.
// Stimulation pacing for SpongeBob (~5.5 cuts/min) follows the published
// figure used in Lillard & Peterson (2011); everything else is estimated.
// No studio, label, or artist artwork is used: posters are generated gradients.
// ---------------------------------------------------------------------------
import type { PlatformItem } from './demoPlatforms';
import { thumb } from './thumb';

type Maturity = PlatformItem['maturity'];
/** [cutsPerMin, loudnessLufs, motion, colorSaturation, flashesPerSec] */
type Stim = [number, number, number, number, number];

function item(
  id: string, title: string, genre: string, rating: string, runtime: string,
  engagementScore: number, maturity: Maturity, calmScore: number, complexity: number,
  tags: string[], colors: [string, string], stim?: Stim,
): PlatformItem {
  return {
    id, title, genre, rating, runtime, tags, engagementScore, maturity, calmScore, complexity,
    emoji: '',
    thumbnail: thumb('', colors[0], colors[1], title),
    ...(stim && {
      stim: {
        cutsPerMin: stim[0], loudnessLufs: stim[1], motion: stim[2],
        colorSaturation: stim[3], flashesPerSec: stim[4], provenance: 'ESTIMATED' as const,
      },
    }),
  };
}

export const streamingAdditions: PlatformItem[] = [
  // Kids and family
  item('spongebob', 'SpongeBob SquarePants', 'Cartoon Comedy', 'TV-Y7', '11 min', 0.93, 'kids', 0.15, 0.1, ['kids', 'animated', 'fast-paced', 'loud', 'familiar'], ['#f5d33a', '#2fa3d6'], [5.5, -15, 0.75, 0.92, 0.4]),
  item('loud-house', 'The Loud House', 'Cartoon Comedy', 'TV-Y7', '11 min', 0.86, 'kids', 0.2, 0.1, ['kids', 'animated', 'chaotic', 'big-family'], ['#f28c38', '#7a3fb0'], [5, -16, 0.65, 0.85, 0.3]),
  item('paw-patrol', 'PAW Patrol', 'Preschool Action', 'TV-Y', '22 min', 0.88, 'kids', 0.3, 0.05, ['kids', 'rescue', 'upbeat'], ['#2c6fd6', '#d63c3c'], [4, -17, 0.6, 0.85, 0.2]),
  item('daniel-tiger', "Daniel Tiger's Neighborhood", 'Preschool', 'TV-Y', '11 min', 0.72, 'kids', 0.92, 0.05, ['kids', 'gentle', 'feelings', 'routines', 'soothing'], ['#e8a33c', '#c0392b'], [1.5, -24, 0.2, 0.6, 0]),
  item('peppa', 'Peppa Pig', 'Preschool', 'TV-Y', '5 min', 0.8, 'kids', 0.78, 0.05, ['kids', 'short', 'gentle', 'familiar'], ['#f29bb8', '#7cc26a'], [2.5, -21, 0.25, 0.8, 0]),
  item('sesame', 'Sesame Street', 'Educational', 'TV-Y', '30 min', 0.7, 'kids', 0.6, 0.15, ['kids', 'learning', 'music', 'familiar'], ['#f2c230', '#2e9e5b'], [3, -20, 0.4, 0.85, 0.1]),
  item('gabby', "Gabby's Dollhouse", 'Preschool Musical', 'TV-Y', '24 min', 0.78, 'kids', 0.5, 0.05, ['kids', 'crafts', 'songs'], ['#e66bb0', '#7b5ad6'], [3.5, -19, 0.45, 0.9, 0.15]),
  item('avatar-tla', 'Avatar: The Last Airbender', 'Animated Adventure', 'TV-Y7', '23 min', 0.85, 'family', 0.35, 0.5, ['adventure', 'animated', 'serialized', 'family'], ['#3b8fd9', '#d9662b'], [4, -18, 0.6, 0.7, 0.2]),
  item('toy-story', 'Toy Story', 'Family Film', 'G', '81 min', 0.84, 'family', 0.5, 0.25, ['family', 'animated', 'classic', 'familiar'], ['#3b7dd8', '#f2c94c'], [4, -19, 0.55, 0.75, 0.1]),
  item('moana', 'Moana', 'Family Musical', 'PG', '107 min', 0.87, 'family', 0.45, 0.3, ['family', 'musical', 'ocean', 'adventure'], ['#1ba3a3', '#f28c38'], [4, -18, 0.55, 0.8, 0.1]),
  item('encanto', 'Encanto', 'Family Musical', 'PG', '102 min', 0.86, 'family', 0.45, 0.3, ['family', 'musical', 'familiar'], ['#d94f8a', '#f2b134'], [4.5, -18, 0.5, 0.85, 0.1]),
  item('spider-verse', 'Spider-Man: Into the Spider-Verse', 'Animated Action', 'PG', '117 min', 0.9, 'family', 0.08, 0.45, ['action', 'animated', 'fast-paced', 'stylized'], ['#d6286b', '#2b2bd6'], [14, -14, 0.9, 0.95, 1.5]),
  item('gbbs', 'The Great British Baking Show', 'Reality Competition', 'TV-PG', '58 min', 0.76, 'family', 0.88, 0.15, ['gentle', 'cozy', 'background-friendly', 'familiar'], ['#7cc2e8', '#f2c6d6'], [4, -22, 0.2, 0.55, 0]),
  item('joy-of-painting', 'The Joy of Painting', 'Art Instruction', 'TV-G', '27 min', 0.62, 'family', 0.98, 0.1, ['soothing', 'gentle', 'background-friendly', 'slow'], ['#3b8f6b', '#1e3b5c'], [0.5, -27, 0.05, 0.5, 0]),
  // Teen
  item('stranger-things', 'Stranger Things', 'Supernatural Drama', 'TV-14', '51 min', 0.95, 'teen', 0.1, 0.55, ['tense', 'serialized', 'horror', '80s'], ['#b3121c', '#140a0a'], [8, -17, 0.65, 0.45, 0.6]),
  item('wednesday', 'Wednesday', 'Mystery Comedy', 'TV-14', '50 min', 0.89, 'teen', 0.3, 0.5, ['mystery', 'dark-comedy', 'serialized'], ['#2b2b38', '#6b2b7a'], [7, -19, 0.5, 0.3, 0.3]),
  item('cobra-kai', 'Cobra Kai', 'Martial Arts Drama', 'TV-14', '30 min', 0.83, 'teen', 0.15, 0.3, ['action', 'rivalry', 'binge'], ['#d61f1f', '#f2c230'], [8, -16, 0.7, 0.6, 0.3]),
  item('top-gun-maverick', 'Top Gun: Maverick', 'Action Film', 'PG-13', '131 min', 0.9, 'teen', 0.08, 0.35, ['action', 'loud', 'blockbuster'], ['#3b6fb3', '#d98a2b'], [12, -14, 0.9, 0.55, 0.8]),
  item('dune-2', 'Dune: Part Two', 'Sci-Fi Epic', 'PG-13', '166 min', 0.88, 'teen', 0.2, 0.8, ['epic', 'long-film', 'cerebral', 'loud'], ['#c98a3b', '#3b2410'], [6, -15, 0.6, 0.45, 0.4]),
  item('b99', 'Brooklyn Nine-Nine', 'Sitcom', 'TV-14', '22 min', 0.84, 'teen', 0.55, 0.2, ['comedy', 'familiar', 'short-episodes', 'rewatchable'], ['#2b5fb3', '#f2c230'], [10, -19, 0.35, 0.6, 0.1]),
  item('friends', 'Friends', 'Sitcom', 'TV-14', '22 min', 0.86, 'teen', 0.7, 0.1, ['comedy', 'familiar', 'background-friendly', 'rewatchable'], ['#7a4fb3', '#f2b134'], [6, -20, 0.25, 0.6, 0]),
  item('seinfeld', 'Seinfeld', 'Sitcom', 'TV-PG', '22 min', 0.78, 'teen', 0.68, 0.25, ['comedy', 'familiar', 'short-episodes'], ['#3b3bb3', '#d9b23b'], [6, -21, 0.25, 0.5, 0]),
  item('abbott', 'Abbott Elementary', 'Workplace Comedy', 'TV-PG', '22 min', 0.82, 'teen', 0.65, 0.2, ['comedy', 'warm', 'short-episodes'], ['#2ba36b', '#f2d23b'], [7, -20, 0.3, 0.6, 0]),
  item('queer-eye', 'Queer Eye', 'Reality Makeover', 'TV-14', '45 min', 0.74, 'teen', 0.7, 0.2, ['feel-good', 'uplifting'], ['#e85a9b', '#f2a53b'], [6, -19, 0.3, 0.75, 0]),
  // Adult
  item('the-bear', 'The Bear', 'Kitchen Drama', 'TV-MA', '30 min', 0.91, 'adult', 0.05, 0.5, ['intense', 'stressful', 'prestige'], ['#2b4f8f', '#d93b2b'], [11, -16, 0.7, 0.45, 0.2]),
  item('breaking-bad', 'Breaking Bad', 'Crime Drama', 'TV-MA', '47 min', 0.93, 'adult', 0.12, 0.7, ['crime', 'tense', 'serialized', 'prestige'], ['#3b8f3b', '#d9b23b'], [6, -19, 0.5, 0.5, 0.2]),
  item('severance', 'Severance', 'Workplace Thriller', 'TV-MA', '50 min', 0.9, 'adult', 0.3, 0.9, ['cerebral', 'mystery', 'serialized', 'slow-burn'], ['#2b6fb3', '#d9e2e8'], [5, -21, 0.3, 0.25, 0.1]),
  item('succession', 'Succession', 'Family Drama', 'TV-MA', '60 min', 0.89, 'adult', 0.2, 0.85, ['prestige', 'tense', 'dialogue-heavy'], ['#1e2b3b', '#8a6b3b'], [9, -20, 0.4, 0.3, 0]),
  item('ted-lasso', 'Ted Lasso', 'Sports Comedy', 'TV-MA', '30 min', 0.85, 'adult', 0.65, 0.2, ['feel-good', 'warm', 'familiar'], ['#d9b23b', '#2b5fb3'], [7, -19, 0.35, 0.6, 0]),
  item('the-crown', 'The Crown', 'Royal Drama', 'TV-MA', '58 min', 0.8, 'adult', 0.55, 0.6, ['prestige', 'slow', 'historical'], ['#5c1e2b', '#c9a43b'], [3, -23, 0.2, 0.35, 0]),
  item('oppenheimer', 'Oppenheimer', 'Historical Drama', 'R', '180 min', 0.88, 'adult', 0.15, 0.9, ['long-film', 'cerebral', 'intense'], ['#d9662b', '#1a1a1a'], [11, -14, 0.6, 0.45, 1.0]),
  item('squid-game', 'Squid Game', 'Survival Thriller', 'TV-MA', '55 min', 0.94, 'adult', 0.03, 0.4, ['violent', 'tense', 'binge'], ['#d6286b', '#1e8f6b'], [7, -16, 0.6, 0.8, 0.3]),
];

export const musicAdditions: PlatformItem[] = [
  item('richter-sleep', 'Sleep · Max Richter', 'Classical · Album', 'E', '504 min', 0.7, 'family', 0.99, 0.1, ['sleep', 'ambient', 'instrumental', 'long-form'], ['#1e2b4f', '#0a0f1e']),
  item('einaudi', 'Divenire · Ludovico Einaudi', 'Piano · Album', 'E', '67 min', 0.74, 'family', 0.9, 0.2, ['piano', 'calm', 'instrumental'], ['#d9d2c3', '#3b3b4f']),
  item('norah-jones', 'Come Away with Me · Norah Jones', 'Vocal Jazz · Album', 'E', '45 min', 0.78, 'family', 0.85, 0.2, ['mellow', 'vocal', 'morning'], ['#8f5c3b', '#2b1e14']),
  item('bon-iver', 'For Emma, Forever Ago · Bon Iver', 'Folk · Album', 'E', '37 min', 0.72, 'family', 0.8, 0.4, ['mellow', 'acoustic', 'introspective'], ['#c9c9c9', '#3b4f5c']),
  item('daft-punk', 'Discovery · Daft Punk', 'Electronic · Album', 'E', '61 min', 0.86, 'family', 0.2, 0.3, ['upbeat', 'dance', 'energetic'], ['#3b2bd6', '#d62b9b']),
  item('taylor-1989', '1989 (Taylor’s Version) · Taylor Swift', 'Pop · Album', 'E', '78 min', 0.95, 'family', 0.4, 0.2, ['pop', 'singalong', 'familiar'], ['#7cc2e8', '#e8d2b3']),
  item('kendrick-gnx', 'GNX · Kendrick Lamar', 'Hip-Hop · Album', 'Explicit', '44 min', 0.94, 'adult', 0.15, 0.6, ['hip-hop', 'explicit', 'energetic'], ['#1a1a1a', '#8f1e1e']),
  item('bad-bunny', 'Debí Tirar Más Fotos · Bad Bunny', 'Latin · Album', 'Explicit', '62 min', 0.92, 'adult', 0.35, 0.4, ['latin', 'party', 'explicit'], ['#2b8f5c', '#d9b23b']),
  item('beyonce', 'Renaissance · Beyoncé', 'Dance · Album', 'Explicit', '62 min', 0.9, 'adult', 0.2, 0.4, ['dance', 'explicit', 'energetic'], ['#c9c9d9', '#5c5c6b']),
  item('billie', 'Hit Me Hard and Soft · Billie Eilish', 'Alt-Pop · Album', 'Explicit', '44 min', 0.89, 'adult', 0.55, 0.4, ['moody', 'explicit'], ['#2b4f8f', '#0a1e3b']),
  item('metallica', 'Master of Puppets · Metallica', 'Metal · Album', 'E', '55 min', 0.8, 'teen', 0.02, 0.5, ['loud', 'high-energy', 'classic'], ['#8f1e1e', '#1a1a1a']),
  item('encanto-st', 'Encanto (Soundtrack)', 'Soundtrack · Disney', 'E', '47 min', 0.88, 'kids', 0.4, 0.1, ['kids', 'singalong', 'familiar'], ['#d94f8a', '#f2b134']),
  item('moana-st', 'Moana (Soundtrack)', 'Soundtrack · Disney', 'E', '61 min', 0.84, 'kids', 0.45, 0.1, ['kids', 'singalong', 'familiar'], ['#1ba3a3', '#f28c38']),
  item('bluey-album', 'Bluey: The Album', 'Kids · Album', 'E', '36 min', 0.8, 'kids', 0.6, 0.05, ['kids', 'gentle', 'familiar'], ['#9cc9f5', '#4a7fc4']),
  item('raffi', 'Baby Beluga · Raffi', 'Kids · Album', 'E', '32 min', 0.65, 'kids', 0.8, 0.05, ['kids', 'gentle', 'classic'], ['#3b8fd9', '#c9e8f5']),
  item('lullabies', 'Bedtime Lullabies', 'Lullaby · Playlist', 'E', '60 min', 0.7, 'kids', 0.97, 0.05, ['sleep', 'kids', 'soothing'], ['#2b2b5c', '#7b6bb3']),
  item('workout', 'Workout Power Mix', 'Workout · Playlist', 'Explicit', '90 min', 0.9, 'adult', 0.03, 0.1, ['high-energy', 'gym', 'explicit'], ['#d92b2b', '#f28c38']),
  item('sunday-chill', 'Sunday Chill', 'Chill · Playlist', 'E', '120 min', 0.82, 'family', 0.85, 0.1, ['chill', 'background-friendly', 'mellow'], ['#7cc2b3', '#2b5c6b']),
  item('road-trip', 'Road Trip Singalongs', 'Rock · Playlist', 'E', '150 min', 0.85, 'family', 0.3, 0.1, ['singalong', 'classic-rock', 'upbeat'], ['#d98a2b', '#5c2b1e']),
  item('dinner-jazz', 'Dinner Party Jazz', 'Jazz · Playlist', 'E', '180 min', 0.68, 'family', 0.8, 0.3, ['jazz', 'background-friendly', 'mellow'], ['#5c3b1e', '#c9a43b']),
  item('rain-sounds', 'Rain Sounds', 'Ambient · Soundscape', 'E', '600 min', 0.66, 'family', 0.98, 0, ['sleep', 'white-noise', 'background-friendly'], ['#3b4f5c', '#1e2b3b']),
];

export const ecommerceAdditions: PlatformItem[] = [
  item('e-reader', 'E-Reader', 'Electronics · Reading', 'All', '$139', 0.86, 'adult', 0.8, 0.4, ['reading', 'calm', 'tech'], ['#3b4f5c', '#c9d2d9']),
  item('earbuds', 'Wireless Earbuds', 'Audio · Earbuds', 'All', '$179', 0.9, 'teen', 0.4, 0.4, ['tech', 'personal', 'music'], ['#e8e8e8', '#5c5c6b']),
  item('yoga-mat', 'Yoga Mat', 'Fitness · Mat', 'All', '$45', 0.74, 'adult', 0.7, 0.2, ['wellness', 'calm'], ['#7b6bb3', '#2b2b5c']),
  item('weighted-blanket', 'Weighted Blanket', 'Home · Bedding', 'All', '$89', 0.82, 'adult', 0.95, 0.1, ['sleep', 'cozy', 'calm'], ['#5c6b8f', '#2b3b4f']),
  item('kids-tablet', 'Kids Tablet', 'Kids · Tablet', 'All', '$109', 0.87, 'teen', 0.3, 0.3, ['kids', 'tech', 'screen-time'], ['#3b8fd9', '#f28c38']),
  item('picture-books', 'Picture Book Set', 'Books · Kids', 'All', '$32', 0.7, 'kids', 0.85, 0.2, ['kids', 'reading', 'bedtime'], ['#f2c230', '#d94f8a']),
  item('monitor-arm', 'Monitor Arm', 'Office · Monitor', 'All', '$59', 0.68, 'adult', 0.5, 0.5, ['work', 'ergonomic'], ['#5c5c6b', '#1e1e2b']),
  item('game-console', 'Video Game Console', 'Gaming · Console', 'All', '$499', 0.95, 'teen', 0.1, 0.6, ['gaming', 'premium', 'high-energy'], ['#2b2bd6', '#1a1a2e']),
  item('candles', 'Scented Candle Set', 'Home · Decor', 'All', '$28', 0.66, 'adult', 0.9, 0.1, ['cozy', 'gift', 'calm'], ['#d9a36b', '#5c3b1e']),
  item('running-shoes', 'Running Shoes', 'Fitness · Shoes', 'All', '$130', 0.84, 'adult', 0.2, 0.3, ['fitness', 'active'], ['#d92b2b', '#1e1e2b']),
  item('baby-monitor', 'Baby Monitor', 'Baby · Safety', 'All', '$129', 0.78, 'family', 0.6, 0.5, ['baby', 'safety', 'gift'], ['#9cc9f5', '#e8f2f5']),
  item('puzzle', '1,000-Piece Puzzle', 'Games · Puzzle', 'All', '$22', 0.64, 'family', 0.85, 0.4, ['family', 'calm', 'screen-free'], ['#2ba36b', '#f2d23b']),
];

export const rideAdditions: PlatformItem[] = [
  item('pet', 'Uber Pet', 'Pet', '5 min', '$16', 0.7, 'family', 0.5, 0.3, ['pets', 'standard'], ['#d9a36b', '#5c3b1e']),
  item('assist', 'Uber Assist', 'Accessible', '9 min', '$13', 0.68, 'family', 0.7, 0.3, ['accessible', 'assisted'], ['#3b8fd9', '#1e2b4f']),
  item('priority', 'UberX Priority', 'Priority', '2 min', '$18', 0.82, 'adult', 0.3, 0.3, ['fast', 'direct'], ['#f2c230', '#1e1e2b']),
  item('black-suv', 'Uber Black SUV', 'Premium SUV', '10 min', '$58', 0.75, 'adult', 0.7, 0.4, ['premium', 'spacious', 'luggage'], ['#1a1a1a', '#5c5c6b']),
];

// Food reuses the maturity buckets for diet: 'kids' = health-forward (boosted for
// Health-first), 'adult' = indulgent (held back for Health-first), 'family' = in between.
export const foodAdditions: PlatformItem[] = [
  item('tikka', 'Chicken Tikka Masala', 'Indian', '4.7★', '35 min', 0.86, 'family', 0.3, 0.5, ['comfort', 'spicy', 'hearty'], ['#d9662b', '#5c1e0a']),
  item('pho', 'Beef Pho', 'Vietnamese', '4.8★', '30 min', 0.84, 'family', 0.7, 0.4, ['comfort', 'soup', 'light'], ['#c9a43b', '#3b2b14']),
  item('smash-burger', 'Smash Burger', 'American', '4.5★', '20 min', 0.92, 'adult', 0.2, 0.2, ['indulgent', 'quick', 'classic'], ['#d9a36b', '#8f1e1e']),
  item('mac-cheese', 'Kids Mac & Cheese', 'Kids Menu', '4.4★', '20 min', 0.75, 'family', 0.6, 0.1, ['kids', 'mild', 'comfort'], ['#f2c230', '#d98a2b']),
  item('greek-bowl', 'Greek Salad Bowl', 'Mediterranean', '4.6★', '20 min', 0.72, 'kids', 0.8, 0.3, ['healthy', 'light', 'fresh'], ['#2ba36b', '#1e5c3b']),
  item('chicken-soup', 'Chicken Noodle Soup', 'Comfort', '4.6★', '25 min', 0.7, 'family', 0.9, 0.2, ['comfort', 'soup', 'mild'], ['#e8c97c', '#8f6b3b']),
  item('poke', 'Poke Bowl', 'Hawaiian', '4.7★', '25 min', 0.8, 'family', 0.6, 0.3, ['fresh', 'healthy'], ['#e85a6b', '#1ba3a3']),
  item('breakfast-burrito', 'Breakfast Burrito', 'Breakfast', '4.5★', '15 min', 0.83, 'family', 0.3, 0.2, ['morning', 'quick', 'hearty'], ['#f2a53b', '#5c3b1e']),
  item('avocado-toast', 'Avocado Toast', 'Cafe', '4.4★', '15 min', 0.7, 'family', 0.7, 0.2, ['morning', 'light', 'healthy'], ['#7cc26a', '#3b5c2b']),
  item('wings', 'Wings Combo', 'Bar Food', '4.3★', '30 min', 0.88, 'adult', 0.1, 0.2, ['indulgent', 'game-day', 'spicy'], ['#d93b2b', '#3b1414']),
  item('pad-thai', 'Pad Thai', 'Thai', '4.6★', '30 min', 0.85, 'family', 0.4, 0.3, ['comfort', 'noodles'], ['#f2a53b', '#8f3b1e']),
  item('bibimbap', 'Bibimbap', 'Korean', '4.8★', '35 min', 0.78, 'family', 0.5, 0.5, ['healthy', 'hearty', 'discovery'], ['#d9662b', '#2b5c3b']),
];
