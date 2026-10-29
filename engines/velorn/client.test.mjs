// SPDX-License-Identifier: GPL-3.0-only
import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { scopedPath, VelornClient, blockedReason } from './client.mjs'

test('scope rejects traversal, existing symlinks and dangling output symlinks', async () => {
  const fixture = await fs.mkdtemp(path.join(os.tmpdir(), 'velorn-path-'))
  try {
    const allowed = path.join(fixture, 'allowed'), outside = path.join(fixture, 'outside')
    await fs.mkdir(allowed); await fs.mkdir(outside)
    assert.equal(await scopedPath(allowed + '/future/render.mp4', [allowed]), allowed + '/future/render.mp4')
    await assert.rejects(scopedPath(allowed + '/../outside/secret', [allowed]), /outside allocated/)
    await fs.symlink(outside, allowed + '/escape')
    await assert.rejects(scopedPath(allowed + '/escape/render.mp4', [allowed]), /outside allocated/)
    await fs.symlink(outside + '/missing', allowed + '/dangling')
    await assert.rejects(scopedPath(allowed + '/dangling', [allowed]), /Dangling symlink/)
    await assert.rejects(scopedPath('relative.mp4', [allowed]), /absolute/)
  } finally { await fs.rm(fixture, { recursive: true, force: true }) }
})

test('generation, network, launcher, batch exports and nested plans cannot bypass call policy', async () => {
  const client = new VelornClient({ projectsRoot: '/tmp', stagingRoot: '/tmp', outputRoot: '/tmp' })
  for (const name of ['queue_prompt_generation_batch', 'install_workflow_setup', 'control_comfyui_launcher', 'run_mcp_action_plan', 'list_recent_projects', 'export_delivery_batch']) {
    assert(blockedReason(name)); client.tools.set(name, {})
    await assert.rejects(client.call(name, { targets: [{ outputPath: '/outside/file.mp4' }], previewOnly: false }), /blocked/)
  }
  assert.equal(blockedReason('set_clip_keyframes'), null)
  await assert.rejects(client.call('not_discovered', {}), /not discovered/)
})

test('preview success:false describes a plan; applied failures remain errors', async () => {
  const client = new VelornClient({ projectsRoot: '/tmp', stagingRoot: '/tmp', outputRoot: '/tmp' })
  client.tools.set('create_project', {})
  client.request = async () => ({ content: [{ type: 'text', text: JSON.stringify({ success: false, previewOnly: true, plan: { action: 'create' } }) }] })
  assert.equal((await client.call('create_project', { name: 'Example', previewOnly: true })).data.success, false)
  client.request = async () => ({ content: [{ type: 'text', text: JSON.stringify({ success: false, message: 'failure' }) }] })
  await assert.rejects(client.call('create_project', { name: 'Example', previewOnly: false }), /failure/)
})
