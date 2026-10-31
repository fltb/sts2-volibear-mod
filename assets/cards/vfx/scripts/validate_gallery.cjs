/* Actual file:// browser test. Screenshots stay in a temporary directory. */
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto'),{execFileSync}=require('child_process');
const {chromium}=require(process.env.VOLIBEAR_PLAYWRIGHT||'playwright');
const root=path.resolve(__dirname,'..');const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.VOLIBEAR_CHROMIUM?{executablePath:process.env.VOLIBEAR_CHROMIUM}:{}),args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],failed=[],external=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),failure:r.failure()}));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 await page.goto('file://'+path.join(root,'index.html'));await page.waitForFunction(()=>window.VFX_VIEWER?.getState().imageLoaded);await page.evaluate(()=>document.fonts.ready);
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));const checked=[],captures=[];const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'volibear-vfx-gallery-'));
 for(const e of manifest.effects){
   const result=await page.evaluate(async x=>{await window.VFX_VIEWER.selectEffect(x.id);window.VFX_VIEWER.renderAt(x.poster_frame);return {...window.VFX_VIEWER.getState(),title:document.getElementById('title').textContent};},e);
   if(result.id!==e.id||result.frame!==e.poster_frame||!result.imageLoaded||result.title!==e.label_zh)throw Error('atlas display failed '+e.id);
   const shot=path.join(tmp,e.id+'_canvas.png');await page.locator('#hero').screenshot({path:shot});captures.push({id:e.id,capture:shot,reference:path.join(root,e.frames[e.poster_frame].path)});
   checked.push(result);
 }
 await page.locator('#search').fill('domain');let filtered=await page.locator('.tile:visible').count();if(filtered!==4)throw Error('search filter');
 await page.locator('#search').fill('');await page.locator('#filter').selectOption('feral');if(await page.locator('.tile:visible').count()!==4)throw Error('family filter');await page.locator('#filter').selectOption('');
 if(await page.locator('#cardSelect option').count()!==89)throw Error('card count');await page.locator('#cardSelect').selectOption('R28');if(!await page.locator('#cardCues').innerText().then(t=>t.includes('feral_transfer')&&t.includes('feral_body')))throw Error('R28 mapping');
 await page.evaluate(async()=>{await VFX_VIEWER.selectEffect('feral_transfer');VFX_VIEWER.renderAt(28);});await page.locator('#background').selectOption('checker');
 const pixelCheck=JSON.parse(execFileSync('python3',[path.join(__dirname,'verify_browser_captures.py')],{input:JSON.stringify(captures),encoding:'utf8'}));if(pixelCheck.status!=='pass')throw Error('actual canvas pixels differ');
 const shots=[];
 const desktop=path.join(tmp,'desktop_feral.png');await page.screenshot({path:desktop,fullPage:false});shots.push({path:desktop,sha256:sha(desktop),scope:'actual_file_gallery_at_feral_frame_28'});
 await page.setViewportSize({width:390,height:844});await page.locator('#background').selectOption('light');await page.evaluate(async()=>{await VFX_VIEWER.selectEffect('guard_hit');VFX_VIEWER.renderAt(6);});
 const mobile=path.join(tmp,'mobile_guard.png');await page.screenshot({path:mobile,fullPage:false});shots.push({path:mobile,sha256:sha(mobile),scope:'actual_file_gallery_mobile_guard_frame_6'});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);if(overflow)throw Error('mobile horizontal overflow');
 const iconLoaded=await page.locator('#icons img').evaluateAll(xs=>xs.every(x=>x.complete&&x.naturalWidth===64));if(!iconLoaded)throw Error('icon loading');
 const report={status:errors.length||failed.length||external.length?'fail':'pass',browser_version:browser.version(),protocol:'file://',effects_actually_rendered:checked.length,actual_canvas_pixel_comparison:pixelCheck,cards_in_selector:89,icons_loaded:16,desktop_and_mobile:true,search_and_filter:true,errors,failed_requests:failed,external_requests:external,rendered:checked,screenshots:shots,inputs:{index_sha256:sha(path.join(root,'index.html')),manifest_sha256:sha(path.join(root,'manifest.json')),font_sha256:sha(path.join(root,'fonts/vfx_ui.woff')),bindings_sha256:sha(path.join(root,'card_vfx_bindings.json')),validator_sha256:sha(__filename)}};
 fs.writeFileSync(path.join(root,'reports/browser_validation.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,effects:checked.length,screenshots:shots,errors,failed_requests:failed,external_requests:external},null,2));await browser.close();if(report.status!=='pass')process.exit(1);
})().catch(e=>{console.error(e);process.exit(1);});
