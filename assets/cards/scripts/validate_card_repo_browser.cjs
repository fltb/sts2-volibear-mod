/* Actual current standalone-repo browser execution. Historical results are not inherited. */
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict'),crypto=require('crypto');
const {pathToFileURL,fileURLToPath}=require('url');
const {chromium}=require('playwright');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const manifest=JSON.parse(fs.readFileSync(path.join(root,'cards/gallery_manifest.json'),'utf8'));
const source=JSON.parse(fs.readFileSync(path.join(root,'data/cards_source.json'),'utf8'));
const assets=JSON.parse(fs.readFileSync(path.join(root,'data/asset_manifest.json'),'utf8'));
const executablePath=process.env.VOLIBEAR_CHROMIUM||undefined;
const screenshotDir=fs.mkdtempSync(path.join(os.tmpdir(),'volibear-cards-browser-'));
const reportDir=path.join(root,'reports/revision_v7');
const url=p=>pathToFileURL(path.join(root,p)).href;
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
const snapshotFiles=['cards/index.html','cards/gallery_data.js','cards/gallery_manifest.json','cards/fonts/gallery_ui.woff','data/cards_source.json','data/cards_art_briefs.json','data/asset_manifest.json','config/export_profiles.json','scripts/card_repo.py','scripts/validate_card_repo_browser.cjs','START_HERE.html','vfx/index.html','vfx/manifest.json','vfx/card_vfx_bindings.json','vfx/fonts/vfx_ui.woff'];
const snapshots=Object.fromEntries(snapshotFiles.map(p=>[p,sha(p)]));
const errors=[],failed=[],external=[],checks=[],filters=[],detailRecords=[],popups=[];
let browser;
const report={schema_version:7,passed:false,checked_at:new Date().toISOString(),origin:'local file://',repo:'volibear_cards_repo',operator:'v7_final_card_delivery',delivery_revision:7,inherited_browser_result:false,playwright_version:require('playwright/package.json').version,browser_selection:executablePath?'explicit VOLIBEAR_CHROMIUM override':'Playwright-managed Chromium'};
function watch(page){page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()}));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});}
function localFile(href,base){const u=new URL(href,base);assert.equal(u.protocol,'file:');const p=fileURLToPath(u);assert(p.startsWith(root+path.sep),'Link escapes standalone repo: '+p);assert(fs.statSync(p).isFile(),'Missing local file: '+p);return p;}
(async()=>{
 browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1360,height:1000},acceptDownloads:true});context.on('page',watch);
 await context.route(/^https?:/,route=>route.abort());
 const page=await context.newPage();
 await page.goto(url('START_HERE.html'));await page.waitForLoadState('networkidle');
 const startLinks=await page.locator('a[href]').evaluateAll(a=>a.map(x=>({label:x.textContent.trim(),href:x.getAttribute('href')})));
 for(const l of startLinks){if(!l.href.startsWith('#')&&!/^(https?:|mailto:)/.test(l.href))localFile(l.href,page.url());}
 const galleryLink=page.locator('a[href="cards/index.html"]').first();assert(await galleryLink.count(),'Start page has no gallery link');
 await galleryLink.click();await page.waitForURL('**/cards/index.html');await page.waitForFunction(()=>document.querySelectorAll('.card').length===89,{},{timeout:15000});
 await page.evaluate(()=>document.fonts.ready);assert.equal(await page.locator('#totalStat').textContent(),'89');assert.equal(await page.locator('#approvedStat').textContent(),'89');assert.equal(await page.locator('#productionStat').textContent(),'89');
 const grid=await page.locator('#gallery img').evaluateAll(async imgs=>{for(const im of imgs){im.loading='eager';await im.decode();}return imgs.map(im=>({src:im.getAttribute('src'),width:im.naturalWidth,height:im.naturalHeight}));});
 assert.equal(grid.length,89);for(const im of grid)assert.deepEqual([im.width,im.height],[250,190]);
 assert.deepEqual(await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id)),source.cards.map(c=>c.id));
 await page.screenshot({path:path.join(screenshotDir,'desktop.png'),fullPage:false});
 checks.push('Standalone START_HERE links exist; gallery opens through its link; all 89 actual 250x190 images decode in source order.');
 await page.locator('.topnav a[href="../vfx/index.html"]').click();await page.waitForURL('**/vfx/index.html');await page.waitForFunction(()=>window.VFX_VIEWER?.getState().imageLoaded);
 assert.equal(await page.locator('.tile').count(),40);assert.equal(await page.locator('#cardSelect option').count(),89);await page.evaluate(async()=>{await window.VFX_VIEWER.selectEffect('feral_transfer');window.VFX_VIEWER.renderAt(28);});assert.equal(await page.evaluate(()=>window.VFX_VIEWER.getState().id),'feral_transfer');
 await page.locator('a[href="../START_HERE.html"]').click();await page.waitForURL('**/START_HERE.html');await page.locator('a[href="cards/index.html"]').first().click();await page.waitForURL('**/cards/index.html');await page.waitForFunction(()=>document.querySelectorAll('.card').length===89);
 checks.push('Actually followed the new VFX navigation, decoded its live atlas, verified 40 effects / 89 bindings, then returned through the standalone START_HERE entry to the card gallery.');
 await page.fill('#search','b02');assert.deepEqual(await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id)),['B02']);
 await page.fill('#search','熊灵侵染');assert.deepEqual(await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id)),['R28']);
 await page.click('#reset');
 for(const [sel,field] of [['#typeFilter','type'],['#rarityFilter','rarity'],['#levelFilter','abstraction']]){
  for(const value of [...new Set(manifest.cards.map(c=>c[field]))]){await page.selectOption(sel,value);const actual=await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id));const expected=manifest.cards.filter(c=>c[field]===value).map(c=>c.id);assert.deepEqual(actual,expected);filters.push({field,value,count:actual.length});}
  await page.selectOption(sel,'');
 }
 for(const [value,locked,count] of [['redrawn',false,61],['locked',true,28]]){
  await page.selectOption('#scopeFilter',value);const actual=await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id));assert.deepEqual(actual,manifest.cards.filter(c=>c.user_locked===locked).map(c=>c.id));assert.equal(actual.length,count);filters.push({field:'scope',value,count});
 }await page.selectOption('#scopeFilter','');
 for(const value of ['quality_desc','quality_asc']){
  await page.selectOption('#sortOrder',value);const actual=await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id));const expected=[...manifest.cards].sort((a,b)=>a.score==null?(b.score==null?a.order-b.order:1):b.score==null?-1:(value==='quality_desc'?b.score-a.score:a.score-b.score)||a.order-b.order).map(c=>c.id);assert.deepEqual(actual,expected);assert.deepEqual(actual.slice(-28),manifest.cards.filter(c=>c.user_locked).map(c=>c.id));filters.push({field:'sort',value,count:actual.length});
 }await page.click('#reset');
 checks.push('V7 locked/redrawn filters return 28/61; both subjective-score orders execute and keep unscored locked originals last.');
 const combo=manifest.cards.find(c=>c.id==='R28');await page.selectOption('#typeFilter',combo.type);await page.selectOption('#rarityFilter',combo.rarity);await page.selectOption('#levelFilter',combo.abstraction);await page.fill('#search','熊灵 兽化');
 assert.deepEqual(await page.locator('.card').evaluateAll(x=>x.map(e=>e.dataset.id)),['R28']);
 await page.fill('#search','ZZZ_NO_SUCH_CARD');assert.equal(await page.locator('.card').count(),0);assert(await page.locator('#empty').isVisible());await page.click('#emptyReset');assert.equal(await page.locator('.card').count(),89);
 checks.push('Case-insensitive ID, Chinese name, all actual type/rarity/abstraction filters, combined four-field search, empty state and reset.');
 for(const [i,c] of manifest.cards.entries()){
  await page.locator(`.card[data-id="${c.id}"]`).evaluate(el=>el.click());
  assert(await page.locator('#detailDialog').evaluate(e=>e.open));assert.equal(await page.locator('#detailID').textContent(),c.id);assert.equal(await page.locator('#detailName').textContent(),c.name);
  assert.equal(await page.locator('#effectText').textContent(),c.base_effect);await page.locator('#upgradeTab').evaluate(el=>el.click());assert.equal(await page.locator('#effectText').textContent(),c.upgraded_effect);assert.equal(await page.locator('#upgradeTab').getAttribute('aria-selected'),'true');await page.locator('#baseTab').evaluate(el=>el.click());assert.equal(await page.locator('#effectText').textContent(),c.base_effect);
  for(const [id,expected] of [['largeImage',[1000,760]],['tinyImage',[125,95]],['grayImage',[125,95]]]){
   const actual=await page.locator('#'+id).evaluate(async im=>{await im.decode();return [im.naturalWidth,im.naturalHeight];});assert.deepEqual(actual,expected);
  }
  for(const id of ['tinyImage','grayImage'])assert.deepEqual(await page.locator('#'+id).evaluate(im=>[getComputedStyle(im).width,getComputedStyle(im).height]),['125px','95px']);
  assert.equal(await page.locator('#intentLead').textContent(),c.signature||'—');assert.equal(await page.locator('#intentBody').textContent(),c.intent||'—');
  const links=await page.locator('#assetLinks a').evaluateAll(a=>a.map(e=>({key:e.dataset.asset,href:e.getAttribute('href')})));
  const expected={large:c.large,small:c.small,tiny:c.tiny,proof:c.proof,review:c.review,sts1:c.exports.sts1_large,...(c.comparison?{comparison:c.comparison}:{})};
  for(const l of links){assert(expected[l.key],`Unknown asset link ${l.key}`);assert.equal(l.href,expected[l.key].href);localFile(l.href,page.url());}
  for(const key of Object.keys(expected))assert(links.some(l=>l.key===key),c.id+': missing '+key+' link');
  const imageHrefs=[...new Set([c.candidate,c.large,c.small,c.tiny,c.gray,c.proof,...(c.comparison?[c.comparison]:[]),...Object.values(c.exports)].map(e=>e.href))];
  const decoded=await page.evaluate(async hrefs=>{const rows=[];for(const href of hrefs){const im=new Image();im.src=href;await im.decode();rows.push({href,size:[im.naturalWidth,im.naturalHeight]});}return rows;},imageHrefs);
  const review=JSON.parse(fs.readFileSync(path.join(root,c.review.path),'utf8'));assert.equal(review.id,c.id);assert.equal(review.decision,'approve');assert.equal(review.master_sha256,assets.cards[c.id].master_sha256);
  detailRecords.push({id:c.id,base_and_upgrade_match:true,actual_tiny_dimensions:[125,95],linked_images_decoded:decoded.length,review_id_and_hash_bound:true});
  await page.locator('#closeDialog').evaluate(el=>el.click());
  if((i+1)%20===0)console.log('V7 browser: inspected '+(i+1)+' of 89 card detail views');
 }
 checks.push('All 89 real detail dialogs execute, base/upgraded text matches source, actual 125x95 color/gray previews decode, and all master/export/proof/mask images linked by the manifest decode.');
 for(const id of ['B02','R28','T02']){
  await page.locator(`.card[data-id="${id}"]`).evaluate(el=>el.click());await page.locator('#largeImage').evaluate(im=>im.decode());
  for(const key of ['large','proof','sts1','review','comparison']){
   const event=page.waitForEvent('popup');await page.locator(`#assetLinks a[data-asset="${key}"]`).evaluate(a=>a.click());const pop=await event;await pop.waitForLoadState('load');
   localFile(pop.url(),page.url());
   if(key==='review'){const body=await pop.locator('body').innerText();assert(body.includes('"id"')&&body.includes(id));}
   else{const dims=await pop.locator('img').first().evaluate(async im=>{await im.decode();return [im.naturalWidth,im.naturalHeight];});if(key==='large')assert.deepEqual(dims,[1000,760]);if(key==='sts1')assert.deepEqual(dims,[500,380]);}
   popups.push({id,key,opened:true});await pop.close();
  }
  await page.locator('#closeDialog').evaluate(el=>el.click());
 }
 checks.push('Actually clicked 15 asset links on B02/R28/T02: full art, proof, benchmark comparison, STS1 mask and JSON review open as local new tabs.');
 await page.locator('.card[data-id="B01"]').click();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#detailID').textContent(),'B02');await page.locator('#largeImage').evaluate(im=>im.decode());await page.keyboard.press('ArrowLeft');assert.equal(await page.locator('#detailID').textContent(),'B01');await page.locator('#largeImage').evaluate(im=>im.decode());await page.keyboard.press('Escape');assert.equal(await page.locator('#detailDialog').evaluate(e=>e.open),false);
 await page.goto(url('cards/index.html')+'#R28');await page.waitForFunction(()=>document.querySelector('#detailDialog').open);assert.equal(await page.locator('#detailID').textContent(),'R28');await page.locator('#largeImage').evaluate(im=>im.decode());await page.screenshot({path:path.join(screenshotDir,'r28_detail.png'),fullPage:false});await page.locator('#closeDialog').evaluate(el=>el.click());
 checks.push('Previous/next arrows, Escape close and direct #R28 hash navigation execute.');
 const mobile=[];
 for(const width of [390,360]){
  await page.setViewportSize({width,height:844});await page.evaluate(()=>document.fonts.ready);await page.waitForLoadState('networkidle');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),width+' grid overflow');
  for(const id of ['B02','R28','R10']){await page.locator(`.card[data-id="${id}"]`).evaluate(el=>el.click());await page.locator('#largeImage').evaluate(im=>im.decode());const dimensions=await page.locator('#detailDialog').evaluate(el=>({scroll:el.scrollWidth,client:el.clientWidth}));assert(dimensions.scroll<=dimensions.client,`${width} ${id} dialog overflow`);mobile.push({width,id,...dimensions});if(width===390&&id==='B02')await page.screenshot({path:path.join(screenshotDir,'mobile_detail.png'),fullPage:false});await page.locator('#closeDialog').evaluate(el=>el.click());}
 }
 checks.push('390px and 360px grids plus B02/R28/long-title R10 detail dialogs have no horizontal overflow.');
 await page.waitForLoadState('networkidle');assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);assert.deepEqual(external,[]);
 for(const p of snapshotFiles)assert.equal(sha(p),snapshots[p],'Repo changed during browser check: '+p);
 Object.assign(report,{passed:true,browser:await browser.version(),card_count:89,all_detail_views_checked:89,grid_images_loaded:grid.length,checks,filter_cases:filters,detail_records:detailRecords,opened_asset_links:popups,mobile_cases:mobile,start_links:startLinks,javascript_errors:errors,failed_requests:failed,external_network_requests:external,output_sha256:snapshots,screenshots:'Temporary images in the operating-system temp directory for visual inspection; not part of user deliverables.',limitations:'This validates the local standalone card gallery and links, not target-game integration or automatic art quality.'});
 fs.mkdirSync(reportDir,{recursive:true});fs.writeFileSync(path.join(reportDir,'browser_validation.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:true,browser:report.browser,cards:89,detail_views:89,checks:checks.length,screenshots:screenshotDir}));
})().catch(e=>{Object.assign(report,{passed:false,failure:String(e.stack||e),checks,javascript_errors:errors,failed_requests:failed,external_network_requests:external,output_sha256:snapshots});fs.mkdirSync(reportDir,{recursive:true});fs.writeFileSync(path.join(reportDir,'browser_validation.json'),JSON.stringify(report,null,2)+'\n');console.error(e.stack||e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
