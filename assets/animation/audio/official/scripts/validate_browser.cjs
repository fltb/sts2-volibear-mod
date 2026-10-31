#!/usr/bin/env node
'use strict';
// Actual offline-browser checks. Whole-library codec decoding is a separate gate.
// Requires Playwright and an installed Chromium; VOLIBEAR_CHROMIUM may select it.
// Without --report, all generated evidence is written to a new temporary folder.
const fs = require('fs');
const path = require('path');
const os = require('os');
const assert = require('assert/strict');
const crypto = require('crypto');
const {pathToFileURL} = require('url');
const {chromium} = require('playwright');

function argumentsOf(argv) {
  const options = {root:path.resolve(__dirname, '..'), report:null, screenshots:null, chromium:process.env.VOLIBEAR_CHROMIUM || undefined};
  for (let i=0; i<argv.length; i++) {
    const flag = argv[i];
    if (flag === '--help') {
      console.log('node scripts/validate_browser.cjs [--root OFFICIAL_DIRECTORY] [--report NEW_REPORT_JSON] [--screenshots DIRECTORY] [--chromium EXECUTABLE]');
      process.exit(0);
    }
    if (!['--root','--report','--screenshots','--chromium'].includes(flag) || !argv[i+1]) throw new Error('Unknown/incomplete argument: ' + flag);
    options[flag.slice(2)] = path.resolve(argv[++i]);
  }
  return options;
}
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const label = (value, fallback) => String(value ?? '').trim() || fallback;
const categoryOf = entry => label(entry.category, '未分类');
const languageOf = entry => label(entry.language, '未标注');
const searchText = entry => [entry.id,entry.filename,entry.category,entry.language,entry.skin].map(v=>String(v??'')).join(' ').toLocaleLowerCase();
function localPath(root, relative) {
  assert.equal(typeof relative, 'string');
  assert(relative && !relative.includes('\\') && !relative.includes('\0') && !relative.includes(':'), 'Unsafe local media path');
  assert(!path.isAbsolute(relative) && relative.split('/').every(p=>p && p!=='.' && p!=='..'), 'Local media path must stay inside official/');
  const file = path.resolve(root, ...relative.split('/'));
  assert(file.startsWith(root + path.sep), 'Media path escaped root');
  return file;
}
function writeJsonAtomic(file, value) {
  fs.mkdirSync(path.dirname(file), {recursive:true});
  const temporary = file + '.' + process.pid + '.tmp';
  fs.writeFileSync(temporary, JSON.stringify(value,null,2) + '\n');
  fs.renameSync(temporary,file);
}

(async () => {
  const options = argumentsOf(process.argv.slice(2));
  const root = path.resolve(options.root);
  for (const file of ['index.html','catalog.js']) assert(fs.statSync(path.join(root,file)).isFile(), 'Missing ' + file);
  const evidenceRoot = fs.mkdtempSync(path.join(os.tmpdir(),'volibear-official-audio-browser-'));
  const reportPath = options.report || path.join(evidenceRoot,'browser_validation.json');
  const screenshotDirectory = options.screenshots || evidenceRoot;
  fs.mkdirSync(screenshotDirectory, {recursive:true});
  const inputPaths = [path.join(root,'index.html'), path.join(root,'catalog.js'), __filename];
  if (fs.existsSync(path.join(root,'catalog.json'))) inputPaths.push(path.join(root,'catalog.json'));
  const fontManifestPath = path.join(root,'fonts/manifest.json');
  const fontManifest = JSON.parse(fs.readFileSync(fontManifestPath,'utf8'));
  const fontPath = localPath(root,fontManifest.file);
  assert.equal(sha(fontPath),fontManifest.sha256,'Font subset SHA differs');
  assert.equal(sha(path.join(root,'index.html')),fontManifest.input_sha256['index.html'],'Font coverage binding is stale for HTML');
  assert.equal(sha(path.join(root,'catalog.json')),fontManifest.input_sha256['catalog.json'],'Font coverage binding is stale for catalog');
  assert.deepEqual(fontManifest.missing_codepoints,[],'Font coverage has missing glyphs');
  inputPaths.push(fontManifestPath,fontPath,path.join(root,'fonts/OFL.txt'),path.join(root,'fonts/characters.txt'),path.join(root,'fonts/build_subset.py'));
  const inputs = Object.fromEntries(inputPaths.map(p=>[path.relative(root,p).split(path.sep).join('/'),sha(p)]));
  const errors = [], failedRequests = [], mediaCancellations = [], externalRequests = [];
  const filterChecks = [], played = [], screenshots = [];
  let browser;
  const report = {schema_version:1,status:'running',scope:'Actual Chromium file:// catalog rendering, local file/SHA references, search/filter counts, representative media playback clocks, switching/stopping, original-file download and responsive layout. Complete codec decoding and human listening are separate checks.',input_sha256:inputs,errors,failed_requests:failedRequests,media_request_cancellations:mediaCancellations,external_requests:externalRequests,filter_checks:filterChecks,played,screenshots};
  try {
    browser = await chromium.launch({executablePath:options.chromium,headless:true,args:['--no-sandbox','--allow-file-access-from-files']});
    report.browser = await browser.version();
    report.playwright = require('playwright/package.json').version;
    const page = await browser.newPage({viewport:{width:1280,height:1000},acceptDownloads:true});
    page.on('pageerror', error => errors.push(String(error)));
    page.on('requestfailed', request => {
      const failure = {url:request.url(),resource_type:request.resourceType(),error:request.failure()};
      if (request.resourceType()==='media' && request.failure()?.errorText==='net::ERR_ABORTED') mediaCancellations.push(failure);
      else failedRequests.push(failure);
    });
    page.on('request', request => { if (/^https?:/i.test(request.url())) externalRequests.push(request.url()); });
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    await page.waitForFunction(()=>['ready','error'].includes(document.documentElement.dataset.catalogState), null, {timeout:15000});
    assert.equal(await page.locator('html').getAttribute('data-catalog-state'),'ready',await page.locator('#catalog-error').textContent());
    await page.evaluate(()=>document.fonts.ready);
    const session = await page.context().newCDPSession(page);
    await session.send('DOM.enable'); await session.send('CSS.enable');
    const documentNode = await session.send('DOM.getDocument');
    const titleNode = await session.send('DOM.querySelector',{nodeId:documentNode.root.nodeId,selector:'h1'});
    const platformFonts = await session.send('CSS.getPlatformFontsForNode',{nodeId:titleNode.nodeId});
    report.font_rendering = {font_file:fontManifest.file,font_sha256:fontManifest.sha256,requested_unicode_count:fontManifest.requested_unicode_count,missing_codepoints:fontManifest.missing_codepoints,title_platform_fonts:platformFonts.fonts};
    assert(platformFonts.fonts.some(font=>font.isCustomFont && font.glyphCount>0 && font.familyName.replace(/ \(Fontations\)$/,'')===fontManifest.derived_family),'Embedded CJK subset did not render the title: '+JSON.stringify(platformFonts));
    const entries = await page.evaluate(()=>window.OFFICIAL_AUDIO_CATALOG.entries);
    assert(Array.isArray(entries) && entries.length>0, 'Catalog must contain its downloaded entries');
    if (fs.existsSync(path.join(root,'catalog.json'))) assert.deepEqual(entries,JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8')).entries,'catalog.js and catalog.json entries differ');
    const ids = new Set(); let sourceBytes = 0;
    const uniqueSha = new Set();
    for (const entry of entries) {
      assert(!ids.has(String(entry.id)), 'Duplicate entry ID'); ids.add(String(entry.id));
      const file = localPath(root,entry.file); const stat = fs.statSync(file);
      assert(stat.isFile() && stat.size>0,'Missing/empty '+entry.file);
      assert.equal(stat.size,entry.bytes,'Byte length differs: '+entry.file);
      assert.equal(sha(file),entry.sha256,'Original SHA differs: '+entry.file);
      sourceBytes += stat.size; uniqueSha.add(entry.sha256);
    }
    report.catalog_count = entries.length;
    report.category_count = new Set(entries.map(categoryOf)).size;
    report.language_count = new Set(entries.map(languageOf)).size;
    report.local_file_integrity = {paths_checked:entries.length,total_bytes:sourceBytes,unique_sha256_count:uniqueSha.size,all_sha256_matched:true};
    assert.equal(await page.locator('audio').count(),1,'Exactly one media player is required');
    assert.equal(await page.locator('audio[autoplay]').count(),0);
    const initial = await page.locator('#player').evaluate(el=>({paused:el.paused,time:el.currentTime,src:el.getAttribute('src'),loop:el.loop}));
    assert(initial.paused && initial.time===0 && initial.src===null && !initial.loop,'Page must not preload/select or auto-play a track');
    report.no_autoplay_on_load = true;
    assert((await page.locator('.intro').textContent()).includes('当前未替换运行音频'));
    async function expectCount(expected, description) {
      assert.equal(await page.locator('.entry').count(),expected,description);
      assert.equal(await page.locator('#count').getAttribute('data-visible'),String(expected),description+' count');
      assert.equal(await page.locator('#empty').isVisible(),expected===0,description+' empty state');
      filterChecks.push({case:description,expected_count:expected,passed:true});
    }
    await expectCount(entries.length,'initial_all');
    const catalogLinks = await page.locator('.entry .download-link').evaluateAll(links=>links.map(a=>({href:a.href,download:a.download})));
    for (let i=0;i<entries.length;i++) {
      assert.equal(catalogLinks[i].href,pathToFileURL(localPath(root,entries[i].file)).href,'Original download path');
      assert(catalogLinks[i].download,'Missing download filename');
    }
    report.all_original_download_links_checked = entries.length;
    for (const cat of [...new Set(entries.map(categoryOf))]) {
      await page.selectOption('#category',cat);
      await expectCount(entries.filter(e=>categoryOf(e)===cat).length,'category:'+cat);
    }
    await page.selectOption('#category','');
    for (const lang of [...new Set(entries.map(languageOf))]) {
      await page.selectOption('#language',lang);
      await expectCount(entries.filter(e=>languageOf(e)===lang).length,'language:'+lang);
    }
    const cross = entries[0];
    await page.selectOption('#category',categoryOf(cross));
    await page.selectOption('#language',languageOf(cross));
    await expectCount(entries.filter(e=>categoryOf(e)===categoryOf(cross)&&languageOf(e)===languageOf(cross)).length,'category_and_language');
    await page.locator('#reset').click();
    const query = String(entries[0].id).toLocaleLowerCase();
    await page.fill('#search','  '+query.toLocaleUpperCase()+'  ');
    await expectCount(entries.filter(e=>searchText(e).includes(query)).length,'trimmed_case_insensitive_id_search');
    const noMatch = 'zz_no_official_audio_match_6f2c9341';
    assert(entries.every(e=>!searchText(e).includes(noMatch)));
    await page.fill('#search',noMatch); await expectCount(0,'no_results');
    await page.locator('#reset').click(); await expectCount(entries.length,'reset_all');
    assert.equal(await page.locator('#category').inputValue(),'');
    assert.equal(await page.locator('#language').inputValue(),'');
    assert.equal(await page.locator('#search').inputValue(),'');
    const sorted = entries.slice().sort((a,b)=>Number(b.duration_seconds)-Number(a.duration_seconds));
    const sampleByFile = new Map();
    for (const lang of new Set(entries.map(languageOf))) {
      const entry = sorted.find(e=>languageOf(e)===lang);
      if (entry) sampleByFile.set(entry.file,entry);
    }
    for (const entry of sorted) { if (sampleByFile.size>=Math.max(2,report.language_count)) break; sampleByFile.set(entry.file,entry); }
    const samples = [...sampleByFile.values()];
    const media = page.locator('#player');
    let previousId = null;
    async function rowFor(entry) {
      const escaped = await page.evaluate(id=>CSS.escape(String(id)),entry.id);
      return page.locator('.entry[data-entry-id="'+escaped+'"]');
    }
    for (const entry of samples) {
      await page.fill('#search',String(entry.id));
      const row = await rowFor(entry); assert.equal(await row.count(),1);
      const beforeSwitch = previousId ? await media.evaluate(el=>({id:el.dataset.entryId,paused:el.paused,current_src:el.currentSrc,current_time:el.currentTime})) : null;
      await row.locator('.play-button').click();
      await page.waitForFunction(id=>{const p=document.getElementById('player');return p.dataset.entryId===String(id)&&p.readyState>=2&&p.currentTime>0&&!p.paused&&!p.error;},entry.id,{timeout:12000});
      const state = await media.evaluate(el=>({id:el.dataset.entryId,current_src:el.currentSrc,paused:el.paused,current_time:el.currentTime,duration:el.duration,ready_state:el.readyState,error:el.error?.code||null,loop:el.loop}));
      assert.equal(state.id,String(entry.id));
      assert.equal(state.current_src,pathToFileURL(localPath(root,entry.file)).href);
      assert(state.current_time>0 && !state.paused && !state.error && !state.loop);
      await page.waitForTimeout(120);
      const later = await media.evaluate(el=>({current_time:el.currentTime,paused:el.paused,error:el.error?.code||null}));
      assert(!later.paused && !later.error && later.current_time>state.current_time+.01,'Sample playback clock did not keep advancing: '+entry.id);
      assert(Math.abs(state.duration-Number(entry.duration_seconds))<.15,'Browser duration differs: '+entry.id);
      assert.equal(await page.locator('audio').count(),1);
      played.push({...state,source_file:entry.file,source_sha256:entry.sha256,switch_from:previousId,before_switch:beforeSwitch,clock_after_120ms:later});
      previousId = String(entry.id);
    }
    report.single_player_switch_checked = played.some(item=>item.before_switch && !item.before_switch.paused && item.before_switch.current_src!==item.current_src);
    if (samples.length>1) assert(report.single_player_switch_checked, 'No live audio-to-audio switch was exercised');
    await page.locator('#stop').click();
    const stopped = await media.evaluate(el=>({paused:el.paused,current_time:el.currentTime}));
    assert(stopped.paused && stopped.current_time===0);
    await page.waitForTimeout(160);
    assert.equal(await media.evaluate(el=>el.currentTime),0,'Stopped player clock advanced');
    report.stop_checked = true;
    const selected = samples[samples.length-1];
    await (await rowFor(selected)).locator('.play-button').click();
    await page.waitForFunction(()=>{const p=document.getElementById('player');return !p.paused&&p.currentTime>0;},null,{timeout:10000});
    await (await rowFor(selected)).locator('.play-button').click();
    const pausedTime = await media.evaluate(el=>el.currentTime);
    assert(await media.evaluate(el=>el.paused));
    await page.waitForTimeout(160);
    assert(Math.abs(await media.evaluate(el=>el.currentTime)-pausedTime)<.03,'Paused clock advanced');
    report.row_pause_toggle_checked = true;
    await page.locator('#stop').click();
    // Hold only the promise returned to the UI, while real native media plays.
    // This deterministically exercises a user pause before play() settles.
    for (const pauseRoute of ['entry_button','native_pause']) {
      await page.evaluate(()=>{
        const p=document.getElementById('player');
        const original=p.play;
        window.__officialPendingPlayProbe={original,reject:null};
        p.play=function(){
          const native=original.call(this); native.catch(()=>{});
          return new Promise((resolve,reject)=>{window.__officialPendingPlayProbe.reject=reject;});
        };
      });
      await (await rowFor(selected)).locator('.play-button').click();
      await page.waitForFunction(()=>{const p=document.getElementById('player');return !p.paused&&p.currentTime>0;},null,{timeout:10000});
      if (pauseRoute==='entry_button') await (await rowFor(selected)).locator('.play-button').click();
      else await media.evaluate(el=>el.pause());
      await page.evaluate(()=>{
        const probe=window.__officialPendingPlayProbe;
        document.getElementById('player').play=probe.original;
        probe.reject(new DOMException('Paused before play promise settled','AbortError'));
        delete window.__officialPendingPlayProbe;
      });
      await page.waitForTimeout(60);
      assert(await media.evaluate(el=>el.paused));
      assert((await page.locator('#playback-status').textContent()).includes('已暂停'),'Pending pause was mislabeled as file failure: '+pauseRoute);
      await page.locator('#stop').click();
    }
    report.pending_play_pause_regression = {passed:true,routes:['entry_button','native_pause'],method:'Temporarily delayed play-promise wrapper over actual native playback; no fabricated file decoding.'};
    const downloadRow = await rowFor(selected);
    const [download] = await Promise.all([page.waitForEvent('download',{timeout:10000}),downloadRow.locator('.download-link').click()]);
    assert.equal(await download.failure(),null,'Browser download failed');
    assert.equal(download.suggestedFilename(),selected.filename || String(selected.file).split('/').pop(),'Original download filename differs');
    const downloadedPath = await download.path();
    assert(downloadedPath && fs.statSync(downloadedPath).size===selected.bytes);
    assert.equal(sha(downloadedPath),selected.sha256);
    report.original_download_probe = {id:selected.id,suggested_filename:download.suggestedFilename(),bytes:fs.statSync(downloadedPath).size,sha256:sha(downloadedPath),byte_identical:true};
    await page.locator('#reset').click();
    await page.evaluate(()=>window.scrollTo(0,0));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Desktop horizontal overflow');
    const desktop = path.join(screenshotDirectory,'official_audio_desktop.png');
    await page.screenshot({path:desktop,fullPage:false}); screenshots.push({file:desktop,sha256:sha(desktop),viewport:[1280,1000]});
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>window.scrollTo(0,0));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile horizontal overflow');
    await page.locator('.entry summary').first().click();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Expanded source/hash causes mobile overflow');
    await page.evaluate(()=>window.scrollTo(0,0));
    const mobile = path.join(screenshotDirectory,'official_audio_mobile.png');
    await page.screenshot({path:mobile,fullPage:false}); screenshots.push({file:mobile,sha256:sha(mobile),viewport:[390,844]});
    report.mobile_no_overflow = true;
    report.visual_review = 'Screenshots captured; this script does not assert human visual or listening approval.';
    assert.equal(errors.length,0,'Browser JavaScript errors');
    assert.equal(failedRequests.length,0,'Failed local requests');
    assert.equal(externalRequests.length,0,'Offline page requested external resources');
    for (const [relative,expected] of Object.entries(inputs)) assert.equal(sha(path.resolve(root,relative)),expected,'Input changed during browser validation: '+relative);
    report.status = 'pass';
  } catch (error) {
    report.status = 'fail'; report.failure = {message:error.message,stack:error.stack};
    throw error;
  } finally {
    if (browser) await browser.close();
    writeJsonAtomic(reportPath,report);
    console.log(JSON.stringify({status:report.status,catalog_entries:report.catalog_count,played_samples:played.length,report:reportPath,screenshots:screenshotDirectory}));
  }
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
