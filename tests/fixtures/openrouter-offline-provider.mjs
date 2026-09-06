// Native provider-boundary experiment. Fixture credentials and in-memory I/O only.
// Unlike a config plugin, this module is mandatory for provider initialization.
import { createOpenRouter } from './config/opencode/node_modules/@openrouter/ai-sdk-provider/dist/index.mjs';
import { createGuard } from './transport-guard.mjs';

export function createOfflineProvider(options) {
  const {fixtureText = 'READY', ...settings} = options;
  if (typeof fixtureText !== 'string') throw new Error('invalid offline response');
  return createOpenRouter({
    ...settings,
    fetch: createGuard({
      transport: async (url, init) => {
        // Stand-in for the future lazy credential lookup: validation must precede it.
        console.error('OFFLINE_CREDENTIAL_LOOKUP');
        const body = JSON.parse(init.body);
        console.error('OFFLINE_REQUEST ' + JSON.stringify({url, model: body.model, provider: body.provider}));
        const envelope = {id: 'offline-fixture', object: 'chat.completion.chunk', created: 1, model: 'fixture/concrete-free-model'};
        const frames = [
          {...envelope, choices: [{index: 0, delta: {role: 'assistant', content: fixtureText}, finish_reason: null}]},
          {...envelope, choices: [{index: 0, delta: {}, finish_reason: 'stop'}],
            usage: {prompt_tokens: 1, completion_tokens: 1, total_tokens: 2, cost: 0}},
        ];
        return new Response(frames.map(frame => 'data: ' + JSON.stringify(frame) + '\n\n').join('') + 'data: [DONE]\n\n',
          {headers: {'content-type': 'text/event-stream'}});
      },
      receipt: value => console.error('OFFLINE_RECEIPT ' + JSON.stringify({...value, fixture: true})),
    }),
  });
}
