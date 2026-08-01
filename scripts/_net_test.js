const https = require('https');
const hosts = ['registry.npmjs.org', 'pypi.org', 'github.com', 'raw.githubusercontent.com'];
let done = 0;
hosts.forEach(h => {
  const t = setTimeout(() => { console.log(h, 'TIMEOUT'); if (++done === hosts.length) process.exit(0); }, 6000);
  const req = https.get('https://' + h + '/', { family: 4 }, r => {
    clearTimeout(t); console.log(h, 'HTTP', r.statusCode); if (++done === hosts.length) process.exit(0);
  });
  req.on('error', e => { clearTimeout(t); console.log(h, 'ERR', e.code); if (++done === hosts.length) process.exit(0); });
});
