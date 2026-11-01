export const settingsSchema = {
  board: {
    show_legal_moves: { label: '显示合法落点', type: 'checkbox' },
    show_coordinates: { label: '显示交叉点坐标', type: 'checkbox' },
    animation_duration_ms: { label: '走子动画（毫秒）', type: 'number', min: 0, max: 2000 },
  },
  ai: {
    enabled: { label: '启用人机对弈', type: 'checkbox' },
    player_side: { label: '玩家阵营', type: 'select', options: [['red', '红方'], ['black', '黑方']] },
    difficulty: { label: 'AI 难度', type: 'select', options: [['easy', '简单'], ['medium', '中等'], ['hard', '困难']] },
    time_limit_ms: { label: 'AI 思考时限（毫秒）', type: 'number', min: 100, max: 60000 },
  },
  vision: {
    enabled: { label: '启用视觉识别（后续版本）', type: 'checkbox' },
    camera_device: { label: '摄像头设备', type: 'text' },
    confidence: { label: '识别置信度阈值', type: 'number', min: 0, max: 1, step: 0.05 },
  },
  robot: {
    enabled: { label: '启用机械臂（后续版本）', type: 'checkbox' },
    port: { label: '机械臂串口', type: 'text', placeholder: '例如 /dev/ttyUSB0' },
    speed_percent: { label: '运动速度（%）', type: 'number', min: 1, max: 100 },
    dry_run: { label: '仅模拟机械臂动作', type: 'checkbox' },
  },
  system: {
    host: { label: '监听地址', type: 'text' },
    port: { label: '服务端口', type: 'number', min: 1, max: 65535 },
    log_level: { label: '日志级别', type: 'select', options: [['DEBUG', 'DEBUG'], ['INFO', 'INFO'], ['WARNING', 'WARNING'], ['ERROR', 'ERROR']] },
  },
};

export const sectionTitles = {
  board: '棋盘与显示',
  ai: '人工智能',
  vision: '视觉识别',
  robot: '机械臂与安全',
  system: '系统',
};

export function initialUiState() {
  return { selected: null, targets: [], activeTab: 'board' };
}

export function canHumanMove(game) {
  return game.mode !== 'pve' || (!game.ai_thinking && game.turn === game.player_side);
}

export function selectSquare(state, game, square, targets) {
  if (!canHumanMove(game)) return { selected: null, targets: [], move: null };
  const piece = game.pieces.find((candidate) => candidate.square === square);
  if (state.selected !== null && state.targets.includes(square)) {
    return { selected: null, targets: [], move: { from: state.selected, to: square } };
  }
  if (state.selected === square) {
    return { selected: null, targets: [], move: null };
  }
  if (piece?.side === game.turn && !game.status.endsWith('_won')) {
    return { selected: square, targets, move: null };
  }
  return { selected: null, targets: [], move: null };
}

export function statusText(game) {
  const side = game.turn === 'red' ? '红方' : '黑方';
  const difficulties = { easy: '简单', medium: '中等', hard: '困难' };
  if (game.ai_thinking) return `AI 思考中（${difficulties[game.difficulty]}）…`;
  if (game.ai_error) return `AI 已暂停：${game.ai_error}`;
  if (game.status === 'check') return `${side}被将军，应将`;
  if (game.status === 'red_won') return '红方获胜';
  if (game.status === 'black_won') return '黑方获胜';
  return `${side}行棋`;
}

export function formatSquare(square) {
  return `(${Math.floor(square / 9)}, ${square % 9})`;
}

export function formatMove(move) {
  return `${move.piece} ${formatSquare(move.from)} → ${formatSquare(move.to)}`;
}

export function mergeConfig(original, patch) {
  const result = structuredClone(original);
  for (const [section, values] of Object.entries(patch)) {
    result[section] = { ...result[section], ...values };
  }
  return result;
}
