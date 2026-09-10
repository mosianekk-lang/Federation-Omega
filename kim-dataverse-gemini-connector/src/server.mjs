import http from 'node:http';
import {loadConfig} from './config.mjs';
import {createProvider} from './providers.mjs';
import {createApp} from './app.mjs';
import {createLogger} from './core.mjs';

const logger = createLogger();
let server;

try {
  const config = loadConfig();
  const provider = createProvider(config);
  server = http.createServer(createApp({config, provider, logger}));
  server.requestTimeout = config.requestTimeoutMs + 5_000;
  server.headersTimeout = Math.min(server.requestTimeout, 65_000);
  server.listen(config.port, '0.0.0.0', () => logger('info', 'server.started', {
    port: config.port,
    provider: provider.name,
    sharedTokenConfigured: Boolean(config.sharedToken),
    allowedModels: config.allowedModels
  }));
} catch (error) {
  logger('error', 'server.configuration_failed', {message: error.message});
  process.exitCode = 1;
}

const stop = (signal) => {
  logger('info', 'server.stopping', {signal});
  if (!server) return process.exit(0);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10_000).unref();
};

process.on('SIGTERM', () => stop('SIGTERM'));
process.on('SIGINT', () => stop('SIGINT'));
