import React from 'react';
import { ArrowLeft, Shield, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useWizard, type Profile } from '@/contexts/WizardContext';

/**
 * Account-level profiles ("Settings"), distinct from per-session "Adjust
 * Preferences". Shows the roster and lets the parent pick who's watching. Each
 * profile carries hard policy (maturity gate + over-stimulation cap) derived from
 * its age range. Editing/adding profiles is a later phase; this is read + select.
 */

function ageLabel(p: Profile): string {
  if (p.kind === 'adult') return 'Adult · 18+';
  return `Kid · ages ${p.ageMin}–${p.ageMax}`;
}

const ProfileCard: React.FC<{ profile: Profile; active: boolean; onSelect: () => void }> = ({
  profile,
  active,
  onSelect,
}) => (
  <button
    type="button"
    onClick={onSelect}
    aria-pressed={active}
    className={`relative flex flex-col items-center gap-3 rounded-2xl border p-6 text-center transition-all ${
      active
        ? 'border-trust bg-trust/5 shadow-lg'
        : 'border-border bg-card hover:border-foreground/30 hover:bg-card/80'
    }`}
  >
    {active && (
      <span className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-trust text-background">
        <Check className="h-4 w-4" />
      </span>
    )}
    <span className="text-5xl" aria-hidden>{profile.avatar}</span>
    <span className="text-lg font-bold text-foreground">{profile.name}</span>
    <span className="text-sm text-muted-foreground">{ageLabel(profile)}</span>

    <div className="mt-1 flex flex-wrap justify-center gap-1.5">
      {profile.maturityGate && (
        <span className="rounded-full border border-trust/30 bg-trust/10 px-2 py-0.5 text-[11px] font-medium text-trust">
          Blocks adult content
        </span>
      )}
      {profile.stimCap !== null ? (
        <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
          Stimulation cap {profile.stimCap.toFixed(2)}
        </span>
      ) : (
        <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
          No limits
        </span>
      )}
    </div>
  </button>
);

const ProfilesScreen: React.FC = () => {
  const { state, setActiveProfile, setCurrentStep } = useWizard();

  const choose = (id: string) => {
    setActiveProfile(id); // loads this profile's age-based default preferences
    setCurrentStep(3); // open the controls so the parent can adjust those defaults
  };

  return (
    <div className="min-h-screen animate-fade-in py-6">
      <div className="mx-auto max-w-3xl px-4 sm:px-8">
        <div className="mb-8 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => setCurrentStep(1)} aria-label="Back">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-foreground sm:text-2xl">Who's watching?</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="h-4 w-4 text-trust" />
              <span>Each profile sets its own content policy</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {state.profiles.map((profile) => (
            <ProfileCard
              key={profile.id}
              profile={profile}
              active={profile.id === state.activeProfileId}
              onSelect={() => choose(profile.id)}
            />
          ))}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Selecting a profile loads age-based default preferences you can adjust next.
          Its maturity gate and stimulation cap stay as parent-set policy (hard) that
          session tweaks can't loosen.
        </p>
      </div>
    </div>
  );
};

export default ProfilesScreen;
