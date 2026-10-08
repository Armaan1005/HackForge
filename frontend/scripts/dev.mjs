// `npm run dev`: starts the FastAPI backend (engine + AI trace logs) and Vite in ONE terminal.
// - Uses the live engine by default (USE_FIXTURES=false); builds data + runs the pipeline on first run.
// - Frees ports 8000/5173 from leftover dev servers first, and shuts the whole process tree down on Ctrl+C,
//   so "port already in use" doesn't happen on the next start.
import { execSync, spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
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
const web = spawn(win ? 'npx.cmd' : 'npx', ['vite', '--port', '5173', '--strictPort'], { cwd: path.join(root, 'frontend'), stdio: 'inherit', env, shell: win, detached: !win });

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
