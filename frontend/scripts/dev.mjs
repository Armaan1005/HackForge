// `npm run dev`: starts the FastAPI backend (engine + AI trace logs) and Vite in ONE terminal.
// - Uses the live engine by default (USE_FIXTURES=false); builds data + runs the pipeline on first run.
// - Frees ports 8000/5173 from leftover dev servers first, and shuts the whole process tree down on Ctrl+C,
//   so "port already in use" doesn't happen on the next start.
import { execSync, spawn, spawnSync } from 'node:child_process';
import { existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const win = process.platform === 'win32';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const backend = path.join(root, 'backend');
const py = path.join(root, '.venv', win ? 'Scripts/python.exe' : 'bin/python');
const env = { USE_FIXTURES: 'false', ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8', FORCE_COLOR: '1' };

function freePort(port) {
  try {
    if (win) {
      const pids = execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`, { encoding: 'utf8' })
        .split(/\s+/).filter(Boolean);
      for (const pid of pids) { execSync(`taskkill /PID ${pid} /T /F`, { stdio: 'ignore' }); console.log(`freed port ${port} (stopped old process ${pid})`); }
    } else {
      execSync(`lsof -ti tcp:${port} | xargs -r kill -9`, { stdio: 'ignore', shell: '/bin/sh' });
    }
  } catch { /* nothing listening */ }
}

function killTree(child) {
  if (!child || child.exitCode !== null) return;
  try { win ? execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore' }) : process.kill(-child.pid, 'SIGTERM'); } catch { /* already gone */ }
}

// ── first-time setup: Python env, Python packages, frontend packages ──
function run(cmd, args, cwd) {
  const r = spawnSync(cmd, args, { cwd, stdio: 'inherit', env, shell: win });
  if (r.status !== 0) { console.error(`
Setup step failed: ${cmd} ${args.join(' ')}`); process.exit(1); }
}
if (!existsSync(py)) {
  console.log('First run: creating the Python environment (.venv)…');
  run(win ? 'python' : 'python3', ['-m', 'venv', '.venv'], root);
  console.log('Installing Python packages (a few minutes, once)…');
  run(py, ['-m', 'pip', 'install', '-q', '-r', path.join('backend', 'requirements.txt')], root);
}
const fe = path.join(root, 'frontend');
const stamp = path.join(fe, 'node_modules', '.package-lock.json');
if (!existsSync(stamp) || statSync(path.join(fe, 'package-lock.json')).mtimeMs > statSync(stamp).mtimeMs) {
  console.log('Installing website packages (new or changed)…');
  run('npm', ['install', '--no-audit', '--no-fund'], path.join(root, 'frontend'));
}
if (!existsSync(path.join(backend, 'aicore-key.json')) && !existsSync(path.join(backend, '.env'))) {
  console.log('Note: no backend/aicore-key.json (SAP AI Core key): AI agents will use template text.');
}

freePort(8000);
freePort(5173);

if (env.USE_FIXTURES === 'false' && !existsSync(path.join(root, 'data', 'processed', 'overview.json'))) {
  console.log('First run: generating synthetic data and running the detection pipeline (~1 min)…');
  for (const mod of ['engine.generate', 'engine.pipeline']) {
    const r = spawnSync(py, ['-m', mod, ...(mod === 'engine.generate' ? ['--seed', '42'] : [])], { cwd: backend, stdio: 'inherit', env });
    if (r.status !== 0) { console.error(`${mod} failed`); process.exit(1); }
  }
}

const api = spawn(py, ['-m', 'uvicorn', 'main:app', '--port', '8000'], { cwd: backend, stdio: 'inherit', env, detached: !win });
let web = null;

let stopping = false;
const stop = () => {
  if (stopping) return;
  stopping = true;
  killTree(api);
  killTree(web);
  process.exit(0);
};
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
process.on('exit', () => { killTree(api); killTree(web); });
api.on('exit', c => { if (c && !stopping) console.error(`\nbackend exited (${c}).`); });

// Start the website only once the API answers, so the first page load never hits a closed port.
async function apiReady(ms = 60000) {
  for (const until = Date.now() + ms; Date.now() < until && api.exitCode === null;) {
    try { if ((await fetch('http://127.0.0.1:8000/api/health')).ok) return true; } catch { /* not up yet */ }
    await new Promise(r => setTimeout(r, 300));
  }
  return false;
}
if (!(await apiReady())) console.error('\nThe API is not answering on :8000 yet; starting the website anyway.');
if (!stopping) web = spawn(win ? 'npx.cmd' : 'npx', ['vite', '--port', '5173', '--strictPort'], { cwd: path.join(root, 'frontend'), stdio: 'inherit', env, shell: win, detached: !win });

// Judges' phones: print the one address that works on this Wi-Fi (Vite also lists virtual adapters, e.g. VMware).
try {
  const lan = await (await fetch('http://127.0.0.1:8000/api/ai/lan')).json();
  if (lan.ip) setTimeout(() => console.log(`\n  \x1b[32m➜\x1b[0m  \x1b[1mJudges' phones\x1b[0m (same Wi-Fi): \x1b[36mhttp://${lan.ip}:5173/challenge\x1b[0m\n`), 1500);
} catch { /* API not up: Vite's own list still shows */ }
