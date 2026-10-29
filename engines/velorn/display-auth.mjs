// SPDX-License-Identifier: GPL-3.0-only
// Keep the local native X display private without disabling Chromium's sandbox.
import fs from 'node:fs/promises'
import path from 'node:path'
import { randomBytes } from 'node:crypto'
import { execFileSync } from 'node:child_process'

export async function createPrivateDisplayAuthority(profileRoot, display) {
  if (typeof profileRoot !== 'string' || !path.isAbsolute(profileRoot) ||
      typeof display !== 'string' || !/^127\.0\.0\.1:[1-9][0-9]*$/.test(display) ||
      Number(display.split(':')[1]) > 59535)
    throw Error('A private X authority needs an absolute host profile and local TCP display.')
  // A shared profile would disclose the display cookie even if the cookie file
  // itself is 0600. Never silently chmod a pre-existing owner directory.
  await fs.mkdir(profileRoot, { recursive: true, mode: 0o700 })
  const profile = await fs.lstat(profileRoot)
  if (!profile.isDirectory() || profile.isSymbolicLink() ||
      (profile.mode & 0o077) !== 0 ||
      (typeof process.getuid === 'function' && profile.uid !== process.getuid()))
    throw Error('Native editor session profile must be a private owner-only directory (0700).')
  const authority = path.join(profileRoot, 'display.Xauthority')
  await fs.writeFile(authority, '', { flag: 'wx', mode: 0o600 })
  try {
    const secret = randomBytes(16).toString('hex')
    // Send the secret over stdin, not in process arguments or logs.
    execFileSync('xauth', ['-f', authority, '-q'], {
      input: `add ${display} MIT-MAGIC-COOKIE-1 ${secret}\n`,
      timeout: 5000, maxBuffer: 16384,
    })
    const stat = await fs.lstat(authority)
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size < 40 ||
        (stat.mode & 0o077) !== 0 ||
        (typeof process.getuid === 'function' && stat.uid !== process.getuid()))
      throw Error('X authority did not produce a private owner-only credential.')
    return authority
  } catch (error) {
    await fs.rm(authority, { force: true })
    throw error
  }
}
