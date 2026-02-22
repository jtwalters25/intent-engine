import React from 'react';
import { WizardProvider, useWizard } from '@/contexts/WizardContext';
import WizardProgress from '@/components/WizardProgress';
import WelcomeScreen from '@/components/screens/WelcomeScreen';
import IntentSetupScreen from '@/components/screens/IntentSetupScreen';
import CuratedHomeScreen from '@/components/screens/CuratedHomeScreen';
import ContentDetailScreen from '@/components/screens/ContentDetailScreen';
import ParentControlsScreen from '@/components/screens/ParentControlsScreen';

const TOTAL_STEPS = 5;

const WizardContent: React.FC = () => {
  const { state } = useWizard();

  const renderStep = () => {
    switch (state.currentStep) {
      case 0:
        return <WelcomeScreen />;
      case 1:
        return <IntentSetupScreen />;
      case 2:
        return <CuratedHomeScreen />;
      case 3:
        return <ContentDetailScreen />;
      case 4:
        return <ParentControlsScreen />;
      default:
        return <WelcomeScreen />;
    }
  };

  // Hide progress on welcome screen
  const showProgress = state.currentStep > 0;

  // Determine time-based background class
  const getTimeBackground = () => {
    if (!state.timeOfDay) return '';
    switch (state.timeOfDay) {
      case 'morning': return 'bg-time-morning';
      case 'afternoon': return 'bg-time-afternoon';
      case 'evening': return 'bg-time-evening';
      case 'bedtime': return 'bg-time-bedtime';
      default: return '';
    }
  };

  return (
    <div className={`min-h-screen bg-background transition-all duration-700 ${getTimeBackground()}`}>
      {showProgress && (
        <div className="sticky top-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border">
          <WizardProgress currentStep={state.currentStep} totalSteps={TOTAL_STEPS} />
        </div>
      )}
      {renderStep()}
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
