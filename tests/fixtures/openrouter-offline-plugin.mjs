// Test-only external boundary: no socket, credentials, or global fetch call.
import { createGuard } from './transport-guard.mjs';

export const OfflineWitness = async () => ({
  config: async config => {
    config.provider.openrouter.options.fetch = createGuard({
      transport: async (url, init) => {
        const body = JSON.parse(init.body);
        console.error('OFFLINE_REQUEST ' + JSON.stringify({url, model: body.model, provider: body.provider}));
        const envelope = {id: 'offline-fixture', object: 'chat.completion.chunk', created: 1, model: 'fixture/concrete-free-model'};
        const frames = [
          {...envelope, choices: [{index: 0, delta: {role: 'assistant', content: 'READY'}, finish_reason: null}]},
          {...envelope, choices: [{index: 0, delta: {}, finish_reason: 'stop'}],
            usage: {prompt_tokens: 1, completion_tokens: 1, total_tokens: 2, cost: 0}},
        ];
        return new Response(frames.map(frame => 'data: ' + JSON.stringify(frame) + '\n\n').join('') + 'data: [DONE]\n\n',
          {headers: {'content-type': 'text/event-stream'}});
      },
      receipt: value => console.error('OFFLINE_RECEIPT ' + JSON.stringify({...value, fixture: true})),
    });
  },
});
