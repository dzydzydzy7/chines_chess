export class ApiClient {
  constructor(fetchImplementation = globalThis.fetch.bind(globalThis)) {
    this.fetch = fetchImplementation;
  }

  getGame() {
    return this.request('/api/game');
  }

  legalMoves(from) {
    return this.request(`/api/game/legal-moves?from=${from}`);
  }

  move(from, to) {
    return this.request('/api/game/move', 'POST', { from, to });
  }

  reset() {
    return this.request('/api/game/reset', 'POST', {});
  }

  getConfig() {
    return this.request('/api/config');
  }

  saveConfig(patch) {
    return this.request('/api/config', 'PUT', patch);
  }

  async request(path, method = 'GET', body) {
    const response = await this.fetch(path, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `请求失败（${response.status}）`);
    return data;
  }
}
