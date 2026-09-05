import http from "node:http";

import { GoogleAuth } from "google-auth-library";

import { createHttpHandler } from "./http-app.js";
import { createOperatorService } from "./operator-service.js";

const {
  ADMIN_TOKEN,
  PORT = "8080",
  PROJECT_ID,
  REGION = "africa-south1",
  TARGET_SERVICE = "architron9",
} = process.env;

const auth = new GoogleAuth({
  scopes: ["https://www.googleapis.com/auth/cloud-platform"],
});
const googleRequest = (options) => auth.request(options);
const service = createOperatorService({
  projectId: PROJECT_ID,
  region: REGION,
  targetService: TARGET_SERVICE,
  googleRequest,
});
const handler = createHttpHandler({ service, adminToken: ADMIN_TOKEN });
const server = http.createServer(handler);

server.listen(Number(PORT), "0.0.0.0", () => {
  console.log(JSON.stringify({
    event: "operator_started",
    port: Number(PORT),
    region: REGION,
    targetService: TARGET_SERVICE,
  }));
});
