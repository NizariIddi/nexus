/**
 * JARVIS Browser Server
 * =====================
 * A persistent Node.js TCP server that keeps Chromium open.
 * Python sends JSON commands, this executes them and returns results.
 * 
 * Start: node browser_server.js
 * Stop:  send {"action":"shutdown"} or Ctrl+C
 */

const puppeteer = require('puppeteer-core');
const net       = require('net');
const fs        = require('fs');
const path      = require('path');

const PORT      = 9009;
const SAVE_DIR  = path.join(process.env.HOME, 'Downloads', 'jarvis_scraped');
const CHROME_PATHS = [
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/snap/bin/chromium',
];

if (!fs.existsSync(SAVE_DIR)) fs.mkdirSync(SAVE_DIR, { recursive: true });

function ts() {
    return new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
}

function findChrome() {
    for (const p of CHROME_PATHS) {
        if (fs.existsSync(p)) return p;
    }
    return null;
}

// ── State ──────────────────────────────────────────────────────────────────
let browser = null;
let page    = null;

async function ensureBrowser() {
    if (browser && page && !page.isClosed()) return;

    const chrome = findChrome();
    if (!chrome) throw new Error(
        'No Chrome/Chromium found.\nInstall: sudo apt install chromium-browser'
    );

    browser = await puppeteer.launch({
        executablePath: chrome,
        headless: false,
        defaultViewport: null,
        args: [
            '--start-maximized',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
        ]
    });

    const pages = await browser.pages();
    page = pages[0] || await browser.newPage();

    // If browser is closed externally, reset state
    browser.on('disconnected', () => {
        browser = null;
        page    = null;
    });
}

// ── Smart element finder ───────────────────────────────────────────────────
async function findElement(sel) {
    // 1. CSS selector
    try {
        const el = await page.$(sel);
        if (el) return el;
    } catch(e) {}

    // 2. Text content match
    try {
        const el = await page.evaluateHandle((s) => {
            const tags = 'button,a,span,div,li,td,th,label,h1,h2,h3,h4,p,input,textarea';
            return Array.from(document.querySelectorAll(tags))
                .find(e => e.innerText && e.innerText.trim().toLowerCase()
                    .includes(s.toLowerCase())) || null;
        }, sel);
        if (el && await el.evaluate(e => !!e)) return el;
    } catch(e) {}

    // 3. Placeholder / name / id / aria-label
    for (const attr of ['placeholder', 'name', 'id', 'aria-label', 'title']) {
        try {
            const el = await page.$(`[${attr}*="${sel}" i]`);
            if (el) return el;
        } catch(e) {}
    }

    // 4. role=button/link with name
    for (const role of ['button', 'link', 'textbox', 'searchbox']) {
        try {
            const el = await page.$(`[role="${role}"]`);
            if (el) {
                const text = await el.evaluate(e => e.innerText || e.value || '');
                if (text.toLowerCase().includes(sel.toLowerCase())) return el;
            }
        } catch(e) {}
    }

    throw new Error(`Could not find element: '${sel}'`);
}

// ── Command handlers ───────────────────────────────────────────────────────
const handlers = {

    async ping() {
        return { output: 'pong' };
    },

    async status() {
        if (!browser || !page || page.isClosed()) {
            return { output: JSON.stringify({ running: false }) };
        }
        return { output: JSON.stringify({
            running: true,
            url: page.url(),
            title: await page.title()
        })};
    },

    async goto({ url }) {
        if (!url) throw new Error('No URL specified.');
        if (!url.startsWith('http')) url = 'https://' + url;
        await ensureBrowser();
        try {
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        } catch(e) {
            if (e.name === 'TimeoutError') {
                // Page partially loaded — that's fine
            } else throw e;
        }
        return { output: `Navigated to: ${page.url()}`, title: await page.title() };
    },

    async go_back() {
        await ensureBrowser();
        await page.goBack({ waitUntil: 'domcontentloaded' });
        return { output: `Went back to: ${page.url()}` };
    },

    async reload() {
        await ensureBrowser();
        await page.reload({ waitUntil: 'domcontentloaded' });
        return { output: `Reloaded: ${page.url()}` };
    },

    async click({ selector }) {
        await ensureBrowser();
        if (!selector) throw new Error('No selector specified.');
        const el = await findElement(selector);
        await el.click();
        await page.waitForTimeout(600);
        return { output: `Clicked: '${selector}'` };
    },

    async type_text({ selector, text, clear = true }) {
        await ensureBrowser();
        if (!selector) throw new Error('No field specified.');
        if (text === undefined || text === '') throw new Error('No text specified.');
        const el = await findElement(selector);
        if (clear) await el.click({ clickCount: 3 });
        await el.type(String(text), { delay: 40 });
        return { output: `Typed in '${selector}': ${String(text).slice(0, 40)}` };
    },

    async fill_form({ fields }) {
        await ensureBrowser();
        if (!fields || typeof fields !== 'object') throw new Error('No fields provided.');
        const filled = [], errors = [];
        for (const [name, value] of Object.entries(fields)) {
            try {
                const el = await findElement(name);
                await el.click({ clickCount: 3 });
                await el.type(String(value), { delay: 20 });
                filled.push(name);
            } catch(e) {
                errors.push(`${name}: ${e.message}`);
            }
        }
        return { output: JSON.stringify({ filled, errors }) };
    },

    async submit({ selector }) {
        await ensureBrowser();
        if (selector) {
            try {
                const el = await findElement(selector);
                await el.click();
            } catch(e) {
                await page.keyboard.press('Enter');
            }
        } else {
            await page.keyboard.press('Enter');
        }
        await page.waitForTimeout(1000);
        return { output: `Submitted. Now at: ${page.url()}` };
    },

    async scroll_down({ amount = 500 }) {
        await ensureBrowser();
        await page.evaluate((a) => window.scrollBy(0, a), amount);
        return { output: `Scrolled down ${amount}px` };
    },

    async scroll_up({ amount = 500 }) {
        await ensureBrowser();
        await page.evaluate((a) => window.scrollBy(0, -a), amount);
        return { output: `Scrolled up ${amount}px` };
    },

    async press_key({ key }) {
        await ensureBrowser();
        if (!key) throw new Error('No key specified.');
        await page.keyboard.press(key);
        await page.waitForTimeout(400);
        return { output: `Pressed: ${key}` };
    },

    async wait({ seconds = 2 }) {
        await ensureBrowser();
        await page.waitForTimeout(seconds * 1000);
        return { output: `Waited ${seconds}s` };
    },

    async get_title() {
        await ensureBrowser();
        return { output: await page.title() };
    },

    async get_url() {
        await ensureBrowser();
        return { output: page.url() };
    },

    async screenshot_page({ filename, full_page = false }) {
        await ensureBrowser();
        filename = filename || `screenshot_${ts()}.png`;
        if (!filename.endsWith('.png')) filename += '.png';
        const filepath = path.join(SAVE_DIR, filename);
        await page.screenshot({ path: filepath, fullPage: full_page });
        return { output: filepath };
    },

    async scrape_text({ selector }) {
        await ensureBrowser();
        let content;
        if (selector) {
            const els = await page.$$(selector);
            const texts = await Promise.all(els.map(e =>
                e.evaluate(n => n.innerText.trim())));
            content = texts.filter(t => t).join('\n');
        } else {
            content = await page.evaluate(() =>
                Array.from(document.querySelectorAll('body *'))
                    .filter(el => el.children.length === 0 && el.innerText.trim())
                    .map(el => el.innerText.trim())
                    .join('\n')
            );
        }
        const filename = path.join(SAVE_DIR, `text_${ts()}.txt`);
        fs.writeFileSync(filename, content, 'utf8');
        const lines   = content.split('\n').filter(l => l.trim());
        const preview = lines.slice(0, 15).join('\n');
        const extra   = lines.length > 15 ? `\n... (${lines.length - 15} more lines)` : '';
        return { output: JSON.stringify({ file: filename, count: lines.length, preview: preview + extra }) };
    },

    async scrape_links({ filter: filt = '' }) {
        await ensureBrowser();
        let links = await page.evaluate(() =>
            Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({ text: a.innerText.trim(), href: a.href }))
                .filter(l => l.href && !l.href.startsWith('javascript'))
        );
        if (filt) links = links.filter(l =>
            l.text.toLowerCase().includes(filt.toLowerCase()) ||
            l.href.toLowerCase().includes(filt.toLowerCase()));
        const seen = new Set();
        links = links.filter(l => { if (seen.has(l.href)) return false; seen.add(l.href); return true; });
        const filename = path.join(SAVE_DIR, `links_${ts()}.csv`);
        const csv = 'text,href\n' + links.map(l =>
            `"${l.text.replace(/"/g, '""')}","${l.href}"`).join('\n');
        fs.writeFileSync(filename, csv, 'utf8');
        const preview = links.slice(0, 20)
            .map(l => `  • ${l.text.slice(0, 40).padEnd(42)} ${l.href.slice(0, 60)}`).join('\n');
        const extra = links.length > 20 ? `\n  ... and ${links.length - 20} more` : '';
        return { output: JSON.stringify({ file: filename, count: links.length, preview: preview + extra }) };
    },

    async scrape_table({ index: idx = 0 }) {
        await ensureBrowser();
        const tables = await page.evaluate(() =>
            Array.from(document.querySelectorAll('table')).map(t =>
                Array.from(t.querySelectorAll('tr')).map(r =>
                    Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim())
                ).filter(r => r.length > 0)
            )
        );
        if (!tables.length) throw new Error('No tables found on this page.');
        if (idx >= tables.length) throw new Error(`Table ${idx} not found. Found ${tables.length}.`);
        const table    = tables[idx];
        const filename = path.join(SAVE_DIR, `table_${idx}_${ts()}.csv`);
        const csv      = table.map(row => row.map(c => `"${c.replace(/"/g,'""')}"`).join(',')).join('\n');
        fs.writeFileSync(filename, csv, 'utf8');
        const preview  = table.slice(0, 8).map(row =>
            '  ' + row.map(c => c.slice(0, 20).padEnd(22)).join(' | ')).join('\n');
        const extra    = table.length > 8 ? `\n  ... and ${table.length - 8} more rows` : '';
        return { output: JSON.stringify({ file: filename, rows: table.length, cols: table[0].length, preview: preview + extra }) };
    },

    async scrape_images() {
        await ensureBrowser();
        const imgs = await page.evaluate(() =>
            Array.from(document.querySelectorAll('img'))
                .map(i => ({ src: i.src, alt: i.alt || '', w: i.naturalWidth, h: i.naturalHeight }))
                .filter(i => i.src && i.src.startsWith('http'))
        );
        const filename = path.join(SAVE_DIR, `images_${ts()}.csv`);
        const csv = 'src,alt,width,height\n' + imgs.map(i =>
            `"${i.src}","${i.alt}","${i.w}","${i.h}"`).join('\n');
        fs.writeFileSync(filename, csv, 'utf8');
        const preview = imgs.slice(0, 10).map(i =>
            `  • ${(i.alt || '(no alt)').slice(0, 30).padEnd(32)} ${i.src.slice(0, 60)}`).join('\n');
        return { output: JSON.stringify({ file: filename, count: imgs.length, preview }) };
    },

    async scrape_data() {
        await ensureBrowser();
        const data = await page.evaluate(() => ({
            title:      document.title,
            url:        window.location.href,
            headings:   Array.from(document.querySelectorAll('h1,h2,h3'))
                            .map(h => ({ tag: h.tagName, text: h.innerText.trim() })).slice(0, 10),
            paragraphs: Array.from(document.querySelectorAll('p'))
                            .map(p => p.innerText.trim()).filter(t => t.length > 30).slice(0, 8),
            tables:     document.querySelectorAll('table').length,
            links:      document.querySelectorAll('a[href]').length,
            images:     document.querySelectorAll('img').length,
        }));
        const filename = path.join(SAVE_DIR, `data_${ts()}.json`);
        fs.writeFileSync(filename, JSON.stringify(data, null, 2), 'utf8');
        return { output: JSON.stringify({ data, file: filename }) };
    },

    async close_browser() {
        if (browser) {
            await browser.close();
            browser = null;
            page    = null;
        }
        return { output: 'Browser closed.' };
    },

    async shutdown() {
        if (browser) await browser.close().catch(() => {});
        server.close();
        process.exit(0);
    },
};

// ── TCP Server ─────────────────────────────────────────────────────────────
const server = net.createServer((socket) => {
    let buffer = '';

    socket.on('data', (chunk) => {
        buffer += chunk.toString();
        // Commands are newline-delimited JSON
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
            if (!line.trim()) continue;
            let cmd;
            try { cmd = JSON.parse(line); } catch(e) {
                socket.write(JSON.stringify({ ok: false, error: 'Invalid JSON' }) + '\n');
                continue;
            }

            const action = cmd.action;
            const params = cmd.params || {};
            const handler = handlers[action];

            if (!handler) {
                socket.write(JSON.stringify({ ok: false, error: `Unknown action: ${action}` }) + '\n');
                continue;
            }

            handler(params)
                .then(result => {
                    socket.write(JSON.stringify({ ok: true, ...result }) + '\n');
                })
                .catch(err => {
                    socket.write(JSON.stringify({ ok: false, error: err.message }) + '\n');
                });
        }
    });

    socket.on('error', () => {});
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`JARVIS Browser Server running on port ${PORT}`);
    console.log(`Chrome: ${findChrome() || 'NOT FOUND'}`);
    console.log('Ready for commands.');
});

server.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
        console.error(`Port ${PORT} already in use. Server may already be running.`);
        process.exit(1);
    }
});

process.on('SIGINT',  async () => { if (browser) await browser.close().catch(()=>{}); process.exit(0); });
process.on('SIGTERM', async () => { if (browser) await browser.close().catch(()=>{}); process.exit(0); });
