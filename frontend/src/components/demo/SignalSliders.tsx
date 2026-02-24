import type { SignalConfig, SignalValues, SignalKey } from '@/data/demoPlatforms';
import { getSignalLabel } from '@/data/demoPlatforms';

interface SignalSlidersProps {
  configs: SignalConfig[];
  values: SignalValues;
  defaults: SignalValues;
  onChange: (key: SignalKey, value: number) => void;
  onReset: () => void;
}

const signalColors: Record<SignalKey, string> = {
  time: 'bg-blue-400',
  viewer: 'bg-purple-400',
  energy: 'bg-amber-400',
  device: 'bg-emerald-400',
  prophecy: 'bg-orange-400',
};

const signalTrackColors: Record<SignalKey, string> = {
  time: 'accent-blue-400',
  viewer: 'accent-purple-400',
  energy: 'accent-amber-400',
  device: 'accent-emerald-400',
  prophecy: 'accent-orange-400',
};

export default function SignalSliders({ configs, values, defaults, onChange, onReset }: SignalSlidersProps) {
  const hasOverrides = configs.some((c) => Math.abs(values[c.key] - defaults[c.key]) > 0.01);

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-syne text-sm font-bold text-white/80">Signal Weights</h3>
        {hasOverrides && (
          <button
            onClick={onReset}
            className="font-dm-mono text-[10px] text-white/30 hover:text-white/60 transition-colors
                       border border-white/10 rounded px-2 py-0.5 hover:border-white/20 cursor-pointer"
          >
            Reset to preset
          </button>
        )}
      </div>

      <div className="space-y-4">
        {configs.map((config) => {
          const value = values[config.key];
          const multiplierDisplay = value <= 0.01 ? '×0.00' : `×${value.toFixed(2)}`;
          const label = getSignalLabel(config, value);
          const color = signalColors[config.key];
          const pct = ((value - config.min) / (config.max - config.min)) * 100;

          return (
            <div key={config.key}>
              {/* Label row */}
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">{config.emoji}</span>
                  <span className="font-dm-mono text-[11px] text-white/60">{config.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-dm-mono text-[10px] text-white/40">{label}</span>
                  <span className="font-dm-mono text-[11px] text-white/70 tabular-nums w-10 text-right">
                    {multiplierDisplay}
                  </span>
                </div>
              </div>

              {/* Slider with colored fill bar */}
              <div className="relative h-6 flex items-center">
                {/* Track background */}
                <div className="absolute inset-x-0 h-1.5 rounded-full bg-white/5" />
                {/* Colored fill */}
                <div
                  className={`absolute left-0 h-1.5 rounded-full ${color} opacity-40 transition-all duration-100`}
                  style={{ width: `${pct}%` }}
                />
                {/* Range input */}
                <input
                  type="range"
                  min={config.min}
                  max={config.max}
                  step={config.step}
                  value={value}
                  onChange={(e) => onChange(config.key, parseFloat(e.target.value))}
                  className={`relative w-full h-1.5 appearance-none bg-transparent cursor-pointer
                    [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5
                    [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full
                    [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-md
                    [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white/50
                    [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-125
                    [&::-moz-range-thumb]:w-3.5 [&::-moz-range-thumb]:h-3.5
                    [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white
                    [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-white/50
                    [&::-moz-range-track]:bg-transparent
                    ${signalTrackColors[config.key]}
                  `}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
