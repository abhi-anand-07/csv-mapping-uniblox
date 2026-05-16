import { createServer } from 'http';
import { readFileSync, existsSync, readdirSync } from 'fs';
import { resolve, extname } from 'path';

const PORT = process.env.PORT || 3000;
const DIST = resolve(process.cwd(), 'dist');

console.log('Starting server...');
console.log('CWD:', process.cwd());
console.log('DIST path:', DIST);
console.log('DIST exists:', existsSync(DIST));

if (existsSync(DIST)) {
  try {
    console.log('DIST contents:', readdirSync(DIST));
  } catch (e) {
    console.log('Could not read DIST:', e.message);
  }
} else {
  console.log('ERROR: dist/ directory not found!');
  console.log('Available files:', readdirSync(process.cwd()));
}

const mimeTypes = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
};

const server = createServer((req, res) => {
  console.log('Request:', req.method, req.url);

  let filePath = req.url === '/' ? '/index.html' : req.url;
  filePath = resolve(DIST, '.' + filePath);

  // Security: don't serve files outside dist
  if (!filePath.startsWith(DIST)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  // SPA fallback: if file doesn't exist, serve index.html
  if (!existsSync(filePath)) {
    console.log('File not found, falling back to index.html:', filePath);
    filePath = resolve(DIST, 'index.html');
  }

  const ext = extname(filePath);
  const contentType = mimeTypes[ext] || 'application/octet-stream';

  try {
    const content = readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
    console.log('Served:', filePath);
  } catch (err) {
    console.log('Error reading file:', err.message);
    res.writeHead(500);
    res.end('Server Error');
  }
});

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
