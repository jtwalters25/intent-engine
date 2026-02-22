import React, { useState, useMemo } from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { mockShows } from '@/data/mockShows';

const ENERGY_MAP: Record<string, number> = { low: 15, medium: 50, high: 85 };

type Mood = 'happy' | 'calm' | 'silly';

const moods: { value: Mood; emoji: string; label: string; energyBias: number }[] = [
  { value: 'happy', emoji: '😊', label: 'Happy', energyBias: 60 },
  { value: 'calm', emoji: '😌', label: 'Calm', energyBias: 20 },
  { value: 'silly', emoji: '🤪', label: 'Silly', energyBias: 85 },
];

const KidBrowseScreen: React.FC = () => {
  const { state } = useWizard();
  const [mood, setMood] = useState<Mood>('happy');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const moodEnergy = moods.find((m) => m.value === mood)!.energyBias;

  const shows = useMemo(() => {
    const { ageRange } = state;
    const [minAge, maxAge] = ageRange.split('-').map(Number);

    const ageFiltered = mockShows.filter((show) => {
      const [sMin, sMax] = show.ageRange.split('-').map(Number);
      return sMin <= maxAge && sMax >= minAge;
    });

    return ageFiltered
      .map((show) => {
        const showEnergy = ENERGY_MAP[show.energyLevel] ?? 50;
        const score = 100 - Math.abs(showEnergy - moodEnergy);
        return { show, score };
      })
      .sort((a, b) => b.score - a.score)
      .map((s) => s.show);
  }, [state, moodEnergy]);

  return (
    <div className="min-h-screen py-6 px-4 sm:px-6 animate-fade-in">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold">
            What do you feel like watching?
          </h1>
        </div>

        {/* Mood picker */}
        <div className="flex justify-center gap-3 mb-8">
          {moods.map((m) => (
            <button
              key={m.value}
              onClick={() => { setMood(m.value); setExpandedId(null); }}
              className={`
                flex flex-col items-center gap-1 px-5 py-3 rounded-2xl text-sm font-semibold transition-all duration-200
                ${mood === m.value
                  ? 'bg-primary/30 ring-2 ring-primary scale-105'
                  : 'bg-card/60 hover:bg-card/80'}
              `}
            >
              <span className="text-3xl">{m.emoji}</span>
              <span>{m.label}</span>
            </button>
          ))}
        </div>

        {/* Content grid — no badges, no explanations */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {shows.map((show) => {
            const isExpanded = expandedId === show.id;
            return (
              <div
                key={show.id}
                className="kid-card cursor-pointer"
                onClick={() => setExpandedId(isExpanded ? null : show.id)}
              >
                <div className="relative overflow-hidden rounded-2xl bg-card shadow-lg ring-1 ring-white/5">
                  <div className="aspect-video overflow-hidden">
                    <img
                      src={show.thumbnail}
                      alt={show.title}
                      loading="lazy"
                      className="h-full w-full object-cover"
                    />
                  </div>
                  <div className="p-3 text-center">
                    <h3 className="font-bold text-sm sm:text-base truncate">
                      {show.title}
                    </h3>
                  </div>
                </div>

                {/* Expanded card — title + Play button only */}
                {isExpanded && (
                  <div className="mt-2 rounded-2xl bg-card/80 backdrop-blur-sm p-4 text-center animate-scale-in ring-1 ring-primary/30">
                    <h3 className="font-bold text-lg mb-3">{show.title}</h3>
                    <button className="inline-flex items-center gap-2 px-8 py-3 rounded-full bg-primary text-primary-foreground font-semibold text-base shadow-lg shadow-primary/30 transition-transform hover:scale-105">
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                      Play
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default KidBrowseScreen;
