import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import AgenticMode from '@/components/demo/AgenticMode';
import { plan, execution } from './agenticFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('cancels in-flight work when the mode is unmounted', async () => {
  const fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal('fetch', fetch);
  const view = render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  expect(screen.getByRole('button', { name: 'Working…' })).toBeDisabled();
  const signal = fetch.mock.calls[0][1].signal;
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it('renders backend plan, ranking, safety evidence, and execution reference', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => plan }).mockResolvedValueOnce({ ok: true, json: async () => execution });
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByText('Intent ranking');
  expect(screen.getByText(/Dark Season 3 · Blocked/)).toBeInTheDocument();
  expect(screen.getByText(/Execution reference: trace_test/)).toBeInTheDocument();
  expect(fetch.mock.calls.map(call => call[0])).toEqual(['/v4/plan', '/v4/execute']);
  expect(screen.getByText('Now · Active')).toBeInTheDocument();
});

it('refreshes server execution without creating another plan', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => plan }).mockResolvedValue({ ok: true, json: async () => execution });
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByText('Intent ranking');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh ranking' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
  expect(fetch.mock.calls[2][0]).toBe('/v4/execute');
});

it('shows service failures without ranking a local fallback', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach');
  expect(screen.queryByText('Intent ranking')).not.toBeInTheDocument();
});

it('retains a plan after execution failure and permits retry', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => plan }).mockResolvedValueOnce({ ok: false, status: 500 }).mockResolvedValueOnce({ ok: true, json: async () => execution });
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh ranking' }));
  await screen.findByText('Intent ranking');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
