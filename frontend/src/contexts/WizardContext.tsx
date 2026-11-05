import React, { createContext, useContext, useState, ReactNode } from 'react';

export type TimeOfDay = 'morning' | 'afternoon' | 'evening' | 'bedtime';
export type LearningFocus = 'stem' | 'literacy' | 'emotional' | 'social' | 'fun';

export interface ChildProfile {
  id: string;
  name: string;
  age: number;
  avatar: string;
}

// Account-level profile. Unlike session preferences (soft, transient), a profile
// carries HARD parent-set policy: the maturity gate and the over-stimulation cap.
// Age range drives the stim cap — a toddler's ceiling is lower than a big kid's.
// Age-based preference defaults a profile loads when selected. These are a
// starting point the parent then adjusts; they are not hard policy.
export interface ProfileDefaults {
  energyLevel: number;          // 0-100
  ageRange: string;             // "min-max" consumed by the home age filter
  prioritizeEducational: boolean;
  lowerStimulation: boolean;
  viewingTimeLimit: number;     // one of 30/45/60/90
  endOnCalmNote: boolean;
}

export interface Profile {
  id: string;
  name: string;
  kind: 'adult' | 'kid';
  ageMin: number;
  ageMax: number | null; // null = open-ended (adult)
  avatar: string;
  maturityGate: boolean;  // kid: block adult-maturity content (hard policy)
  stimCap: number | null; // over-stimulation ceiling 0-1 (hard policy); null = none
  defaults: ProfileDefaults; // age-based starting preferences (adjustable)
}

export const SAMPLE_PROFILES: Profile[] = [
  {
    id: 'parent', name: 'Parent', kind: 'adult', ageMin: 18, ageMax: null, avatar: '🧑',
    maturityGate: false, stimCap: null,
    defaults: { energyLevel: 60, ageRange: '0-99', prioritizeEducational: false, lowerStimulation: false, viewingTimeLimit: 90, endOnCalmNote: false },
  },
  {
    id: 'toddler', name: 'Toddler', kind: 'kid', ageMin: 2, ageMax: 4, avatar: '🧸',
    maturityGate: true, stimCap: 0.3,
    defaults: { energyLevel: 20, ageRange: '2-4', prioritizeEducational: true, lowerStimulation: true, viewingTimeLimit: 30, endOnCalmNote: true },
  },
  {
    id: 'big-kid', name: 'Big Kid', kind: 'kid', ageMin: 5, ageMax: 9, avatar: '🚀',
    maturityGate: true, stimCap: 0.5,
    defaults: { energyLevel: 50, ageRange: '5-9', prioritizeEducational: true, lowerStimulation: false, viewingTimeLimit: 45, endOnCalmNote: true },
  },
];

export interface WizardState {
  currentStep: number;
  selectedChild: ChildProfile | null;
  profiles: Profile[];
  activeProfileId: string;
  profileSelected: boolean; // false until the first "Who's watching?" choice
  timeOfDay: TimeOfDay | null;
  energyLevel: number; // 0-100, where 0 is calm, 100 is high energy
  learningFocus: LearningFocus[];
  ageRange: string;
  // Parent controls
  prioritizeEducational: boolean;
  lowerStimulation: boolean;
  rotateWeekly: boolean;
  viewingTimeLimit: number; // minutes
  endOnCalmNote: boolean;
  // Selected content
  selectedShow: Show | null;
}

export interface Show {
  id: string;
  title: string;
  description: string;
  thumbnail: string;
  badges: string[];
  reasons: string[];
  category: string;
  energyLevel: 'low' | 'medium' | 'high';
  ageRange: string;
  learningFocus: LearningFocus[];
}

interface WizardContextType {
  state: WizardState;
  setCurrentStep: (step: number) => void;
  setSelectedChild: (child: ChildProfile | null) => void;
  setActiveProfile: (id: string) => void;
  setTimeOfDay: (time: TimeOfDay | null) => void;
  setEnergyLevel: (level: number) => void;
  toggleLearningFocus: (focus: LearningFocus) => void;
  setAgeRange: (range: string) => void;
  setPrioritizeEducational: (value: boolean) => void;
  setLowerStimulation: (value: boolean) => void;
  setRotateWeekly: (value: boolean) => void;
  setViewingTimeLimit: (minutes: number) => void;
  setEndOnCalmNote: (value: boolean) => void;
  setSelectedShow: (show: Show | null) => void;
  nextStep: () => void;
  prevStep: () => void;
  resetWizard: () => void;
}

const initialState: WizardState = {
  currentStep: 0,
  selectedChild: null,
  profiles: SAMPLE_PROFILES,
  activeProfileId: 'big-kid',
  profileSelected: false,
  timeOfDay: null,
  energyLevel: 50,
  learningFocus: [],
  ageRange: '5-7',
  prioritizeEducational: false,
  lowerStimulation: false,
  rotateWeekly: false,
  viewingTimeLimit: 45,
  endOnCalmNote: true,
  selectedShow: null,
};

const WizardContext = createContext<WizardContextType | undefined>(undefined);

export const WizardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, setState] = useState<WizardState>(initialState);

  const setCurrentStep = (step: number) => setState(prev => ({ ...prev, currentStep: step }));
  const setSelectedChild = (child: ChildProfile | null) => setState(prev => ({ ...prev, selectedChild: child }));

  // Selecting a profile loads its age-based default preferences (the parent can
  // then adjust them) and maps onto the legacy selectedChild for back-compat.
  const setActiveProfile = (id: string) => setState(prev => {
    const profile = prev.profiles.find(p => p.id === id);
    if (!profile) return { ...prev, activeProfileId: id, profileSelected: true };
    const d = profile.defaults;
    return {
      ...prev,
      activeProfileId: id,
      profileSelected: true,
      selectedChild: { id: profile.id, name: profile.name, age: profile.ageMin, avatar: profile.avatar },
      energyLevel: d.energyLevel,
      ageRange: d.ageRange,
      prioritizeEducational: d.prioritizeEducational,
      lowerStimulation: d.lowerStimulation,
      viewingTimeLimit: d.viewingTimeLimit,
      endOnCalmNote: d.endOnCalmNote,
    };
  });
  const setTimeOfDay = (time: TimeOfDay | null) => setState(prev => ({ ...prev, timeOfDay: time }));
  const setEnergyLevel = (level: number) => setState(prev => ({ ...prev, energyLevel: level }));
  
  const toggleLearningFocus = (focus: LearningFocus) => {
    setState(prev => ({
      ...prev,
      learningFocus: prev.learningFocus.includes(focus)
        ? prev.learningFocus.filter(f => f !== focus)
        : [...prev.learningFocus, focus],
    }));
  };

  const setAgeRange = (range: string) => setState(prev => ({ ...prev, ageRange: range }));
  const setPrioritizeEducational = (value: boolean) => setState(prev => ({ ...prev, prioritizeEducational: value }));
  const setLowerStimulation = (value: boolean) => setState(prev => ({ ...prev, lowerStimulation: value }));
  const setRotateWeekly = (value: boolean) => setState(prev => ({ ...prev, rotateWeekly: value }));
  const setViewingTimeLimit = (minutes: number) => setState(prev => ({ ...prev, viewingTimeLimit: minutes }));
  const setEndOnCalmNote = (value: boolean) => setState(prev => ({ ...prev, endOnCalmNote: value }));
  const setSelectedShow = (show: Show | null) => setState(prev => ({ ...prev, selectedShow: show }));

  const nextStep = () => setState(prev => ({ ...prev, currentStep: prev.currentStep + 1 }));
  const prevStep = () => setState(prev => ({ ...prev, currentStep: Math.max(0, prev.currentStep - 1) }));
  const resetWizard = () => setState(initialState);

  return (
    <WizardContext.Provider
      value={{
        state,
        setCurrentStep,
        setSelectedChild,
        setActiveProfile,
        setTimeOfDay,
        setEnergyLevel,
        toggleLearningFocus,
        setAgeRange,
        setPrioritizeEducational,
        setLowerStimulation,
        setRotateWeekly,
        setViewingTimeLimit,
        setEndOnCalmNote,
        setSelectedShow,
        nextStep,
        prevStep,
        resetWizard,
      }}
    >
      {children}
    </WizardContext.Provider>
  );
};

export const useWizard = () => {
  const context = useContext(WizardContext);
  if (context === undefined) {
    throw new Error('useWizard must be used within a WizardProvider');
  }
  return context;
};
