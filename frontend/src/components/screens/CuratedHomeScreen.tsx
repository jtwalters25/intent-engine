import React, { useMemo, useState } from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { mockShows } from '@/data/mockShows';
import ContentRow from '@/components/ContentRow';
import ShowCard from '@/components/ShowCard';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Settings, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import PinGateModal from '@/components/PinGateModal';

// Map energy level strings to numeric values for comparison
const ENERGY_MAP: Record<string, number> = { low: 15, medium: 50, high: 85 };

const CuratedHomeScreen: React.FC = () => {
  const { state, setSelectedShow, nextStep, prevStep, setCurrentStep } = useWizard();
  const [isPinVerified, setIsPinVerified] = useState(false);
  const [showPinModal, setShowPinModal] = useState(false);

  const organizedContent = useMemo(() => {
    const { timeOfDay, energyLevel, learningFocus, ageRange } = state;

    // --- Age filter (hard filter) ---
    const [minAge, maxAge] = ageRange.split('-').map(Number);
    const ageFiltered = mockShows.filter((show) => {
      const [sMin, sMax] = show.ageRange.split('-').map(Number);
      return sMin <= maxAge && sMax >= minAge;
    });

    // --- Score every show by energy proximity ---
    const scored = ageFiltered.map((show) => {
      const showEnergy = ENERGY_MAP[show.energyLevel] ?? 50;
      const energyDiff = Math.abs(showEnergy - energyLevel);
      // 0 = perfect match, 100 = worst match → invert for sorting
      const energyScore = 100 - energyDiff;
      return { show, energyScore };
    });

    // Sort best-match first
    scored.sort((a, b) => b.energyScore - a.energyScore);

    // Determine energy preference label for row titles
    const energyLabel = energyLevel <= 30 ? 'calm' : energyLevel <= 65 ? 'balanced' : 'energetic';

    // Track which show IDs we've already placed to avoid duplicates
    const seen = new Set<string>();
    const rows: { title: string; shows: typeof mockShows }[] = [];

    const addRow = (title: string, shows: typeof mockShows) => {
      // Deduplicate against previously placed shows
      const unique = shows.filter((s) => !seen.has(s.id));
      if (unique.length === 0) return;
      unique.forEach((s) => seen.add(s.id));
      rows.push({ title, shows: unique });
    };

    // --- Row 1: Top picks based on energy match ---
    const topPicks = scored.slice(0, 6).map((s) => s.show);
    const topPickTitle =
      energyLabel === 'calm'
        ? 'Calm picks for your kids'
        : energyLabel === 'energetic'
          ? 'High-energy picks for your kids'
          : 'Top picks for your kids';
    addRow(topPickTitle, topPicks);

    // --- Row 2: Time-context row (only if it adds different content) ---
    if (timeOfDay === 'bedtime' || timeOfDay === 'evening') {
      if (energyLevel <= 50) {
        // Low/moderate energy at bedtime → show calm content
        const calmShows = scored
          .filter((s) => s.show.energyLevel === 'low')
          .map((s) => s.show);
        addRow(
          timeOfDay === 'bedtime'
            ? 'Wind-down stories for bedtime'
            : 'Perfect for a calm evening',
          calmShows,
        );
      } else {
        // High energy override at bedtime → acknowledge the override
        const activeShows = scored
          .filter((s) => s.show.energyLevel !== 'low')
          .map((s) => s.show);
        addRow('Active picks — bedtime mode overridden', activeShows);
      }
    } else if (timeOfDay === 'morning') {
      const morningShows = scored
        .filter((s) => s.show.energyLevel !== 'low')
        .map((s) => s.show);
      addRow('Start the day with energy', morningShows);
    }

    // --- Learning focus rows ---
    const focusConfig: Record<string, { filter: string; title: string }> = {
      stem: { filter: 'stem', title: 'Explore STEM & curiosity' },
      emotional: { filter: 'emotional', title: 'Stories about kindness and empathy' },
      literacy: { filter: 'literacy', title: 'Reading and language adventures' },
      social: { filter: 'social', title: 'Making friends and building connections' },
      fun: { filter: 'fun', title: 'Just for laughs and giggles' },
    };

    for (const focus of learningFocus) {
      const cfg = focusConfig[focus];
      if (!cfg) continue;
      const focusShows = scored
        .filter((s) => s.show.learningFocus.includes(cfg.filter))
        .map((s) => s.show);
      addRow(cfg.title, focusShows);
    }

    // --- Final row: remaining shows the user hasn't seen ---
    const remaining = scored.map((s) => s.show).filter((s) => !seen.has(s.id));
    if (remaining.length > 0) {
      addRow(`More for ages ${ageRange}`, remaining);
    }

    return rows;
  }, [state]);

  const handleShowClick = (show: typeof mockShows[0]) => {
    setSelectedShow(show);
    nextStep();
  };

  const handleSettingsClick = () => {
    if (isPinVerified) {
      setCurrentStep(3);
    } else {
      setShowPinModal(true);
    }
  };

  const handlePinSuccess = () => {
    setIsPinVerified(true);
    setShowPinModal(false);
    setCurrentStep(3);
  };

  return (
    <div className="min-h-screen py-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-8 md:px-12 mb-8">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={prevStep}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-foreground">
              Picked for Your Kids
            </h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="w-4 h-4 text-trust" />
              <span>Curated based on your preferences</span>
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSettingsClick}
          className="flex items-center gap-2"
        >
          <Settings className="w-4 h-4" />
          <span className="hidden sm:inline">Parent Controls</span>
        </Button>
      </div>

      {/* Content Rows */}
      <div className="space-y-8">
        {organizedContent.map((row, index) => (
          <ContentRow
            key={index}
            title={row.title}
            className="animate-slide-up"
            style={{ animationDelay: `${index * 0.1}s` } as React.CSSProperties}
          >
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

      {/* Empty State */}
      {organizedContent.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <p className="text-muted-foreground mb-4">
            No shows match your current preferences.
          </p>
          <Button onClick={prevStep}>Adjust Preferences</Button>
        </div>
      )}

      <PinGateModal
        open={showPinModal}
        onSuccess={handlePinSuccess}
        onClose={() => setShowPinModal(false)}
      />
    </div>
  );
};

export default CuratedHomeScreen;
