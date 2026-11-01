import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient } from '../web/api_client.js';

test('API client sends moves as JSON and returns game state', async () => {
  const calls = [];
  const fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ turn: 'black' }) };
  };
  const client = new ApiClient(fetch);
  const state = await client.move(54, 45);
  assert.equal(state.turn, 'black');
  assert.equal(calls[0].url, '/api/game/move');
  assert.deepEqual(JSON.parse(calls[0].options.body), { from: 54, to: 45 });
});

test('API client exposes undo save history restore and replay operations', async () => {
  const calls = [];
  const fetch = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({}) };
  };
  const client = new ApiClient(fetch);
  await client.undo();
  await client.saveGame();
  await client.listGames();
  await client.restoreGame('abc123');
  await client.replayGame('abc123', 4);
  assert.deepEqual(calls.map((call) => [call.options.method || 'GET', call.url]), [
    ['POST', '/api/game/undo'],
    ['POST', '/api/game/save'],
    ['GET', '/api/games'],
    ['POST', '/api/games/abc123/restore'],
    ['GET', '/api/games/abc123/replay?ply=4'],
  ]);
});

test('API client exposes server validation errors', async () => {
  const fetch = async () => ({ ok: false, status: 422, json: async () => ({ error: 'illegal move' }) });
  const client = new ApiClient(fetch);
  await assert.rejects(() => client.reset(), /illegal move/);
});
