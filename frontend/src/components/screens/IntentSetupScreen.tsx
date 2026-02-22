import React, { useState, useEffect } from 'react';
import { useWizard, TimeOfDay, LearningFocus } from '@/contexts/WizardContext';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Sun, Cloud, Moon, Stars, Beaker, BookOpen, Heart, Users, PartyPopper, ChevronDown, Clock, Zap, GraduationCap, Settings2, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import PinGateModal from '@/components/PinGateModal';

const getAutoTimeOfDay = (): TimeOfDay => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 20) return 'evening';
  return 'bedtime';
};

const getContextualGreeting = (time: TimeOfDay): { headline: string; subtext: string } => {
  switch (time) {
    case 'morning':
      return { headline: 'Good morning!', subtext: 'Starting the day with curiosity and wonder' };
    case 'afternoon':
      return { headline: 'Afternoon adventures', subtext: 'Balanced content for midday engagement' };
    case 'evening':
      return { headline: 'Time to wind down', subtext: 'Gentle, soothing content for the evening' };
    case 'bedtime':
      return { headline: 'Ready for bedtime?', subtext: 'Quiet moments before sleep' };
  }
};

const getDefaultEnergyLevel = (time: TimeOfDay): number => {
  switch (time) {
    case 'morning': return 70;
    case 'afternoon': return 60;
    case 'evening': return 30;
    case 'bedtime': return 15;
  }
};

const getEnergyModeLabel = (level: number): string => {
  if (level <= 25) return 'Very calm';
  if (level <= 40) return 'Calm';
  if (level <= 60) return 'Balanced';
  if (level <= 80) return 'Energetic';
  return 'High energy';
};

const getCtaText = (level: number): string => {
  if (level <= 25) return 'Start calm viewing';
  if (level <= 40) return 'Start relaxed viewing';
  if (level <= 60) return 'Start balanced viewing';
  if (level <= 80) return 'Start active viewing';
  return 'Start energetic viewing';
};

const getOptimizedForText = (level: number): string => {
  if (level <= 40) return 'Optimized for winding down';
  if (level <= 60) return 'A mix of calm and active content';
  return 'Optimized for active play';
};

const timeLabels: Record<TimeOfDay, { label: string; icon: React.ReactNode }> = {
  morning: { label: 'Morning', icon: <Sun className="w-4 h-4" /> },
  afternoon: { label: 'Afternoon', icon: <Cloud className="w-4 h-4" /> },
  evening: { label: 'Evening', icon: <Moon className="w-4 h-4" /> },
  bedtime: { label: 'Bedtime', icon: <Stars className="w-4 h-4" /> },
};

const learningOptions: { value: LearningFocus; label: string; icon: React.ReactNode }[] = [
  { value: 'stem', label: 'STEM & Curiosity', icon: <Beaker className="w-4 h-4" /> },
  { value: 'literacy', label: 'Literacy & Language', icon: <BookOpen className="w-4 h-4" /> },
  { value: 'emotional', label: 'Emotional Intelligence', icon: <Heart className="w-4 h-4" /> },
  { value: 'social', label: 'Social Skills', icon: <Users className="w-4 h-4" /> },
  { value: 'fun', label: 'Just for Fun', icon: <PartyPopper className="w-4 h-4" /> },
];

const ageRanges = ['3-5', '4-6', '5-7', '6-8', '7-9'];

const IntentSetupScreen: React.FC = () => {
  const {
    state,
    setTimeOfDay,
    setEnergyLevel,
    toggleLearningFocus,
    setAgeRange,
    nextStep,
  } = useWizard();

  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [isTimeOverridden, setIsTimeOverridden] = useState(false);
  const [isPinVerified, setIsPinVerified] = useState(false);
  const [showPinModal, setShowPinModal] = useState(false);

  const handlePreferencesClick = () => {
    if (isPinVerified) {
      setIsPreferencesOpen(!isPreferencesOpen);
    } else {
      setShowPinModal(true);
    }
  };

  const handlePinSuccess = () => {
    setIsPinVerified(true);
    setShowPinModal(false);
    setIsPreferencesOpen(true);
  };

  const autoDetectedTime = getAutoTimeOfDay();

  useEffect(() => {
    if (!hasInitialized) {
      const autoTime = getAutoTimeOfDay();
      const autoEnergy = getDefaultEnergyLevel(autoTime);

      setTimeOfDay(autoTime);
      setEnergyLevel(autoEnergy);

      if (autoTime === 'evening' || autoTime === 'bedtime') {
        if (!state.learningFocus.includes('emotional')) {
          toggleLearningFocus('emotional');
        }
      } else {
        if (!state.learningFocus.includes('stem')) {
          toggleLearningFocus('stem');
        }
      }

      setHasInitialized(true);
    }
  }, [hasInitialized, setTimeOfDay, setEnergyLevel, toggleLearningFocus, state.learningFocus]);

  const currentTime = state.timeOfDay || getAutoTimeOfDay();
  const greeting = getContextualGreeting(currentTime);
  const energyMode = getEnergyModeLabel(state.energyLevel);

  return (
    <div className="min-h-screen py-8 px-4 sm:px-8 animate-fade-in">
      <div className="max-w-2xl mx-auto">
        {/* Trust badge */}
        <div className="flex items-center justify-center gap-2 text-trust mb-6 animate-slide-up">
          <Shield className="w-4 h-4" />
          <span className="text-xs font-medium tracking-wide uppercase">Parent-Intent Mode</span>
        </div>

        {/* Header */}
        <div className="text-center mb-8 animate-slide-up" style={{ animationDelay: '0.05s' }}>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            {greeting.headline}
          </h1>
          <p className="text-muted-foreground">{greeting.subtext}</p>
        </div>

        {/* Context card */}
        <div className="bg-card/60 backdrop-blur-sm rounded-2xl p-6 mb-6 border border-border/50 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2 text-primary">
                <Clock className="w-5 h-5" />
              </div>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Time</span>
              <span className="text-sm font-medium text-foreground flex items-center gap-1.5 mt-0.5">
                {timeLabels[currentTime].icon}
                {timeLabels[currentTime].label}
                <span className="text-[10px] text-muted-foreground font-normal">
                  {isTimeOverridden ? '(session)' : '(auto)'}
                </span>
              </span>
            </div>

            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2 text-primary">
                <Zap className="w-5 h-5" />
              </div>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Energy</span>
              <span className="text-sm font-medium text-foreground mt-0.5">{energyMode}</span>
            </div>

            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2 text-primary">
                <GraduationCap className="w-5 h-5" />
              </div>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Ages</span>
              <span className="text-sm font-medium text-foreground mt-0.5">{state.ageRange}</span>
            </div>
          </div>
        </div>

        {/* Adjust preferences */}
        <Collapsible open={isPreferencesOpen} onOpenChange={(open) => {
          if (open && !isPinVerified) {
            setShowPinModal(true);
            return;
          }
          setIsPreferencesOpen(open);
        }}>
          <CollapsibleTrigger asChild>
            <button
              onClick={(e) => {
                if (!isPinVerified) {
                  e.preventDefault();
                  handlePreferencesClick();
                }
              }}
              className="w-full flex items-center justify-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors py-3 mb-4 animate-slide-up"
              style={{ animationDelay: '0.15s' }}
            >
              <Settings2 className="w-4 h-4" />
              <span>Adjust preferences</span>
              <ChevronDown className={cn(
                "w-4 h-4 transition-transform duration-200",
                isPreferencesOpen && "rotate-180"
              )} />
            </button>
          </CollapsibleTrigger>

          <CollapsibleContent className="space-y-6 animate-fade-in">
            {/* Session Mode */}
            <div className="bg-card/40 rounded-xl p-5 border border-border/30">
              <h3 className="text-sm font-medium text-foreground mb-3">Session Mode</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {(Object.keys(timeLabels) as TimeOfDay[]).map((time) => {
                  const isSelected = currentTime === time;
                  return (
                    <button
                      key={time}
                      onClick={() => {
                        setTimeOfDay(time);
                        setEnergyLevel(getDefaultEnergyLevel(time));
                        setIsTimeOverridden(time !== autoDetectedTime);
                      }}
                      className={cn(
                        'flex flex-col items-center gap-1.5 px-3 py-3 rounded-xl text-xs font-medium transition-all duration-200',
                        isSelected
                          ? 'bg-primary/20 text-primary ring-1 ring-primary/50'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      <span className="text-lg">{timeLabels[time].icon}</span>
                      {timeLabels[time].label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Energy Level */}
            <div className="bg-card/40 rounded-xl p-5 border border-border/30">
              <h3 className="text-sm font-medium text-foreground mb-4">Energy Level</h3>
              <div className="flex justify-between text-xs text-muted-foreground mb-3">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-energy-low" />
                  Calm
                </span>
                <span className="flex items-center gap-1">
                  High Energy
                  <span className="w-2 h-2 rounded-full bg-energy-high" />
                </span>
              </div>
              <Slider
                value={[state.energyLevel]}
                onValueChange={(values) => setEnergyLevel(values[0])}
                max={100}
                step={1}
                className="mb-3"
              />
              <p className="text-xs text-center text-muted-foreground">
                {state.energyLevel <= 40
                  ? 'Lower stimulation, calmer pacing'
                  : state.energyLevel <= 70
                    ? 'Balanced engagement and energy'
                    : 'Active and exciting content'}
              </p>
            </div>

            {/* Learning Focus */}
            <div className="bg-card/40 rounded-xl p-5 border border-border/30">
              <h3 className="text-sm font-medium text-foreground mb-3">Learning Focus</h3>
              <div className="flex flex-wrap gap-2">
                {learningOptions.map((option) => {
                  const isSelected = state.learningFocus.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      onClick={() => toggleLearningFocus(option.value)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200',
                        isSelected
                          ? 'bg-primary/20 text-primary ring-1 ring-primary/50'
                          : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
                      )}
                    >
                      {option.icon}
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Age Range */}
            <div className="bg-card/40 rounded-xl p-5 border border-border/30">
              <h3 className="text-sm font-medium text-foreground mb-3">Age Range</h3>
              <Select value={state.ageRange} onValueChange={setAgeRange}>
                <SelectTrigger className="w-full sm:w-48 bg-background/50">
                  <SelectValue placeholder="Select age range" />
                </SelectTrigger>
                <SelectContent>
                  {ageRanges.map((range) => (
                    <SelectItem key={range} value={range}>
                      Ages {range}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Optimized for */}
        <div className="text-center mb-8 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <p className="text-sm text-muted-foreground">
            {getOptimizedForText(state.energyLevel)}
          </p>
        </div>

        {/* CTA */}
        <div className="flex flex-col items-center gap-2 animate-slide-up" style={{ animationDelay: '0.25s' }}>
          <Button
            onClick={nextStep}
            size="lg"
            className="px-10 py-6 text-base font-semibold rounded-full bg-primary hover:bg-primary/90 shadow-lg shadow-primary/30 transition-all duration-300"
          >
            {getCtaText(state.energyLevel)} →
          </Button>
          {!isPreferencesOpen && (
            <button
              onClick={handlePreferencesClick}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors mt-1"
            >
              Change settings
            </button>
          )}
        </div>
      </div>

      <PinGateModal
        open={showPinModal}
        onSuccess={handlePinSuccess}
        onClose={() => setShowPinModal(false)}
      />
    </div>
  );
};

export default IntentSetupScreen;
