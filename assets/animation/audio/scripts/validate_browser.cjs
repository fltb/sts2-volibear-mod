const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict'),crypto=require('crypto');
const {pathToFileURL}=require('url');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),repo=path.dirname(root),reportDir=path.join(root,'reports');
const shotDir=fs.mkdtempSync(path.join(os.tmpdir(),'volibear-v5-audio-browser-'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
 const errors=[],failed=[];const browser=await chromium.launch({executablePath:process.env.VOLIBEAR_CHROMIUM||undefined,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage({viewport:{width:1280,height:1000}});
 page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()}));
 await page.goto(pathToFileURL(path.join(root,'index.html')).href);await page.evaluate(()=>document.fonts.ready);
 assert.equal(await page.locator('.card').count(),47);
 // file:// media elements work without fetch(). Pass exact local bytes to the
 // WebAudio decoder and independently load all actual file:// media URLs.
 const payload=manifest.assets.map(a=>({...a,base64:fs.readFileSync(path.join(root,a.file)).toString('base64')}));
 const decoded=await page.evaluate(async assets=>{const ctx=new AudioContext();const out=[];for(const a of assets){const el=new Audio();el.preload='auto';const loaded=new Promise((resolve,reject)=>{el.onloadedmetadata=resolve;el.onerror=()=>reject(new Error(a.file+' media load'));});el.src=a.file;el.load();await loaded;const bytes=Uint8Array.from(atob(a.base64),c=>c.charCodeAt(0));const b=await ctx.decodeAudioData(bytes.buffer);const x=b.getChannelData(0);let peak=0;for(const s of x)peak=Math.max(peak,Math.abs(s));out.push({id:a.id,sample_rate:b.sampleRate,channels:b.numberOfChannels,duration:b.duration,media_url_duration:el.duration,peak});el.removeAttribute('src');el.load();}await ctx.close();return out;},payload);
 assert.equal(decoded.length,47);for(const d of decoded){const src=manifest.assets.find(a=>a.id===d.id);assert.equal(d.channels,1);assert(Math.abs(d.duration-src.duration_seconds)<.05);assert(d.peak>0&&d.peak<1);}
 const played=[];for(const id of ['voice_roar','lightning_strike','domain_loop']){const a=page.locator('audio[data-asset="'+id+'"]');await a.evaluate(async el=>{el.volume=.2;await el.play()});await page.waitForTimeout(180);const s=await a.evaluate(el=>({paused:el.paused,currentTime:el.currentTime,readyState:el.readyState,error:el.error?.code||null,loop:el.loop}));assert(!s.paused&&s.currentTime>0&&s.readyState>=2&&!s.error);played.push({id,...s});await page.locator('#stop').click();assert(await a.evaluate(el=>el.paused&&el.currentTime===0));}
 await page.selectOption('#category','voice');assert.equal(await page.locator('.card').count(),13);
 await page.selectOption('#category','loop');assert.equal(await page.locator('.card').count(),2);
 await page.selectOption('#category','all');await page.fill('#search','lightning');assert.equal(await page.locator('.card').count(),4);await page.fill('#search','');
 await page.screenshot({path:path.join(shotDir,'audio_desktop.png'),fullPage:false});
 await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(shotDir,'audio_mobile.png'),fullPage:false});
 assert.equal(errors.length,0);assert.equal(failed.length,0);
 const report={status:'pass',scope:'actual Chromium local-file metadata decode and playback clock; no human listening review',browser:await browser.version(),playwright:require('playwright/package.json').version,decoded,played,filters_checked:['all47','voice13','loop2','lightning4'],stop_all_checked:true,mobile_no_overflow:true,errors,failed_requests:failed,input_sha256:{manifest:sha(path.join(root,'manifest.json')),index:sha(path.join(root,'index.html')),manifest_js:sha(path.join(root,'manifest.js')),font:sha(path.join(repo,'ui/fonts/volibear_ui_v5.woff')),test:sha(__filename)},screenshot_directory:shotDir};
 fs.mkdirSync(reportDir,{recursive:true});fs.writeFileSync(path.join(reportDir,'browser_validation.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,decoded:decoded.length,played:played.length,browser:report.browser,screenshots:shotDir}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
