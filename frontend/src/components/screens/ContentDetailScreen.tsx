import React from 'react';
import { useWizard } from '@/contexts/WizardContext';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Play, Check, Clock, Star, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

const ContentDetailScreen: React.FC = () => {
  const { state, prevStep, setCurrentStep } = useWizard();
  const show = state.selectedShow;

  if (!show) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No show selected</p>
          <Button onClick={prevStep}>Go Back</Button>
        </div>
      </div>
    );
  }

  const handleBackToBrowse = () => {
    setCurrentStep(1); // Back to curated home
  };

  return (
    <div className="min-h-screen animate-fade-in">
      {/* Hero Section */}
      <div className="relative">
        {/* Background Image */}
        <div className="absolute inset-0 h-[50vh] sm:h-[60vh]">
          <img
            src={show.thumbnail}
            alt={show.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20" />
          <div className="absolute inset-0 bg-gradient-to-r from-background/90 via-background/50 to-transparent" />
        </div>

        {/* Content */}
        <div className="relative px-4 sm:px-8 md:px-12 pt-8 pb-12">
          {/* Back Button */}
          <Button
            variant="ghost"
            onClick={handleBackToBrowse}
            className="mb-8 hover:bg-secondary/50"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Browse
          </Button>

          <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 pt-12 sm:pt-20">
            {/* Left - Show Info */}
            <div className="animate-slide-up">
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-foreground mb-4">
                {show.title}
              </h1>

              {/* Badges */}
              <div className="flex flex-wrap gap-2 mb-6">
                {show.badges.map((badge, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 rounded-full text-sm bg-secondary text-secondary-foreground"
                  >
                    {badge}
                  </span>
                ))}
              </div>

              <p className="text-lg text-muted-foreground mb-8 max-w-xl">
                {show.description}
              </p>

              {/* Action Buttons */}
              <div className="flex flex-wrap gap-4">
                <Button
                  size="lg"
                  className="px-8 py-6 text-lg font-semibold rounded-lg bg-primary hover:bg-primary/90 shadow-lg shadow-primary/30"
                >
                  <Play className="w-5 h-5 mr-2 fill-current" />
                  Play
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  className="px-8 py-6 text-lg font-semibold rounded-lg"
                >
                  <Star className="w-5 h-5 mr-2" />
                  Add to List
                </Button>
              </div>

              {/* Meta Info */}
              <div className="flex items-center gap-6 mt-8 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span>22 min episodes</span>
                </div>
                <div className="flex items-center gap-2">
                  <Star className="w-4 h-4 text-social" />
                  <span>Ages {show.ageRange}</span>
                </div>
              </div>
            </div>

            {/* Right - Why We Picked This */}
            <div className="animate-slide-up" style={{ animationDelay: '0.2s' }}>
              <div className="bg-card/80 backdrop-blur-sm rounded-2xl p-6 sm:p-8 border border-border">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 rounded-lg bg-trust/20">
                    <Shield className="w-5 h-5 text-trust" />
                  </div>
                  <h2 className="text-xl font-semibold text-foreground">
                    Why we picked this
                  </h2>
                </div>

                <ul className="space-y-4">
                  {show.reasons.map((reason, index) => (
                    <li
                      key={index}
                      className="flex items-start gap-3 animate-fade-in"
                      style={{ animationDelay: `${0.3 + index * 0.1}s` }}
                    >
                      <div className="p-1 rounded-full bg-trust/20 mt-0.5">
                        <Check className="w-4 h-4 text-trust" />
                      </div>
                      <span className="text-foreground/90">{reason}</span>
                    </li>
                  ))}
                </ul>

                {/* Additional Trust Signal */}
                <div className="mt-8 pt-6 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    This content has been reviewed for{' '}
                    <span className="text-trust font-medium">age-appropriateness</span> and matches
                    your preferences for{' '}
                    <span className="text-primary font-medium">
                      {state.timeOfDay} viewing
                    </span>
                    .
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Episode Selector (Mock) */}
      <div className="px-4 sm:px-8 md:px-12 py-12">
        <h3 className="text-xl font-semibold mb-6 text-foreground">Episodes</h3>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((ep) => (
            <div
              key={ep}
              className="group bg-card rounded-xl p-4 hover:bg-accent transition-colors cursor-pointer"
            >
              <div className="flex gap-4">
                <div className="w-24 h-16 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
                  <img
                    src={show.thumbnail}
                    alt={`Episode ${ep}`}
                    className="w-full h-full object-cover opacity-70 group-hover:opacity-100 transition-opacity"
                  />
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-foreground mb-1">
                    Episode {ep}
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    22 min
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ContentDetailScreen;
