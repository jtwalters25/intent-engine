import type { PlatformKey } from '@/data/demoPlatforms';
import { platforms, platformKeys } from '@/data/demoPlatforms';

interface PlatformTabsProps {
  active: PlatformKey;
  onSelect: (key: PlatformKey) => void;
}

export default function PlatformTabs({ active, onSelect }: PlatformTabsProps) {
  return (
    <div className="flex gap-1 rounded-lg border border-white/10 bg-white/[0.02] p-1">
      {platformKeys.map((key) => {
        const platform = platforms[key];
        const isActive = key === active;
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            className={`
              flex-1 flex items-center justify-center gap-2 rounded-md px-4 py-2.5
              font-syne text-sm font-semibold transition-all duration-200 cursor-pointer
              ${isActive
                ? 'bg-white/10 text-white shadow-sm'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.03]'
              }
            `}
          >
            <span className="text-base">{platform.emoji}</span>
            <span className="hidden sm:inline">{platform.label}</span>
          </button>
        );
      })}
    </div>
  );
}
