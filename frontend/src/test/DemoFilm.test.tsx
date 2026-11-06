import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import Demo from '@/pages/Demo';
import { platforms, platformKeys, rankWithSignals } from '@/data/demoPlatforms';

const tileOrder = () => screen.getAllByTestId('film-tile').map((el) => el.getAttribute('data-title'));

// Platform switches fade for 150ms before swapping content
async function switchPlatform(label: string) {
  fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${label}`) }));
  await act(() => new Promise((r) => setTimeout(r, 200)));
}

describe('Demo film view', () => {
  it('shows tiles in the engine order for every platform and context', async () => {
    render(<Demo />);
    for (const pk of platformKeys) {
      const platform = platforms[pk];
      await switchPlatform(platform.label);
      for (const ck of platform.contextKeys) {
        const ctx = platform.contexts[ck];
        fireEvent.click(screen.getByRole('button', { name: ctx.label, pressed: undefined }));
        const expected = rankWithSignals(platform.catalog, ctx.defaults).map((r) => r.title);
        expect(tileOrder(), `${pk} / ${ck}`).toEqual(expected);
      }
    }
  });

  it('shows the catalog engagement order in Engagement view', async () => {
    render(<Demo />);
    for (const pk of platformKeys) {
      const platform = platforms[pk];
      await switchPlatform(platform.label);
      fireEvent.click(screen.getByRole('button', { name: 'Engagement' }));
      expect(tileOrder(), pk).toEqual(platform.catalog.map((c) => c.title));
    }
  });

  it('explains a held-back TV-Y title with its stimulation', () => {
    render(<Demo />);
    fireEvent.click(screen.getByRole('button', { name: /Sensory Rush Rhymes, held back: High stim/ }));
    expect(screen.getByText('Held back.')).toBeInTheDocument();
    expect(screen.getByText(/Stimulation 0\.96 is over the 0\.50 cap/)).toBeInTheDocument();
  });

  it('keeps the formula and sliders one click away', () => {
    render(<Demo />);
    const why = screen.getByRole('button', { name: 'Why this order?' });
    expect(why).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(why);
    expect(screen.getByText('Scoring Formula')).toBeVisible();
    expect(screen.getByText('Signal Weights')).toBeVisible();
  });
});
