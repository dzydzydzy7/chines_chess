import test from 'node:test';
import assert from 'node:assert/strict';
import { initialUiState, selectSquare, statusText, settingsSchema, mergeConfig } from '../web/ui_state.js';

const game = {
  pieces: [{ square: 54, side: 'red', kind: 'pawn', name: '兵' }],
  turn: 'red',
  status: 'playing',
  history: [],
};

test('initial UI state has no selection and starts on board tab', () => {
  assert.equal(initialUiState().selected, null);
  assert.equal(initialUiState().activeTab, 'board');
});

test('clicking a friendly piece selects it and stores legal targets', () => {
  const result = selectSquare(initialUiState(), game, 54, [45]);
  assert.deepEqual(result, { selected: 54, targets: [45], move: null });
});

test('clicking an opponent piece during its turn does not select it', () => {
  const position = { ...game, turn: 'black' };
  const result = selectSquare(initialUiState(), position, 54, []);
  assert.equal(result.selected, null);
});

test('clicking a legal destination emits one move and clears selection', () => {
  const state = { ...initialUiState(), selected: 54, targets: [45] };
  const result = selectSquare(state, game, 45, []);
  assert.deepEqual(result.move, { from: 54, to: 45 });
  assert.equal(result.selected, null);
  assert.deepEqual(result.targets, []);
});

test('clicking selected piece deselects it', () => {
  const state = { ...initialUiState(), selected: 54, targets: [45] };
  const result = selectSquare(state, game, 54, []);
  assert.equal(result.selected, null);
});

test('status text describes turn check and winner', () => {
  assert.equal(statusText(game), '红方行棋');
  assert.equal(statusText({ ...game, status: 'check' }), '红方被将军，应将');
  assert.equal(statusText({ ...game, status: 'red_won' }), '红方获胜');
});

test('settings schema includes all project subsystems', () => {
  assert.deepEqual(Object.keys(settingsSchema), ['board', 'ai', 'vision', 'robot', 'system']);
  for (const fields of Object.values(settingsSchema)) {
    assert.ok(Object.keys(fields).length > 0);
  }
});

test('config update changes only submitted values', () => {
  const original = { board: { show_coordinates: true, show_legal_moves: true } };
  const merged = mergeConfig(original, { board: { show_coordinates: false } });
  assert.deepEqual(merged, { board: { show_coordinates: false, show_legal_moves: true } });
  assert.equal(original.board.show_coordinates, true);
});
