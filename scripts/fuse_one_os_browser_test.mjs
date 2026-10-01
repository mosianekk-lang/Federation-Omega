/** Browser court against an isolated real SOL runtime; no provider executor is installed.
 * Requires Playwright and the Python requirements of services/sol62_client_runtime.
 * Optional: FUSE_BROWSER_TEST_PYTHON, PLAYWRIGHT_MODULE_PATH,
 * CHROMIUM_EXECUTABLE_PATH, CHROMIUM_ARGS_JSON, FUSE_BROWSER_TEST_OUTPUT.
 * The fixture's random session is consumed in memory and never logged or saved.
 */
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = process.env.FUSE_BROWSER_TEST_OUTPUT ? path.resolve(process.env.FUSE_BROWSER_TEST_OUTPUT) : fs.mkdtempSync(path.join(os.tmpdir(), 'fuse-one-browser-'));
assert.ok(output !== root && !output.startsWith(root + path.sep), 'Browser evidence must be written outside the source repository');
fs.mkdirSync(output, {recursive:true});
const port = await new Promise((resolve,reject)=>{const probe=net.createServer();probe.on('error',reject);probe.listen(0,'127.0.0.1',()=>{const assigned=probe.address().port;probe.close(()=>resolve(assigned));});});
const origin = 'http://127.0.0.1:' + port;
const checks = [];
let server, browser;
const pass = (name, scope='REAL_LOCAL_BACKEND') => checks.push({name, scope, passed:true});
(async()=>{
  server = spawn(process.env.FUSE_BROWSER_TEST_PYTHON || 'python3', [path.join(root,'scripts/fuse_one_os_ui_fixture.py')], {stdio:['ignore','pipe','pipe'], env:{...process.env,FUSE_UI_TEST_PORT:String(port)}});
  let serverError=''; server.stderr.on('data', chunk=>{serverError+=chunk.toString();});
  const session=await new Promise((resolve,reject)=>{
    let buffer=''; server.stdout.on('data',chunk=>{buffer+=chunk.toString(); const end=buffer.indexOf('\n'); if(end>=0){try{resolve(JSON.parse(buffer.slice(0,end)).session);}catch(e){reject(e);}}});
    server.once('error',reject);
    server.once('exit',code=>reject(new Error('Test runtime exited '+code+': '+serverError.slice(-500))));
  });
  let ready=false;
  for(let i=0;i<100;i++){try{const response=await fetch(origin+'/health'); if(response.ok){ready=true;break;}}catch(_){} await new Promise(resolve=>setTimeout(resolve,100));}
  assert.ok(ready, 'Isolated local runtime did not become ready');
  const args=process.env.CHROMIUM_ARGS_JSON ? JSON.parse(process.env.CHROMIUM_ARGS_JSON) : ['--no-sandbox'];
  assert.ok(Array.isArray(args) && args.every(arg=>typeof arg==='string'), 'CHROMIUM_ARGS_JSON must contain a string array');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH || undefined,args});
  const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  let chatPosts=0,missionPosts=0;
  page.on('request',req=>{if(req.method()==='POST'&&req.url().endsWith('/v1/chat')) chatPosts++; if(req.method()==='POST'&&req.url().endsWith('/v1/missions')) missionPosts++;});
  await page.goto(origin+'/',{waitUntil:'networkidle'});
  await page.locator('#health').filter({hasText:'Runtime needs attention'}).waitFor();
  assert.equal(await page.locator('#integrityReady').textContent(),'Chain verified');
  assert.equal(await page.locator('#executionReady').textContent(),'Binding needed');
  pass('Health distinguishes responding runtime, integrity and missing executor');
  await page.click('#openSessionTop'); await page.fill('#token',session); await page.click('#saveToken');
  await page.waitForFunction(()=>document.getElementById('serviceCount').textContent==='35');
  assert.equal(await page.locator('#sourceCount').textContent(),'16'); assert.equal(await page.locator('#gapCount').textContent(),'19');
  assert.equal(await page.locator('#sidebarSession').textContent(),'Session verified');
  pass('Authenticated UI reads real 35-service catalog with 16 definitions and 19 source gaps');
  await page.click('#openSessionTop');
  await page.screenshot({path:output+'/FUSE-ONE-Overview.png',fullPage:true});
  await page.click('[data-view="catalog"]'); await page.fill('#serviceSearch','workflow.enterprise');
  assert.equal(await page.locator('#serviceList .service-card').count(),1);
  assert.match(await page.locator('#serviceList').textContent(),/Alias mapped/);
  assert.match(await page.locator('#serviceList').textContent(),/Not Assessed/);
  pass('Catalog search renders legacy alias and unassessed runtime truthfully');
  await page.fill('#serviceSearch',''); await page.selectOption('#serviceFilter','missing');
  assert.equal(await page.locator('#serviceList .service-card').count(),19);
  pass('Catalog source gap filter selects real unresolved definitions');
  await page.selectOption('#serviceFilter','all'); await page.screenshot({path:output+'/FUSE-ONE-Catalog.png',fullPage:true});
  await page.click('[data-view="connections"]'); await page.fill('#connectionSearch','canva');
  assert.equal(await page.locator('#connectionsList .service-card').count(),1);
  assert.match(await page.locator('#connectionsList').textContent(),/Client route/);
  pass('Provider search shows Canva as a reported client route, not a verified integration');
  await page.click('[data-view="chat"]'); await page.fill('#chatIntent','Test retained draft without a provider executor');
  await page.evaluate(()=>{document.getElementById('chatForm').requestSubmit();document.getElementById('chatForm').requestSubmit();});
  await page.waitForFunction(()=>document.getElementById('chatNotice').textContent.includes('retained'));
  assert.equal(chatPosts,1); assert.equal(await page.locator('#chatIntent').inputValue(),'Test retained draft without a provider executor');
  assert.equal(await page.locator('#sendChat').isEnabled(),true);
  pass('Real 503 holds preserve chat draft and synchronous duplicate submit sends one request');
  await page.click('[data-view="missions"]'); await page.fill('#objective','Verify isolated UI mission create and readback');
  await page.evaluate(()=>{document.getElementById('missionForm').requestSubmit();document.getElementById('missionForm').requestSubmit();});
  await page.waitForFunction(()=>!document.getElementById('missionCard').hidden);
  const missionId=await page.locator('#missionId').textContent(); assert.match(missionId,/^sol62-/);assert.equal(missionPosts,1);
  pass('Real isolated mission registration and duplicate-submit prevention');
  await page.click('#loadMission'); await page.waitForFunction(()=>document.getElementById('missionNotice').textContent==='Mission readback received.');
  assert.equal(missionPosts,1); assert.equal(await page.locator('#missionId').textContent(),missionId);
  pass('Exact existing mission readback resumes without new mission');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('#openSessionTop').isVisible(),true);
  await page.click('[data-view="overview"]');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:output+'/FUSE-ONE-Mobile.png',fullPage:true});
  pass('390px mobile layout has no horizontal overflow and session access remains visible');
  await page.click('#openSessionTop'); await page.click('#clearToken');
  assert.equal(await page.locator('#serviceCount').textContent(),'—');
  assert.equal(await page.locator('#missionId').textContent(),''); assert.equal(await page.locator('#missionState').textContent(),'');
  assert.equal(await page.locator('#chatLog .msg').count(),0); assert.equal(await page.evaluate(()=>sessionStorage.getItem('fuseSession')),null);
  pass('Clearing session removes stored token, catalog counts, conversations and mission identity');
  assert.deepEqual(errors,[]); pass('No uncaught browser JavaScript errors');
  fs.writeFileSync(output+'/ui_browser_result.json',JSON.stringify({schema:'FUSE_ONE_UI_BROWSER_CHECKS_V1',checks,test_count:checks.length,provider_called:false,deployed:false,production_certified:false,screenshots:['FUSE-ONE-Overview.png','FUSE-ONE-Catalog.png','FUSE-ONE-Mobile.png']},null,2)+'\n');
  console.log(JSON.stringify({passed:checks.length,screenshots:3,scope:'REAL_LOCAL_BACKEND_NO_PROVIDER',output}));
})().catch(error=>{console.error(error.stack);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill('SIGTERM');});
