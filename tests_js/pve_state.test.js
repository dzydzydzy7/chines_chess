import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../web/api_client.js';
import { canHumanMove, selectSquare, settingsSchema, statusText } from '../web/ui_state.js';

const pveGame = {
  pieces: [{ square: 27, side: 'black', kind: 'pawn', name: '卒' }],
  turn: 'black',
  status: 'playing',
  history: [],
  mode: 'pve',
  player_side: 'red',
  difficulty: 'medium',
  ai_thinking: true,
  ai_error: null,
};

test('PVE input is allowed only for the player on their turn', () => {
  assert.equal(canHumanMove({ ...pveGame, mode: 'pvp' }), true);
  assert.equal(canHumanMove(pveGame), false);
  assert.equal(canHumanMove({ ...pveGame, ai_thinking: false }), false);
  assert.equal(canHumanMove({ ...pveGame, turn: 'red', ai_thinking: false }), true);
});

test('piece selection is blocked during AI turn', () => {
  const result = selectSquare({ selected: null, targets: [] }, pveGame, 27, [36]);
  assert.equal(result.selected, null);
  assert.deepEqual(result.targets, []);
});

test('status text exposes thinking and recoverable AI errors', () => {
  assert.equal(statusText(pveGame), 'AI 思考中（中等）…');
  assert.equal(statusText({ ...pveGame, ai_thinking: false, ai_error: 'stopped' }), 'AI 已暂停：stopped');
});

test('AI settings include player side without future-version labels', () => {
  assert.deepEqual(settingsSchema.ai.player_side.options, [['red', '红方'], ['black', '黑方']]);
  assert.equal(settingsSchema.ai.enabled.label, '启用人机对弈');
});

test('API client starts PVE with side difficulty and time limit', async () => {
  const calls = [];
  const fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ mode: 'pve' }) };
  };
  const client = new ApiClient(fetch);
  const state = await client.startPve('black', 'hard', 800);
  assert.equal(state.mode, 'pve');
  assert.equal(calls[0].url, '/api/game/pve');
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    player_side: 'black',
    difficulty: 'hard',
    time_limit_ms: 800,
  });
});
