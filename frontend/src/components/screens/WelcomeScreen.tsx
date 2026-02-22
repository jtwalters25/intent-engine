import React from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { childProfiles } from '@/data/mockShows';
import { Button } from '@/components/ui/button';
import { Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

const WelcomeScreen: React.FC = () => {
  const { state, setSelectedChild, nextStep } = useWizard();

  const handleChildSelect = (child: typeof childProfiles[0]) => {
    setSelectedChild(child);
  };

  const handleContinue = () => {
    if (state.selectedChild) {
      nextStep();
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 animate-fade-in">
      {/* Trust Badge */}
      <div className="flex items-center gap-2 text-trust mb-8 animate-slide-up">
        <Shield className="w-5 h-5" />
        <span className="text-sm font-medium">Parent-Intent Mode — You're in control</span>
      </div>

      {/* Welcome Message */}
      <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-center mb-4 animate-slide-up" style={{ animationDelay: '0.1s' }}>
        Let's find the perfect shows
        <br />
        <span className="text-primary">for tonight</span>
      </h1>

      <p className="text-muted-foreground text-center mb-12 max-w-md animate-slide-up" style={{ animationDelay: '0.2s' }}>
        Choose your child's profile to get personalized content based on your preferences
      </p>

      {/* Profile Selection */}
      <div className="flex flex-wrap justify-center gap-6 mb-12">
        {childProfiles.map((child, index) => (
          <button
            key={child.id}
            onClick={() => handleChildSelect(child)}
            className={cn(
              'flex flex-col items-center gap-3 p-6 rounded-2xl transition-all duration-300 animate-scale-in',
              'hover:scale-105 hover:bg-card',
              state.selectedChild?.id === child.id
                ? 'bg-card ring-2 ring-primary shadow-lg shadow-primary/20'
                : 'bg-secondary/50'
            )}
            style={{ animationDelay: `${0.3 + index * 0.1}s` }}
          >
            <div className={cn(
              'w-20 h-20 sm:w-24 sm:h-24 rounded-full flex items-center justify-center text-4xl sm:text-5xl',
              'bg-gradient-to-br from-secondary to-muted transition-transform duration-300',
              state.selectedChild?.id === child.id && 'scale-110'
            )}>
              {child.avatar}
            </div>
            <div className="text-center">
              <p className="font-semibold text-foreground">{child.name}</p>
              <p className="text-sm text-muted-foreground">age {child.age}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Continue Button */}
      <Button
        onClick={handleContinue}
        disabled={!state.selectedChild}
        size="lg"
        className={cn(
          'px-8 py-6 text-lg font-semibold rounded-full transition-all duration-300 animate-slide-up',
          state.selectedChild
            ? 'bg-primary hover:bg-primary/90 shadow-lg shadow-primary/30'
            : 'opacity-50 cursor-not-allowed'
        )}
        style={{ animationDelay: '0.6s' }}
      >
        Get Started →
      </Button>
    </div>
  );
};

export default WelcomeScreen;
