// `npm run dev`: starts the FastAPI backend (Gemini trace logs) and Vite in ONE terminal.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const py = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const env = { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8', FORCE_COLOR: '1' };

const api = spawn(py, ['-m', 'uvicorn', 'main:app', '--port', '8000'], { cwd: path.join(root, 'backend'), stdio: 'inherit', env });
const web = spawn(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['vite'], { cwd: path.join(root, 'frontend'), stdio: 'inherit', env, shell: process.platform === 'win32' });

const stop = () => { api.kill(); web.kill(); process.exit(); };
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
api.on('exit', c => { if (c) console.error(`\nbackend exited (${c}). Is port 8000 already in use?`); });
