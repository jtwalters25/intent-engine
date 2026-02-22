import React from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { ArrowLeft, Shield, Check, Clock, Sparkles, Ban, Volume2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

const ParentControlsScreen: React.FC = () => {
  const {
    state,
    setPrioritizeEducational,
    setLowerStimulation,
    setRotateWeekly,
    setViewingTimeLimit,
    setEndOnCalmNote,
    setCurrentStep,
  } = useWizard();

  const handleBackToBrowse = () => {
    setCurrentStep(2); // Back to curated home
  };

  const handleSave = () => {
    setCurrentStep(2); // Back to curated home after saving
  };

  const timeOptions = [
    { value: 30, label: '30 min' },
    { value: 45, label: '45 min' },
    { value: 60, label: '1 hour' },
    { value: 90, label: '1.5 hours' },
  ];

  return (
    <div className="min-h-screen py-8 px-4 sm:px-8 animate-fade-in">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Button variant="ghost" size="icon" onClick={handleBackToBrowse}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Parent Controls</h1>
            <p className="text-muted-foreground">Fine-tune the viewing experience</p>
          </div>
        </div>

        {/* Quick Toggles Section */}
        <div className="bg-card rounded-2xl p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <h2 className="text-lg font-semibold mb-6 text-foreground flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            Content Preferences
          </h2>

          <div className="space-y-6">
            {/* Prioritize Educational */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-stem/20">
                  <Sparkles className="w-5 h-5 text-stem" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Prioritize educational content</p>
                  <p className="text-sm text-muted-foreground">Boost learning-focused shows</p>
                </div>
              </div>
              <Switch
                checked={state.prioritizeEducational}
                onCheckedChange={setPrioritizeEducational}
              />
            </div>

            {/* Lower Stimulation */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-badge-calm/20">
                  <Volume2 className="w-5 h-5 text-badge-calm" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Lower stimulation mode</p>
                  <p className="text-sm text-muted-foreground">Prefer calmer, quieter content</p>
                </div>
              </div>
              <Switch
                checked={state.lowerStimulation}
                onCheckedChange={setLowerStimulation}
              />
            </div>

            {/* Rotate Weekly */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-literacy/20">
                  <RefreshCw className="w-5 h-5 text-literacy" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Rotate recommendations weekly</p>
                  <p className="text-sm text-muted-foreground">Fresh content every week</p>
                </div>
              </div>
              <Switch
                checked={state.rotateWeekly}
                onCheckedChange={setRotateWeekly}
              />
            </div>
          </div>
        </div>

        {/* Session Settings */}
        <div className="bg-card rounded-2xl p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <h2 className="text-lg font-semibold mb-6 text-foreground flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
            Session Settings
          </h2>

          {/* Viewing Time Limit */}
          <div className="mb-8">
            <p className="font-medium text-foreground mb-2">Viewing time limit</p>
            <p className="text-sm text-muted-foreground mb-4">Set a healthy viewing duration</p>
            <div className="flex flex-wrap gap-3">
              {timeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setViewingTimeLimit(option.value)}
                  className={cn(
                    'px-4 py-2 rounded-lg font-medium transition-all duration-300',
                    state.viewingTimeLimit === option.value
                      ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/30'
                      : 'bg-secondary hover:bg-accent text-foreground'
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* End on Calm Note */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emotional/20">
                <Clock className="w-5 h-5 text-emotional" />
              </div>
              <div>
                <p className="font-medium text-foreground">End on a calm note</p>
                <p className="text-sm text-muted-foreground">Suggest calming content before session ends</p>
              </div>
            </div>
            <Switch
              checked={state.endOnCalmNote}
              onCheckedChange={setEndOnCalmNote}
            />
          </div>
        </div>

        {/* Trust & Safety Box */}
        <div className="bg-trust/10 border border-trust/30 rounded-2xl p-6 mb-8 animate-slide-up" style={{ animationDelay: '0.3s' }}>
          <h2 className="text-lg font-semibold mb-4 text-foreground flex items-center gap-2">
            <Shield className="w-5 h-5 text-trust" />
            Trust & Safety
          </h2>
          <p className="text-sm text-muted-foreground mb-4">
            Parent-Intent Mode is designed with your family's wellbeing in mind.
          </p>
          <ul className="space-y-3">
            {[
              'No ads, ever',
              'No autoplay escalation',
              'Designed for healthy viewing habits',
              'Content reviewed for age-appropriateness',
            ].map((item, index) => (
              <li key={index} className="flex items-center gap-3">
                <div className="p-1 rounded-full bg-trust/20">
                  <Check className="w-4 h-4 text-trust" />
                </div>
                <span className="text-foreground/90">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Save Button */}
        <div className="flex justify-end animate-slide-up" style={{ animationDelay: '0.4s' }}>
          <Button
            onClick={handleSave}
            size="lg"
            className="px-8 rounded-full bg-primary hover:bg-primary/90 shadow-lg shadow-primary/30"
          >
            Save & Apply
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ParentControlsScreen;
