#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawnSync } = require('child_process');

const PKG = require('../package.json');
const REPO_URL = 'https://github.com/gufranco/claude-engineering-rules.git';
const DEFAULT_TARGET = path.join(os.homedir(), '.claude');
const DEFAULT_CACHE_DIR = path.join(os.homedir(), '.claude-engineering-rules-src');

const CATEGORIES = {
  skills: { type: 'dir', src: 'skills', dst: 'skills' },
  agents: { type: 'dir', src: 'agents', dst: 'agents' },
  hooks: { type: 'dir', src: 'hooks', dst: 'hooks' },
  rules: { type: 'dir', src: 'rules', dst: 'rules' },
  standards: { type: 'dir', src: 'standards', dst: 'standards' },
  checklists: { type: 'dir', src: 'checklists', dst: 'checklists' },
  'claude-md': { type: 'file', src: 'CLAUDE.md', dst: 'CLAUDE.md' },
  settings: { type: 'file', src: 'settings.json', dst: 'settings.json' },
};

const CATEGORY_ORDER = [
  'rules',
  'standards',
  'checklists',
  'skills',
  'agents',
  'hooks',
  'claude-md',
  'settings',
];

function log(msg) {
  process.stdout.write(msg + '\n');
}

function warn(msg) {
  process.stderr.write('warn: ' + msg + '\n');
}

function die(msg, code) {
  process.stderr.write('error: ' + msg + '\n');
  process.exit(typeof code === 'number' ? code : 1);
}

function printHelp() {
  log(`claude-engineering-rules v${PKG.version}

USAGE
  npx claude-engineering-rules <command> [category] [options]

COMMANDS
  install [category]   Install one or all categories into the target dir
  list                 List available categories
  doctor               Diagnose target dir, source dir, and platform
  help                 Show this help
  version              Show version

CATEGORIES (for install)
  all                  Everything (default)
  skills               skills/
  agents               agents/
  hooks                hooks/
  rules                rules/
  standards            standards/
  checklists           checklists/
  claude-md            CLAUDE.md
  settings             settings.json (existing file is backed up first)

OPTIONS
  --target <path>      Install target (default: ~/.claude)
  --source <path>      Source repo path (default: auto-detect or clone to ${DEFAULT_CACHE_DIR})
  --copy               Copy files instead of symlinking
  --symlink            Symlink (default)
  --force              Replace existing entries without backup
  --dry-run            Print planned actions, change nothing
  --yes, -y            Skip confirmation prompts
  --verbose, -v        Verbose logging

EXAMPLES
  npx claude-engineering-rules install
  npx claude-engineering-rules install skills
  npx claude-engineering-rules install all --copy
  npx claude-engineering-rules install settings --dry-run
  npx claude-engineering-rules doctor
`);
}

function parseArgs(argv) {
  const args = {
    _: [],
    target: DEFAULT_TARGET,
    source: null,
    mode: 'symlink',
    force: false,
    dryRun: false,
    yes: false,
    verbose: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--target') {
      args.target = path.resolve(argv[++i] || '');
    } else if (a === '--source') {
      args.source = path.resolve(argv[++i] || '');
    } else if (a === '--copy') {
      args.mode = 'copy';
    } else if (a === '--symlink') {
      args.mode = 'symlink';
    } else if (a === '--force') {
      args.force = true;
    } else if (a === '--dry-run') {
      args.dryRun = true;
    } else if (a === '--yes' || a === '-y') {
      args.yes = true;
    } else if (a === '--verbose' || a === '-v') {
      args.verbose = true;
    } else if (a === '--help' || a === '-h') {
      args._.unshift('help');
    } else if (a === '--version' || a === '-V') {
      args._.unshift('version');
    } else if (a.startsWith('--')) {
      die('unknown flag: ' + a);
    } else {
      args._.push(a);
    }
  }
  return args;
}

function isRepoRoot(dir) {
  return (
    fs.existsSync(path.join(dir, 'CLAUDE.md')) &&
    fs.existsSync(path.join(dir, 'skills')) &&
    fs.existsSync(path.join(dir, 'agents')) &&
    fs.existsSync(path.join(dir, 'hooks')) &&
    fs.existsSync(path.join(dir, 'rules')) &&
    fs.existsSync(path.join(dir, 'standards'))
  );
}

function looksLikeNpmCache(dir) {
  const norm = dir.replace(/\\/g, '/');
  return /\/(_npx|_cacache|\.npm\/_npx)\//.test(norm) || /\/npm-cache\//.test(norm);
}

function resolveSource(args) {
  if (args.source) {
    if (!isRepoRoot(args.source)) {
      die(`--source ${args.source} is not a valid claude-engineering-rules repo root`);
    }
    return args.source;
  }
  const scriptRoot = path.resolve(__dirname, '..');
  if (isRepoRoot(scriptRoot) && !looksLikeNpmCache(scriptRoot)) {
    return scriptRoot;
  }
  // Running from npm cache or non-repo: ensure persistent clone.
  return ensureClone(args);
}

function ensureClone(args) {
  const dest = DEFAULT_CACHE_DIR;
  if (isRepoRoot(dest)) {
    if (args.verbose) log(`source: using cached clone at ${dest}`);
    // Best-effort update; ignore failures (offline, etc).
    if (!args.dryRun) {
      const r = spawnSync('git', ['-C', dest, 'pull', '--ff-only', '--quiet'], { stdio: 'ignore' });
      if (r.status !== 0 && args.verbose) warn(`git pull in ${dest} failed (continuing)`);
    }
    return dest;
  }
  if (args.dryRun) {
    log(`would clone ${REPO_URL} into ${dest}`);
    return dest;
  }
  ensureDir(path.dirname(dest));
  log(`cloning ${REPO_URL} into ${dest}`);
  const r = spawnSync('git', ['clone', '--depth', '1', REPO_URL, dest], { stdio: 'inherit' });
  if (r.status !== 0) die(`git clone failed (exit ${r.status}). Install git or pass --source <path>.`);
  return dest;
}

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function backupPath(target) {
  return `${target}.bak.${timestamp()}`;
}

function lstatSafe(p) {
  try {
    return fs.lstatSync(p);
  } catch {
    return null;
  }
}

function readlinkSafe(p) {
  try {
    return fs.readlinkSync(p);
  } catch {
    return null;
  }
}

function pointsAt(linkPath, expectedTarget) {
  const link = readlinkSafe(linkPath);
  if (!link) return false;
  const resolved = path.isAbsolute(link)
    ? link
    : path.resolve(path.dirname(linkPath), link);
  return path.resolve(resolved) === path.resolve(expectedTarget);
}

function removeEntry(p, dryRun) {
  if (dryRun) {
    log(`  rm ${p}`);
    return;
  }
  const st = lstatSafe(p);
  if (!st) return;
  if (st.isSymbolicLink() || st.isFile()) {
    fs.unlinkSync(p);
  } else if (st.isDirectory()) {
    fs.rmSync(p, { recursive: true, force: true });
  }
}

function symlinkType(srcStat) {
  if (process.platform !== 'win32') return undefined;
  // Windows: use 'junction' for directories (no admin needed), 'file' for files.
  return srcStat.isDirectory() ? 'junction' : 'file';
}

function copyRecursive(src, dst) {
  // Node 16+ has fs.cpSync.
  fs.cpSync(src, dst, { recursive: true, force: true });
}

function applyEntry(srcAbs, dstAbs, mode, args) {
  const srcStat = fs.statSync(srcAbs);
  const existing = lstatSafe(dstAbs);

  if (existing) {
    // Already correct symlink? skip.
    if (mode === 'symlink' && existing.isSymbolicLink() && pointsAt(dstAbs, srcAbs)) {
      if (args.verbose) log(`  ok  ${dstAbs} (already linked)`);
      return 'skipped';
    }
    if (args.force) {
      log(`  replace ${dstAbs} (--force)`);
      removeEntry(dstAbs, args.dryRun);
    } else {
      const bak = backupPath(dstAbs);
      log(`  backup ${dstAbs} -> ${bak}`);
      if (!args.dryRun) fs.renameSync(dstAbs, bak);
    }
  }

  if (args.dryRun) {
    log(`  ${mode === 'symlink' ? 'ln -s' : 'cp -r'} ${srcAbs} ${dstAbs}`);
    return 'planned';
  }

  ensureDir(path.dirname(dstAbs));
  if (mode === 'symlink') {
    try {
      fs.symlinkSync(srcAbs, dstAbs, symlinkType(srcStat));
      log(`  link  ${dstAbs}`);
    } catch (err) {
      if (process.platform === 'win32' && (err.code === 'EPERM' || err.code === 'EACCES')) {
        warn(`symlink failed on Windows (EPERM). Falling back to copy for ${dstAbs}. Enable Developer Mode or rerun with --copy to silence this.`);
        copyRecursive(srcAbs, dstAbs);
        log(`  copy  ${dstAbs}`);
      } else {
        throw err;
      }
    }
  } else {
    copyRecursive(srcAbs, dstAbs);
    log(`  copy  ${dstAbs}`);
  }
  return 'installed';
}

function installCategory(name, sourceRoot, args) {
  const cat = CATEGORIES[name];
  if (!cat) die(`unknown category: ${name}`);
  const srcAbs = path.join(sourceRoot, cat.src);
  const dstAbs = path.join(args.target, cat.dst);
  if (!fs.existsSync(srcAbs)) {
    warn(`source missing: ${srcAbs} (skipped)`);
    return 'missing';
  }
  log(`[${name}]`);
  return applyEntry(srcAbs, dstAbs, args.mode, args);
}

function cmdInstall(args) {
  const which = args._[1] || 'all';
  const sourceRoot = resolveSource(args);
  if (!args.dryRun) ensureDir(args.target);
  log(`source: ${sourceRoot}`);
  log(`target: ${args.target}`);
  log(`mode:   ${args.mode}${args.dryRun ? ' (dry-run)' : ''}`);
  log('');

  const list = which === 'all' ? CATEGORY_ORDER : [which];
  for (const name of list) {
    if (!CATEGORIES[name]) die(`unknown category: ${name}. Run 'list' to see options.`);
    installCategory(name, sourceRoot, args);
  }
  log('');
  log(args.dryRun ? 'dry-run complete. No changes written.' : 'install complete.');
}

function cmdList() {
  log('Available categories:');
  for (const name of CATEGORY_ORDER) {
    const cat = CATEGORIES[name];
    log(`  ${name.padEnd(12)} ${cat.type === 'dir' ? cat.src + '/' : cat.src}`);
  }
}

function cmdDoctor(args) {
  log(`claude-engineering-rules v${PKG.version}`);
  log(`node:     ${process.version}`);
  log(`platform: ${process.platform} (${process.arch})`);
  log(`target:   ${args.target}`);
  log(`  exists: ${fs.existsSync(args.target)}`);

  let sourceRoot = null;
  try {
    sourceRoot = resolveSource({ ...args, dryRun: true });
  } catch (e) {
    warn('source resolution: ' + e.message);
  }
  log(`source:   ${sourceRoot || '(unresolved)'}`);
  if (sourceRoot) log(`  valid:  ${isRepoRoot(sourceRoot)}`);

  if (process.platform === 'win32') {
    log('win32:    symlinks require Developer Mode or Admin. Junctions used for directories.');
  }

  const gitOk = spawnSync('git', ['--version'], { stdio: 'ignore' }).status === 0;
  log(`git:      ${gitOk ? 'ok' : 'MISSING (needed for npx flow)'}`);
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0) {
    printHelp();
    return;
  }
  const args = parseArgs(argv);
  const cmd = args._[0];
  switch (cmd) {
    case 'install':
      return cmdInstall(args);
    case 'list':
      return cmdList();
    case 'doctor':
      return cmdDoctor(args);
    case 'help':
    case undefined:
      return printHelp();
    case 'version':
      return log(PKG.version);
    default:
      die(`unknown command: ${cmd}. Run 'help' for usage.`);
  }
}

try {
  main();
} catch (err) {
  die(err && err.stack ? err.stack : String(err));
}
