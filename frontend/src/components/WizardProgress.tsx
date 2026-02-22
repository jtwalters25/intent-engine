import React from 'react';
import { cn } from '@/lib/utils';

interface WizardProgressProps {
  currentStep: number;
  totalSteps: number;
}

const stepLabels = ['Welcome', 'Intent', 'Browse', 'Details', 'Controls'];

const WizardProgress: React.FC<WizardProgressProps> = ({ currentStep, totalSteps }) => {
  return (
    <div className="flex items-center justify-center gap-2 py-4">
      {Array.from({ length: totalSteps }, (_, i) => (
        <React.Fragment key={i}>
          <div className="flex flex-col items-center gap-1">
            <div
              className={cn(
                'h-2.5 w-2.5 rounded-full transition-all duration-300',
                i < currentStep
                  ? 'bg-primary scale-100'
                  : i === currentStep
                  ? 'bg-primary scale-125 animate-glow-pulse'
                  : 'bg-muted'
              )}
            />
            <span
              className={cn(
                'text-xs transition-colors duration-300 hidden sm:block',
                i <= currentStep ? 'text-foreground' : 'text-muted-foreground'
              )}
            >
              {stepLabels[i]}
            </span>
          </div>
          {i < totalSteps - 1 && (
            <div
              className={cn(
                'h-0.5 w-8 sm:w-12 transition-all duration-300',
                i < currentStep ? 'bg-primary' : 'bg-muted'
              )}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

export default WizardProgress;
