import { contexts, type ContextKey } from '@/data/demoContent';

interface ContextSwitcherProps {
  activeContext: ContextKey;
  onSelect: (key: ContextKey) => void;
}

const contextKeys: ContextKey[] = ['bedtime', 'solo-morning', 'family-weekend', 'focus-session'];

export default function ContextSwitcher({ activeContext, onSelect }: ContextSwitcherProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {contextKeys.map((key) => {
        const ctx = contexts[key];
        const isActive = key === activeContext;
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            className={`
              flex items-center gap-2 rounded-lg border px-4 py-2.5 font-syne text-sm font-semibold
              transition-all duration-200 cursor-pointer
              ${isActive
                ? 'border-blue-500/50 bg-blue-500/10 text-blue-300 shadow-[0_0_10px_rgba(59,130,246,0.15)]'
                : 'border-white/10 bg-white/[0.02] text-white/50 hover:border-white/20 hover:text-white/70'
              }
            `}
          >
            <span className="text-base">{ctx.emoji}</span>
            {ctx.label}
          </button>
        );
      })}
    </div>
  );
}
