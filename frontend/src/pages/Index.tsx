import React, { useState } from 'react';
import { WizardProvider, useWizard } from '@/contexts/WizardContext';
import IntentSetupScreen from '@/components/screens/IntentSetupScreen';
import CuratedHomeScreen from '@/components/screens/CuratedHomeScreen';
import ContentDetailScreen from '@/components/screens/ContentDetailScreen';
import ParentControlsScreen from '@/components/screens/ParentControlsScreen';
import KidBrowseScreen from '@/components/screens/KidBrowseScreen';
import { Eye, EyeOff } from 'lucide-react';

const WizardContent: React.FC = () => {
  const { state } = useWizard();
  const [isKidView, setIsKidView] = useState(false);

  // Flow: Intent (0) → Browse (1) → Details (2) → Controls (3)
  const renderStep = () => {
    // Kid view replaces browse and detail steps
    if (isKidView && (state.currentStep === 1 || state.currentStep === 2)) {
      return <KidBrowseScreen />;
    }

    switch (state.currentStep) {
      case 0:
        return <IntentSetupScreen />;
      case 1:
        return <CuratedHomeScreen />;
      case 2:
        return <ContentDetailScreen />;
      case 3:
        return <ParentControlsScreen />;
      default:
        return <IntentSetupScreen />;
    }
  };

  // Time-based ambient background
  const getTimeBackground = () => {
    if (!state.timeOfDay) return '';
    const map: Record<string, string> = {
      morning: 'bg-time-morning',
      afternoon: 'bg-time-afternoon',
      evening: 'bg-time-evening',
      bedtime: 'bg-time-bedtime',
    };
    return map[state.timeOfDay] ?? '';
  };

  // Toggle only visible on steps 0-2 (not on parent controls)
  const showToggle = state.currentStep >= 0 && state.currentStep <= 2;

  return (
    <div className={`min-h-screen bg-background transition-all duration-700 ${getTimeBackground()} ${isKidView ? 'kid-mode' : ''}`}>
      {renderStep()}

      {showToggle && (
        <button
          onClick={() => setIsKidView(!isKidView)}
          className={`
            fixed bottom-6 right-6 z-50
            flex items-center gap-2 px-4 py-2.5 rounded-full
            text-sm font-medium shadow-lg
            transition-all duration-300
            ${isKidView
              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
              : 'bg-card/90 backdrop-blur-sm text-foreground border border-border/50 hover:bg-card'}
          `}
        >
          {isKidView ? (
            <>
              <EyeOff className="w-4 h-4" />
              Back to Parent View
            </>
          ) : (
            <>
              <Eye className="w-4 h-4" />
              Preview as Kid
            </>
          )}
        </button>
      )}
    </div>
  );
};

const Index: React.FC = () => {
  return (
    <WizardProvider>
      <WizardContent />
    </WizardProvider>
  );
};

export default Index;
