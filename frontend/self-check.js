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
  'warnings-panel', 'warnings-list', 'warnings-raw', 'warnings-raw-content', 'margin-public-note',
  'data-source-label', 'btn-refresh', 'refresh-countdown',
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

    // 3. 数据说明区可见且渲染三条中文说明
    const warningsDisplay = elements['warnings-panel'].style.display;
    if (warningsDisplay === 'none') throw new Error('数据说明面板被隐藏');
    const marginNote = elements['margin-public-note'].innerHTML;
    if (!marginNote.includes('杠杆可借性未经私有验证')) {
      throw new Error('页面级杠杆可借性说明未渲染');
    }
    const warningsHtml = elements['warnings-list'].innerHTML;
    if (!warningsHtml.includes('isMarginTradingAllowed') || !warningsHtml.includes('已结算历史') || !warningsHtml.includes('bStock')) {
      throw new Error('数据说明中文内容未渲染');
    }
    const rawText = elements['warnings-raw-content'].textContent;
    if (!rawText.includes('lastFundingRate') || !rawText.includes('fapi/v1/fundingRate')) {
      throw new Error('数据说明英文原文未渲染');
    }
    console.log('[PASS] 数据说明区可见且内容已渲染');

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

    // 8. 时间转换正确 (fixture 第一行 next_funding_time 北京时间为 16:00)
    if (!tbodyAll.includes('16:00')) {
      throw new Error('下一次结算时间未正确转换为北京时间 HH:mm');
    }
    console.log('[PASS] 时间转换正确');

    // 9. 列名/文案符合契约
    if (!html.includes('资金费率/结算时间')) {
      throw new Error('缺少“资金费率/结算时间”列名');
    }
    if (html.includes('最近更新的资金费率')) {
      throw new Error('仍保留旧的“最近更新的资金费率”列名');
    }
    if (html.includes('UI 标记')) {
      throw new Error('仍保留旧的“UI 标记”列名');
    }
    console.log('[PASS] 列名/文案符合契约');

    // 10. 无交易按钮/开仓票据
    if (html.includes('手动开仓') || html.includes('下单') || html.includes('开仓')) {
      throw new Error('页面不应包含交易按钮或开仓票据');
    }
    console.log('[PASS] 无交易按钮/开仓票据');

    // 11. 资金费率字符串移位格式化（7 个必测样例）
    const helpers = globalThis.__appHelpers;
    if (!helpers || typeof helpers.formatFundingRate !== 'function') {
      throw new Error('格式化辅助函数未暴露');
    }
    const rateCases = [
      ['0.00010000', '+0.01%'],
      ['-0.00005000', '-0.005%'],
      ['0.00000000', '0%'],
      ['-0.00000000', '0%'],
      ['0', '0%'],
      ['0.00008556', '+0.008556%'],
      ['', '—']
    ];
    for (const [input, expected] of rateCases) {
      const actual = helpers.formatFundingRate(input);
      if (actual !== expected) {
        throw new Error(`formatFundingRate(${JSON.stringify(input)}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    console.log('[PASS] 资金费率格式化 7 个样例');

    // 12. 数据说明中文条目数与 API warnings 数组长度一致
    const chineseItems = [
      '杠杆交易对官方清单需 API key（当前无 key 阶段），杠杆可借性未经私有验证；候选判断使用公开现货 isMarginTradingAllowed 字段。',
      '表中资金费率为本周期实时预估值，将于所示结算时间收取，结算前会漂移；已结算历史以 /fapi/v1/fundingRate 为准。',
      'bStock（美股）合约的现货腿按 baseAsset+B+quoteAsset 别名连接（如 TSLAUSDT → TSLABUSDT）；质押率动态未知，未做任何硬编码。'
    ];
    if (chineseItems.length !== fixture.warnings.length) {
      throw new Error(`数据说明中文条目数 ${chineseItems.length} 与 API warnings 长度 ${fixture.warnings.length} 不一致`);
    }
    console.log('[PASS] 数据说明条目数与 API warnings 一致');

    // 13. MARGIN_PUBLIC_UNVERIFIED 不做行内 badge，其他枚举原值进 title
    if (tbodyAll.includes('MARGIN_PUBLIC_UNVERIFIED')) {
      throw new Error('MARGIN_PUBLIC_UNVERIFIED 不应作为行内 badge 直出');
    }
    if (!tbodyAll.includes('title="PERP_ONLY_NO_SPOT_LEG"') || !tbodyAll.includes('title="TRADIFI_BSTOCK"')) {
      throw new Error('枚举原值未放入 title 属性');
    }
    console.log('[PASS] 提示标记映射正确');

    // 14. 离线 fixture 按钮及文案已删除
    if (html.includes('btn-offline')) {
      throw new Error('仍保留 btn-offline 元素 id');
    }
    if (html.includes('加载离线 fixture')) {
      throw new Error('仍保留“加载离线 fixture”按钮文案');
    }
    console.log('[PASS] 离线 fixture 按钮及文案已删除');

    // 15. 自动刷新 60s 与倒计时元素
    if (!html.includes('60000')) {
      throw new Error('未找到 60000 自动刷新间隔常量');
    }
    if (!html.includes('下次刷新')) {
      throw new Error('未找到“下次刷新”倒计时文案');
    }
    if (!html.includes('Config.cache_ttl_seconds=60')) {
      throw new Error('未注明与后端缓存 TTL 对齐的注释');
    }
    console.log('[PASS] 自动刷新 60s 与倒计时元素存在');

    // 16. 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式
    const enumDisplayChecks = [
      ['MARGIN_SPOT_CANDIDATE(杠杆现货候选)', '路由分类'],
      ['SPOT_ONLY_CANDIDATE(仅现货候选)', '路由分类'],
      ['PERP_ONLY_EXCLUDED(仅合约，排除)', '路由分类'],
      ['CRYPTO(加密货币)', '资产标签'],
      ['BSTOCK(美股代币)', '资产标签'],
      ['PRIVATE_BORROW_VALIDATION_REQUIRED(需私有借币验证)', '负费率状态'],
      ['DISABLED_BSTOCK(禁用:bStock 不可借)', '负费率状态'],
      ['DISABLED_SPOT_ONLY(禁用:无杠杆)', '负费率状态'],
      ['DISABLED_PERP_ONLY(禁用:无现货腿)', '负费率状态']
    ];
    for (const [expected, column] of enumDisplayChecks) {
      if (!tbodyAll.includes(expected)) {
        throw new Error(`${column} 列未渲染预期格式: ${expected}`);
      }
    }
    console.log('[PASS] 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式');

    // 17. 筛选下拉 option 文本使用同格式
    const filterOptions = [
      'CRYPTO(加密货币)',
      'BSTOCK(美股代币)',
      'UNKNOWN(未知)',
      'MARGIN_SPOT_CANDIDATE(杠杆现货候选)',
      'SPOT_ONLY_CANDIDATE(仅现货候选)',
      'PERP_ONLY_EXCLUDED(仅合约，排除)'
    ];
    for (const opt of filterOptions) {
      if (!html.includes(opt)) {
        throw new Error(`筛选下拉缺少 option 文案: ${opt}`);
      }
    }
    console.log('[PASS] 筛选下拉 option 使用「英文枚举(中文解释)」格式');

    // 18. 侧栏品牌已中文化
    if (!html.includes('资金费率对冲')) {
      throw new Error('侧栏品牌未改为“资金费率对冲”');
    }
    console.log('[PASS] 侧栏品牌已中文化');

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);
