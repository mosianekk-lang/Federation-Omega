import { HeartbeatBackendClient, GoogleIdentityTokenProvider } from "./backend.js";
import { loadConfig } from "./config.js";
import { JwtOAuthVerifier } from "./oauth.js";
import { createApp } from "./server.js";

const config = loadConfig();
const verifier = new JwtOAuthVerifier(config);
const backend = new HeartbeatBackendClient(config, new GoogleIdentityTokenProvider());
const app = createApp(config, verifier, backend);

app.listen(config.port, "0.0.0.0", () => {
  console.log(JSON.stringify({
    severity: "INFO",
    event: "heartbeat_gateway_listening",
    port: config.port,
    auth: "oauth2-resource-server",
  }));
});
