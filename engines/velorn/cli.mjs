// SPDX-License-Identifier: GPL-3.0-only
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'
import { launchVelorn } from './launcher.mjs'
export function options(argv) {
  const values = {}
  for (let index = 0; index < argv.length; index++) {
    const flag = argv[index]
    if (!flag.startsWith('--')) throw Error(`Unexpected argument: ${flag}`)
    if (['--no-sandbox', '--software-gpu'].includes(flag)) values[flag.slice(2)] = true
    else {
      if (!argv[index + 1] || argv[index + 1].startsWith('--')) throw Error(`Missing value for ${flag}`)
      values[flag.slice(2)] = argv[++index]
    }
  }
  const required = name => { if (!values[name]) throw Error(`--${name} is required`); return path.resolve(values[name]) }
  return {
    source: required('source'), profileRoot: required('profile'), projectsRoot: required('projects'),
    stagingRoot: required('staging'), outputRoot: required('outputs'),
    xvfbBinary: values['xvfb-binary'], xvfbLibraryDir: values['xvfb-lib-dir'],
    display: values.display, noSandbox: !!values['no-sandbox'], softwareGpu: !!values['software-gpu'],
  }
}
async function main() {
  const session = await launchVelorn(options(process.argv.slice(2)))
  const respond = message => process.stdout.write(JSON.stringify(message) + '\n')
  const stop = async () => { await session.close(); process.exit(0) }
  process.once('SIGINT', stop); process.once('SIGTERM', stop)
  respond({ ready: true, revision: session.revision, upstreamMcp: session.client.url, logPath: session.logPath,
    scope: 'Trusted local integration only; upstream unauthenticated MCP is not a model security boundary.' })
  try {
    for await (const line of readline.createInterface({ input: process.stdin, crlfDelay: Infinity })) {
      let request
      try {
        request = JSON.parse(line)
        let result
        if (request.method === 'tools/list') result = { tools: await session.client.discover() }
        else if (request.method === 'tools/call') result = await session.client.call(request.params?.name, request.params?.arguments)
        else if (request.method === 'shutdown') break
        else throw Error('Use tools/list, tools/call, or shutdown.')
        respond({ id: request.id ?? null, result })
      } catch (error) { respond({ id: request?.id ?? null, error: { message: error.message } }) }
    }
  } finally { await session.close() }
}
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]))
  main().catch(error => { console.error(error.stack); process.exitCode = 1 })
