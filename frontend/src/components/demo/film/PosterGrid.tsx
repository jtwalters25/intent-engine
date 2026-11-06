import type { RankedPlatformItem } from '@/data/demoPlatforms';
import { posterTone } from './posterTone';
import { useFlip } from './useFlip';

export type OrderView = 'moment' | 'engagement';

interface PosterGridProps {
  /** Items in display order */
  items: RankedPlatformItem[];
  view: OrderView;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** Short reason pill for a held-back title. */
function heldLabel(item: RankedPlatformItem): string | null {
  if (!item.breakdown.blocked) return null;
  return item.breakdown.viewerMultiplier === 0 ? item.rating : 'High stim';
}

export default function PosterGrid({ items, view, selectedId, onSelect }: PosterGridProps) {
  const register = useFlip(items.map((i) => i.id));

  return (
    <ol className="film-grid" aria-label={view === 'moment' ? 'Ranked for this moment' : 'Ranked by engagement'}>
      {items.map((item, i) => {
        const held = view === 'moment' ? heldLabel(item) : null;
        // movement = engagement index - moment index, so the engagement rank is i + 1 + movement
        const was = view === 'moment' && item.movement !== 0 ? i + 1 + item.movement : null;
        const selected = selectedId === item.id;
        return (
          <li key={item.id} ref={register(item.id)} className="film-slot" data-testid="film-tile" data-title={item.title}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              aria-pressed={selected}
              aria-label={`${i + 1}. ${item.title}${held ? `, held back: ${held}` : ''}`}
              className={`film-tile ${held ? 'is-held' : ''} ${selected ? 'is-selected' : ''} ${selectedId && !selected ? 'is-dimmed' : ''}`}
              style={{ ['--tone' as string]: posterTone(item) }}
            >
              <span className="film-rank">{i + 1}</span>
              {held && <span className="film-pill">{held}</span>}
              <span className="film-meta">
                <span className="film-title">{item.title}</span>
                <span className="film-sub">
                  {item.rating} · {item.runtime}
                  {was !== null && <span className="film-was">was #{was}</span>}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/** Titles the engine held back for this moment, kept visible so the "why" stays one tap away. */
export function HeldStrip({ items, selectedId, onSelect }: Omit<PosterGridProps, 'view'>) {
  if (!items.length) return null;
  return (
    <section className="film-held" aria-label="Held back for this moment">
      <h3 className="film-held-head">Held back for this moment <span>{items.length}</span></h3>
      <ul className="film-held-row">
        {items.map((item) => (
          <li key={item.id} data-testid="film-held" data-title={item.title}>
            <button
              type="button"
              onClick={() => onSelect(item.id)}
              aria-pressed={selectedId === item.id}
              aria-label={`${item.title}, held back: ${heldLabel(item)}`}
              className={`film-held-tile ${selectedId === item.id ? 'is-selected' : ''}`}
              style={{ ['--tone' as string]: posterTone(item) }}
            >
              <span className="film-held-title">{item.title}</span>
              <span className="film-held-why">{heldLabel(item)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
