import { z } from 'zod';

// ---------------------------------------------------------------------------
// Discover backend client (spec §14). Mirrors the V4 transport: zod-validated,
// timeout-bounded, no fabricated fallbacks — a failed call throws.
// ---------------------------------------------------------------------------

const number = z.number().finite();

const claimSchema = z.object({
  text: z.string(),
  kind: z.enum(['match', 'tradeoff', 'caveat']),
  attribute: z.string(),
  evidence_status: z.enum(['VERIFIED', 'EXTRACTED', 'UNKNOWN']),
  signal: z.string().nullable().optional(),
});

const resultSchema = z.object({
  candidate_id: z.string(),
  rank: number.int(),
  title: z.string(),
  source_url: z.string(),
  provider: z.string(),
  category: z.string().nullable().optional(),
  location_name: z.string().nullable().optional(),
  start_time: z.string().nullable().optional(),
  price_min: z.union([z.string(), number]).nullable().optional(),
  price_max: z.union([z.string(), number]).nullable().optional(),
  currency: z.string().nullable().optional(),
  final_score: number,
  status: z.enum(['boosted', 'neutral', 'demoted']),
  needs_verification: z.boolean(),
  signals: z.record(number),
  constraints: z.record(z.string()),
  explanation: z.object({ text: z.string(), claims: z.array(claimSchema) }),
});

const responseSchema = z.object({
  results: z.array(resultSchema),
  needs_verification_ids: z.array(z.string()),
  excluded_count: number.int(),
  warnings: z.array(z.string()),
  ranking_fingerprint: z.string(),
  engine_version: z.string(),
  config_version: z.string(),
});

export type DiscoveryClaim = z.infer<typeof claimSchema>;
export type DiscoveryResult = z.infer<typeof resultSchema>;
export type DiscoveryResponse = z.infer<typeof responseSchema>;

export interface DiscoverSearchInput {
  query: string;
  location?: string;
  startDate?: string; // YYYY-MM-DD
  endDate?: string;
  budgetTotal?: number;
  partySize?: number;
  childrenAges?: number[];
}

export type Helpfulness = 'very_helpful' | 'somewhat_helpful' | 'not_helpful';

export interface DiscoverFeedbackInput {
  requestId: string;
  selectedCandidateId?: string;
  helpfulness: Helpfulness;
  wouldUseAgain?: boolean;
  feedbackText?: string;
}

async function post<T>(path: string, body: unknown, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(cancel, 15000);
  try {
    const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
    const response = await fetch(`${base}/discover/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 422) throw new Error('That request was invalid. Please check your inputs.');
      if (response.status === 502) throw new Error('No results could be retrieved right now. Please try again.');
      throw new Error('The discovery service is unavailable. Please try again.');
    }
    const checked = schema.safeParse(await response.json());
    if (!checked.success) throw new Error('The discovery service returned an invalid response.');
    return checked.data;
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('The discovery service timed out. Please try again.');
    if (error instanceof TypeError) throw new Error('Cannot reach the discovery service. Please try again.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

function toRequestBody(input: DiscoverSearchInput): Record<string, unknown> {
  const body: Record<string, unknown> = { query: input.query };
  if (input.location) body.location = input.location;
  if (input.startDate) body.start_date = input.startDate;
  if (input.endDate) body.end_date = input.endDate;
  if (input.budgetTotal != null) body.budget_total = input.budgetTotal;
  if (input.partySize != null) body.party_size = input.partySize;
  if (input.childrenAges && input.childrenAges.length) body.children_ages = input.childrenAges;
  return body;
}

export const searchDiscover = (input: DiscoverSearchInput, signal?: AbortSignal) =>
  post('search', toRequestBody(input), responseSchema, signal);

const feedbackAckSchema = z.object({ status: z.string(), request_id: z.string() });

export const sendDiscoverFeedback = (input: DiscoverFeedbackInput, signal?: AbortSignal) =>
  post('feedback', {
    request_id: input.requestId,
    selected_candidate_id: input.selectedCandidateId ?? null,
    helpfulness: input.helpfulness,
    would_use_again: input.wouldUseAgain ?? null,
    feedback_text: input.feedbackText ?? null,
  }, feedbackAckSchema, signal);
