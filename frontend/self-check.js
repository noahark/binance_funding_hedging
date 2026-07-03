/**
 * 前端自检脚本：在 Node 环境下用 mock DOM 运行 index.html 的内联脚本，
 * 加载 fixture 数据并断言市场表渲染结果。
 *
 * 运行: node frontend/self-check.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

const root = __dirname;
const htmlPath = path.join(root, 'index.html');
const fixturePath = path.join(root, 'fixture', 'public-market-snapshot.json');

const html = fs.readFileSync(htmlPath, 'utf8');
const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

// 提取内联 JS
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('未找到内联脚本');
const script = scriptMatch[1];

// 语法检查
new Function(script);
console.log('[PASS] 内联脚本语法检查');

let fetchUrl = null;

function makeElement(id) {
  const el = {
    id,
    _innerHTML: '',
    _textContent: '',
    _display: '',
    _value: '',
    _checked: false,
    listeners: {},
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = String(v); },
    get textContent() { return this._textContent; },
    set textContent(v) { this._textContent = String(v); },
    get style() {
      const self = this;
      return {
        get display() { return self._display; },
        set display(v) { self._display = String(v); }
      };
    },
    get value() { return this._value; },
    set value(v) { this._value = String(v); },
    get checked() { return this._checked; },
    set checked(v) { this._checked = Boolean(v); },
    addEventListener(type, handler) {
      (this.listeners[type] = this.listeners[type] || []).push(handler);
    }
  };
  return el;
}

const elements = {};
const ids = [
  'warnings-panel', 'warnings-list', 'data-source-label', 'btn-refresh', 'btn-offline',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only',
  'summary-row', 'status-area', 'market-table-body', 'footer-note'
];
ids.forEach(id => { elements[id] = makeElement(id); });

global.document = {
  getElementById: (id) => {
    if (!elements[id]) throw new Error(`未 mock 的元素: ${id}`);
    return elements[id];
  }
};

global.fetch = async (url) => {
  fetchUrl = String(url);
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => fixture
  };
};

// 运行脚本
eval(script);

// 等待 async 渲染
setTimeout(() => {
  try {
    // 1. 默认请求 /api/public-market/snapshot
    if (fetchUrl !== '/api/public-market/snapshot') {
      throw new Error(`默认请求地址错误: ${fetchUrl}`);
    }
    console.log('[PASS] 默认请求 /api/public-market/snapshot');

    // 2. 数据源标签
    const sourceLabel = elements['data-source-label'].textContent;
    if (!sourceLabel.includes('/api/public-market/snapshot')) {
      throw new Error(`数据源标签错误: ${sourceLabel}`);
    }
    console.log('[PASS] 数据源标签显示后端 API');

    // 3. warnings 可见
    const warningsDisplay = elements['warnings-panel'].style.display;
    if (warningsDisplay === 'none' || warningsDisplay === '') {
      // style.display 被设为 '' 表示使用 CSS 默认，即可见；'none' 为隐藏
      if (warningsDisplay === 'none') throw new Error('warnings 面板被隐藏');
    }
    const warningsHtml = elements['warnings-list'].innerHTML;
    if (!warningsHtml.includes('margin') && !warningsHtml.includes('lastFundingRate') && !warningsHtml.includes('TRADIFI_PERPETUAL')) {
      throw new Error('warnings 内容未渲染');
    }
    console.log('[PASS] warnings 可见且内容已渲染');

    // 4. 默认隐藏 PERP_ONLY_EXCLUDED，应渲染 4 行（BTC/ETH/XVG/TSLA）
    const tbody = elements['market-table-body'].innerHTML;
    const rowCount = (tbody.match(/<tr/g) || []).length;
    if (rowCount !== 4) {
      throw new Error(`默认筛选后期望 4 行数据，实际 ${rowCount} 行`);
    }
    console.log('[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 4 行');

    // 5. 打开“显示 PERP_ONLY_EXCLUDED”后应渲染全部 6 行
    const cb = elements['filter-show-perp-only'];
    cb.checked = true;
    (cb.listeners.change || []).forEach(h => h());
    const tbodyAll = elements['market-table-body'].innerHTML;
    const rowCountAll = (tbodyAll.match(/<tr/g) || []).length;
    if (rowCountAll !== 6) {
      throw new Error(`显示 PERP_ONLY_EXCLUDED 后期望 6 行数据，实际 ${rowCountAll} 行`);
    }
    console.log('[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行');

    // 6. BSTOCK 标识
    const bstockCount = (tbodyAll.match(/class="bstock"/g) || []).length;
    if (bstockCount !== 2) {
      throw new Error(`期望 2 行 BSTOCK 标识，实际 ${bstockCount}`);
    }
    console.log('[PASS] BSTOCK 行标识正确');

    // 7. alias 行显示实际现货 symbol 与 B 后缀别名徽章
    if (!tbodyAll.includes('TSLABUSDT')) {
      throw new Error('未渲染实际现货 symbol TSLABUSDT');
    }
    if (!tbodyAll.includes('B 后缀别名')) {
      throw new Error('未渲染 B 后缀别名标识');
    }
    console.log('[PASS] alias 行显示实际现货腿与 B 后缀别名标识');

    // 8. 时间转换正确 (fixture 第一行 next_funding_time 北京时间为 2026-07-03 16:00:00)
    if (!tbodyAll.includes('2026-07-03 16:00:00')) {
      throw new Error('下一次结算时间未正确转换为北京时间');
    }
    console.log('[PASS] 时间转换正确');

    // 9. 列名/文案符合契约
    const htmlUpper = html.toUpperCase();
    if (htmlUpper.includes('已结算') || htmlUpper.includes('预测')) {
      throw new Error('页面文案包含禁止的“已结算”或“预测”');
    }
    if (!html.includes('最近更新的资金费率')) {
      throw new Error('缺少“最近更新的资金费率”列名');
    }
    console.log('[PASS] 列名/文案符合契约');

    // 10. 无交易按钮/开仓票据
    if (html.includes('手动开仓') || html.includes('下单') || html.includes('开仓')) {
      throw new Error('页面不应包含交易按钮或开仓票据');
    }
    console.log('[PASS] 无交易按钮/开仓票据');

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);
