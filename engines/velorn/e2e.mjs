// SPDX-License-Identifier: GPL-3.0-only
// Scripted technical fixture, not autonomous model/creative quality acceptance.
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { launchVelorn } from './launcher.mjs'
import { options } from './cli.mjs'
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex')
async function main() {
  const fixture = await fs.mkdtemp(path.join(os.tmpdir(), 'zx7-velorn-e2e-'))
  const rootArgs = ['--profile', fixture + '/profile', '--projects', fixture + '/projects', '--staging', fixture + '/staging', '--outputs', fixture + '/outputs']
  const config = options([...process.argv.slice(2), ...rootArgs])
  const require = createRequire(path.join(config.source, 'package.json'))
  const ffmpeg = require('ffmpeg-static'), probeExport = require('@derhuerst/ffprobe-static')
  const ffprobe = typeof probeExport === 'string' ? probeExport : probeExport.path
  await fs.mkdir(config.stagingRoot, { recursive: true })
  const run = (binary, argv) => execFileSync(binary, argv, { encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 })
  run(ffmpeg, ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=24:d=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', config.stagingRoot + '/source.mp4'])
  run(ffmpeg, ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=440:d=2', '-c:a', 'pcm_s16le', config.stagingRoot + '/tone.wav'])
  let session = await launchVelorn(config)
  const { client } = session
  const call = async (name, args = {}) => (await client.call(name, args)).data
  const wait = predicate => client.waitForState(predicate)
  try {
    const discovered = await client.discover()
    assert.equal(discovered.length, 130)
    assert(discovered.some(tool => tool.name === 'set_clip_keyframes'))
    await assert.rejects(client.call('queue_prompt_generation_batch', {}), /blocked/)
    await assert.rejects(client.call('import_asset_from_path', { path: '/etc/passwd', previewOnly: false }), /outside allocated/)
    await call('create_project', { name: 'Native proof', width: 320, height: 180, fps: 24, previewOnly: false })
    const state = await wait(state => state?.project?.name === 'Native proof')
    const projectPath = state.project.path
    await call('import_asset_from_path', { path: config.stagingRoot + '/source.mp4', previewOnly: false })
    await wait(state => state?.assetCount === 1)
    await call('import_asset_from_path', { path: config.stagingRoot + '/tone.wav', previewOnly: false })
    await wait(state => state?.assetCount === 2)
    await call('add_asset_to_timeline', { assetName: 'source.mp4', startSeconds: 0, includeAudio: false, previewOnly: false })
    await wait(state => state?.currentTimeline?.clipCount === 1)
    await call('add_asset_to_timeline', { assetName: 'tone.wav', startSeconds: 0, previewOnly: false })
    await wait(state => state?.currentTimeline?.clipCount === 2)
    await call('add_track', { type: 'video', name: 'Fixture title', previewOnly: false })
    await wait(state => state?.currentTimeline?.trackCount === 3)
    const title = await call('add_text_clip', { text: 'Native render', startSeconds: 0, durationSeconds: 2, style: { fontSize: 24 }, previewOnly: false })
    await wait(state => state?.currentTimeline?.clipCount === 3)
    const titleId = title.result.clip.id
    await call('set_clip_keyframes', { clipId: titleId, keyframes: [
      { property: 'opacity', time: 0, value: 20, easing: 'cubicBezier(0.2,0,0.8,1)' },
      { property: 'opacity', time: 1, value: 100, easing: 'linear' },
    ], previewOnly: false })
    await call('save_project', { previewOnly: false })
    const nativePath = path.join(projectPath, 'project.comfystudio')
    const revision1 = await fs.readFile(nativePath)
    await fs.writeFile(path.join(fixture, 'revision-1.comfystudio'), revision1)
    const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
    const bodyRoute = JSON.parse(execFileSync('python3', ['-c', `
import json, sys
from studio_next.body_editor_client import LocalEditorClient
from studio_next.body_integration import body_catalog
request = json.load(sys.stdin)
client = LocalEditorClient('http://127.0.0.1:19790/mcp', allowed_tools={'get_project':'read', 'update_text_clip':'write'})
catalog = body_catalog(request['workspace'], editor_client=client)
tools = {tool['id']:tool for tool in catalog.discover()}
native = {tool['name']:tool for tool in client.list_tools()}
assert tools['body.editor.update_text_clip']['schema']['properties']['arguments'] == native['update_text_clip']['inputSchema']
read = catalog.invoke('body.editor.get_project', {'arguments':{}})
args = {'arguments':{'clipId':request['clipId'], 'text':'Reopened revision', 'previewOnly':False}}
blocked = False
try:
    catalog.invoke('body.editor.update_text_clip', args)
except PermissionError:
    blocked = True
assert blocked
write = catalog.invoke('body.editor.update_text_clip', args, {'write'})
assert not write.get('isError')
print(json.dumps({'nativeToolCount':len(native), 'bodyNativeTools':[name for name in tools if name.startswith('body.editor.')], 'writeWithoutGrantBlocked':blocked, 'readSucceeded':not read.get('isError'), 'writeSucceeded':not write.get('isError')}))
`], { cwd: repositoryRoot, input: JSON.stringify({ workspace: projectPath, clipId: titleId }), encoding: 'utf8', timeout: 30000, maxBuffer: 8 * 1024 * 1024 }))
    assert.equal(bodyRoute.nativeToolCount, 130); assert.equal(bodyRoute.writeWithoutGrantBlocked, true)
    const permissionsFile = path.join(fixture, 'body-permissions.json')
    await fs.writeFile(permissionsFile, JSON.stringify({ allowed_tools: { get_project: 'read' }, allowed_access: ['read'] }))
    const bodyCli = JSON.parse(execFileSync('python3', ['-m', 'studio_next.body_editor_client', '--endpoint', client.url,
      '--permissions', permissionsFile, '--request'], { cwd: repositoryRoot, input: JSON.stringify({ operation: 'call', tool_name: 'get_project', arguments: {} }), encoding: 'utf8', timeout: 15000 }))
    assert.equal(bodyCli.isError, undefined); assert(Array.isArray(bodyCli.content))
    await call('save_project', { previewOnly: false })
    const revision2 = await fs.readFile(nativePath)
    assert.notDeepEqual(revision1, revision2)
    await fs.writeFile(path.join(fixture, 'revision-2.comfystudio'), revision2)
    const native = JSON.parse(revision2)
    assert.equal(native.timelines[0].clips.length, 3); assert.equal(native.timelines[0].tracks.length, 3)
    assert(native.assets.every(asset => !path.isAbsolute(asset.path)))
    await call('open_project', { projectPath, previewOnly: false })
    await wait(state => state?.currentTimeline?.clipCount === 3)
    let reopened
    const reopenDeadline = Date.now() + 15000
    do {
      reopened = await call('get_timeline', { includeClips: true })
      if (reopened.clips.some(clip => clip.id === titleId && clip.textProperties?.text === 'Reopened revision')) break
      await new Promise(resolve => setTimeout(resolve, 150))
    } while (Date.now() < reopenDeadline)
    assert(reopened.clips.some(clip => clip.id === titleId && clip.textProperties?.text === 'Reopened revision'))
    const output = path.join(config.outputRoot, 'native-export.mp4')
    const exportPlan = await call('export_timeline', { outputPath: output, target: 'h264_project', width: 320, height: 180,
      range: 'custom', startSeconds: 0, endSeconds: 2, fps: 24, includeAudio: true, previewOnly: false })
    assert.equal(exportPlan.success, true)
    const workerLogPath = path.join(session.appProfile, 'export-worker.log')
    const deadline = Date.now() + 90000
    let workerLog = ''
    while (Date.now() < deadline) {
      workerLog = await fs.readFile(workerLogPath, 'utf8').catch(() => '')
      if (workerLog.includes('[ExportWorker] Export complete')) break
      if (/!!! RENDER PROCESS GONE/.test(workerLog)) throw Error(workerLog)
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    assert(workerLog.includes('[ExportWorker] Export complete'), 'Production export did not complete')
    assert(workerLog.includes('Starting exportTimeline')); assert(workerLog.includes('Loaded video: file:')); assert(workerLog.includes('FFmpeg result'))
    const probe = JSON.parse(run(ffprobe, ['-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', output]))
    const video = probe.streams.find(stream => stream.codec_type === 'video'), audio = probe.streams.find(stream => stream.codec_type === 'audio')
    assert.equal(video.codec_name, 'h264'); assert.equal(video.width, 320); assert.equal(video.height, 180)
    assert.equal(video.r_frame_rate, '24/1'); assert.equal(Number(video.nb_read_frames), 48)
    assert.equal(audio.codec_name, 'aac'); assert(Math.abs(Number(probe.format.duration) - 2) < 0.05)
    run(ffmpeg, ['-v', 'error', '-xerror', '-i', output, '-f', 'null', '-'])
    const pcm = execFileSync(ffmpeg, ['-v', 'error', '-i', output, '-map', '0:a:0', '-f', 'f32le', '-ac', '1', 'pipe:1'])
    let sum = 0
    for (let index = 0; index < pcm.length; index += 4) sum += pcm.readFloatLE(index) ** 2
    const audioRms = Math.sqrt(sum / (pcm.length / 4))
    assert(audioRms > 0.03 && audioRms < 0.2)
    run(ffmpeg, ['-v', 'error', '-y', '-ss', '0.5', '-i', output, '-frames:v', '1', path.join(config.outputRoot, 'decoded-frame.png')])
    // Stop the entire owned application, then reopen disk state in a new
    // process/profile. This is clean restart evidence, not render-crash resume.
    await session.close()
    session = await launchVelorn({ ...config, profileRoot: path.join(fixture, 'restart-profile') })
    const restarted = session.client
    await restarted.call('open_project', { projectPath, previewOnly: false })
    await restarted.waitForState(state => state?.currentTimeline?.clipCount === 3 && state?.assetCount === 2)
    const restartedTimeline = (await restarted.call('get_timeline', { includeClips: true })).data
    assert.equal(restartedTimeline.tracks.length, 3)
    assert.equal(restartedTimeline.clips.length, 3)
    const savedTitle = native.timelines[0].clips.find(clip => clip.id === titleId)
    const restartedTitle = restartedTimeline.clips.find(clip => clip.id === titleId)
    assert.equal(restartedTitle.textProperties.text, 'Reopened revision')
    assert.deepEqual(restartedTitle.keyframes, savedTitle.keyframes)
    const restartedAssets = (await restarted.call('get_assets')).data.assets
    assert.equal(restartedAssets.length, native.assets.length)
    for (const saved of native.assets) {
      const asset = restartedAssets.find(asset => asset.id === saved.id)
      assert(asset, 'Reopened asset identity changed')
      assert.equal(path.resolve(projectPath, asset.path), path.resolve(projectPath, saved.path))
      await fs.access(path.resolve(projectPath, asset.path))
    }
    const receipt = { success: true, kind: 'scripted native integration fixture; no autonomous model evaluation',
      upstreamCommit: session.revision, renderer: 'existing production dist served by Vite preview; existing Electron main and ExportWorker',
      rendererIndexSha256: hash(await fs.readFile(path.join(config.source, 'dist/index.html'))), discoveredToolCount: discovered.length,
      bodyRoute, bodyCliReadPassed: true, processRestartReopenPassed: true, nativeProject: nativePath,
      preservedRevisions: [{ file: 'revision-1.comfystudio', sha256: hash(revision1) }, { file: 'revision-2.comfystudio', sha256: hash(revision2) }], reopenedRevision: 2,
      editableTracks: 3, editableClips: 3, frames: 48, fps: '24/1', durationSeconds: Number(probe.format.duration),
      videoCodec: video.codec_name, audioCodec: audio.codec_name, audioRms, fullDecodePassed: true,
      output, outputSha256: hash(await fs.readFile(output)), bytes: (await fs.stat(output)).size, workerLogPath, fixture,
      limitations: ['Clean saved-project restart tested; render interruption/crash recovery not tested', 'Not a creative-field completion or professional quality certification', 'Upstream raw MCP has no auth; wrapper policy is not OS isolation'] }
    await fs.writeFile(path.join(fixture, 'receipt.json'), JSON.stringify(receipt, null, 2))
    await fs.writeFile(path.join(fixture, 'probe.json'), JSON.stringify(probe, null, 2))
    console.log(JSON.stringify(receipt, null, 2))
  } finally { await session.close() }
}
main().catch(error => { console.error(error.stack); process.exitCode = 1 })
