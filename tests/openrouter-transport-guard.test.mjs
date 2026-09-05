import test from 'node:test';
import assert from 'node:assert/strict';
import { createGuard } from '../scripts/dev/openrouter-transport-guard.mjs';

const endpoint = 'https://openrouter.ai/api/v1/chat/completions';
function request() {
  return {model: 'openrouter/free', stream: true,
    messages: [{role: 'user', content: 'Reply with READY only.'}],
    provider: {zdr: true, data_collection: 'deny', require_parameters: true,
      allow_fallbacks: false, max_price: {prompt: 0, completion: 0, request: 0, image: 0}}};
}
function stream({model = 'fixture/concrete-free', cost = 0, done = true} = {}) {
  const frames = [
    {id: 'fixture-1', model, choices: [{index: 0, delta: {content: 'READY'}, finish_reason: null}]},
    {id: 'fixture-1', model, choices: [{index: 0, delta: {}, finish_reason: 'stop'}], usage: {cost}},
  ];
  return frames.map(x => `data: ${JSON.stringify(x)}\n\n`).join('') + (done ? 'data: [DONE]\n\n' : '');
}
function fixture(options = {}) {
  const calls = [], receipts = [];
  const guard = createGuard({transport: async (url, init) => {
    calls.push({url, init});
    return new Response(options.body ?? stream(options), {
      status: options.status ?? 200, headers: {'content-type': 'text/event-stream'},
    });
  }, receipt: value => receipts.push(value)});
  return {guard, calls, receipts};
}
const init = body => ({method: 'POST', body: JSON.stringify(body)});

test('accepts native OpenCode text parts and explicit usage inclusion', async () => {
  const f = fixture(), r = request();
  r.usage = {include: true};
  r.messages.unshift({role: 'system', content: [{type: 'text', text: 'Synthetic instruction.'}]});
  await f.guard(endpoint, init(r));
  assert.deepEqual(JSON.parse(f.calls[0].init.body), r);
});
test('native parts cannot carry images or disable usage', async () => {
  for (const mutate of [r => {r.usage = {include: false};}, r => {
    r.messages[0].content = [{type: 'image_url', image_url: {url: 'https://invalid.test'}}];
  }]) {
    const f = fixture(), r = request(); mutate(r);
    await assert.rejects(f.guard(endpoint, init(r)), /openrouter_guard/);
    assert.equal(f.calls.length, 0);
  }
});

test('valid fixture is witnessed before any content is released', async () => {
  const f = fixture();
  const response = await f.guard(endpoint, init(request()));
  assert.match(await response.text(), /READY/);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].init.redirect, 'error');
  assert.equal(f.receipts.length, 1);
  assert.equal(f.receipts[0].model, 'fixture/concrete-free');
  assert.equal(f.receipts[0].cost, 0);
  assert.match(f.receipts[0].request_sha256, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(f.receipts).includes('READY'), false);
});
for (const [name, mutate] of Object.entries({
  paid: r => {r.model = 'vendor/paid';},
  zdr: r => {delete r.provider.zdr;},
  collection: r => {r.provider.data_collection = 'allow';},
  fallback: r => {r.provider.allow_fallbacks = true;},
  parameters: r => {r.provider.require_parameters = false;},
  price: r => {r.provider.max_price.prompt = 0.01;},
  booleanPrice: r => {r.provider.max_price.request = false;},
  routes: r => {r.models = ['vendor/paid'];},
  shell: r => {r.tools = [{type: 'function', function: {name: 'bash'}}];},
})) test(`rejects ${name} before transport`, async () => {
  const f = fixture(), r = request(); mutate(r);
  await assert.rejects(f.guard(endpoint, init(r)), /openrouter_guard/);
  assert.equal(f.calls.length, 0); assert.equal(f.receipts.length, 0);
});
test('endpoint confusion never reaches transport', async () => {
  for (const url of [endpoint + '?x=1', endpoint + '/extra', 'http://openrouter.ai/api/v1/chat/completions', 'https://openrouter.ai.evil.test/api/v1/chat/completions']) {
    const f = fixture();
    await assert.rejects(f.guard(url, init(request())), /openrouter_guard/);
    assert.equal(f.calls.length, 0);
  }
});
test('second request is refused even after a successful response', async () => {
  const f = fixture(); await f.guard(endpoint, init(request()));
  await assert.rejects(f.guard(endpoint, init(request())), /openrouter_guard/);
  assert.equal(f.calls.length, 1);
});
test('cancelled stream refuses before receipt and cancels its reader', {timeout: 1000}, async () => {
  const controller = new AbortController();
  let cancelled = false, receipts = 0;
  const guard = createGuard({transport: async () => new Response(new ReadableStream({
    start() { queueMicrotask(() => controller.abort()); },
    cancel() { cancelled = true; },
  }), {headers: {'content-type': 'text/event-stream'}}), receipt: () => receipts++});
  await assert.rejects(guard(endpoint, {...init(request()), signal: controller.signal}), /openrouter_guard/);
  assert.equal(receipts, 0); assert.equal(cancelled, true);
});
test('OpenRouter documented usage frame repeats stop without content', async () => {
  // Shape pinned from https://openrouter.ai/docs/api_reference/streaming
  const envelope = {id: 'fixture-1', model: 'fixture/concrete-free'};
  const frames = [
    {...envelope, choices: [{index: 0, delta: {content: 'READY'}, finish_reason: 'stop'}]},
    {...envelope, choices: [{index: 0, delta: {content: '', role: 'assistant'}, finish_reason: 'stop', native_finish_reason: 'stop'}], usage: {cost: 0}},
  ];
  const f = fixture({body: frames.map(x => `data: ${JSON.stringify(x)}\n\n`).join('') + 'data: [DONE]\n\n'});
  await f.guard(endpoint, init(request()));
  assert.equal(f.receipts.length, 1);
});
for (const [name, options] of Object.entries({
  paid: {cost: 0.01}, missingCost: {body: stream().replace('"cost":0', '"tokens":1')},
  stringCost: {cost: '0'}, booleanCost: {cost: false},
  underflowCost: {body: stream().replace('"cost":0', '"cost":1e-400')},
  routerAlias: {model: 'openrouter/free'}, malformedModel: {model: 'free'},
  truncated: {done: false}, malformed: {body: 'data: not-json\n\ndata: [DONE]\n\n'},
  redirect: {status: 302}, providerError: {body: 'data: {"error":"bad"}\n\ndata: [DONE]\n\n'},
  legacyFunction: {body: stream().replace('"content":"READY"', '"function_call":{"name":"bash","arguments":"{}"}')},
  unknownDelta: {body: stream().replace('"content":"READY"', '"unexpected":"READY"')},
  duplicateCost: {body: stream().replace('"cost":0', '"cost":1,"cost":0')},
  incompleteEvent: {body: stream().trimEnd()},
  emptyChoices: {body: 'data: {"id":"fixture-1","model":"fixture/concrete-free","choices":[]}\n\n' + stream()},
  prematureUsage: {body: stream().replace('"content":"READY"},"finish_reason":null}]', '"content":"READY"},"finish_reason":null}],"usage":{"cost":0}')},
})) test(`refuses ${name} response without receipt or content`, async () => {
  const f = fixture(options);
  await assert.rejects(f.guard(endpoint, init(request())), /openrouter_guard/);
  assert.equal(f.calls.length, 1); assert.equal(f.receipts.length, 0);
});
