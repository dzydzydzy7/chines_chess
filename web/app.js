import { ApiClient } from './api_client.js';
import { canHumanMove, formatMove, initialUiState, mergeConfig, sectionTitles, selectSquare, settingsSchema, statusText } from './ui_state.js';

const api = new ApiClient();
const board = document.querySelector('#chessboard');
const status = document.querySelector('#game-status');
const history = document.querySelector('#move-history');
const emptyHistory = document.querySelector('#empty-history');
const moveCount = document.querySelector('#move-count');
const toast = document.querySelector('#toast');
let game;
let liveGame;
let replay = null;
let config;
let ui = initialUiState();
let busy = false;
let toastTimer;
let pollTimer;

function showToast(message) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.hidden = false;
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2600);
}

function boardLines() {
  const verticals = Array.from({ length: 9 }, (_, col) => {
    const x = col * 100;
    return col === 0 || col === 8
      ? `<line x1="${x}" y1="0" x2="${x}" y2="900"/>`
      : `<line x1="${x}" y1="0" x2="${x}" y2="400"/><line x1="${x}" y1="500" x2="${x}" y2="900"/>`;
  }).join('');
  const horizontals = Array.from({ length: 10 }, (_, row) => `<line x1="0" y1="${row * 100}" x2="800" y2="${row * 100}"/>`).join('');
  return `<svg class="board-lines" viewBox="-4 -4 808 908" aria-hidden="true">${verticals}${horizontals}
    <path d="M300 0L500 200M500 0L300 200M300 700L500 900M500 700L300 900"/>
    <text class="river-text" x="115" y="465">楚 河</text><text class="river-text" x="510" y="465">漢 界</text></svg>`;
}

function renderBoard() {
  const pieces = new Map(game.pieces.map((piece) => [piece.square, piece]));
  const targets = config.board.show_legal_moves ? ui.targets : [];
  board.innerHTML = boardLines();
  for (let square = 0; square < 90; square += 1) {
    const row = Math.floor(square / 9);
    const col = square % 9;
    const piece = pieces.get(square);
    const button = document.createElement('button');
    button.className = 'square';
    button.style.left = `${col * 12.5}%`;
    button.style.top = `${row * (100 / 9)}%`;
    button.dataset.square = String(square);
    button.setAttribute('aria-label', `${row + 1} 行 ${col + 1} 列${piece ? ` ${piece.name}` : ' 空位'}`);
    if (ui.selected === square) button.classList.add('selected');
    if (targets.includes(square)) button.classList.add(piece ? 'legal-capture' : 'legal-empty');
    if (piece) button.innerHTML = `<span class="piece ${piece.side}">${piece.name}</span>`;
    if (config.board.show_coordinates) button.innerHTML += `<span class="coordinate">${row},${col}</span>`;
    button.addEventListener('click', () => onSquare(square));
    board.append(button);
  }
}

function renderGame() {
  status.textContent = replay ? `回放：第 ${replay.ply} 手` : statusText(game);
  document.querySelector('#game-mode').textContent = game.mode === 'pve'
    ? `人机对弈 · 玩家${game.player_side === 'red' ? '红方' : '黑方'}`
    : '双人对弈';
  moveCount.textContent = `${game.history.length} 手`;
  emptyHistory.hidden = game.history.length > 0;
  history.innerHTML = '';
  game.history.forEach((move, index) => {
    const item = document.createElement('li');
    const side = index % 2 === 0 ? '红' : '黑';
    item.innerHTML = `<span>${index + 1}. ${side}</span><strong>${formatMove(move)}</strong>`;
    if (move.ai) item.title = `AI ${move.ai.version} · 深度 ${move.ai.completed_depth} · ${Math.round(move.ai.elapsed_ms)} ms`;
    history.append(item);
  });
  history.scrollTop = history.scrollHeight;
  document.querySelector('#replay-controls').hidden = !replay;
  document.querySelector('#undo-game').disabled = Boolean(replay) || !game.history.length;
  document.querySelector('#save-game').disabled = Boolean(replay);
  document.querySelector('#new-game').disabled = Boolean(replay);
  if (replay) {
    document.querySelector('#replay-progress').textContent = `${replay.ply} / ${replay.length}`;
    document.querySelector('#replay-previous').disabled = replay.ply === 0;
    document.querySelector('#replay-next').disabled = replay.ply === replay.length;
  }
  renderBoard();
  scheduleAiPolling();
}

function scheduleAiPolling() {
  clearTimeout(pollTimer);
  if (!game?.ai_thinking || replay) return;
  const gameId = game.id;
  const historyLength = game.history.length;
  pollTimer = setTimeout(async () => {
    try {
      const latest = await api.getGame();
      if (replay || game.id !== gameId || game.history.length !== historyLength) return;
      game = latest;
      liveGame = latest;
      renderGame();
    } catch (error) {
      showToast(error.message);
      pollTimer = setTimeout(scheduleAiPolling, 500);
    }
  }, 100);
}

async function onSquare(square) {
  if (busy || replay || !canHumanMove(game)) return;
  const piece = game.pieces.find((candidate) => candidate.square === square);
  const isDestination = ui.selected !== null && ui.targets.includes(square);
  let targets = [];
  if (!isDestination && piece?.side === game.turn && ui.selected !== square) {
    try {
      targets = (await api.legalMoves(square)).targets;
    } catch (error) {
      showToast(error.message);
      return;
    }
  }
  const result = selectSquare(ui, game, square, targets);
  ui = { ...ui, selected: result.selected, targets: result.targets };
  renderBoard();
  if (result.move) await performMove(result.move.from, result.move.to);
}

async function performMove(from, to) {
  busy = true;
  try {
    game = await api.move(from, to);
    liveGame = game;
    renderGame();
  } catch (error) {
    showToast(error.message);
  } finally {
    busy = false;
  }
}

function switchTab(tabName) {
  ui.activeTab = tabName;
  document.querySelectorAll('[data-tab]').forEach((tab) => {
    const active = tab.dataset.tab === tabName;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });
  document.querySelector('#board-panel').hidden = tabName !== 'board';
  document.querySelector('#history-panel').hidden = tabName !== 'history';
  document.querySelector('#settings-panel').hidden = tabName !== 'settings';
  if (tabName === 'history') loadGameHistory();
}

async function loadGameHistory() {
  const container = document.querySelector('#game-list');
  try {
    const games = (await api.listGames()).games;
    document.querySelector('#empty-games').hidden = games.length > 0;
    container.innerHTML = '';
    for (const saved of games) {
      const item = document.createElement('article');
      item.className = 'saved-game';
      const information = document.createElement('div');
      const id = document.createElement('strong');
      id.textContent = saved.id;
      const time = document.createElement('span');
      time.textContent = `${new Date(saved.created_at).toLocaleString()} · ${saved.move_count} 手`;
      information.append(id, time);
      const actions = document.createElement('div');
      const restore = document.createElement('button');
      restore.className = 'secondary-button';
      restore.textContent = '恢复';
      restore.addEventListener('click', () => restoreGame(saved.id));
      const replayButton = document.createElement('button');
      replayButton.className = 'secondary-button';
      replayButton.textContent = '回放';
      replayButton.addEventListener('click', () => startReplay(saved.id));
      actions.append(restore, replayButton);
      item.append(information, actions);
      container.append(item);
    }
  } catch (error) {
    showToast(error.message);
  }
}

async function restoreGame(id) {
  try {
    replay = null;
    game = await api.restoreGame(id);
    liveGame = game;
    ui = { ...ui, selected: null, targets: [] };
    switchTab('board');
    renderGame();
    showToast('对局已恢复');
  } catch (error) {
    showToast(error.message);
  }
}

async function startReplay(id, ply = 0) {
  try {
    game = await api.replayGame(id, ply);
    replay = { id, ply, length: game.replay_length };
    ui = { ...ui, selected: null, targets: [] };
    switchTab('board');
    renderGame();
  } catch (error) {
    showToast(error.message);
  }
}

function renderSettings() {
  const form = document.querySelector('#settings-form');
  form.innerHTML = '';
  for (const [section, fields] of Object.entries(settingsSchema)) {
    const fieldset = document.createElement('fieldset');
    fieldset.className = 'settings-section';
    fieldset.innerHTML = `<h2>${sectionTitles[section]}</h2>`;
    for (const [key, definition] of Object.entries(fields)) {
      const value = config[section][key];
      const wrapper = document.createElement('div');
      wrapper.className = 'setting';
      const label = document.createElement('label');
      label.textContent = definition.label;
      let input;
      if (definition.type === 'select') {
        input = document.createElement('select');
        for (const [optionValue, text] of definition.options) input.add(new Option(text, optionValue));
        input.value = value;
      } else {
        input = document.createElement('input');
        input.type = definition.type;
        if (definition.type === 'checkbox') input.checked = value;
        else input.value = value;
      }
      input.name = `${section}.${key}`;
      for (const attribute of ['min', 'max', 'step', 'placeholder']) {
        if (definition[attribute] !== undefined) input.setAttribute(attribute, definition[attribute]);
      }
      label.append(input);
      wrapper.append(label);
      fieldset.append(wrapper);
    }
    form.append(fieldset);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const patch = {};
  for (const [section, fields] of Object.entries(settingsSchema)) {
    patch[section] = {};
    for (const [key, definition] of Object.entries(fields)) {
      const input = document.querySelector(`[name="${section}.${key}"]`);
      if (definition.type === 'checkbox') patch[section][key] = input.checked;
      else if (definition.type === 'number') patch[section][key] = Number(input.value);
      else patch[section][key] = input.value;
    }
  }
  try {
    const aiChanged = JSON.stringify(config.ai) !== JSON.stringify(patch.ai);
    config = mergeConfig(config, await api.saveConfig(patch));
    if (aiChanged) {
      game = await api.getGame();
      liveGame = game;
      replay = null;
      ui = { ...ui, selected: null, targets: [] };
      switchTab('board');
      renderGame();
      showToast('设置已保存，对局已按新 AI 配置开始');
    } else {
      showToast('设置已保存');
      renderBoard();
    }
  } catch (error) {
    showToast(error.message);
  }
}

document.querySelectorAll('[data-tab]').forEach((tab) => tab.addEventListener('click', () => switchTab(tab.dataset.tab)));
document.querySelector('#new-game').addEventListener('click', async () => {
  try {
    ui = { ...ui, selected: null, targets: [] };
    game = config.ai.enabled
      ? await api.startPve(config.ai.player_side, config.ai.difficulty, config.ai.time_limit_ms)
      : await api.reset();
    liveGame = game;
    renderGame();
  } catch (error) {
    showToast(error.message);
  }
});
document.querySelector('#undo-game').addEventListener('click', async () => {
  if (busy || replay) return;
  busy = true;
  try {
    game = await api.undo();
    liveGame = game;
    ui = { ...ui, selected: null, targets: [] };
    renderGame();
  } catch (error) {
    showToast(error.message);
  } finally {
    busy = false;
  }
});
document.querySelector('#save-game').addEventListener('click', async () => {
  try {
    game = await api.saveGame();
    liveGame = game;
    renderGame();
    showToast(`对局已保存：${game.id}`);
  } catch (error) {
    showToast(error.message);
  }
});
document.querySelector('#replay-previous').addEventListener('click', () => {
  if (replay) startReplay(replay.id, replay.ply - 1);
});
document.querySelector('#replay-next').addEventListener('click', () => {
  if (replay) startReplay(replay.id, replay.ply + 1);
});
document.querySelector('#replay-exit').addEventListener('click', () => {
  replay = null;
  game = liveGame;
  renderGame();
});
document.querySelector('#settings-form').addEventListener('submit', saveSettings);

try {
  [game, config] = await Promise.all([api.getGame(), api.getConfig()]);
  liveGame = game;
  document.documentElement.style.setProperty('--move-duration', `${config.board.animation_duration_ms}ms`);
  renderGame();
  renderSettings();
} catch (error) {
  status.textContent = '无法连接后端';
  showToast(error.message);
}
