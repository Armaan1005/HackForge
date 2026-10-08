// `npm run dev`: starts the FastAPI backend (engine + Gemini trace logs) and Vite in ONE terminal.
// Uses the live engine by default (USE_FIXTURES=false); generates data + runs the pipeline on first run.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const backend = path.join(root, 'backend');
const py = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const env = { USE_FIXTURES: 'false', ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8', FORCE_COLOR: '1' };

if (env.USE_FIXTURES === 'false' && !existsSync(path.join(root, 'data', 'processed', 'overview.json'))) {
  console.log('First run: generating synthetic data and running the detection pipeline (~1 min)…');
  for (const mod of ['engine.generate', 'engine.pipeline']) {
    const r = spawnSync(py, ['-m', mod, ...(mod === 'engine.generate' ? ['--seed', '42'] : [])], { cwd: backend, stdio: 'inherit', env });
    if (r.status !== 0) { console.error(`${mod} failed`); process.exit(1); }
  }
}

const api = spawn(py, ['-m', 'uvicorn', 'main:app', '--port', '8000'], { cwd: backend, stdio: 'inherit', env });
const web = spawn(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['vite'], { cwd: path.join(root, 'frontend'), stdio: 'inherit', env, shell: process.platform === 'win32' });

const stop = () => { api.kill(); web.kill(); process.exit(); };
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
api.on('exit', c => { if (c) console.error(`\nbackend exited (${c}). Is port 8000 already in use?`); });
