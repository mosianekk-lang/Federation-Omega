import http from 'node:http';
import {loadConfig} from '../src/config.mjs';
import {createApp} from '../src/app.mjs';

const config = loadConfig({port: 0, providerMode: 'vertex', project: 'smoke-project'});
const provider = {name: 'fake', validateSource() {}, async generate() { return {text: 'smoke-ok', payload: {candidates: [{content: {parts: [{text: 'smoke-ok'}]}, finishReason: 'STOP'}]}}; }};
const server = http.createServer(createApp({config, provider, logger: () => {}}));
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const address = server.address();
const health = await fetch(`http://127.0.0.1:${address.port}/health`);
const generate = await fetch(`http://127.0.0.1:${address.port}/v1/generate`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({prompt: 'smoke'})});
server.close();
if (!health.ok || !generate.ok || (await generate.json()).data.text !== 'smoke-ok') process.exit(1);
console.log('SMOKE_OK');
