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
import { Sun, Cloud, Moon, Stars, Beaker, BookOpen, Heart, Users, PartyPopper, ArrowLeft, ChevronDown, Clock, Zap, GraduationCap, Settings2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// Auto-detect time of day based on current hour
const getAutoTimeOfDay = (): TimeOfDay => {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 20) return 'evening';
  return 'bedtime';
};

// Get contextual greeting based on time
const getContextualGreeting = (time: TimeOfDay): { headline: string; subtext: string } => {
  switch (time) {
    case 'morning':
      return {
        headline: 'Ready for an energizing morning?',
        subtext: 'Starting the day with curiosity and wonder',
      };
    case 'afternoon':
      return {
        headline: 'Ready for afternoon adventures?',
        subtext: 'Balanced content for midday engagement',
      };
    case 'evening':
      return {
        headline: 'Ready for a calm evening?',
        subtext: 'Winding down with gentle, soothing content',
      };
    case 'bedtime':
      return {
        headline: 'Ready for bedtime stories?',
        subtext: 'Quiet moments before sleep',
      };
  }
};

// Get default energy level based on time
const getDefaultEnergyLevel = (time: TimeOfDay): number => {
  switch (time) {
    case 'morning': return 70;
    case 'afternoon': return 60;
    case 'evening': return 30;
    case 'bedtime': return 15;
  }
};

// Get energy mode label
const getEnergyModeLabel = (level: number): string => {
  if (level <= 25) return 'Very calm';
  if (level <= 40) return 'Calm';
  if (level <= 60) return 'Balanced';
  if (level <= 80) return 'Energetic';
  return 'High energy';
};

// Get dynamic CTA text based on energy level
const getCtaText = (level: number): string => {
  if (level <= 25) return 'Start calm viewing';
  if (level <= 40) return 'Start relaxed viewing';
  if (level <= 60) return 'Start balanced viewing';
  if (level <= 80) return 'Start active viewing';
  return 'Start energetic viewing';
};

// Get dynamic "Optimized for" text
const getOptimizedForText = (level: number): string => {
  if (level <= 40) {
    return 'Optimized for winding down • Designed to support healthy routines';
  }
  if (level <= 60) {
    return 'Optimized for balanced engagement • A mix of calm and active content';
  }
  return 'Optimized for active play • Energetic content for playtime';
};

const timeLabels: Record<TimeOfDay, { label: string; icon: React.ReactNode }> = {
  morning: { label: 'Morning', icon: <Sun className="w-4 h-4" /> },
  afternoon: { label: 'Afternoon', icon: <Cloud className="w-4 h-4" /> },
  evening: { label: 'Evening', icon: <Moon className="w-4 h-4" /> },
  bedtime: { label: 'Bedtime', icon: <Stars className="w-4 h-4" /> },
};

const learningOptions: { value: LearningFocus; label: string; icon: React.ReactNode; color: string }[] = [
  { value: 'stem', label: 'STEM & Curiosity', icon: <Beaker className="w-4 h-4" />, color: 'stem' },
  { value: 'literacy', label: 'Literacy & Language', icon: <BookOpen className="w-4 h-4" />, color: 'literacy' },
  { value: 'emotional', label: 'Emotional Intelligence', icon: <Heart className="w-4 h-4" />, color: 'emotional' },
  { value: 'social', label: 'Social Skills', icon: <Users className="w-4 h-4" />, color: 'social' },
  { value: 'fun', label: 'Just for Fun', icon: <PartyPopper className="w-4 h-4" />, color: 'fun' },
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
    prevStep,
  } = useWizard();

  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [isTimeOverridden, setIsTimeOverridden] = useState(false);
  
  const autoDetectedTime = getAutoTimeOfDay();

  // Auto-infer defaults on mount
  useEffect(() => {
    if (!hasInitialized) {
      const autoTime = getAutoTimeOfDay();
      const autoEnergy = getDefaultEnergyLevel(autoTime);
      
      setTimeOfDay(autoTime);
      setEnergyLevel(autoEnergy);
      
      // Set default learning focus based on time
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
        {/* Confident Contextual Header */}
        <div className="text-center mb-8 animate-slide-up">
          <p className="text-muted-foreground text-sm mb-3">
            Based on the current time and <span className="text-primary font-medium">{state.selectedChild?.name}'s</span> profile
          </p>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            {greeting.headline}
          </h1>
          <p className="text-muted-foreground">
            {greeting.subtext}
          </p>
        </div>

        {/* Auto-Inferred Context Card */}
        <div className="bg-card/60 backdrop-blur-sm rounded-2xl p-6 mb-6 border border-border/50 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <div className="grid grid-cols-3 gap-4 mb-4">
            {/* Time of Day */}
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

            {/* Energy Mode */}
            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2 text-primary">
                <Zap className="w-5 h-5" />
              </div>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Energy</span>
              <span className="text-sm font-medium text-foreground mt-0.5">{energyMode}</span>
            </div>

            {/* Age Alignment */}
            <div className="flex flex-col items-center text-center">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2 text-primary">
                <GraduationCap className="w-5 h-5" />
              </div>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">Ages</span>
              <span className="text-sm font-medium text-foreground mt-0.5">{state.ageRange}</span>
            </div>
          </div>

          {/* Reassurance Line */}
          <p className="text-xs text-muted-foreground text-center border-t border-border/30 pt-4">
            Most families choose calm content at this hour
          </p>
        </div>

        {/* Adjust Preferences - Progressive Disclosure */}
        <Collapsible open={isPreferencesOpen} onOpenChange={setIsPreferencesOpen}>
          <CollapsibleTrigger asChild>
            <button 
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
            {/* Session Mode Override */}
            <div className="bg-card/40 rounded-xl p-5 border border-border/30">
              <h3 className="text-sm font-medium text-foreground mb-3">Session Mode</h3>
              <p className="text-xs text-muted-foreground mb-4">Choose the viewing mode for this session</p>
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
              <p className="text-xs text-muted-foreground/70 mt-3 text-center italic">
                This only affects this session's recommendations
              </p>
            </div>

            {/* Energy Level Slider */}
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
              <p className="text-xs text-muted-foreground mb-4">Select one or more areas</p>
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
              <h3 className="text-sm font-medium text-foreground mb-3">Age / Grade Alignment</h3>
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
              <p className="text-xs text-muted-foreground mt-2">
                Content optimized for ages {state.ageRange}
              </p>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Optimized For Line */}
        <div className="text-center mb-8 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <p className="text-sm text-muted-foreground">
            {getOptimizedForText(state.energyLevel)}
          </p>
        </div>

        {/* Navigation */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 animate-slide-up" style={{ animationDelay: '0.25s' }}>
          <Button
            variant="ghost"
            onClick={prevStep}
            className="flex items-center gap-2 text-muted-foreground order-2 sm:order-1"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Button>
          
          <div className="flex flex-col items-center gap-2 order-1 sm:order-2">
            <Button
              onClick={nextStep}
              size="lg"
              className="px-10 py-6 text-base font-semibold rounded-full bg-primary hover:bg-primary/90 shadow-lg shadow-primary/30 transition-all duration-300"
            >
              {getCtaText(state.energyLevel)} →
            </Button>
            {!isPreferencesOpen && (
              <button 
                onClick={() => setIsPreferencesOpen(true)}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Change settings
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntentSetupScreen;
