/* eslint-disable no-undef */
import { spawn } from 'child_process';
import { platform } from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isWindows = platform() === 'win32';

console.log('🚀 Starting AI Smart Travel Planner...\n');

// Start frontend
console.log('📱 Starting Frontend on http://127.0.0.1:5173/');
const frontend = spawn(isWindows ? 'npm.cmd' : 'npm', ['run', 'dev', '--', '--host', '127.0.0.1'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: isWindows
});

// Start backend
console.log('🔧 Starting Backend on http://127.0.0.1:8000/\n');
const backend = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'], {
  cwd: path.join(__dirname, 'backend'),
  stdio: 'inherit',
  shell: isWindows
});

// Handle termination
process.on('SIGINT', () => {
  console.log('\n\n🛑 Stopping servers...');
  frontend.kill();
  backend.kill();
  process.exit(0);
});

frontend.on('exit', (code) => {
  if (code !== null) {
    console.log(`Frontend exited with code ${code}`);
  }
});

backend.on('exit', (code) => {
  if (code !== null) {
    console.log(`Backend exited with code ${code}`);
  }
});
