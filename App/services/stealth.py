"""Stealth 反检测脚本 — 隐藏 Playwright 自动化指纹.

注入到每个 BrowserContext，对抗:
  - navigator.webdriver 检测
  - window.chrome 缺失检测
  - navigator.plugins 空白检测
  - HeadlessChrome UA 检测
  - Permissions API 泄露
  - WebGL 指纹
  - 阿里系 Baxia 反爬

此外提供:
  - random_delay(): 操作间隔随机延迟 (默认 1-5 秒)
  - MOUSE_TRAJECTORY_JS: 鼠标轨迹模拟注入脚本

参考: puppeteer-extra-plugin-stealth, playwright-stealth, 以及阿里安全团队公开专利.
"""

import random
import time


def random_delay(min_sec: float = 1.0, max_sec: float = 5.0) -> None:
    """执行随机延迟，模拟人类操作间隔。

    用于 data_collector / execution_engine 等模块，
    在每个页面操作之间调用，降低被反爬系统识别的风险。

    参数:
        min_sec: 最小延迟秒数，默认 1.0
        max_sec: 最大延迟秒数，默认 5.0
    """
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

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

# ═══════════════════════════════════════════════════════════════
# 鼠标轨迹模拟脚本 (独立注入，用于需要真人鼠标行为的关键操作)
# ═══════════════════════════════════════════════════════════════

MOUSE_TRAJECTORY_JS = r"""
// ── 鼠标轨迹模拟 ────────────────────────────────
// 使用贝塞尔曲线模拟真实鼠标移动路径
// 每次调用 produceMouseMovement(fromX, fromY, toX, toY) 产生一组
// 带随机抖动的鼠标位置序列，并通过 dispatchEvent 派发 mouseover/mousemove

(function() {
    if (window.__mouseTrajectoryInstalled) return;
    window.__mouseTrajectoryInstalled = true;

    // 贝塞尔曲线插值
    function bezierPoint(t, p0, p1, p2, p3) {
        const u = 1 - t;
        return {
            x: u*u*u*p0.x + 3*u*u*t*p1.x + 3*u*t*t*p2.x + t*t*t*p3.x,
            y: u*u*u*p0.y + 3*u*u*t*p1.y + 3*u*t*t*p2.y + t*t*t*p3.y
        };
    }

    // 生成两个随机控制点，使曲线呈自然弧线
    function randomControlPoints(p0, p3) {
        const dist = Math.sqrt((p3.x-p0.x)**2 + (p3.y-p0.y)**2);
        const jitter = dist * 0.3;
        const angle1 = Math.atan2(p3.y-p0.y, p3.x-p0.x) + (Math.random()-0.5)*1.2;
        const angle2 = angle1 + (Math.random()-0.5)*0.8;
        const len1 = dist * (0.2 + Math.random()*0.3);
        const len2 = dist * (0.2 + Math.random()*0.3);
        return [
            { x: p0.x + Math.cos(angle1)*len1 + (Math.random()-0.5)*jitter,
              y: p0.y + Math.sin(angle1)*len1 + (Math.random()-0.5)*jitter },
            { x: p3.x + Math.cos(angle2+Math.PI)*len2 + (Math.random()-0.5)*jitter,
              y: p3.y + Math.sin(angle2+Math.PI)*len2 + (Math.random()-0.5)*jitter },
        ];
    }

    // 鼠标自然抖动 — 真实鼠标在移动中有微小振动
    function applyTremor(pos, intensity) {
        return {
            x: pos.x + (Math.random()-0.5)*intensity,
            y: pos.y + (Math.random()-0.5)*intensity,
        };
    }

    // 公开接口：模拟鼠标从 (fromX,fromY) 移动到 (toX,toY)
    window.produceMouseMovement = function(fromX, fromY, toX, toY) {
        const p0 = { x: fromX, y: fromY };
        const p3 = { x: toX, y: toY };
        const [p1, p2] = randomControlPoints(p0, p3);

        // 根据距离决定步数，每步约 3-8 像素
        const dist = Math.sqrt((toX-fromX)**2 + (toY-fromY)**2);
        const steps = Math.max(8, Math.floor(dist / (3 + Math.random()*5)));

        // 每步耗时 10-40ms（真人鼠标移动速度）
        const baseStepDelay = 10 + Math.random()*30;

        const events = [];
        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const pt = bezierPoint(t, p0, p1, p2, p3);
            const tremored = applyTremor(pt, 1 + t*0.5);
            // 添加微小随机暂停模拟真实鼠标的微观停顿
            const extra = Math.random() < 0.15 ? Math.random()*40 : 0;
            events.push({
                x: Math.round(tremored.x),
                y: Math.round(tremored.y),
                delay: baseStepDelay + extra,
            });
        }
        return events;
    };

    // 模拟鼠标悬停 (hover) 在元素上
    window.simulateMouseHover = function(element, durationMs) {
        if (!element) return Promise.resolve();
        const rect = element.getBoundingClientRect();
        const cx = rect.left + rect.width/2 + (Math.random()-0.5)*rect.width*0.3;
        const cy = rect.top + rect.height/2 + (Math.random()-0.5)*rect.height*0.3;

        // 派发 mouseover
        element.dispatchEvent(new MouseEvent('mouseover', {
            bubbles: true, clientX: cx, clientY: cy
        }));
        element.dispatchEvent(new MouseEvent('mousemove', {
            bubbles: true, clientX: cx, clientY: cy
        }));
        return new Promise(resolve => setTimeout(resolve, durationMs || (100 + Math.random()*200)));
    };

    // 模拟真实单击 (先 mousedown 再 mouseup，有间隔)
    window.simulateHumanClick = function(element) {
        if (!element) return Promise.resolve();
        const rect = element.getBoundingClientRect();
        const cx = rect.left + rect.width * (0.2 + Math.random()*0.6);
        const cy = rect.top + rect.height * (0.2 + Math.random()*0.6);

        element.dispatchEvent(new MouseEvent('mouseover', {
            bubbles: true, clientX: cx, clientY: cy
        }));
        element.dispatchEvent(new MouseEvent('mousemove', {
            bubbles: true, clientX: cx, clientY: cy
        }));
        element.dispatchEvent(new MouseEvent('mousedown', {
            bubbles: true, clientX: cx, clientY: cy, button: 0, buttons: 1
        }));
        // 真实点击有 50-150ms 的按下延迟
        return new Promise(resolve => {
            setTimeout(() => {
                element.dispatchEvent(new MouseEvent('mouseup', {
                    bubbles: true, clientX: cx, clientY: cy, button: 0
                }));
                // 部分点击附带 click 事件
                if (Math.random() < 0.95) {
                    element.dispatchEvent(new MouseEvent('click', {
                        bubbles: true, clientX: cx, clientY: cy, button: 0
                    }));
                }
                resolve();
            }, 50 + Math.random()*100);
        });
    };

    // 模拟人类双击 (两次单击，间隔 200-400ms)
    window.simulateHumanDblClick = async function(element) {
        await window.simulateHumanClick(element);
        await new Promise(r => setTimeout(r, 200 + Math.random()*200));
        await window.simulateHumanClick(element);
    };
})();
""".strip()
