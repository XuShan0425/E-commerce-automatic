"""Stealth 反检测脚本 — 隐藏 Playwright 自动化指纹.

注入到每个 BrowserContext，对抗:
  - navigator.webdriver 检测
  - window.chrome 缺失检测
  - navigator.plugins 空白检测
  - HeadlessChrome UA 检测
  - Permissions API 泄露
  - WebGL 指纹
  - 阿里系 Baxia 反爬

参考: puppeteer-extra-plugin-stealth, playwright-stealth, 以及阿里安全团队公开专利.
"""

# ═══════════════════════════════════════════════════════════════
# 主注入脚本 (在页面任何 JS 执行前运行)
# ═══════════════════════════════════════════════════════════════

STEALTH_JS = r"""
// ── 1. 隐藏 navigator.webdriver ──────────────
// 这是最基础的检测，阿里 Baxia 会检查
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
});

// ── 2. 伪造 window.chrome ─────────────────────
// 真实 Chrome 一定有 window.chrome.runtime
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {};
}
if (!window.chrome.loadTimes) {
    window.chrome.loadTimes = function() {};
}
if (!window.chrome.csi) {
    window.chrome.csi = function() {};
}
if (!window.chrome.app) {
    window.chrome.app = {};
}

// ── 3. 伪造 navigator.plugins ────────────────
// 真实 Chrome 至少有 PDF Viewer, Chrome PDF Viewer, Native Client
const fakePlugins = [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
];

(function patchPlugins() {
    const oldPlugins = navigator.plugins;

    // 用 Proxy 拦截 plugins 访问
    const pluginArray = Object.setPrototypeOf([
        ...fakePlugins,
    ], PluginArray.prototype);

    // 覆盖 navigator.plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => pluginArray,
    });
})();

// ── 4. 伪造 navigator.mimeTypes ───────────────
const fakeMimeTypes = [
    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
    { type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
];
(function patchMimeTypes() {
    const mimeArray = Object.setPrototypeOf([
        ...fakeMimeTypes,
    ], MimeTypeArray.prototype);
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => mimeArray,
    });
})();

// ── 5. 伪造 navigator.languages ────────────────
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en'],
});

// ── 6. 修复 Permissions.query ──────────────────
// 自动化浏览器可能直接拒绝某些 permission 查询，真实浏览器不会
if (navigator.permissions && navigator.permissions.query) {
    const origQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = function(parameters) {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return origQuery(parameters);
    };
}

// ── 7. 修复 Notification.permission ─────────────
if (!Notification.permission) {
    Object.defineProperty(Notification, 'permission', {
        get: () => 'default',
    });
}

// ── 8. 修复 navigator.platform ──────────────────
// Headless 可能返回 "Win32" → 真实 Chrome 也一样，不用改
// 但确保 navigator.vendor === "Google Inc."
Object.defineProperty(navigator, 'vendor', {
    get: () => 'Google Inc.',
});

// ── 9. 修复 screen 相关属性 ─────────────────────
// 避免暴露 headless 模式下的不匹配
Object.defineProperty(screen, 'colorDepth', {
    get: () => 24,
});
Object.defineProperty(screen, 'pixelDepth', {
    get: () => 24,
});

// ── 10. 修复 navigator.hardwareConcurrency ──────
// 真实机器通常是 4-16，保留原始值即可
// 但确保不为 0 (headless 可能为 0)
if (!navigator.hardwareConcurrency || navigator.hardwareConcurrency < 2) {
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 4,
    });
}

// ── 11. 修复 navigator.deviceMemory ─────────────
if (!navigator.deviceMemory) {
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
    });
}

// ── 12. 拦截 baxia 检测 (阿里专有) ──────────────
// Baxia 会检查多种自动化标记
// 移除任何可能暴露的 CDP runtime 标记
if (window.__nightmare) { delete window.__nightmare; }
if (window._phantom) { delete window._phantom; }
if (window.callPhantom) { delete window.callPhantom; }
if (window.Buffer) { delete window.Buffer; }
if (window.emit) { delete window.emit; }
if (window.spawn) { delete window.spawn; }

// ── 13. 覆盖 toString 欺骗检测 ──────────────────
// 某些检测会 Function.prototype.toString.call(navigator.webdriver) 等方式
const originalFunctionToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === window.alert || this === window.console?.log) {
        return 'function ' + (this.name || '') + '() { [native code] }';
    }
    return originalFunctionToString.call(this);
};

// ── 14. Canvas 指纹混淆 ─────────────────────────
// 轻微噪声化 canvas toDataURL 使指纹不稳定
const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    const ctx = this.getContext('2d');
    if (ctx) {
        const imageData = ctx.getImageData(0, 0, 1, 1);
        if (imageData && imageData.data && imageData.data[3] !== undefined) {
            imageData.data[3] = (imageData.data[3] ^ 1) | 0;
            ctx.putImageData(imageData, 0, 0);
        }
    }
    return origToDataURL.apply(this, arguments);
};

// ── 15. WebGL 指纹混淆 ──────────────────────────
const getParam = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // 修改 UNMASKED_VENDOR_WEBGL 和 UNMASKED_RENDERER_WEBGL
    if (parameter === 37445) {  // UNMASKED_VENDOR_WEBGL
        return 'Intel Inc.';
    }
    if (parameter === 37446) {  // UNMASKED_RENDERER_WEBGL
        return 'Intel Iris OpenGL Engine';
    }
    return getParam.call(this, parameter);
};

// ── 16. 隐藏 automation 相关扩展 ────────────────
Object.defineProperty(navigator, 'userAgent', {
    get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
});

// ── 17. Connection 信息 ─────────────────────────
if (navigator.connection) {
    Object.defineProperty(navigator.connection, 'rtt', {
        get: () => 100,
    });
}
""".strip()
