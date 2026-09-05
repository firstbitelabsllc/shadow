// Experimental, unregistered OpenCode transport boundary. No credential owner.
// This seam is not a sandbox, admission authority, or authenticated live proof.
// Transport and receipt sink are trusted launcher inputs, never model inputs.
import { createHash } from 'node:crypto';

const ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions';
const LIMIT = 1024 * 1024;
const fail = () => { throw new Error('openrouter_guard_refused'); };
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const zero = x => typeof x === 'number' && Number.isFinite(x) && x === 0;
const fields = (x, keys) => object(x) && Object.keys(x).length === keys.length && keys.every(k => Object.hasOwn(x, k));

function uniqueJson(text) {
  let value;
  try { value = JSON.parse(text); } catch { fail(); }
  // Parse first for grammar; scan keys separately because JSON.parse discards
  // duplicate values (including a paid cost preceding a zero cost).
  const stack = [];
  const tokens = [...text.matchAll(/"(?:\\[\s\S]|[^"\\])*"|[{}\[\]:,]|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g)];
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i][0];
    if (token === '{') stack.push(new Set());
    else if (token === '[') stack.push(null);
    else if (token === '}' || token === ']') stack.pop();
    else if (token.startsWith('"') && tokens[i + 1]?.[0] === ':') {
      const key = JSON.parse(token), keys = stack.at(-1);
      if (!keys || keys.has(key)) fail();
      // A tiny nonzero JSON decimal can underflow to zero in JSON.parse.
      // Cost must be zero in the provider bytes as well as the parsed number.
      if (key === 'cost' && !/^-?0(?:\.0+)?(?:[eE][+-]?\d+)?$/.test(tokens[i + 2]?.[0] ?? '')) fail();
      keys.add(key);
    }
  }
  return value;
}

function validateRequest(input, init) {
  if (input !== ENDPOINT || init?.method !== 'POST' || typeof init.body !== 'string' || Buffer.byteLength(init.body) > LIMIT) fail();
  const body = uniqueJson(init.body);
  const allowed = ['model', 'messages', 'stream', 'stream_options', 'usage', 'provider', 'temperature', 'top_p', 'max_tokens', 'tools', 'tool_choice'];
  if (!object(body) || Object.keys(body).some(k => !allowed.includes(k))) fail();
  if (body.model !== 'openrouter/free' || body.stream !== true) fail();
  const textContent = value => typeof value === 'string' || (Array.isArray(value) && value.length > 0 &&
    value.every(part => fields(part, ['type', 'text']) && part.type === 'text' && typeof part.text === 'string'));
  if (!Array.isArray(body.messages) || !body.messages.length || body.messages.some(m =>
    !fields(m, ['role', 'content']) || !['user', 'assistant', 'system'].includes(m.role) || !textContent(m.content))) fail();
  if (body.usage !== undefined && (!fields(body.usage, ['include']) || body.usage.include !== true)) fail();
  if (body.stream_options !== undefined && (!fields(body.stream_options, ['include_usage']) || body.stream_options.include_usage !== true)) fail();
  // Tool-enabled candidate work remains gated on a separately proved capability.
  if (body.tools !== undefined && (!Array.isArray(body.tools) || body.tools.length)) fail();
  if (body.tool_choice !== undefined && body.tool_choice !== 'none') fail();
  const p = body.provider;
  if (!fields(p, ['zdr', 'data_collection', 'require_parameters', 'allow_fallbacks', 'max_price']) ||
      p.zdr !== true || p.data_collection !== 'deny' || p.require_parameters !== true || p.allow_fallbacks !== false ||
      !fields(p.max_price, ['prompt', 'completion', 'request', 'image']) || !Object.values(p.max_price).every(zero)) fail();
  // Re-encode what was validated: duplicate JSON keys cannot differ on the wire.
  return JSON.stringify(body);
}

async function verifiedBody(response, signal) {
  if (response.status !== 200 || response.redirected ||
      (response.url && response.url !== ENDPOINT) ||
      response.headers.get('content-type')?.split(';')[0].trim() !== 'text/event-stream' || !response.body) fail();
  const reader = response.body.getReader();
  let onAbort;
  const aborted = new Promise((_, reject) => {
    onAbort = () => reject(new Error('openrouter_guard_refused'));
    signal.addEventListener('abort', onAbort, {once: true});
  });
  let size = 0;
  const chunks = [];
  try {
    if (signal.aborted) fail();
    for (;;) {
      const {done, value} = await Promise.race([reader.read(), aborted]);
      if (done) break;
      size += value.byteLength;
      if (size > LIMIT) fail();
      chunks.push(value);
    }
  } catch {
    void reader.cancel().catch(() => {});
    fail();
  } finally { signal.removeEventListener('abort', onAbort); reader.releaseLock(); }
  let text;
  try { text = new TextDecoder('utf-8', {fatal: true}).decode(Buffer.concat(chunks)); } catch { fail(); }
  if (!text.replaceAll('\r\n', '\n').endsWith('\n\n')) fail();
  let model, id, cost, finished = false, done = false;
  const events = text.replaceAll('\r\n', '\n').split('\n\n');
  for (const event of events) {
    const lines = event.split('\n').filter(line => line && !line.startsWith(':'));
    if (!lines.length) continue;
    if (done || lines.some(line => !line.startsWith('data: '))) fail();
    const data = lines.map(line => line.slice(6)).join('\n');
    if (data === '[DONE]') { done = true; continue; }
    const frame = uniqueJson(data);
    if (!object(frame) || Object.hasOwn(frame, 'error') || typeof frame.id !== 'string' || !frame.id ||
        typeof frame.model !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\/[A-Za-z0-9][A-Za-z0-9._:+/-]{0,191}$/.test(frame.model) ||
        frame.model.split('/')[0].toLowerCase() === 'openrouter') fail();
    if ((model && model !== frame.model) || (id && id !== frame.id)) fail();
    model = frame.model; id = frame.id;
    if (!Array.isArray(frame.choices) || frame.choices.length !== 1 || cost !== undefined) fail();
    for (const choice of frame.choices) {
      if (!object(choice) || choice.index !== 0 || !object(choice.delta) ||
          Object.keys(choice.delta).some(k => !['role', 'content'].includes(k)) ||
          (choice.delta.role !== undefined && choice.delta.role !== 'assistant') ||
          (choice.delta.content != null && typeof choice.delta.content !== 'string')) fail();
      if (choice.finish_reason != null) {
        if (choice.finish_reason !== 'stop' || (finished &&
            (!object(frame.usage) || (choice.delta.content != null && choice.delta.content !== '')))) fail();
        finished = true;
      } else if (finished) fail();
    }
    if (frame.usage != null) {
      if (!finished || !object(frame.usage) || !zero(frame.usage.cost)) fail();
      cost = 0;
    }
  }
  if (!done || !finished || cost !== 0 || !model) fail();
  return {text, model, cost};
}

export function createGuard({transport, receipt}) {
  if (typeof transport !== 'function' || typeof receipt !== 'function') fail();
  let used = false;
  return async (input, init) => {
    if (used) fail();
    used = true; // Includes failed attempts: retries cannot evade the budget.
    const body = validateRequest(input, init);
    const signal = AbortSignal.any([AbortSignal.timeout(30_000), ...(init.signal ? [init.signal] : [])]);
    if (signal.aborted) fail();
    const response = await transport(ENDPOINT, {...init, body, redirect: 'error', signal});
    const verified = await verifiedBody(response, signal);
    await receipt({request_sha256: createHash('sha256').update(body).digest('hex'), model: verified.model, cost: verified.cost});
    return new Response(verified.text, {headers: {'content-type': 'text/event-stream'}});
  };
}
