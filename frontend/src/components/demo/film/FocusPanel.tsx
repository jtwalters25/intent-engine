import { useEffect, useState } from 'react';
import {
  STIM_CAP,
  stimComponents,
  type RankedPlatformItem,
  type SignalConfig,
  type SignalKey,
} from '@/data/demoPlatforms';

interface FocusPanelProps {
  item: RankedPlatformItem;
  /** Rank in the moment ordering (1-based) and list length */
  rank: number;
  total: number;
  signalConfigs: SignalConfig[];
}

const FACTOR_FIELDS: { key: SignalKey; field: 'timeMultiplier' | 'viewerMultiplier' | 'energyMultiplier' | 'deviceMultiplier' | 'prophecyBoost' }[] = [
  { key: 'time', field: 'timeMultiplier' },
  { key: 'viewer', field: 'viewerMultiplier' },
  { key: 'energy', field: 'energyMultiplier' },
  { key: 'device', field: 'deviceMultiplier' },
  { key: 'prophecy', field: 'prophecyBoost' },
];

function Meter({ name, value, fill, over }: { name: string; value: string; fill: number; over: boolean }) {
  // Start empty, then fill on the next frame so each new item animates in
  const [width, setWidth] = useState(0);
  useEffect(() => {
    setWidth(0);
    const id = requestAnimationFrame(() => setWidth(Math.round(fill * 100)));
    return () => cancelAnimationFrame(id);
  }, [fill]);
  return (
    <div className={`film-meter ${over ? 'is-over' : ''}`}>
      <span className="film-meter-name">{name}</span>
      <span className="film-track"><span className="film-fill" style={{ width: `${width}%` }} /></span>
      <span className="film-meter-val">{value}</span>
    </div>
  );
}

export default function FocusPanel({ item, rank, total, signalConfigs }: FocusPanelProps) {
  const b = item.breakdown;
  const labelOf = (key: SignalKey) => signalConfigs.find((c) => c.key === key)?.label ?? key;

  // Strongest multipliers above neutral, from the engine's own breakdown
  const lifts = FACTOR_FIELDS
    .map(({ key, field }) => ({ label: labelOf(key), value: b[field] }))
    .filter((f) => f.value > 1.04)
    .sort((x, y) => y.value - x.value)
    .slice(0, 2);
  const drag = FACTOR_FIELDS
    .map(({ key, field }) => ({ label: labelOf(key), value: b[field] }))
    .filter((f) => f.value < 0.9)
    .sort((x, y) => x.value - y.value)[0];

  let headline: string;
  let detail: string;
  if (b.blocked && b.viewerMultiplier === 0) {
    headline = 'Held back.';
    detail = `Rated ${item.rating}, which isn't right for who's watching.`;
  } else if (b.blocked) {
    headline = 'Held back.';
    detail = `Stimulation ${b.stimIndex?.toFixed(2)} is over the ${STIM_CAP.toFixed(2)} cap for winding down.`;
  } else if (lifts.length) {
    headline = `Lifted by ${lifts.map((l) => l.label.toLowerCase()).join(' and ')}.`;
    detail = drag ? `Held down a little by ${drag.label.toLowerCase()}.` : 'Nothing in this moment holds it down.';
  } else {
    headline = drag ? `Held down by ${drag.label.toLowerCase()}.` : 'Ranked on engagement alone.';
    detail = 'No signal in this moment lifts it.';
  }

  const stim = item.stim;
  const comps = stim ? stimComponents(stim) : null;
  const over = !!b.stimBlocked;

  return (
    <section className="film-focus" aria-live="polite" aria-label={`Why ${item.title} is ranked here`}>
      <p className="film-eyebrow">
        {b.blocked ? 'Held back' : `#${rank} of ${total}`} · for this moment
      </p>
      <h2 className="film-focus-title">{item.title}</h2>
      <p className="film-focus-sub">{item.genre} · {item.rating} · {item.runtime}</p>

      <div className="film-reason">
        <p className="film-reason-head">{headline}</p>
        <p className="film-reason-detail">{detail}</p>
      </div>

      <dl className="film-scores">
        <div><dt>Engagement</dt><dd>{b.baseScore.toFixed(2)}</dd></div>
        <div><dt>For this moment</dt><dd className={b.blocked ? 'is-zero' : ''}>{b.finalScore.toFixed(2)}</dd></div>
      </dl>

      {stim && comps && (
        <div className="film-meters">
          <p className="film-meters-head">
            <span>Stimulation <b className={over ? 'is-over' : ''}>{b.stimIndex?.toFixed(2)}</b> · cap {STIM_CAP.toFixed(2)}</span>
            {stim.provenance !== 'MEASURED' && <span className="film-tag">{stim.provenance.toLowerCase()}</span>}
          </p>
          <Meter name="Pacing" value={`${stim.cutsPerMin} cuts/min`} fill={comps.pacing} over={over} />
          <Meter name="Loudness" value={`${stim.loudnessLufs} LUFS`} fill={comps.loudness} over={over} />
          <Meter name="Motion" value={stim.motion.toFixed(2)} fill={comps.motion} over={over} />
        </div>
      )}

      {item.tags.length > 0 && (
        <ul className="film-tags" aria-label="Tags">
          {item.tags.slice(0, 5).map((t) => <li key={t}>{t.replace(/-/g, ' ')}</li>)}
        </ul>
      )}
    </section>
  );
}
