import {readFile} from 'node:fs/promises';

const registry = JSON.parse(await readFile(new URL('../docs/feature-registry.json', import.meta.url), 'utf8'));
const ids = new Set();
const states = new Set(['IMPLEMENTED', 'DESIGNED', 'RESEARCH']);
for (const feature of registry.features) {
  if (!/^KDV-F\d{3}$/.test(feature.id)) throw new Error(`Invalid feature id: ${feature.id}`);
  if (ids.has(feature.id)) throw new Error(`Duplicate feature id: ${feature.id}`);
  if (!states.has(feature.state)) throw new Error(`Invalid feature state for ${feature.id}`);
  if (!feature.name || !feature.acceptance) throw new Error(`Incomplete feature: ${feature.id}`);
  ids.add(feature.id);
}
if (ids.size < 100) throw new Error(`Feature registry has only ${ids.size} entries`);
console.log(JSON.stringify({status: 'FEATURE_REGISTRY_VALID', count: ids.size, implemented: registry.features.filter((item) => item.state === 'IMPLEMENTED').length}));
