import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Discover from '@/pages/Discover';
import * as api from '@/data/discoverApi';

afterEach(() => { vi.restoreAllMocks(); });

const response: api.DiscoveryResponse = {
  results: [
    {
      candidate_id: 'tm:1', rank: 1, title: 'Science Museum',
      source_url: 'https://example.com/e', provider: 'ticketmaster',
      category: 'Museum', location_name: 'Seattle', start_time: null,
      price_min: null, price_max: null, currency: null,
      final_score: 1.42, status: 'boosted', needs_verification: false,
      signals: { educational_value: 0.9 }, constraints: {},
      explanation: {
        text: 'Recommended because it matches your educational value.',
        claims: [{ text: 'matches your educational value', kind: 'match', attribute: 'educational value', evidence_status: 'VERIFIED', signal: 'educational_value' }],
      },
    },
    {
      candidate_id: 'tm:2', rank: 2, title: 'Mystery Dinner',
      source_url: 'https://example.com/d', provider: 'ticketmaster',
      category: 'Food', location_name: null, start_time: null,
      price_min: null, price_max: null, currency: null,
      final_score: 1.0, status: 'neutral', needs_verification: true,
      signals: {}, constraints: { budget: 'UNKNOWN' },
      explanation: { text: 'Budget needs verification.', claims: [{ text: 'budget needs verification', kind: 'caveat', attribute: 'budget', evidence_status: 'UNKNOWN', signal: null }] },
    },
  ],
  needs_verification_ids: ['tm:2'],
  excluded_count: 1,
  warnings: [],
  ranking_fingerprint: 'abcdef123456',
  engine_version: 'discover-ranker-0.1.0',
  config_version: 'default',
};

describe('Discover page', () => {
  it('runs a search and renders ranked results with grounded explanations', async () => {
    const spy = vi.spyOn(api, 'searchDiscover').mockResolvedValue(response);
    render(<Discover />);

    fireEvent.click(screen.getByRole('button', { name: /discover/i }));

    await waitFor(() => expect(screen.getByText('Science Museum')).toBeInTheDocument());
    expect(spy).toHaveBeenCalled();
    // Verified recommendation + its grounded claim.
    expect(screen.getByText('matches your educational value')).toBeInTheDocument();
    // Needs-verification item is surfaced in its own section.
    expect(screen.getByText('Mystery Dinner')).toBeInTheDocument();
    expect(screen.getByText('Needs verification')).toBeInTheDocument();
    // Source link points at the provider URL.
    expect(screen.getByText('Science Museum').closest('a')).toHaveAttribute('href', 'https://example.com/e');
  });

  it('shows an error message when the service fails', async () => {
    vi.spyOn(api, 'searchDiscover').mockRejectedValue(new Error('No results could be retrieved right now. Please try again.'));
    render(<Discover />);
    fireEvent.click(screen.getByRole('button', { name: /discover/i }));
    await waitFor(() => expect(screen.getByText(/No results could be retrieved/)).toBeInTheDocument());
  });
});
