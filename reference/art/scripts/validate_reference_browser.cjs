#!/usr/bin/env node
const fs=require('fs'),path=require('path'),os=require('os'),crypto=require('crypto');
const {pathToFileURL,fileURLToPath}=require('url');const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const need=(v,s)=>{if(!v)throw Error(s)};
(async()=>{
 const shots=fs.mkdtempSync(path.join(os.tmpdir(),'volibear-v5-reference-browser-'));
 const tracked=['START_HERE.html','reference_manifest.json','fonts/reference_ui.woff'];const before=Object.fromEntries(tracked.map(f=>[f,sha(path.join(root,f))]));
 const browser=await chromium.launch({headless:true,...(process.env.VOLIBEAR_CHROMIUM?{executablePath:process.env.VOLIBEAR_CHROMIUM}:{})});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],failed=[];page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()?.errorText}));
 await page.goto(pathToFileURL(path.join(root,'START_HERE.html')).href,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);
 await page.waitForFunction(()=>document.images.length===35&&[...document.images].every(i=>i.complete&&i.naturalWidth>0));
 const links=await page.locator('[href],[src]').evaluateAll(es=>es.flatMap(e=>['href','src'].map(k=>e.getAttribute(k))).filter(Boolean).map(s=>new URL(s,document.baseURI).href));
 let local=0;for(const u of links)if(u.startsWith('file:')){need(fs.existsSync(fileURLToPath(u.split('#')[0])),'Missing local target '+u);local++;}
 const video=await page.locator('video').evaluateAll(es=>es.map(v=>({src:v.getAttribute('src'),url:v.currentSrc,readyState:v.readyState,duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error?.code||null})));
 need(video.length===4&&video.every(v=>v.readyState>=1&&!v.error&&v.duration>0),'Reference video metadata failed: '+JSON.stringify(video));
 for(let i=0;i<video.length;i++){
  await page.locator('video').nth(i).evaluate(async v=>{v.muted=true;await v.play()});
  await page.waitForFunction(i=>document.querySelectorAll('video')[i].currentTime>.15,i);
  video[i].clock_advanced=await page.locator('video').nth(i).evaluate(v=>{const t=v.currentTime;v.pause();return t});
 }
 await page.screenshot({path:path.join(shots,'reference_desktop.png')});await page.locator('h2').nth(1).evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:path.join(shots,'reference_cards.png')});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(shots,'reference_mobile.png')});need(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Reference mobile overflow');
 // Chromium intentionally aborts a metadata-only media request when it has
 // read the necessary header. Count it separately only after real playback.
 const metadataAborts=failed.filter(f=>f.error==='net::ERR_ABORTED'&&video.some(v=>v.url===f.url&&v.clock_advanced>.15));
 const actualFailures=failed.filter(f=>!metadataAborts.includes(f));
 need(!errors.length&&!actualFailures.length,'Browser error/failure '+JSON.stringify({errors,actualFailures}));for(const f of tracked)need(sha(path.join(root,f))===before[f],'Input changed '+f);
 const screenshots=fs.readdirSync(shots).map(n=>({name:n,path:path.join(shots,n),sha256:sha(path.join(shots,n))}));
 const report={schema_version:1,status:'pass',checked_at:new Date().toISOString(),browser:await browser.version(),input_sha256:before,image_count:35,video_count:4,video,local_links_checked:local,javascript_errors:errors,failed_requests:actualFailures,metadata_request_cancellations_after_successful_media_load_and_playback:metadataAborts,screenshots,visual_review:'pending actual screenshot inspection'};
 fs.writeFileSync(path.join(root,'reports/browser_validation_v5.json'),JSON.stringify(report,null,2)+'\n');await browser.close();console.log(JSON.stringify({status:'pass',images:35,videos:4,local_links:local,shots},null,2));
})().catch(e=>{console.error(e.stack);process.exit(1)});
