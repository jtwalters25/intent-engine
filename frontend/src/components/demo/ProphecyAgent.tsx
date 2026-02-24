import { useState, useEffect } from 'react';

interface ProphecyAgentProps {
  prophecyValue: number;
}

export default function ProphecyAgent({ prophecyValue }: ProphecyAgentProps) {
  const [minutesLeft, setMinutesLeft] = useState(47);

  // Mock countdown timer
  useEffect(() => {
    if (prophecyValue < 0.1) return;
    const interval = setInterval(() => {
      setMinutesLeft((m) => (m <= 1 ? 59 : m - 1));
    }, 60000);
    return () => clearInterval(interval);
  }, [prophecyValue]);

  if (prophecyValue < 0.1) {
    return (
      <div className="rounded-lg border border-white/5 bg-white/[0.01] p-3">
        <div className="flex items-center gap-2">
          <span className="text-sm opacity-40">🔮</span>
          <span className="font-syne text-xs font-semibold text-white/30">Prophecy Agent</span>
        </div>
        <p className="font-dm-mono text-[10px] text-white/20 mt-1">Disabled for this context</p>
      </div>
    );
  }

  const intensity = prophecyValue > 0.7 ? 'Full auto' : prophecyValue > 0.4 ? 'Moderate' : 'Low';

  return (
    <div className="rounded-lg border border-orange-500/20 bg-orange-500/5 p-3">
      <div className="flex items-center gap-2">
        <span className="text-sm">🔮</span>
        <span className="font-syne text-xs font-semibold text-orange-300/90">Prophecy Agent</span>
        <span className="ml-auto font-dm-mono text-[10px] text-orange-400/60 border border-orange-500/20 rounded px-1.5 py-0.5">
          {intensity}
        </span>
      </div>
      <p className="font-dm-mono text-[10px] text-orange-300/50 mt-1.5 leading-relaxed">
        Auto-switch scheduled for 9:00 PM daily.
        <br />
        Next trigger in <span className="text-orange-300/80">{minutesLeft} min</span>.
      </p>
    </div>
  );
}
