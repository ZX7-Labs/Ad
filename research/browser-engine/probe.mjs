/** Synthetic HyperFrames native-seeking vs Inkscape vector reference research.
 * No runtime adapter or arbitrary-code sandbox is implemented here.
 * Fixed author-owned HTML only. No external media, fonts or generated art.
 */
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {mkdtemp, readFile, rm, writeFile, mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';
import {
  createCaptureSession, initializeSession, captureFrame,
  closeCaptureSession, closeBrowserPool, resolveConfig,
} from '@hyperframes/engine';

const {values} = parseArgs({options: {out: {type:'string'}, 'chrome-path': {type:'string'}}});
if (!values.out) throw new Error('--out is required');
const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
const sha = data => createHash('sha256').update(data).digest('hex');
const run = (file, args) => execFileSync(file,args,{timeout:60000,maxBuffer:8*1024*1024});
const WIDTH=64, HEIGHT=48, ORDER=[0,7,3,11,7,0];

function html(rate) {
  return `<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<style>html,body{margin:0;width:64px;height:48px;overflow:hidden;background:#000}
#box{position:absolute;top:12px;width:16px;height:16px;background:#f00}</style>
<div id="box"></div><script>
const rate=${JSON.stringify(rate)};
window.__hf={duration:12*rate.den/rate.num,seek(t){
 const frame=Math.round(t*rate.num/rate.den);
 document.getElementById('box').style.left=(8+frame*2)+'px';
}};window.__hf.seek(0);
</script>`;
}

function decodePng(path) {
  const pixels=run('ffmpeg',['-v','error','-xerror','-nostdin','-i',path,
    '-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-']);
  if(pixels.length!==WIDTH*HEIGHT*3) throw new Error('Unexpected decoded geometry');
  return pixels;
}

function redBox(pixels) {
  let count=0,x0=WIDTH,y0=HEIGHT,x1=-1,y1=-1;
  for(let y=0;y<HEIGHT;y++) for(let x=0;x<WIDTH;x++) {
    const at=(y*WIDTH+x)*3;
    if(pixels[at]>200 && pixels[at+1]<50 && pixels[at+2]<50) {
      count++;x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
    }
  }
  return {count,x0,y0,x1,y1};
}

const stage=await mkdtemp(join(tmpdir(),'zx7-browser-research-'));
const results=[];
let content='';
const server=createServer((req,res)=>{
  if(req.url!=='/index.html') {res.writeHead(404);res.end();return;}
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});
  res.end(content);
});
await new Promise((ok,fail)=>{server.once('error',fail);server.listen(0,'127.0.0.1',ok);});
const origin=`http://127.0.0.1:${server.address().port}`;
try {
  for(const rate of [{num:12,den:1},{num:30000,den:1001}]) {
    content=html(rate);
    const output=join(stage,`${rate.num}-${rate.den}`);
    const config=resolveConfig({forceScreenshot:true,browserGpuMode:'software',
      enableBrowserPool:false,chromePath:values['chrome-path']});
    let session;
    try {
      // Published 0.8.214 signatures were read from its source/declarations;
      // its README's older object-style example is not this installed API.
      session=await createCaptureSession(origin,output,{width:WIDTH,height:HEIGHT,
        fps:rate,format:'png',requiresWebGpu:false,compositionDurationSeconds:12*rate.den/rate.num},null,config);
      await session.page.setRequestInterception(true);
      session.page.on('request',req=>{
        if(req.url()===`${origin}/index.html`) void req.continue(); else void req.abort();
      });
      await initializeSession(session);
      const seen=new Map();
      const frames=[];
      for(const index of ORDER) {
        const capture=await captureFrame(session,index,index*rate.den/rate.num);
        const actual=decodePng(capture.path);
        const reference=join(output,`reference-${index}.png`);
        const svg=join(output,`reference-${index}.svg`);
        await writeFile(svg,`<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48"><rect width="64" height="48" fill="#000"/><rect x="${8+index*2}" y="12" width="16" height="16" fill="#f00"/></svg>`);
        run('inkscape',[svg,'--export-type=png',`--export-filename=${reference}`]);
        const referencePixels=decodePng(reference);
        const expectedBox={count:256,x0:8+index*2,y0:12,x1:23+index*2,y1:27};
        const observed=redBox(actual),referenceBox=redBox(referencePixels);
        if(JSON.stringify(referenceBox)!==JSON.stringify(expectedBox)) throw new Error('Independent SVG geometry oracle failed');
        const hash=sha(actual);
        const repeat=seen.has(index)?seen.get(index)===hash:null;
        seen.set(index,hash);
        frames.push({index,requested_time:{ticks:index,rate},returned_time:capture.time,
          observed_box:observed,geometry_matches:JSON.stringify(observed)===JSON.stringify(expectedBox),
          pixel_bytes_match_svg:actual.equals(referencePixels),decoded_rgb_sha256:hash,
          repeated_decoded_frame_matches:repeat});
      }
      results.push({rate,capture_mode:session.captureMode,browser_version:await session.browser.version(),
        authored_html_sha256:sha(content),warnings:session.warnings,frames});
    } finally {if(session)await closeCaptureSession(session);}
  }
} finally {
  await closeBrowserPool();
  await new Promise(ok=>server.close(ok));
  await rm(stage,{recursive:true,force:true});
}
const geometry=results.every(r=>r.frames.every(f=>f.geometry_matches));
const repeats=results.every(r=>r.frames.every(f=>f.repeated_decoded_frame_matches!==false));
const report={schema:1,source_commit:run('git',['-C',repo,'rev-parse','HEAD']).toString().trim(),
  working_tree_dirty:!!run('git',['-C',repo,'status','--porcelain']).length,
  package_version:JSON.parse(await readFile(join(here,'node_modules/@hyperframes/engine/package.json'),'utf8')).version,
  package_lock_sha256:sha(await readFile(join(here,'package-lock.json'))),
  probe_sha256:sha(await readFile(fileURLToPath(import.meta.url))),
  source_snapshot_reviewed:'a5496b1887950777b78ed5ac2bff3505961cb5fe',node_version:process.version,
  ffmpeg_version:run('ffmpeg',['-version']).toString().split('\n')[0],
  inkscape_version:run('inkscape',['--version']).toString().trim(),
  fixed_fixture_geometry_passed:geometry,repeated_out_of_order_frames_passed:repeats,
  scope:'Known trusted opaque rectangle; native HyperFrames screenshot seeking and SVG raster reference',
  not_established:['untrusted-code sandbox','typography','audio','video injection','WebGPU','craft quality','performance ranking','autonomous model'],
  browser_worker_isolation_verified:false,
  security_note:'Upstream launch includes --no-sandbox; request interception and fixed CSP are diagnostic restrictions, not host isolation',results};
await mkdir(dirname(resolve(values.out)),{recursive:true});
await writeFile(values.out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({geometry_passed:geometry,repeated_frames_passed:repeats,rates:results.map(x=>x.rate)}));
if(!geometry||!repeats)process.exitCode=1;
