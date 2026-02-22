import React, { createContext, useContext, useState, ReactNode } from 'react';

export type TimeOfDay = 'morning' | 'afternoon' | 'evening' | 'bedtime';
export type LearningFocus = 'stem' | 'literacy' | 'emotional' | 'social' | 'fun';

export interface ChildProfile {
  id: string;
  name: string;
  age: number;
  avatar: string;
}

export interface WizardState {
  currentStep: number;
  selectedChild: ChildProfile | null;
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
