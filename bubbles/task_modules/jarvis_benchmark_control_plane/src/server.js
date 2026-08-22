import { createServer } from 'node:http';
import { createHttpApp } from './http-app.js';
import { loadRuntime } from './config.js';

const host = process.env.HOST || '127.0.0.1';
const port = Number(process.env.PORT || 8787);
const adminToken = process.env.JARVIS_BENCHMARK_ADMIN_TOKEN || '';

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('PORT must be an integer between 1 and 65535');
}
if (!['127.0.0.1', '::1', 'localhost'].includes(host)
  && (process.env.JARVIS_ALLOW_REMOTE_BIND !== 'true' || adminToken.length < 24)) {
  throw new Error('Remote binding requires JARVIS_ALLOW_REMOTE_BIND=true and an admin token of at least 24 characters');
}

const runtime = loadRuntime();
const app = createHttpApp({ ...runtime, adminToken });
const server = createServer({ requestTimeout: 15_000, headersTimeout: 10_000, keepAliveTimeout: 5_000 }, app.handler);

server.on('clientError', (error, socket) => {
  socket.end('HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n');
  process.stderr.write(`${JSON.stringify({ level: 'warn', event: 'client_error', code: error.code })}\n`);
});

server.listen(port, host, () => {
  process.stdout.write(`${JSON.stringify({
    level: 'info',
    event: 'server_started',
    host,
    port,
    writeApi: adminToken ? 'ENABLED' : 'DISABLED',
  })}\n`);
});

function shutdown(signal) {
  process.stdout.write(`${JSON.stringify({ level: 'info', event: 'shutdown', signal })}\n`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
