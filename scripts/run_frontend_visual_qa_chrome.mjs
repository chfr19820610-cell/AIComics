import { spawn } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const frontendBaseUrl = process.env.AICOMIC_FRONTEND_BASE_URL || 'http://127.0.0.1:8000';
const accessToken = process.env.AICOMIC_QA_ACCESS_TOKEN || '';
const runId = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
const reportDir = path.resolve(process.cwd(), 'reports', `frontend_visual_qa_${runId}`);
const chromePort = 9300 + Math.floor(Math.random() * 300);
const chromeProfileDir = path.join('/tmp', `aicomic-chrome-visual-qa-${process.pid}`);

const routes = [
  '/login',
  '/creator',
  '/projects',
  '/dashboard',
  '/episodes',
  '/jobs',
  '/batches',
  '/provider',
  '/review',
];

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.handlers = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.addEventListener('message', (event) => {
      const payload = JSON.parse(event.data);
      if (payload.id && this.pending.has(payload.id)) {
        const { resolve, reject } = this.pending.get(payload.id);
        this.pending.delete(payload.id);
        if (payload.error) {
          reject(new Error(`${payload.error.message}: ${JSON.stringify(payload.error.data ?? '')}`));
        } else {
          resolve(payload.result ?? {});
        }
        return;
      }
      if (payload.method && this.handlers.has(payload.method)) {
        for (const handler of this.handlers.get(payload.method)) {
          handler(payload.params ?? {});
        }
      }
    });
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
  }

  on(method, handler) {
    const handlers = this.handlers.get(method) ?? [];
    handlers.push(handler);
    this.handlers.set(method, handlers);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(message);
    });
  }

  close() {
    this.ws?.close();
  }
}

async function waitForChromeVersion() {
  const url = `http://127.0.0.1:${chromePort}/json/version`;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return response.json();
      }
    } catch {
      await delay(150);
    }
  }
  throw new Error('Google Chrome remote debugging endpoint did not become ready.');
}

async function newPageTarget() {
  const response = await fetch(`http://127.0.0.1:${chromePort}/json/new?about:blank`, { method: 'PUT' });
  if (!response.ok) {
    throw new Error(`Failed to create Chrome target: ${response.status}`);
  }
  return response.json();
}

function pageAnalysisScript() {
  const pathname = window.location.pathname;
  const policyByPath = {
    '/creator': { allowedBlankCandidates: 4, mixedLanguageLimit: 12 },
    '/projects': { allowedBlankCandidates: 1, mixedLanguageLimit: 30 },
    '/dashboard': { allowedBlankCandidates: 1, mixedLanguageLimit: 10 },
    '/review': { allowedBlankCandidates: 2, mixedLanguageLimit: 10 },
    '/login': { allowedBlankCandidates: 0, mixedLanguageLimit: 8 },
  };
  const qaPolicy = policyByPath[pathname] ?? { allowedBlankCandidates: 0, mixedLanguageLimit: 8 };
  const px = (value) => {
    const parsed = Number.parseFloat(value || '0');
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const hasMedia = (element) => Boolean(element.querySelector('video, img, canvas, .ant-image'));
  const hasDataDenseTable = (element) => Boolean(element.querySelector('.ant-table, table'));
  const looksLikePathOrId = (text) => (
    text.includes('/Users/')
    || text.includes('/api/')
    || text.includes('.json')
    || text.includes('.mp4')
    || text.includes('.md')
    || /creator_run_\d+/.test(text)
    || /rev_\d+/.test(text)
  );
  const rectPayload = (rect) => ({
    x: Math.round(rect.x),
    y: Math.round(rect.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    area: Math.round(rect.width * rect.height),
  });
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const textOf = (element) => (element.textContent || '').replace(/\s+/g, ' ').trim();
  const allVisible = Array.from(document.querySelectorAll('body *')).filter(isVisible);
  const leafTextElements = allVisible.filter((element) => {
    const text = textOf(element);
    return text && Array.from(element.children).filter(isVisible).length === 0;
  });
  const fontSamples = leafTextElements.slice(0, 900).map((element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      tag: element.tagName.toLowerCase(),
      className: String(element.className || '').slice(0, 120),
      text: textOf(element).slice(0, 80),
      fontSize: Math.round(px(style.fontSize) * 10) / 10,
      fontWeight: style.fontWeight,
      lineHeight: style.lineHeight,
      rect: rectPayload(rect),
    };
  });
  const fontSizeCounts = {};
  for (const sample of fontSamples) {
    fontSizeCounts[sample.fontSize] = (fontSizeCounts[sample.fontSize] ?? 0) + 1;
  }
  const cardLike = Array.from(document.querySelectorAll('.ant-card, .ant-pro-card, .ant-table-wrapper, .ant-alert, .ant-list, .ant-descriptions')).filter(isVisible);
  const containers = cardLike.map((element) => {
    const rect = element.getBoundingClientRect();
    const textLength = textOf(element).length;
    const media = hasMedia(element);
    const table = hasDataDenseTable(element);
    return {
      selector: element.className || element.tagName.toLowerCase(),
      title: textOf(element.querySelector('.ant-card-head-title, .ant-pro-card-title, .ant-alert-message') || element).slice(0, 90),
      rect: rectPayload(rect),
      textLength,
      hasMedia: media,
      hasDataDenseTable: table,
      density: rect.width * rect.height > 0 ? Math.round((textLength / (rect.width * rect.height)) * 1000000) / 100 : 0,
    };
  });
  const blankCandidates = containers
    .filter((item) => item.rect.area > 90000 && item.textLength < 180 && !item.hasMedia && !item.hasDataDenseTable)
    .sort((a, b) => b.rect.area - a.rect.area)
    .slice(0, 8);
  const pageContainer = document.querySelector('.ant-pro-page-container-children-container');
  const pageContainerStyle = pageContainer ? window.getComputedStyle(pageContainer) : null;
  const tables = Array.from(document.querySelectorAll('.ant-table-wrapper')).filter(isVisible).map((element) => {
    const rows = Array.from(element.querySelectorAll('.ant-table-row')).filter(isVisible);
    const rowHeights = rows.map((row) => row.getBoundingClientRect().height).filter(Boolean);
    const avgRowHeight = rowHeights.length
      ? Math.round(rowHeights.reduce((sum, height) => sum + height, 0) / rowHeights.length)
      : 0;
    return {
      rect: rectPayload(element.getBoundingClientRect()),
      rows: rows.length,
      columns: element.querySelectorAll('thead th').length,
      avgRowHeight,
      hasPagination: Boolean(element.querySelector('.ant-pagination')),
    };
  });
  const headings = Array.from(document.querySelectorAll('h1, h2, h3, .ant-pro-page-container-warp-page-header .ant-page-header-heading-title, .ant-card-head-title, .ant-pro-card-title'))
    .filter(isVisible)
    .slice(0, 80)
    .map((element) => {
      const style = window.getComputedStyle(element);
      return {
        text: textOf(element).slice(0, 80),
        fontSize: Math.round(px(style.fontSize) * 10) / 10,
        fontWeight: style.fontWeight,
        rect: rectPayload(element.getBoundingClientRect()),
      };
    });
  const issues = [];
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const scrollHeight = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  const fontSizes = Object.keys(fontSizeCounts).map(Number).sort((a, b) => a - b);
  if (scrollWidth > window.innerWidth + 4) {
    issues.push(`horizontal-overflow:${scrollWidth - window.innerWidth}px`);
  }
  if (fontSizes.length >= 7 || (fontSizes.at(-1) ?? 0) - (fontSizes[0] ?? 0) >= 18) {
    issues.push(`font-scale-fragmented:${fontSizes.join(',')}`);
  }
  if (blankCandidates.length > qaPolicy.allowedBlankCandidates) {
    issues.push(`large-low-density-blocks:${blankCandidates.length}`);
  }
  if (pageContainerStyle && px(pageContainerStyle.paddingTop) >= 24 && px(pageContainerStyle.paddingLeft) >= 24) {
    issues.push(`page-padding-large:${pageContainerStyle.padding}`);
  }
  if (scrollHeight < window.innerHeight * 0.78) {
    issues.push(`underfilled-viewport:${scrollHeight}px`);
  }
  const mixedLanguageElements = leafTextElements.filter((element) => {
    const text = textOf(element);
    if (!/[\u4e00-\u9fff]/.test(text) || !/[A-Za-z]{4,}/.test(text)) {
      return false;
    }
    if (looksLikePathOrId(text)) {
      return false;
    }
    if (text.length > 120) {
      return false;
    }
    return true;
  }).length;
  if (mixedLanguageElements > qaPolicy.mixedLanguageLimit) {
    issues.push(`mixed-cn-en-labels:${mixedLanguageElements}`);
  }
  return {
    url: window.location.href,
    pathname,
    title: document.title,
    qaPolicy,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      scrollWidth,
      scrollHeight,
    },
    bodyTextLength: textOf(document.body).length,
    fontSizeCounts,
    fontSamples: fontSamples.slice(0, 80),
    headings,
    tables,
    containers: containers.slice(0, 60),
    blankCandidates,
    pageContainerPadding: pageContainerStyle ? pageContainerStyle.padding : '',
    issueHints: issues,
  };
}

async function run() {
  await mkdir(reportDir, { recursive: true });
  const chrome = spawn(chromePath, [
    '--headless=new',
    `--remote-debugging-port=${chromePort}`,
    `--user-data-dir=${chromeProfileDir}`,
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=1440,1000',
    'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'] });

  const chromeErrors = [];
  chrome.stderr.on('data', (chunk) => chromeErrors.push(chunk.toString()));
  try {
    const version = await waitForChromeVersion();
    const target = await newPageTarget();
    const client = new CdpClient(target.webSocketDebuggerUrl);
    await client.connect();
    const pageEvents = [];
    const ignoredEventPatterns = [
      /net::ERR_CONNECTION_REFUSED/i,
      /net::ERR_BLOCKED_BY_ORB/i,
      /Failed to load resource: net::ERR_CONNECTION_REFUSED/i,
      /Failed to load resource: net::ERR_BLOCKED_BY_ORB/i,
    ];
    let activeRoute = '';
    client.on('Runtime.consoleAPICalled', (params) => {
      if (['error', 'warning'].includes(params.type)) {
        pageEvents.push({
          route: activeRoute,
          type: `console.${params.type}`,
          text: (params.args || []).map((arg) => arg.value || arg.description || '').join(' ').slice(0, 500),
        });
      }
    });
    client.on('Runtime.exceptionThrown', (params) => {
      pageEvents.push({
        route: activeRoute,
        type: 'exception',
        text: String(params.exceptionDetails?.text || params.exceptionDetails?.exception?.description || '').slice(0, 500),
      });
    });
    client.on('Log.entryAdded', (params) => {
      if (['error', 'warning'].includes(params.entry?.level)) {
        pageEvents.push({
          route: activeRoute,
          type: `log.${params.entry.level}`,
          text: String(params.entry.text || '').slice(0, 500),
        });
      }
    });
    client.on('Network.loadingFailed', (params) => {
      pageEvents.push({
        route: activeRoute,
        type: 'network.failed',
        text: `${params.errorText || 'failed'} ${params.blockedReason || ''}`.trim(),
      });
    });
    await client.send('Page.enable');
    await client.send('Runtime.enable');
    await client.send('Network.enable');
    await client.send('Log.enable');
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });
    if (accessToken) {
      await client.send('Page.addScriptToEvaluateOnNewDocument', {
        source: `
          try {
            localStorage.setItem('aicomic_access_token', ${JSON.stringify(accessToken)});
            localStorage.setItem('aicomic_current_user', ${JSON.stringify(JSON.stringify({
              user_id: 'user_frontend_qa_admin',
              username: 'frontend_qa_admin',
              display_name: 'Frontend QA Admin',
              default_role: 'admin',
            }))});
          } catch (error) {}
        `,
      });
    }

    const pages = [];
    for (const route of routes) {
      activeRoute = route;
      await client.send('Page.navigate', { url: `${frontendBaseUrl}${route}` });
      await delay(route === '/login' ? 2200 : 3200);
      if (accessToken) {
        await client.send('Runtime.evaluate', {
          expression: `
            try {
              localStorage.setItem('aicomic_access_token', ${JSON.stringify(accessToken)});
              localStorage.setItem('aicomic_current_user', ${JSON.stringify(JSON.stringify({
                user_id: 'user_frontend_qa_admin',
                username: 'frontend_qa_admin',
                display_name: 'Frontend QA Admin',
                default_role: 'admin',
              }))});
            } catch (error) {}
          `,
          awaitPromise: true,
        });
      }
      await delay(900);
      const analysis = await client.send('Runtime.evaluate', {
        expression: `(${pageAnalysisScript.toString()})()`,
        returnByValue: true,
        awaitPromise: true,
      });
      const metrics = analysis.result?.value ?? {};
      const screenshot = await client.send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: true,
        fromSurface: true,
      });
      const safeName = route === '/' ? 'root' : route.replace(/^\//, '').replace(/\//g, '_');
      const screenshotPath = path.join(reportDir, `${safeName}.png`);
      await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'));
      const routeEvents = pageEvents.filter((item) => item.route === route);
      const filteredEvents = routeEvents.filter((item) => !ignoredEventPatterns.some((pattern) => pattern.test(item.text)));
      pages.push({
        route,
        screenshotPath,
        eventCount: filteredEvents.length,
        rawEventCount: routeEvents.length,
        events: filteredEvents.slice(0, 20),
        rawEvents: routeEvents.slice(0, 20),
        ...metrics,
      });
    }

    const report = {
      runId,
      runAt: new Date().toISOString(),
      chrome: {
        product: version.Browser,
        userAgent: version['User-Agent'],
        executablePath: chromePath,
      },
      frontendBaseUrl,
      authenticated: Boolean(accessToken),
      viewport: { width: 1440, height: 1000 },
      pages,
      reportDir,
    };
    const reportPath = path.join(reportDir, 'frontend_visual_qa_report.json');
    await writeFile(reportPath, JSON.stringify(report, null, 2));
    console.log(JSON.stringify({
      runId,
      reportPath,
      pageCount: pages.length,
      routes: pages.map((page) => ({
        route: page.route,
        pathname: page.pathname,
        hints: page.issueHints,
        eventCount: page.eventCount,
        screenshotPath: page.screenshotPath,
      })),
    }, null, 2));
    client.close();
  } finally {
    chrome.kill('SIGTERM');
    await delay(300);
    await rm(chromeProfileDir, { recursive: true, force: true });
  }
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
