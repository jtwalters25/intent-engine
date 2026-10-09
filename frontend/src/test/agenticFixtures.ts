export const plan = {
  plan_id: 'plan_test', domain: 'streaming', objective: 'wind_down',
  current_state: { viewer: 'kids', energy: .9 }, desired_state: { energy: .1 },
  constraints: [{ type: 'viewer_maturity', value: 'kids', hard: true, source: 'SYSTEM' }],
  steps: [{ step_id: 'step_one', offset_minutes: 0, intent: { energy: .55, tone: 'calm' }, transition_reason: 'Lower stimulation.' }],
  assumptions: ['Server kids profile.'], confidence: .9,
  created_at: '2026-10-09T18:00:00Z', expires_at: '2026-10-09T19:00:00Z', planner_version: 'v4-rule-based-1',
};
export const execution = {
  trace_id: 'trace_test', active_step: plan.steps[0],
  ranking: [{ item: { item_id: 'dark-s3', title: 'Dark Season 3' }, rank: 1, final_score: 0, status: 'blocked', explanation: 'Blocked by safety gate.',
    score_breakdown: { base_score: .9, final_score: 0, diversity_penalty: 0, blocked: true, block_reason: 'Adult content blocked.', multipliers: { context: 1, profile: 1, urgency: 1, cost: 1, prophecy: 1 } } }],
  explanation: { plan_reason: 'Lower stimulation.', ranking_reason: 'Deterministic ranking.' },
};
