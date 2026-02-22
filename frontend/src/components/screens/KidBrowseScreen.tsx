import React, { useMemo } from 'react';
import { useWizard, Show } from '@/contexts/WizardContext';
import { mockShows } from '@/data/mockShows';
import ContentRow from '@/components/ContentRow';
import ShowCard from '@/components/ShowCard';
import { Play, Info } from 'lucide-react';

const ENERGY_MAP: Record<string, number> = { low: 15, medium: 50, high: 85 };

const CATEGORY_LABELS: Record<string, string> = {
  bedtime: 'Calm & Bedtime Stories',
  science: 'STEM Adventures',
  emotional: 'Feelings & Empathy',
  social: 'Making Friends',
  literacy: 'Stories & Words',
  fun: 'Just for Fun',
};

const KidBrowseScreen: React.FC = () => {
  const { state, setSelectedShow, setCurrentStep } = useWizard();
  const moodEnergy = state.energyLevel ?? 50;

  const { sortedShows, rows } = useMemo(() => {
    const { ageRange } = state;
    const [minAge, maxAge] = ageRange.split('-').map(Number);

    const ageFiltered = mockShows.filter((show) => {
      const [sMin, sMax] = show.ageRange.split('-').map(Number);
      return sMin <= maxAge && sMax >= minAge;
    });

    const sorted = ageFiltered
      .map((show) => {
        const showEnergy = ENERGY_MAP[show.energyLevel] ?? 50;
        const score = 100 - Math.abs(showEnergy - moodEnergy);
        return { show, score };
      })
      .sort((a, b) => b.score - a.score)
      .map((s) => s.show);

    // Group by category, preserving energy-score order within each group
    const categoryMap: Record<string, Show[]> = {};
    for (const show of sorted) {
      if (!categoryMap[show.category]) categoryMap[show.category] = [];
      categoryMap[show.category].push(show);
    }

    const rows = Object.entries(categoryMap)
      .filter(([, shows]) => shows.length > 0)
      .map(([cat, shows]) => ({
        title: CATEGORY_LABELS[cat] ?? cat,
        shows,
      }));

    return { sortedShows: sorted, rows };
  }, [state, moodEnergy]);

  const featured = sortedShows[0];

  const handleShowClick = (show: Show) => {
    setSelectedShow(show);
    setCurrentStep(2);
  };

  return (
    <div className="min-h-screen bg-[#141414] text-white overflow-x-hidden">

      {/* ── Hero Banner ── */}
      {featured && (
        <div className="relative h-[72vh] min-h-[440px] w-full">
          {/* Backdrop image + gradients */}
          <div className="absolute inset-0">
            <img
              src={featured.thumbnail}
              alt={featured.title}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/55 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-r from-[#141414]/90 via-[#141414]/35 to-transparent" />
          </div>

          {/* Hero text + actions */}
          <div className="relative h-full flex flex-col justify-end pb-20 px-8 sm:px-12 md:px-16">
            <h1 className="text-5xl sm:text-6xl font-black mb-4 leading-tight drop-shadow-xl max-w-xl">
              {featured.title}
            </h1>
            <p className="text-base sm:text-lg text-white/75 mb-7 max-w-md line-clamp-2 leading-relaxed">
              {featured.description}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleShowClick(featured)}
                className="flex items-center gap-2 px-7 py-3 bg-white text-black font-bold text-base rounded-md hover:bg-white/85 transition-colors"
              >
                <Play className="w-5 h-5 fill-black" />
                Play
              </button>
              <button
                onClick={() => handleShowClick(featured)}
                className="flex items-center gap-2 px-7 py-3 bg-white/20 text-white font-bold text-base rounded-md hover:bg-white/30 transition-colors backdrop-blur-sm"
              >
                <Info className="w-5 h-5" />
                More Info
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Content Rows ── */}
      <div className="relative z-10 -mt-20 pb-16 space-y-6">
        {/* Top picks row — all shows, best match first */}
        <ContentRow title="Top picks for you">
          {sortedShows.map((show) => (
            <ShowCard
              key={show.id}
              title={show.title}
              thumbnail={show.thumbnail}
              badges={show.badges}
              onClick={() => handleShowClick(show)}
            />
          ))}
        </ContentRow>

        {/* Per-category rows */}
        {rows.map((row) => (
          <ContentRow key={row.title} title={row.title}>
            {row.shows.map((show) => (
              <ShowCard
                key={show.id}
                title={show.title}
                thumbnail={show.thumbnail}
                badges={show.badges}
                onClick={() => handleShowClick(show)}
              />
            ))}
          </ContentRow>
        ))}
      </div>
    </div>
  );
};

export default KidBrowseScreen;
