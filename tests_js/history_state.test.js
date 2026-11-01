import test from 'node:test';
import assert from 'node:assert/strict';
import { formatMove, formatSquare } from '../web/ui_state.js';

test('history coordinates use row and column instead of linear square indices', () => {
  assert.equal(formatSquare(54), '(6, 0)');
  assert.equal(formatSquare(45), '(5, 0)');
});

test('history move includes piece name and two-dimensional coordinates', () => {
  assert.equal(formatMove({ piece: '兵', from: 54, to: 45 }), '兵 (6, 0) → (5, 0)');
});
