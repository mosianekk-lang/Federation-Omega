export type CfbeCapability = {
  id: string;
  name: string;
  priority: 'P0' | 'P1' | 'P2';
  layer: string;
  benchmark: string;
  state: 'WORK_PACKAGE_CREATED';
};

const DEFINITIONS: Omit<CfbeCapability, 'state'>[] = [
  { id: 'FM-CFBE-001', name: 'Web-safe owner auth adapter', priority: 'P0', layer: 'Web/Auth', benchmark: 'OpenAI/Google/Expo' },
  { id: 'FM-CFBE-002', name: 'Web-safe session storage adapter', priority: 'P0', layer: 'Web/Auth', benchmark: 'Expo/Chrome' },
  { id: 'FM-CFBE-003', name: 'Web export and hosting config', priority: 'P0', layer: 'Release', benchmark: 'Expo/Vercel/Cloud Run' },
  { id: 'FM-CFBE-004', name: 'PWA manifest + installability', priority: 'P1', layer: 'Web/PWA', benchmark: 'Expo/PWA leaders' },
  { id: 'FM-CFBE-005', name: 'Offline application shell', priority: 'P1', layer: 'Web/PWA', benchmark: 'Expo/Cloudflare' },
  { id: 'FM-CFBE-006', name: 'Adaptive desktop/tablet/foldable layout', priority: 'P1', layer: 'UX', benchmark: 'Android/Figma' },
  { id: 'FM-CFBE-007', name: 'Streaming response transport', priority: 'P1', layer: 'Chat', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-008', name: 'Conversation history + sync', priority: 'P1', layer: 'Chat', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-009', name: 'Multi-turn thread model', priority: 'P1', layer: 'Chat', benchmark: 'ChatGPT/Claude' },
  { id: 'FM-CFBE-010', name: 'Rich result renderer', priority: 'P1', layer: 'UX', benchmark: 'ChatGPT/Notion' },
  { id: 'FM-CFBE-011', name: 'Action progress timeline', priority: 'P1', layer: 'Agent UX', benchmark: 'ChatGPT Work/Cursor' },
  { id: 'FM-CFBE-012', name: 'Stop/cancel/interrupt controls', priority: 'P1', layer: 'Agent UX', benchmark: 'Claude/Cursor' },
  { id: 'FM-CFBE-013', name: 'Tool/connector action cards + permissions', priority: 'P1', layer: 'Actions', benchmark: 'ChatGPT/Notion' },
  { id: 'FM-CFBE-014', name: 'Attachment/image/camera ingestion', priority: 'P1', layer: 'Multimodal', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-015', name: 'Voice input/live conversation', priority: 'P1', layer: 'Multimodal', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-016', name: 'Screen-share context', priority: 'P2', layer: 'Multimodal', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-017', name: 'Quick actions + prompt starters', priority: 'P2', layer: 'UX', benchmark: 'ChatGPT/Perplexity' },
  { id: 'FM-CFBE-018', name: 'Command palette', priority: 'P2', layer: 'UX', benchmark: 'Cursor/Notion' },
  { id: 'FM-CFBE-019', name: 'Auto-routing + dynamic reasoning effort', priority: 'P1', layer: 'Routing', benchmark: 'OpenAI/Notion' },
  { id: 'FM-CFBE-020', name: 'Long-running Work/Build jobs', priority: 'P1', layer: 'Agents', benchmark: 'ChatGPT Work/Cursor' },
  { id: 'FM-CFBE-021', name: 'Parallel agent sweeps', priority: 'P1', layer: 'Agents', benchmark: 'Cursor/Replit' },
  { id: 'FM-CFBE-022', name: 'Multi-model challenger/best-of', priority: 'P1', layer: 'Agents', benchmark: 'Cursor/Notion' },
  { id: 'FM-CFBE-023', name: 'Durable workflow checkpoints', priority: 'P1', layer: 'Runtime', benchmark: 'Temporal/Cloudflare' },
  { id: 'FM-CFBE-024', name: 'Self-healing retries + semantic readback', priority: 'P1', layer: 'Runtime', benchmark: 'Cloudflare/Cursor' },
  { id: 'FM-CFBE-025', name: 'Event-triggered tasks', priority: 'P1', layer: 'Automation', benchmark: 'Notion/Cursor' },
  { id: 'FM-CFBE-026', name: 'Scheduled tasks', priority: 'P1', layer: 'Automation', benchmark: 'OpenAI/Notion' },
  { id: 'FM-CFBE-027', name: 'Push/web/email notifications', priority: 'P2', layer: 'Automation', benchmark: 'OpenAI/Cursor' },
  { id: 'FM-CFBE-028', name: 'Human-in-loop approvals', priority: 'P1', layer: 'Safety', benchmark: 'LangGraph/Cloudflare' },
  { id: 'FM-CFBE-029', name: 'Takeover/remote-control handoff', priority: 'P2', layer: 'Agent UX', benchmark: 'OpenAI/Perplexity' },
  { id: 'FM-CFBE-030', name: 'Workspace synchronized context', priority: 'P1', layer: 'Context', benchmark: 'Notion/OpenAI' },
  { id: 'FM-CFBE-031', name: 'Plugin/connector directory + discovery', priority: 'P1', layer: 'Integrations', benchmark: 'OpenAI/Notion' },
  { id: 'FM-CFBE-032', name: 'Google Workspace deep integration', priority: 'P1', layer: 'Integrations', benchmark: 'Google/Notion' },
  { id: 'FM-CFBE-033', name: 'GitHub review/action integration', priority: 'P1', layer: 'Integrations', benchmark: 'Cursor/GitHub' },
  { id: 'FM-CFBE-034', name: 'Browser/computer action tools', priority: 'P1', layer: 'Actions', benchmark: 'OpenAI/Perplexity' },
  { id: 'FM-CFBE-035', name: 'App sync/pre-index pipelines', priority: 'P1', layer: 'Context', benchmark: 'OpenAI/Notion' },
  { id: 'FM-CFBE-036', name: 'Stable-prefix cache planning', priority: 'P1', layer: 'Performance', benchmark: 'Frontier inference stacks' },
  { id: 'FM-CFBE-037', name: 'Tiered memory/personal context', priority: 'P1', layer: 'Context', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-038', name: 'Semantic search across Drive/project', priority: 'P1', layer: 'Research', benchmark: 'Notion/OpenAI' },
  { id: 'FM-CFBE-039', name: 'Research citations/source cards', priority: 'P1', layer: 'Research', benchmark: 'Perplexity/Notion' },
  { id: 'FM-CFBE-040', name: 'Provenance/trace explorer', priority: 'P1', layer: 'Trust', benchmark: 'FUSE/Notion' },
  { id: 'FM-CFBE-041', name: 'Privacy/incognito mode', priority: 'P1', layer: 'Privacy', benchmark: 'Perplexity/Chrome' },
  { id: 'FM-CFBE-042', name: 'Per-connector data boundary controls', priority: 'P1', layer: 'Privacy', benchmark: 'Notion/OpenAI' },
  { id: 'FM-CFBE-043', name: 'Local/on-device processing route', priority: 'P2', layer: 'Privacy', benchmark: 'Apple/Android' },
  { id: 'FM-CFBE-044', name: 'Per-tool permission settings', priority: 'P1', layer: 'Safety', benchmark: 'Notion/OpenAI' },
  { id: 'FM-CFBE-045', name: 'Authority/effect preview before action', priority: 'P0', layer: 'Safety', benchmark: 'FUSE/LangGraph' },
  { id: 'FM-CFBE-046', name: 'Audit log + receipts', priority: 'P0', layer: 'Trust', benchmark: 'FUSE/Notion' },
  { id: 'FM-CFBE-047', name: 'Secure append-only device enrollment', priority: 'P0', layer: 'Identity', benchmark: 'FUSE/Google' },
  { id: 'FM-CFBE-048', name: 'Passkeys/WebAuthn optional login', priority: 'P1', layer: 'Identity', benchmark: 'Apple/Google' },
  { id: 'FM-CFBE-049', name: 'Cross-device session continuity', priority: 'P1', layer: 'Identity', benchmark: 'ChatGPT/Gemini' },
  { id: 'FM-CFBE-050', name: 'Account/device management console', priority: 'P2', layer: 'Identity', benchmark: 'Google/Apple' },
  { id: 'FM-CFBE-051', name: 'Latency-budget routing', priority: 'P1', layer: 'Performance', benchmark: 'Frontier agent systems' },
  { id: 'FM-CFBE-052', name: 'Optimistic UI + skeleton states', priority: 'P2', layer: 'Performance', benchmark: 'Figma/Vercel' },
  { id: 'FM-CFBE-053', name: 'Edge CDN/static delivery', priority: 'P1', layer: 'Release', benchmark: 'Vercel/Cloudflare' },
  { id: 'FM-CFBE-054', name: 'Token/response streaming UI', priority: 'P1', layer: 'Performance', benchmark: 'ChatGPT/Claude' },
  { id: 'FM-CFBE-055', name: 'Context/data prefetching', priority: 'P2', layer: 'Performance', benchmark: 'Notion/Perplexity' },
  { id: 'FM-CFBE-056', name: 'Positive + negative caching', priority: 'P2', layer: 'Performance', benchmark: 'Cloudflare' },
  { id: 'FM-CFBE-057', name: 'Offline drafts/action queue', priority: 'P2', layer: 'Resilience', benchmark: 'PWA leaders' },
  { id: 'FM-CFBE-058', name: 'Background sync', priority: 'P2', layer: 'Resilience', benchmark: 'PWA/Android' },
  { id: 'FM-CFBE-059', name: 'Low-bandwidth mode', priority: 'P2', layer: 'Resilience', benchmark: 'Android/Google' },
  { id: 'FM-CFBE-060', name: 'Service-worker upgrade/migration safety', priority: 'P2', layer: 'Resilience', benchmark: 'PWA leaders' },
  { id: 'FM-CFBE-061', name: 'Crash/error telemetry', priority: 'P1', layer: 'Observability', benchmark: 'Sentry' },
  { id: 'FM-CFBE-062', name: 'SLO dashboard', priority: 'P1', layer: 'Observability', benchmark: 'Datadog/Sentry' },
  { id: 'FM-CFBE-063', name: 'Recovery CTAs + error taxonomy', priority: 'P1', layer: 'Observability', benchmark: 'Sentry/Google' },
  { id: 'FM-CFBE-064', name: 'Automatic rollback', priority: 'P1', layer: 'Release', benchmark: 'Vercel/Cloud Run' },
  { id: 'FM-CFBE-065', name: 'Canary deployments', priority: 'P1', layer: 'Release', benchmark: 'Cloud Run/Vercel' },
  { id: 'FM-CFBE-066', name: 'Preview deployments', priority: 'P1', layer: 'Release', benchmark: 'Vercel/Replit' },
  { id: 'FM-CFBE-067', name: 'Deployment protection/IAP', priority: 'P0', layer: 'Security', benchmark: 'Cloud Run/Vercel' },
  { id: 'FM-CFBE-068', name: 'Atomic full-stack deploy/rollback', priority: 'P1', layer: 'Release', benchmark: 'Vercel/Cloudflare' },
  { id: 'FM-CFBE-069', name: 'SBOM + AI-BOM + provenance', priority: 'P1', layer: 'Supply Chain', benchmark: 'SLSA/FUSE' },
  { id: 'FM-CFBE-070', name: 'Signed build artifacts', priority: 'P1', layer: 'Supply Chain', benchmark: 'Sigstore/SLSA' },
  { id: 'FM-CFBE-071', name: 'Release update/rollback pipeline', priority: 'P1', layer: 'Release', benchmark: 'Expo EAS/Vercel' },
  { id: 'FM-CFBE-072', name: 'Browser end-to-end tests', priority: 'P0', layer: 'Assurance', benchmark: 'Playwright/Replit' },
  { id: 'FM-CFBE-073', name: 'Visual regression tests', priority: 'P1', layer: 'Assurance', benchmark: 'Figma/Playwright' },
  { id: 'FM-CFBE-074', name: 'Accessibility automated + manual gates', priority: 'P1', layer: 'Assurance', benchmark: 'W3C/market leaders' },
  { id: 'FM-CFBE-075', name: 'Cross-browser compatibility matrix', priority: 'P1', layer: 'Assurance', benchmark: 'BrowserStack/Playwright' },
  { id: 'FM-CFBE-076', name: 'Adaptive-layout device matrix', priority: 'P1', layer: 'Assurance', benchmark: 'Android/Expo' },
  { id: 'FM-CFBE-077', name: 'Native/web parity tests', priority: 'P0', layer: 'Assurance', benchmark: 'Expo' },
  { id: 'FM-CFBE-078', name: 'Provider conformance tests', priority: 'P0', layer: 'Assurance', benchmark: 'FUSE/OpenAI' },
  { id: 'FM-CFBE-079', name: 'Deterministic replay + 10-clean-runs', priority: 'P0', layer: 'Assurance', benchmark: 'FUSE 10X' },
  { id: 'FM-CFBE-080', name: 'Chaos/recovery exercises', priority: 'P1', layer: 'Assurance', benchmark: 'Cloudflare/Netflix patterns' },
  { id: 'FM-CFBE-081', name: 'Live evaluation loop', priority: 'P1', layer: 'Evaluation', benchmark: 'OpenAI/Anthropic patterns' },
  { id: 'FM-CFBE-082', name: 'Synthetic + real-user value telemetry', priority: 'P1', layer: 'Evaluation', benchmark: 'Replit/Figma' },
  { id: 'FM-CFBE-083', name: 'Owner-hour productivity metric', priority: 'P1', layer: 'Value', benchmark: 'FUSE/Notion' },
  { id: 'FM-CFBE-084', name: 'Pareto route-selection UI', priority: 'P2', layer: 'Value', benchmark: 'FUSE' },
  { id: 'FM-CFBE-085', name: 'Prompt/algorithm A-B + shadow testing', priority: 'P1', layer: 'Evaluation', benchmark: 'Frontier labs' },
  { id: 'FM-CFBE-086', name: 'Experiment governance + kill criteria', priority: 'P1', layer: 'Evaluation', benchmark: 'FUSE' },
  { id: 'FM-CFBE-087', name: 'Feedback/rating/ranking loop', priority: 'P2', layer: 'Learning', benchmark: 'ChatGPT/Perplexity' },
  { id: 'FM-CFBE-088', name: 'Goal-based onboarding + templates', priority: 'P2', layer: 'UX', benchmark: 'Notion/Replit' },
  { id: 'FM-CFBE-089', name: 'Creativity canvas + variant comparator', priority: 'P1', layer: 'Creative', benchmark: 'Figma/Replit' },
  { id: 'FM-CFBE-090', name: 'Artifact/project workspace gallery', priority: 'P1', layer: 'Workspace', benchmark: 'ChatGPT Work/Notion' },
  { id: 'FM-CFBE-091', name: 'Editable outputs + live code preview', priority: 'P1', layer: 'Workspace', benchmark: 'Figma/Replit/v0' },
  { id: 'FM-CFBE-092', name: 'Artifact versioning + branching', priority: 'P1', layer: 'Workspace', benchmark: 'GitHub/Notion' },
  { id: 'FM-CFBE-093', name: 'Controlled share/export links', priority: 'P2', layer: 'Workspace', benchmark: 'Notion/Vercel' },
  { id: 'FM-CFBE-094', name: 'Themes/design tokens + sovereign design freedom', priority: 'P1', layer: 'Design', benchmark: 'Figma' },
  { id: 'FM-CFBE-095', name: 'Keyboard shortcuts/gestures/command center', priority: 'P2', layer: 'UX', benchmark: 'Cursor/Notion' },
  { id: 'FM-CFBE-096', name: 'Accessibility personalization', priority: 'P2', layer: 'Accessibility', benchmark: 'Apple/Android' },
  { id: 'FM-CFBE-097', name: 'Localization/i18n', priority: 'P2', layer: 'Global', benchmark: 'Google/Apple' },
  { id: 'FM-CFBE-098', name: 'Cost/latency budgets + usage guardrails', priority: 'P1', layer: 'Economics', benchmark: 'Notion/OpenAI' },
  { id: 'FM-CFBE-099', name: 'Help/trust/diagnostics/support center', priority: 'P2', layer: 'Support', benchmark: 'Apple/Google' },
  { id: 'FM-CFBE-100', name: 'Sovereign proof-vs-promise capability passport', priority: 'P0', layer: 'Trust', benchmark: 'FUSE' },
];

export const CFBE_MOBILE_CAPABILITIES: CfbeCapability[] = DEFINITIONS.map((item) => ({
  ...item,
  state: 'WORK_PACKAGE_CREATED',
}));

export const CFBE_MOBILE_CAPABILITY_COUNT = CFBE_MOBILE_CAPABILITIES.length;

export function capabilityPassportSummary() {
  return CFBE_MOBILE_CAPABILITIES.reduce(
    (summary, item) => {
      summary.total += 1;
      summary[item.priority] += 1;
      return summary;
    },
    { total: 0, P0: 0, P1: 0, P2: 0 },
  );
}
