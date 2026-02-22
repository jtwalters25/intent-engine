import React, { useMemo } from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { mockShows } from '@/data/mockShows';
import ContentRow from '@/components/ContentRow';
import ShowCard from '@/components/ShowCard';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Settings, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

const CuratedHomeScreen: React.FC = () => {
  const { state, setSelectedShow, nextStep, prevStep, setCurrentStep } = useWizard();

  // Filter and organize shows based on user preferences
  const organizedContent = useMemo(() => {
    const { timeOfDay, energyLevel, learningFocus, ageRange } = state;

    // Get base age from range (e.g., "5-7" -> [5, 7])
    const [minAge, maxAge] = ageRange.split('-').map(Number);

    // Filter shows that match age range
    const ageFilteredShows = mockShows.filter((show) => {
      const [showMin, showMax] = show.ageRange.split('-').map(Number);
      return showMin <= maxAge && showMax >= minAge;
    });

    // Sort by energy level preference
    const sortByEnergy = (shows: typeof mockShows) => {
      return [...shows].sort((a, b) => {
        const energyMap = { low: 0, medium: 50, high: 100 };
        const targetEnergy = energyLevel;
        const aDiff = Math.abs(energyMap[a.energyLevel] - targetEnergy);
        const bDiff = Math.abs(energyMap[b.energyLevel] - targetEnergy);
        return aDiff - bDiff;
      });
    };

    // Build content rows based on preferences
    const rows: { title: string; shows: typeof mockShows }[] = [];

    // Bedtime/calm content for evening/bedtime
    if (timeOfDay === 'bedtime' || timeOfDay === 'evening' || energyLevel < 40) {
      const calmShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.energyLevel === 'low')
      );
      if (calmShows.length > 0) {
        rows.push({
          title: timeOfDay === 'bedtime' 
            ? `Calm stories for ${state.selectedChild?.name}'s bedtime` 
            : `Perfect for winding down`,
          shows: calmShows,
        });
      }
    }

    // Learning focus rows
    if (learningFocus.includes('stem')) {
      const stemShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.learningFocus.includes('stem'))
      );
      if (stemShows.length > 0) {
        rows.push({
          title: 'Explore STEM & curiosity',
          shows: stemShows,
        });
      }
    }

    if (learningFocus.includes('emotional')) {
      const emotionalShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.learningFocus.includes('emotional'))
      );
      if (emotionalShows.length > 0) {
        rows.push({
          title: 'Stories about kindness and empathy',
          shows: emotionalShows,
        });
      }
    }

    if (learningFocus.includes('literacy')) {
      const literacyShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.learningFocus.includes('literacy'))
      );
      if (literacyShows.length > 0) {
        rows.push({
          title: 'Reading and language adventures',
          shows: literacyShows,
        });
      }
    }

    if (learningFocus.includes('social')) {
      const socialShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.learningFocus.includes('social'))
      );
      if (socialShows.length > 0) {
        rows.push({
          title: 'Making friends and building connections',
          shows: socialShows,
        });
      }
    }

    if (learningFocus.includes('fun')) {
      const funShows = sortByEnergy(
        ageFilteredShows.filter((s) => s.learningFocus.includes('fun'))
      );
      if (funShows.length > 0) {
        rows.push({
          title: 'Just for laughs and giggles',
          shows: funShows,
        });
      }
    }

    // Grade-aligned content
    const gradeShows = sortByEnergy(ageFilteredShows).slice(0, 8);
    if (gradeShows.length > 0) {
      rows.push({
        title: `Grade-aligned learning for ages ${ageRange}`,
        shows: gradeShows,
      });
    }

    return rows;
  }, [state]);

  const handleShowClick = (show: typeof mockShows[0]) => {
    setSelectedShow(show);
    nextStep();
  };

  const handleSettingsClick = () => {
    setCurrentStep(4); // Go to parent controls
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
              {state.selectedChild?.name}'s Picks
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
    </div>
  );
};

export default CuratedHomeScreen;
