/**
 * app.js - Main Controller for Pacemaker Dashboard
 * 优化版本：添加防抖、文档片段、DOM缓存
 */

(function () {
    'use strict';

    // --- State ---
    let allPatients = [];
    let currentPatient = null;
    let currentTab = 'overview';
    let dataLoadPromise = null;
    let allRecordsLoadPromise = null;
    let detailedAnalyticsLoaded = false;
    let qualityIssues = [];
    let qualityReviewState = {};
    const qualityState = { type: 'all', severity: 'all', status: 'all', search: '' };
    const QUALITY_REVIEW_STORAGE_KEY = 'PacemakerDashboard.qualityReview.v1';
    const QUALITY_REVIEW_STATUSES = Object.freeze({
        pending: '待核查',
        confirmed: '已确认原报告无误',
        corrected: '源文件已修正',
        ignored: '暂时忽略',
    });
    const DISPLAY_SETTINGS_STORAGE_KEY = 'PacemakerDashboard.displaySettings.v1';
    const DISPLAY_SETTINGS_DEFAULTS = Object.freeze({
        density: 'standard',
        listSize: 'standard',
        parameterLabelSize: 'standard',
        parameterValueSize: 'standard',
        conclusionSize: 'standard',
        conclusionWeight: 'strong',
        conclusionTone: 'theme',
    });
    const DISPLAY_SETTINGS_VALUES = Object.freeze({
        density: ['compact', 'standard', 'large'],
        listSize: ['small', 'standard', 'large'],
        parameterLabelSize: ['small', 'standard', 'large'],
        parameterValueSize: ['small', 'standard', 'large'],
        conclusionSize: ['small', 'standard', 'large'],
        conclusionWeight: ['normal', 'strong', 'extra'],
        conclusionTone: ['theme', 'primary', 'contrast'],
    });
    const DISPLAY_SETTINGS_CSS = Object.freeze({
        listSize: { small: '0.88rem', standard: '0.96rem', large: '1.08rem' },
        parameterLabelSize: { small: '0.72rem', standard: '0.8rem', large: '0.9rem' },
        parameterValueSize: { small: '0.84rem', standard: '0.93rem', large: '1.06rem' },
        conclusionSize: { small: '1.1rem', standard: '1.28rem', large: '1.46rem' },
        conclusionWeight: { normal: '650', strong: '750', extra: '800' },
        conclusionTone: {
            theme: 'var(--text-primary)',
            primary: 'var(--primary)',
            contrast: 'var(--text-primary)',
        },
    });
    let displaySettings = { ...DISPLAY_SETTINGS_DEFAULTS };
    const ANON_RECORD_FILENAME = /^P\d{4}\.json$/;

    window.addEventListener('pm:auth-logout', () => {
        allPatients = [];
        currentPatient = null;
        dataLoadPromise = null;
        allRecordsLoadPromise = null;
        detailedAnalyticsLoaded = false;
        qualityIssues = [];
        if (window.PACEMAKER_DATA) window.PACEMAKER_DATA = null;
        dashboardCharts.forEach((chart) => chart.destroy());
        dashboardCharts = [];
    });

    // --- Cached DOM Elements ---
    const dom = {
        list: null,
        search: null,
        count: null,
        sidebar: null,
        main: null,
        detail: null,
        tabs: null,
        panes: null,
        // Dashboard view
        dashboardView: null,
        backBtn: null,
        qualityCenter: null,
        qualityPendingBadge: null,
        qualitySummary: null,
        qualityPipelineWarning: null,
        qualityStatus: null,
        qualityTypeFilter: null,
        qualitySeverityFilter: null,
        qualityStatusFilter: null,
        qualitySearch: null,
        qualityIssueList: null,
        // Detail view elements
        pName: null, pId: null, dBrand: null, dModel: null, dDate: null,
        batStatus: null, batLife: null,
        pacingMode: null, lowerRate: null, upperRate: null,
        visitConclusion: null, nextVisitDate: null,
        amsSwitch: null, atafLoad: null, vtEvents: null, otherEvents: null,
        leadTableBody: null, recordTimeline: null,
        trendsChartCanvas: null
    };

    let chartInstance = null;
    let dashboardCharts = [];

    // 仅允许录入经厂商技术资料和临床流程确认的品牌/型号规则。
    // 未配置型号时只识别报告中的 ERI/EOS/EOL 等设备状态，不以通用电压阈值下结论。
    const CLINICAL_RULES = Object.freeze({
        version: '1.0.0',
        battery: {
            default: {
                voltageThreshold: null,
                criticalKeywords: ['eri', 'eos', 'eol', 'rrt', 'replace', '更换', '需更换', '寿命终止'],
                normalKeywords: ['正常', 'normal', 'ok'],
                evidence: 'status-only'
            },
            brands: {
                '美敦力': { models: {} },
                '雅培': { models: {} },
                '波科': { models: {} },
                '百多力': { models: {} },
                '创领': { models: {} }
            }
        }
    });

    // --- Utility Functions ---

    function escapeHtml(str) {
        if (!str) return '';
        const s = String(str);
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function pathToFileUrl(path) {
        const raw = String(path || '').trim();
        if (!raw) return '';
        const normalized = raw.replace(/^file:\/\//i, '').replace(/\\/g, '/');
        const encoded = encodeURI(normalized).replace(/#/g, '%23').replace(/\?/g, '%3F');
        if (normalized.startsWith('//')) return `file:${encoded}`;
        if (/^[A-Za-z]:\//.test(normalized)) return `file:///${encoded}`;
        return `file://${encoded.startsWith('/') ? '' : '/'}${encoded}`;
    }

    function debounce(func, wait) {
        let timer = null;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function makeTooltipConfig(tc) {
        return {
            backgroundColor: tc.tooltipBg,
            titleColor: tc.tooltipTitle,
            bodyColor: tc.tooltipBody,
            borderColor: tc.tooltipBorder,
            borderWidth: 1,
            padding: 12,
            cornerRadius: tc.isPixel ? 0 : 8
        };
    }

    function parseToTimestamp(dateInput) {
        if (!dateInput) return 0;
        const txt = String(dateInput).trim();
        if (/^\d{1,6}(\.\d+)?$/.test(txt)) {
            const serial = Number(txt);
            if (Number.isFinite(serial) && serial > 25500 && serial < 60000) {
                return new Date((serial - 25569) * 86400 * 1000).getTime();
            }
        }
        const str = txt.replace(/\./g, '-').replace(/年|月/g, '-').replace(/日|号/g, '');
        const ts = Date.parse(str);
        return isNaN(ts) ? 0 : ts;
    }

    function getBatteryRule(brand, model) {
        const brandRule = CLINICAL_RULES.battery.brands[brand] || {};
        const modelRule = brandRule.models?.[model];
        return { ...CLINICAL_RULES.battery.default, ...(brandRule.default || {}), ...(modelRule || {}) };
    }

    function assessBattery(battery, brand, model) {
        const rule = getBatteryRule(brand, model);
        const status = String(battery?.status || '').trim();
        const life = String(battery?.life || '').trim();
        const statusText = `${status} ${life}`.toLowerCase();
        const voltage = battery?.voltage;

        if (rule.criticalKeywords.some(keyword => statusText.includes(keyword.toLowerCase()))) {
            return { level: 'critical', label: '报告提示需关注', reason: status || life || 'ERI/EOS/EOL', rule };
        }
        if (typeof rule.voltageThreshold === 'number' && Number.isFinite(voltage) && voltage < rule.voltageThreshold) {
            return { level: 'critical', label: '型号规则提示需关注', reason: `${voltage.toFixed(2)}V`, rule };
        }
        if (rule.normalKeywords.some(keyword => statusText.includes(keyword.toLowerCase()))) {
            return { level: 'normal', label: '报告状态正常', reason: status, rule };
        }
        return { level: 'review', label: '需人工核对', reason: '未配置可验证的型号级阈值或明确状态', rule };
    }

    function getLatestRawRecord(records) {
        if (!Array.isArray(records) || records.length === 0) return null;
        return records.reduce((latest, current) => {
            const latestDate = latest?.footer_meta?.['程控日期'] || latest?.meta?.['程控日期'];
            const currentDate = current?.footer_meta?.['程控日期'] || current?.meta?.['程控日期'];
            return parseToTimestamp(currentDate) >= parseToTimestamp(latestDate) ? current : latest;
        }, records[0]);
    }

    function formatDate(dateInput) {
        if (!dateInput) return 'Unknown Date';
        let dateObj;
        if (/^\d{5}$/.test(dateInput)) {
            dateObj = new Date((dateInput - 25569) * 86400 * 1000);
        } else {
            const str = String(dateInput).replace(/\./g, '-').replace(/年|月/g, '-').replace(/日|号/g, '');
            const ts = Date.parse(str);
            if (isNaN(ts)) return dateInput;
            dateObj = new Date(ts);
        }
        const y = dateObj.getFullYear();
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function parsePatientData(json) {
        const rawRecords = json['程控记录'] || [];

        const history = rawRecords.map(r => {
            const h = r.header || {};
            const basic = r.basic_params || {};
            const test = r.test_params || {};
            const meas = basic.measurements || {};
            const thresh = test.threshold_tests || {};
            const batt = test.battery_and_leads || {};
            const events = r.events_and_footer || {};
            const meta = r.meta || {};
            const footerMeta = r.footer_meta || {};

            const f = (val) => {
                if (!val) return null;
                const num = parseFloat(val);
                return isNaN(num) ? null : num;
            };

            const rawVisitDate = footerMeta['程控日期'] || meta['程控日期'] || null;
            const rawImplantDate = h['植入日期'] || null;

            return {
                dateStr: rawVisitDate ? formatDate(rawVisitDate) : 'Unknown',
                timestamp: rawVisitDate ? parseToTimestamp(rawVisitDate) : 0,
                implantDateStr: rawImplantDate ? formatDate(rawImplantDate) : '--',
                header: h,
                mode: basic.settings?.['模式'] || '--',
                lowerRate: basic.settings?.['低限频率（次/分）'] || '--',
                upperRate: basic.settings?.['上限跟踪频率（次/分）'] || '--',
                battery: {
                    voltage: f(batt['电池电压（V）']),
                    life: batt['预估寿命'] || '--'
                },
                events: {
                    ams_count: events['模式转换次数'] || events['房室传导模式转换（%）'] || events['运动模式转换（%）'] || null,
                    ams_duration: events['持续最长时间'] || null,
                    ataf_load: events['AT/AF负荷%'] || events['AT/AF负荷'] || null,
                    ataf_count: events['AT/AF事件次数'] || null,
                    ataf_desc: events['快心房率事件说明'] || events['AT/AF事件说明'] || null,
                    vt_count: events['快心室率次数'] || events['快心室率事件次数'] || null,
                    vt_desc: events['快心室率事件说明'] || events['快心室率说明'] || null,
                    other: events['其余事件'] || events['其他事件'] || null,
                    conclusion: events['结论'] || '无记录',
                    next_visit: events['建议下次程控时间'] || '未指定'
                },
                rv_threshold: thresh['右心室_阈值'] || '--',
                lv_threshold: thresh['左心室_阈值'] || '--',
                ra_threshold: thresh['心房_阈值'] || '--',
                rv_impedance: thresh['右心室_阻抗'] || '--',
                lv_impedance: thresh['左心室_阻抗'] || '--',
                ra_impedance: thresh['心房_阻抗'] || '--',
                rv_sense: thresh['右心室_感知'] || '--',
                lv_sense: thresh['左心室_感知'] || '--',
                ra_sense: thresh['心房_感知'] || '--',
                rv_output: meas['右心室_输出电压'] ? `${meas['右心室_输出电压']}V/${meas['右心室_输出脉宽'] || '?'}ms` : '--',
                ra_output: meas['心房_输出电压'] ? `${meas['心房_输出电压']}V/${meas['心房_输出脉宽'] || '?'}ms` : '--',
                lv_output: meas['左心室_输出电压'] ? `${meas['左心室_输出电压']}V/${meas['左心室_输出脉宽'] || '?'}ms` : '--',
                measurement_raw: meas,
                settings_raw: basic.settings || {},
                thresholds_raw: thresh,
                battery_raw: batt,
                events_raw: events,
                header_raw: h,
                footer_meta_raw: footerMeta
            };
        });

        history.sort((a, b) => b.timestamp - a.timestamp);

        const latestRec = history.length > 0 ? history[0] : null;

        return {
            id: json['登记号'],
            name: json['姓名'],
            brand: latestRec ? latestRec.header['品牌'] : 'Unknown',
            model: latestRec ? latestRec.header['型号'] : 'Unknown',
            implantDate: latestRec ? latestRec.implantDateStr : '--',
            history: history,
            file_name: json.file_name
        };
    }

    function renderKeyValue(obj, extraClass = '') {
        if (!obj || Object.keys(obj).length === 0) return '<span class="text-muted text-sm">No data</span>';

        return Object.entries(obj).map(([k, v]) => {
            if (v === null || v === undefined || v === '' || v === '/') return '';

            let displayVal = v;
            let valueHtml = '';
            if (k.includes('日期') || k.includes('时间')) {
                displayVal = formatDate(v);
                valueHtml = escapeHtml(displayVal);
            } else if (typeof v === 'object') {
                valueHtml = `<pre style="margin:0; font-size:0.75rem">${escapeHtml(JSON.stringify(v, null, 2))}</pre>`;
            } else {
                // Extract unit from the key (e.g. "电池电压（V）" -> "V")
                const unitMatch = k.match(/（(.*?)）|\((.*?)\)/);
                let unit = '';

                if (unitMatch) {
                    unit = unitMatch[1] || unitMatch[2];
                } else {
                    // Fallback for missing units based on keyword matching
                    if (k.includes('电压') || k.includes('阈值')) unit = 'V';
                    else if (k.includes('脉宽')) unit = 'ms';
                    else if (k.includes('阻抗')) unit = 'Ω';
                    else if (k.includes('感知') && !k.includes('极性')) unit = 'mV';
                    else if (k.includes('比例') || k.includes('负荷')) unit = '%';
                    else if (k.includes('频率')) unit = '次/分';
                }

                if (unit && !isNaN(parseFloat(v)) && v !== 'OFF' && v !== 'ON' && v !== '依赖') {
                    const safeUnit = escapeHtml(unit);
                    const safeValue = escapeHtml(v);
                    valueHtml = `${safeValue} <span style="font-size:0.8em; color:var(--text-muted)">${safeUnit}</span>`;
                } else {
                    valueHtml = escapeHtml(displayVal);
                }
            }

            const label = k.replace(/（.*?）|\(.*?\)/g, '').replace(/_/g, ' ').replace('电池预估寿命', '预估寿命');
            return `<div class="kv-row ${escapeHtml(extraClass)}"><span class="kv-key">${escapeHtml(label)}</span><span class="kv-val">${valueHtml}</span></div>`;
        }).join('');
    }

    function isRenderableParameterValue(value) {
        return value !== null && value !== undefined && value !== '' && value !== '/';
    }

    function parameterGroupForKey(key, fallback = '其他参数') {
        const text = String(key || '');
        if (/心房|右房|atrium|atrial/i.test(text)) return '心房';
        if (/右心室|右室|\bRV\b|right\s*ventricle/i.test(text)) return '右心室';
        if (/左心室|左室|\bLV\b|left\s*ventricle/i.test(text)) return '左心室';
        if (/心室|ventricle|ventricular/i.test(text)) return '心室';
        return fallback;
    }

    function collectParameterGroups(sources, fallback) {
        const groups = {};
        (sources || []).forEach((source) => {
            if (!source || typeof source !== 'object') return;
            Object.entries(source).forEach(([key, value]) => {
                if (!isRenderableParameterValue(value)) return;
                const group = parameterGroupForKey(key, fallback);
                if (!groups[group]) groups[group] = {};
                groups[group][key] = value;
            });
        });
        return groups;
    }

    function renderParameterGroupCard(title, values) {
        const entries = Object.fromEntries(
            Object.entries(values || {}).filter(([, value]) => isRenderableParameterValue(value)),
        );
        if (Object.keys(entries).length === 0) return '';
        return `<section class="report-chamber-card">
            <h6>${escapeHtml(title)}</h6>
            <div class="kv-grid">${renderKeyValue(entries)}</div>
        </section>`;
    }

    function renderParameterDomain(title, sources, fallback) {
        const groups = collectParameterGroups(sources, fallback);
        const groupOrder = [fallback, '通用设置', '心房', '右心室', '左心室', '心室', '其他参数'];
        const orderedGroups = [...new Set(groupOrder)].filter(group => groups[group]);
        Object.keys(groups).forEach(group => {
            if (!orderedGroups.includes(group)) orderedGroups.push(group);
        });
        const cards = orderedGroups
            .map(group => renderParameterGroupCard(group, groups[group]))
            .join('');
        return `<section class="report-domain">
            <h5>${escapeHtml(title)}</h5>
            <div class="report-chamber-grid">${cards || '<p class="report-empty">本次报告未提供相关参数。</p>'}</div>
        </section>`;
    }

    function renderBatteryAndPacingParameters(record) {
        return `<div class="report-domain-stack">
            ${renderParameterDomain('电池', [record.battery_raw], '电池信息')}
            ${renderParameterDomain('起搏参数', [record.settings_raw, record.measurement_raw], '通用设置')}
        </div>`;
    }

    function renderThresholdParameters(record) {
        return renderParameterDomain('阈值测试', [record.thresholds_raw], '其他参数');
    }

    function isWithheldText(value) {
        return typeof value === 'string' && value.startsWith('[已脱敏：');
    }

    // --- Initialization ---

    function initDOM() {
        dom.list = document.getElementById('patientList');
        dom.search = document.getElementById('patientSearch');
        dom.count = document.getElementById('patientCount');
        dom.sidebar = document.getElementById('sidebar');
        dom.main = document.getElementById('mainContent');
        dom.dashboardView = document.getElementById('dashboardView');
        dom.detail = document.getElementById('patientDetail');
        dom.backBtn = document.getElementById('backToDashboard');
        dom.qualityCenter = document.getElementById('qualityCenter');
        dom.qualityPendingBadge = document.getElementById('qualityPendingBadge');
        dom.qualitySummary = document.getElementById('qualitySummary');
        dom.qualityPipelineWarning = document.getElementById('qualityPipelineWarning');
        dom.qualityStatus = document.getElementById('qualityStatus');
        dom.qualityTypeFilter = document.getElementById('qualityTypeFilter');
        dom.qualitySeverityFilter = document.getElementById('qualitySeverityFilter');
        dom.qualityStatusFilter = document.getElementById('qualityStatusFilter');
        dom.qualitySearch = document.getElementById('qualitySearch');
        dom.qualityIssueList = document.getElementById('qualityIssueList');
        dom.tabs = document.querySelectorAll('.tab-btn');
        dom.panes = document.querySelectorAll('.tab-pane');

        // Cache detail view elements
        dom.pName = document.getElementById('pName');
        dom.pId = document.getElementById('pId');
        dom.dBrand = document.getElementById('dBrand');
        dom.dModel = document.getElementById('dModel');
        dom.dDate = document.getElementById('dDate');
        dom.batStatus = document.getElementById('batStatus');
        dom.batLife = document.getElementById('batLife');
        dom.batIndicator = document.getElementById('batIndicator');
        dom.pacingMode = document.getElementById('pacingMode');
        dom.lowerRate = document.getElementById('lowerRate');
        dom.upperRate = document.getElementById('upperRate');
        dom.visitConclusion = document.getElementById('visitConclusion');
        dom.nextVisitDate = document.getElementById('nextVisitDate');
        dom.amsSwitch = document.getElementById('amsSwitch');
        dom.atafLoad = document.getElementById('atafLoad');
        dom.vtEvents = document.getElementById('vtEvents');
        dom.otherEvents = document.getElementById('otherEvents');
        dom.leadTableBody = document.getElementById('leadTableBody');
        dom.recordTimeline = document.getElementById('recordTimeline');
        dom.trendsChartCanvas = document.getElementById('trendsChart');
    }

    // --- Data Loading ---

    function isLocalFilePreview() {
        return window.location.protocol === 'file:';
    }

    async function waitForAuthorizedSession() {
        const state = window.PM_AUTH?.authenticated !== undefined
            ? window.PM_AUTH
            : await (window.PM_AUTH_READY || Promise.resolve(window.PM_AUTH));
        if (!state?.authenticated) {
            throw new Error('当前会话未获授权，无法读取研究数据。');
        }
        return state;
    }

    function loadLegacyLocalBundle() {
        if (window.PACEMAKER_DATA) return Promise.resolve(window.PACEMAKER_DATA);
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'data/data_bundle.js';
            script.onload = () => {
                if (window.PACEMAKER_DATA) {
                    resolve(window.PACEMAKER_DATA);
                } else {
                    reject(new Error('本地数据包不可用。'));
                }
            };
            script.onerror = () => reject(new Error('无法加载本地预览数据。'));
            document.head.appendChild(script);
        });
    }

    async function loadDataIndex() {
        await waitForAuthorizedSession();
        if (window.PACEMAKER_DATA?.index) return window.PACEMAKER_DATA;
        if (dataLoadPromise) return dataLoadPromise;

        dataLoadPromise = (async () => {
            if (isLocalFilePreview()) {
                return loadLegacyLocalBundle();
            }

            const response = await fetch('data/index.json', {
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (!response.ok || response.redirected) {
                throw new Error('数据访问被拒绝或会话已失效。');
            }
            const index = await response.json();
            if (!Array.isArray(index)) {
                throw new Error('索引文件格式不正确。');
            }
            window.PACEMAKER_DATA = { index, records: {} };
            return window.PACEMAKER_DATA;
        })().catch((error) => {
            dataLoadPromise = null;
            throw error;
        });
        return dataLoadPromise;
    }

    async function loadIndex() {
        const data = await loadDataIndex();
        allPatients = Array.isArray(data.index) ? data.index : [];
        renderList(allPatients);
        renderQualityCenter(data.quality);
    }

    function formatQualityTime(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    }

    function qualitySeverityLabel(severity) {
        return ({ blocker: '阻断', review: '待核查', warning: '警告' })[severity] || '提示';
    }

    function loadQualityReviewState() {
        try {
            const storage = window.localStorage;
            const raw = storage ? storage.getItem(QUALITY_REVIEW_STORAGE_KEY) : '';
            const parsed = raw ? JSON.parse(raw) : {};
            qualityReviewState = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
                ? parsed : {};
        } catch (_) {
            qualityReviewState = {};
        }
    }

    function saveQualityReviewState() {
        try {
            const storage = window.localStorage;
            if (!storage) return false;
            storage.setItem(
                QUALITY_REVIEW_STORAGE_KEY,
                JSON.stringify(qualityReviewState),
            );
            return true;
        } catch (_) {
            return false;
        }
    }

    function loadDisplaySettings() {
        const next = { ...DISPLAY_SETTINGS_DEFAULTS };
        try {
            const storage = window.localStorage;
            const raw = storage ? storage.getItem(DISPLAY_SETTINGS_STORAGE_KEY) : '';
            const parsed = raw ? JSON.parse(raw) : {};
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                Object.keys(DISPLAY_SETTINGS_DEFAULTS).forEach((key) => {
                    const value = parsed[key];
                    if (DISPLAY_SETTINGS_VALUES[key].includes(value)) next[key] = value;
                });
            }
        } catch (_) {
            // File-based offline environments may deny localStorage; defaults remain usable.
        }
        displaySettings = next;
        return next;
    }

    function saveDisplaySettings() {
        try {
            const storage = window.localStorage;
            if (!storage) return false;
            storage.setItem(DISPLAY_SETTINGS_STORAGE_KEY, JSON.stringify(displaySettings));
            return true;
        } catch (_) {
            return false;
        }
    }

    function applyDisplaySettings(nextSettings, persist = true) {
        const next = { ...DISPLAY_SETTINGS_DEFAULTS };
        Object.keys(DISPLAY_SETTINGS_DEFAULTS).forEach((key) => {
            const value = nextSettings?.[key];
            if (DISPLAY_SETTINGS_VALUES[key].includes(value)) next[key] = value;
        });
        displaySettings = next;

        const root = document.documentElement;
        root.setAttribute('data-display-density', next.density);
        root.style.setProperty('--pm-list-font-size', DISPLAY_SETTINGS_CSS.listSize[next.listSize]);
        root.style.setProperty('--pm-param-label-size', DISPLAY_SETTINGS_CSS.parameterLabelSize[next.parameterLabelSize]);
        root.style.setProperty('--pm-param-value-size', DISPLAY_SETTINGS_CSS.parameterValueSize[next.parameterValueSize]);
        root.style.setProperty('--pm-conclusion-size', DISPLAY_SETTINGS_CSS.conclusionSize[next.conclusionSize]);
        root.style.setProperty('--pm-conclusion-weight', DISPLAY_SETTINGS_CSS.conclusionWeight[next.conclusionWeight]);
        root.style.setProperty('--pm-conclusion-color', DISPLAY_SETTINGS_CSS.conclusionTone[next.conclusionTone]);
        if (persist) saveDisplaySettings();
        return next;
    }

    function setupDisplaySettings() {
        const button = document.getElementById('displaySettingsBtn');
        const overlay = document.getElementById('displaySettingsOverlay');
        const closeButton = document.getElementById('displaySettingsClose');
        const resetButton = document.getElementById('displaySettingsReset');
        if (!button || !overlay) return;

        const controls = {
            density: document.getElementById('displayDensitySelect'),
            listSize: document.getElementById('displayListFontSelect'),
            parameterLabelSize: document.getElementById('displayParamLabelSelect'),
            parameterValueSize: document.getElementById('displayParamValueSelect'),
            conclusionSize: document.getElementById('displayConclusionSizeSelect'),
            conclusionWeight: document.getElementById('displayConclusionWeightSelect'),
            conclusionTone: document.getElementById('displayConclusionToneSelect'),
        };
        const status = document.getElementById('displaySettingsStatus');

        function syncControls() {
            Object.keys(controls).forEach((key) => {
                if (controls[key]) controls[key].value = displaySettings[key];
            });
        }

        function setOpen(open) {
            overlay.classList.toggle('hidden', !open);
            button.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (open) {
                syncControls();
                window.setTimeout(() => controls.density?.focus(), 0);
            } else {
                button.focus();
            }
        }

        applyDisplaySettings(loadDisplaySettings(), false);
        syncControls();
        button.addEventListener('click', () => setOpen(overlay.classList.contains('hidden')));
        closeButton?.addEventListener('click', () => setOpen(false));
        overlay.addEventListener('click', (event) => {
            if (event.target === overlay) setOpen(false);
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && !overlay.classList.contains('hidden')) setOpen(false);
        });

        Object.keys(controls).forEach((key) => {
            controls[key]?.addEventListener('change', (event) => {
                applyDisplaySettings({ ...displaySettings, [key]: event.target.value });
                if (status) status.textContent = '已应用，并保存在本机浏览器。';
            });
        });

        resetButton?.addEventListener('click', () => {
            applyDisplaySettings(DISPLAY_SETTINGS_DEFAULTS);
            syncControls();
            if (status) status.textContent = '已恢复默认显示设置。';
        });
    }

    function normalizeQualityReviewStatus(status) {
        return Object.prototype.hasOwnProperty.call(QUALITY_REVIEW_STATUSES, status)
            ? status : 'pending';
    }

    function qualityReviewStatusLabel(status) {
        return QUALITY_REVIEW_STATUSES[normalizeQualityReviewStatus(status)];
    }

    function getQualityIssueKey(issue) {
        const base = issue?.issue_id || [
            issue?.source_path, issue?.filename, issue?.issue_type,
        ].join('|');
        return `${base}|${issue?.detail || ''}|${JSON.stringify(issue?.values || {})}`;
    }

    function getQualityReview(issue) {
        const key = getQualityIssueKey(issue);
        const saved = Object.prototype.hasOwnProperty.call(qualityReviewState, key)
            ? qualityReviewState[key] : {};
        return {
            status: normalizeQualityReviewStatus(saved.status || issue?.status),
            note: typeof saved.note === 'string' ? saved.note : '',
            updatedAt: saved.updatedAt || '',
        };
    }

    function getQualityReviewCounts() {
        const counts = { pending: 0, confirmed: 0, corrected: 0, ignored: 0 };
        qualityIssues.forEach((issue) => {
            counts[getQualityReview(issue).status] += 1;
        });
        counts.handled = counts.confirmed + counts.corrected + counts.ignored;
        return counts;
    }

    function updateQualityPendingBadge() {
        if (!dom.qualityPendingBadge) return;
        const pending = getQualityReviewCounts().pending;
        dom.qualityPendingBadge.textContent = pending > 0 ? `待核查 ${pending}` : '无待核查';
        dom.qualityPendingBadge.classList.toggle('has-issues', pending > 0);
    }

    function renderQualitySummary(summary) {
        if (!dom.qualitySummary) return;
        const counts = getQualityReviewCounts();
        const cards = [
            { key: 'total_files', label: '扫描文件', className: 'neutral' },
            { key: 'matched_files', label: '匹配成功', className: 'success' },
            { key: 'unmatched_files', label: '模板未匹配', className: 'danger' },
            { key: 'total_issues', label: '问题总数', className: 'neutral', value: qualityIssues.length },
            { key: 'pending_local', label: '本机待核查', className: 'warning', value: counts.pending },
            { key: 'confirmed_local', label: '已确认原报告无误', className: 'success', value: counts.confirmed },
            { key: 'corrected_local', label: '源文件已修正', className: 'success', value: counts.corrected },
            { key: 'ignored_local', label: '暂时忽略', className: 'neutral', value: counts.ignored },
        ];
        dom.qualitySummary.innerHTML = cards.map(card => {
            const value = Number(card.value ?? summary?.[card.key] ?? 0);
            return `<div class="quality-stat-card ${card.className}">
                <span class="quality-stat-label">${escapeHtml(card.label)}</span>
                <strong class="quality-stat-value">${Number.isFinite(value) ? value : 0}</strong>
            </div>`;
        }).join('');
    }

    function getFilteredQualityIssues() {
        const term = qualityState.search.trim().toLowerCase();
        return qualityIssues.filter(issue => {
            const review = getQualityReview(issue);
            if (qualityState.type !== 'all' && issue.issue_type !== qualityState.type) return false;
            if (qualityState.severity !== 'all' && issue.severity !== qualityState.severity) return false;
            if (qualityState.status !== 'all' && review.status !== qualityState.status) return false;
            if (!term) return true;
            const values = Object.values(issue.values || {});
            const haystack = [
                issue.issue_type, qualityReviewStatusLabel(review.status), review.note,
                issue.status, issue.filename, issue.source_path,
                issue.patient_name, issue.registration_id, issue.report_date,
                issue.detail, ...values,
            ].join(' ').toLowerCase();
            return haystack.includes(term);
        });
    }

    function renderQualityIssueList() {
        if (!dom.qualityIssueList) return;
        const filtered = getFilteredQualityIssues();
        const total = qualityIssues.length;
        const reviewCounts = getQualityReviewCounts();
        const sourcePath = window.PACEMAKER_DATA?.quality?.summary?.source_dir;
        const updatedAt = window.PACEMAKER_DATA?.quality?.summary?.matching_report_updated_at;
        const metadata = [
            `显示 ${filtered.length}/${total} 条问题`,
            `本机待核查 ${reviewCounts.pending}`,
            `已处理 ${reviewCounts.handled}`,
            sourcePath ? `数据源：${sourcePath}` : '',
            updatedAt ? `匹配报告：${formatQualityTime(updatedAt)}` : '',
        ].filter(Boolean).join('　');
        if (dom.qualityStatus) dom.qualityStatus.textContent = metadata;

        if (filtered.length === 0) {
            dom.qualityIssueList.innerHTML = total === 0
                ? '<div class="quality-empty success">✓ 当前未发现需要人工核查的问题。</div>'
                : '<div class="quality-empty">没有符合当前筛选条件的问题。</div>';
            return;
        }

        dom.qualityIssueList.innerHTML = filtered.map(issue => {
            const severityClass = ['blocker', 'review', 'warning'].includes(issue.severity)
                ? issue.severity : 'info';
            const issueKey = getQualityIssueKey(issue);
            const review = getQualityReview(issue);
            const valuesHtml = Object.entries(issue.values || {})
                .filter(([, value]) => String(value || '').trim())
                .map(([label, value]) => `<span class="quality-value"><b>${escapeHtml(label)}</b>${escapeHtml(value)}</span>`)
                .join('');
            const path = String(issue.source_path || '');
            const pathHtml = path
                ? `<code>${escapeHtml(path)}</code><span class="quality-source-actions"><button type="button" class="quality-open-path" data-open-path="${escapeHtml(path)}">打开文件</button><button type="button" class="quality-copy-path" data-copy-path="${escapeHtml(path)}">复制路径</button></span>`
                : '<span class="quality-no-path">未提供完整来源路径</span>';
            const statusOptions = Object.entries(QUALITY_REVIEW_STATUSES)
                .map(([value, label]) => `<option value="${value}"${review.status === value ? ' selected' : ''}>${escapeHtml(label)}</option>`)
                .join('');
            const reviewUpdated = review.updatedAt
                ? `上次保存：${formatQualityTime(review.updatedAt)}` : '尚未记录本机核查状态';
            return `<article class="quality-issue quality-issue-${severityClass}" data-quality-issue-id="${escapeHtml(issueKey)}">
                <div class="quality-issue-header">
                    <div class="quality-issue-title">
                        <span class="quality-severity quality-severity-${severityClass}">${escapeHtml(qualitySeverityLabel(issue.severity))}</span>
                        <strong>${escapeHtml(issue.issue_type || '数据质量问题')}</strong>
                    </div>
                    <span class="quality-issue-status">${escapeHtml(qualityReviewStatusLabel(review.status))}</span>
                </div>
                <div class="quality-issue-meta">
                    <span>${escapeHtml(issue.patient_name || '未识别患者')}</span>
                    <span>${escapeHtml(issue.registration_id ? `登记号 ${issue.registration_id}` : '登记号未提取')}</span>
                    <span>${escapeHtml(issue.report_date || '日期未提取')}</span>
                    <span class="quality-filename">${escapeHtml(issue.filename || '未提供文件名')}</span>
                </div>
                <p class="quality-issue-detail">${escapeHtml(issue.detail || '请打开原始报告人工核对。')}</p>
                ${valuesHtml ? `<div class="quality-values">${valuesHtml}</div>` : ''}
                <div class="quality-issue-source"><span>来源：</span>${pathHtml}</div>
                <div class="quality-review-controls">
                    <label>人工状态
                        <select data-review-status aria-label="人工核查状态">${statusOptions}</select>
                    </label>
                    <label class="quality-review-note">核查备注
                        <input type="text" data-review-note value="${escapeHtml(review.note)}" placeholder="暂时忽略时必须填写原因">
                    </label>
                    <button type="button" class="quality-save-review" data-save-review>保存核查状态</button>
                    <span class="quality-review-updated">${escapeHtml(reviewUpdated)}</span>
                </div>
            </article>`;
        }).join('');
    }

    function renderQualityCenter(quality) {
        if (!dom.qualityCenter) return;
        if (!quality || quality.available !== true) {
            dom.qualityCenter.classList.add('hidden');
            return;
        }

        dom.qualityCenter.classList.remove('hidden');
        qualityIssues = Array.isArray(quality.issues) ? quality.issues : [];
        if (dom.qualityCenter) dom.qualityCenter.open = false;
        qualityState.type = 'all';
        qualityState.severity = 'all';
        qualityState.status = 'all';
        qualityState.search = '';
        if (dom.qualitySearch) dom.qualitySearch.value = '';
        if (dom.qualitySeverityFilter) dom.qualitySeverityFilter.value = 'all';
        if (dom.qualityStatusFilter) dom.qualityStatusFilter.value = 'all';
        if (dom.qualityTypeFilter) {
            const types = [...new Set(qualityIssues.map(issue => issue.issue_type).filter(Boolean))].sort();
            dom.qualityTypeFilter.innerHTML = '<option value="all">全部问题</option>' + types
                .map(type => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`)
                .join('');
            dom.qualityTypeFilter.value = 'all';
        }
        renderQualitySummary(quality.summary || {});
        updateQualityPendingBadge();
        if (dom.qualityPipelineWarning) {
            const warning = String(quality.pipeline_warning || '').trim();
            dom.qualityPipelineWarning.textContent = warning
                ? `本轮处理未完整成功：${warning} 当前页面仍显示上一次稳定患者数据，以下问题请人工核查。`
                : '';
            dom.qualityPipelineWarning.classList.toggle('hidden', !warning);
        }
        renderQualityIssueList();
    }

    async function loadPatientRecord(filename) {
        const data = await loadDataIndex();
        if (data.records?.[filename]) return data.records[filename];

        if (isLocalFilePreview()) {
            throw new Error('本地数据包中未找到该记录。');
        }
        if (!ANON_RECORD_FILENAME.test(String(filename))) {
            throw new Error('无效的脱敏记录标识。');
        }

        const response = await fetch('data/records/' + encodeURIComponent(filename), {
            credentials: 'same-origin',
            cache: 'no-store',
        });
        if (!response.ok || response.redirected) {
            throw new Error('逐例记录访问被拒绝或会话已失效。');
        }
        const record = await response.json();
        if (!record || typeof record !== 'object') {
            throw new Error('逐例记录格式不正确。');
        }
        data.records[filename] = record;
        return record;
    }

    async function loadPatientDetails(filename) {
        try {
            const data = await loadPatientRecord(filename);
            currentPatient = parsePatientData(data);
            renderPatient(currentPatient);
            const overviewTab = document.querySelector('.tab-btn[data-tab="overview"]');
            if (overviewTab) handleTabClick(overviewTab);
            showPatientDetail();
        } catch (err) {
            console.error(err);
            alert('无法加载该患者的脱敏记录：' + (err.message || '未知错误'));
        }
    }

    async function loadAllRecordsForResearch() {
        await loadDataIndex();
        if (allRecordsLoadPromise) return allRecordsLoadPromise;

        const filenames = allPatients
            .map((patient) => patient.file_name)
            .filter((filename) => filename && !window.PACEMAKER_DATA.records?.[filename]);

        allRecordsLoadPromise = (async () => {
            let nextIndex = 0;
            const workers = Array.from(
                { length: Math.min(6, filenames.length) },
                async () => {
                    while (nextIndex < filenames.length) {
                        const filename = filenames[nextIndex];
                        nextIndex += 1;
                        await loadPatientRecord(filename);
                    }
                },
            );
            await Promise.all(workers);
            return window.PACEMAKER_DATA.records;
        })().catch((error) => {
            allRecordsLoadPromise = null;
            throw error;
        });
        return allRecordsLoadPromise;
    }

    function setResearchAnalyticsStatus(message, isError = false) {
        const status = document.getElementById('researchAnalyticsStatus');
        if (!status) return;
        status.textContent = message;
        status.classList.toggle('error', isError);
    }

    async function loadResearchAnalytics() {
        const button = document.getElementById('loadResearchAnalytics');
        if (button) {
            button.disabled = true;
            button.textContent = '加载中…';
        }
        setResearchAnalyticsStatus('正在按需加载脱敏逐例记录并生成研究统计…');
        try {
            await loadAllRecordsForResearch();
            detailedAnalyticsLoaded = true;
            renderDeepCharts();
            renderLeadCharts();
            setResearchAnalyticsStatus('已加载 ' + Object.keys(window.PACEMAKER_DATA.records).length + ' 份脱敏记录。');
        } catch (error) {
            console.error(error);
            setResearchAnalyticsStatus('研究统计加载失败：' + (error.message || '未知错误'), true);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = detailedAnalyticsLoaded ? '重新生成研究统计' : '重试加载';
            }
        }
    }

    // --- View Switching ---

    function showDashboard() {
        dom.dashboardView.classList.remove('hidden');
        dom.detail.classList.add('hidden');
        document.body.classList.remove('detail-open');
        document.querySelectorAll('.patient-item').forEach(i => i.classList.remove('active'));
        currentPatient = null;
        requestAnimationFrame(resizeAllCharts);
    }

    function showPatientDetail() {
        dom.dashboardView.classList.add('hidden');
        dom.detail.classList.remove('hidden');
        document.body.classList.add('detail-open');
        if (dom.main && dom.main.scrollTo) {
            dom.main.scrollTo({ top: 0, behavior: 'auto' });
        }
        window.scrollTo({ top: 0, behavior: 'auto' });
        setTimeout(resizeAllCharts, 120);
        setTimeout(resizeAllCharts, 360);
    }

    // --- Dashboard Statistics ---

    function isMobileViewport() {
        return window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
    }

    function getChartMetrics() {
        const mobile = isMobileViewport();
        return {
            mobile,
            legendFont: mobile ? 11 : 13,
            legendPadding: mobile ? 10 : 16,
            tickFont: mobile ? 11 : 12,
            barThickness: mobile ? 16 : 20,
            modelLabelLimit: mobile ? 16 : 30
        };
    }

    function truncateChartLabel(value, limit) {
        const text = String(value || '');
        return text.length > limit ? `${text.slice(0, limit)}...` : text;
    }

    function resizeAllCharts() {
        const charts = [chartInstance, ...dashboardCharts, ...deepCharts, ...leadParamCharts].filter(Boolean);
        charts.forEach(chart => chart.resize());
    }

    function getThemeColors() {
        const ct = document.documentElement.getAttribute('data-theme');
        if (ct === 'pixel') {
            return {
                isDark: false,
                isPixel: true,
                text: '#536B65',
                grid: 'rgba(65, 104, 94, 0.14)',
                tooltipBg: '#FFFDF5',
                tooltipTitle: '#28433B',
                tooltipBody: '#536B65',
                tooltipBorder: '#648F84'
            };
        }
        const isSysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const isDark = ct === 'dark' || (!ct && isSysDark);
        return {
            isDark,
            isPixel: false,
            text: isDark ? '#CBD5E1' : '#718096',
            grid: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
            tooltipBg: isDark ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.95)',
            tooltipTitle: isDark ? '#F8FAFC' : '#1E293B',
            tooltipBody: isDark ? '#CBD5E1' : '#64748B',
            tooltipBorder: isDark ? '#334155' : '#E2E8F0'
        };
    }

    const CHART_PALETTE = [
        '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
        '#EC4899', '#06B6D4', '#F97316', '#14B8A6', '#6366F1',
        '#84CC16', '#E11D48', '#0EA5E9', '#A855F7', '#22D3EE'
    ];

    const PIXEL_CHART_PALETTE = [
        '#4D9B8A', '#E5A95B', '#6F95C8', '#D97675', '#8F79B8',
        '#74A76F', '#C97C9A', '#62AAB2', '#C88855', '#7A88B5',
        '#9AAE67', '#B86773', '#5B9CC0', '#A77DA5', '#67A79B'
    ];

    function getChartPalette() {
        return document.documentElement.getAttribute('data-theme') === 'pixel'
            ? PIXEL_CHART_PALETTE
            : CHART_PALETTE;
    }

    function aggregateStats(patients) {
        const brandMap = {};
        const modelMap = {};
        const modelToBrandMap = {};
        const yearMap = {};
        const visitBuckets = { '1次': 0, '2次': 0, '3次': 0, '4次': 0, '5次+': 0 };
        const ageBuckets = { '<1年': 0, '1-3年': 0, '3-5年': 0, '5-10年': 0, '10年+': 0, '未知': 0 };
        let latestDate = '';
        let totalVisits = 0;

        patients.forEach(p => {
            // Brand
            const b = p.brand || '未知';
            brandMap[b] = (brandMap[b] || 0) + 1;

            // Model
            const m = p.model || '未知';
            modelMap[m] = (modelMap[m] || 0) + 1;
            if (m !== '未知') {
                modelToBrandMap[m] = p.brand || '未知';
            }

            // Visits
            const cnt = p.count || 1;
            totalVisits += cnt;
            if (cnt >= 5) visitBuckets['5次+']++;
            else visitBuckets[cnt + '次']++;

            // Implant date parsing
            const ts = parseToTimestamp(p.implant_date);
            if (ts > 0) {
                const d = new Date(ts);
                const yr = d.getFullYear();
                if (yr >= 2000 && yr <= 2030) {
                    yearMap[yr] = (yearMap[yr] || 0) + 1;
                    const dateStr = formatDate(p.implant_date);
                    if (dateStr > latestDate) latestDate = dateStr;

                    // Device age
                    const ageYears = (Date.now() - ts) / (365.25 * 24 * 3600 * 1000);
                    if (ageYears < 1) ageBuckets['<1年']++;
                    else if (ageYears < 3) ageBuckets['1-3年']++;
                    else if (ageYears < 5) ageBuckets['3-5年']++;
                    else if (ageYears < 10) ageBuckets['5-10年']++;
                    else ageBuckets['10年+']++;
                } else {
                    ageBuckets['未知']++;
                }
            } else {
                ageBuckets['未知']++;
            }
        });

        // Sort years
        const years = Object.keys(yearMap).map(Number).sort((a, b) => a - b);
        const yearLabels = years.map(String);
        const yearValues = years.map(y => yearMap[y]);

        // Model top 10
        const modelSorted = Object.entries(modelMap).sort((a, b) => b[1] - a[1]).slice(0, 10);

        return {
            total: patients.length,
            brandCount: Object.keys(brandMap).length,
            avgVisits: patients.length > 0 ? (totalVisits / patients.length).toFixed(1) : 0,
            latestDate: latestDate || '--',
            brandLabels: Object.keys(brandMap),
            brandValues: Object.values(brandMap),
            modelLabels: modelSorted.map(e => e[0]),
            modelValues: modelSorted.map(e => e[1]),
            modelToBrand: modelToBrandMap,
            yearLabels,
            yearValues,
            visitLabels: Object.keys(visitBuckets),
            visitValues: Object.values(visitBuckets),
            ageLabels: Object.keys(ageBuckets),
            ageValues: Object.values(ageBuckets)
        };
    }

    function animateValue(el, target, suffix) {
        suffix = suffix || '';
        const isFloat = String(target).includes('.');
        const duration = 800;
        const start = performance.now();
        const end = parseFloat(target);
        if (isNaN(end)) { el.textContent = target; return; }
        function step(now) {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const val = eased * end;
            el.textContent = (isFloat ? val.toFixed(1) : Math.round(val)) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    function renderDashboard() {
        if (!allPatients || allPatients.length === 0) return;

        const stats = aggregateStats(allPatients);
        const tc = getThemeColors();
        const cm = getChartMetrics();
        const chartPalette = getChartPalette();

        // KPI animation
        animateValue(document.getElementById('kpiTotalPatients'), stats.total);
        animateValue(document.getElementById('kpiBrandCount'), stats.brandCount);
        animateValue(document.getElementById('kpiAvgVisits'), stats.avgVisits);
        document.getElementById('kpiLatestImplant').textContent = stats.latestDate;

        // Destroy old charts
        dashboardCharts.forEach(c => c.destroy());
        dashboardCharts = [];

        const commonTooltip = makeTooltipConfig(tc);

        // 1. Brand Doughnut
        dashboardCharts.push(new Chart(document.getElementById('chartBrand'), {
            type: 'doughnut',
            data: {
                labels: stats.brandLabels,
                datasets: [{
                    data: stats.brandValues,
                    backgroundColor: chartPalette.slice(0, stats.brandLabels.length),
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { display: false, position: 'bottom', labels: { color: tc.text, padding: cm.legendPadding, usePointStyle: true, pointStyleWidth: 8, font: { size: cm.legendFont } } },
                    tooltip: commonTooltip
                }
            }
        }));

        // 2. Model Top 10 - Horizontal Bar
        dashboardCharts.push(new Chart(document.getElementById('chartModel'), {
            type: 'bar',
            data: {
                labels: stats.modelLabels,
                datasets: [{
                    data: stats.modelValues,
                    backgroundColor: chartPalette.slice(0, stats.modelLabels.length).map(c => c + '99'),
                    borderColor: chartPalette.slice(0, stats.modelLabels.length),
                    borderWidth: 1,
                    borderRadius: tc.isPixel ? 0 : 4,
                    barThickness: cm.barThickness
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                layout: {
                    padding: { left: 20 } // 增大左侧安全间距，防止较长的中文字符被画布截断
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...commonTooltip,
                        callbacks: {
                            title: function (context) {
                                const modelLabel = context[0].label;
                                const brand = stats.modelToBrand[modelLabel] || '';
                                return brand && brand !== '未知' ? `${brand} ${modelLabel}` : modelLabel;
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { color: tc.grid }, ticks: { color: tc.text, stepSize: 1 }, beginAtZero: true },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: tc.text,
                            font: { family: "system-ui, -apple-system, sans-serif", size: cm.tickFont },
                            padding: 8,
                            crossAlign: 'near',
                            callback: function (value, index, values) {
                                const modelLabel = this.getLabelForValue(value);
                                const brand = stats.modelToBrand[modelLabel] || '';
                                const label = brand && brand !== '未知' ? `${brand} ${modelLabel}` : modelLabel;
                                return truncateChartLabel(label, cm.modelLabelLimit);
                            }
                        }
                    }
                }
            }
        }));

        // 3. Year Trend - Area Chart
        dashboardCharts.push(new Chart(document.getElementById('chartYearTrend'), {
            type: 'line',
            data: {
                labels: stats.yearLabels,
                datasets: [{
                    label: '植入数量',
                    data: stats.yearValues,
                    borderColor: tc.isPixel ? chartPalette[2] : '#3B82F6',
                    backgroundColor: tc.isPixel ? 'rgba(111,149,200,0.16)' : (tc.isDark ? 'rgba(59,130,246,0.15)' : 'rgba(59,130,246,0.1)'),
                    fill: true,
                    tension: tc.isPixel ? 0 : 0.4,
                    pointStyle: tc.isPixel ? 'rect' : 'circle',
                    pointBackgroundColor: tc.isPixel ? chartPalette[2] : '#3B82F6',
                    pointRadius: 4,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 4. Visit Distribution - Bar
        dashboardCharts.push(new Chart(document.getElementById('chartVisitDist'), {
            type: 'bar',
            data: {
                labels: stats.visitLabels,
                datasets: [{
                    label: '患者数',
                    data: stats.visitValues,
                    backgroundColor: chartPalette.slice(0, 5).map(c => c + '99'),
                    borderColor: chartPalette.slice(0, 5),
                    borderWidth: 1,
                    borderRadius: tc.isPixel ? 0 : 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 5. Device Age - Doughnut
        const ageColors = ['#06B6D4', '#3B82F6', '#8B5CF6', '#F59E0B', '#EF4444', '#94A3B8'];
        dashboardCharts.push(new Chart(document.getElementById('chartDeviceAge'), {
            type: 'doughnut',
            data: {
                labels: stats.ageLabels,
                datasets: [{
                    data: stats.ageValues,
                    backgroundColor: ageColors,
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, padding: cm.legendPadding, usePointStyle: true, pointStyleWidth: 8, font: { size: cm.legendFont } } },
                    tooltip: commonTooltip
                }
            }
        }));
    }

    // --- Deep Clinical Statistics ---

    let deepCharts = [];

    function aggregateDeepStats() {
        const records = window.PACEMAKER_DATA?.records;
        if (!detailedAnalyticsLoaded || !records) return null;

        const modeMap = {};
        const voltages = [];       // { name, id, voltage, file_name }
        const monthMap = {};       // 'YYYY-MM' -> count
        const afBuckets = { '无记录': 0, '0%': 0, '<1%': 0, '1-10%': 0, '10-50%': 0, '>50%': 0 };
        const batteryAlerts = [];  // explicit ERI/EOS/EOL or model-validated alerts
        let batteryReviewCount = 0;

        Object.entries(records).forEach(([filename, patient]) => {
            const recs = patient['程控记录'] || [];
            if (recs.length === 0) return;

            // Use latest record for mode/battery/AF
            const latest = getLatestRawRecord(recs);
            const name = patient['姓名'] || '未知';
            const pid = patient['登记号'] || '';
            const brand = latest.header?.['品牌'] || patient['品牌'] || '未知';
            const model = latest.header?.['型号'] || patient['型号'] || '未知';

            // Pacing Mode
            const mode = latest.basic_params?.settings?.['模式'];
            if (mode && mode !== '/' && mode !== '--') {
                const modeClean = mode.trim().toUpperCase();
                modeMap[modeClean] = (modeMap[modeClean] || 0) + 1;
            }

            // Battery Voltage
            const batt = latest.test_params?.battery_and_leads;
            const vStr = batt?.['电池电压（V）'] || batt?.['电池电压(V)'] || batt?.['电池电压'];
            if (vStr) {
                const v = parseFloat(vStr);
                if (!isNaN(v) && v > 0 && v < 5) {
                    voltages.push({ name, id: pid, voltage: v, file_name: filename });
                }
            }
            const assessment = assessBattery({
                voltage: vStr ? parseFloat(vStr) : null,
                status: batt?.['电池状态'] || '',
                life: batt?.['预估寿命'] || batt?.['电池预估寿命'] || ''
            }, brand, model);
            if (assessment.level === 'critical') {
                batteryAlerts.push({
                    name, id: pid, voltage: vStr ? parseFloat(vStr) : null,
                    status: assessment.reason, file_name: filename, brand, model
                });
            } else if (assessment.level === 'review') {
                batteryReviewCount++;
            }

            // AT/AF Burden
            const ev = latest.events_and_footer || {};
            const afRaw = ev['AT/AF负荷%'] || ev['AT/AF负荷'];
            if (afRaw !== undefined && afRaw !== null && afRaw !== '' && afRaw !== '/') {
                const afVal = parseFloat(String(afRaw).replace('%', '').trim());
                if (!isNaN(afVal) && afVal >= 0 && afVal <= 100) {
                    if (afVal === 0) afBuckets['0%']++;
                    else if (afVal < 1) afBuckets['<1%']++;
                    else if (afVal < 10) afBuckets['1-10%']++;
                    else if (afVal < 50) afBuckets['10-50%']++;
                    else afBuckets['>50%']++;
                } else {
                    afBuckets['无记录']++;
                }
            } else {
                afBuckets['无记录']++;
            }

            // Monthly visit dates (all records)
            recs.forEach(r => {
                const rawDate = r.footer_meta?.['程控日期'] || r.meta?.['程控日期'];
                if (rawDate) {
                    const ts = parseToTimestamp(rawDate);
                    if (ts > 0) {
                        const d = new Date(ts);
                        const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
                        monthMap[key] = (monthMap[key] || 0) + 1;
                    }
                }
            });
        });

        // Sort modes by count
        const modeSorted = Object.entries(modeMap).sort((a, b) => b[1] - a[1]);

        // Voltage distribution buckets
        const voltBuckets = { '<2.4V': 0, '2.4-2.6V': 0, '2.6-2.8V': 0, '2.8-3.0V': 0, '3.0-3.2V': 0, '>3.2V': 0 };
        voltages.forEach(v => {
            if (v.voltage < 2.4) voltBuckets['<2.4V']++;
            else if (v.voltage < 2.6) voltBuckets['2.4-2.6V']++;
            else if (v.voltage < 2.8) voltBuckets['2.6-2.8V']++;
            else if (v.voltage < 3.0) voltBuckets['2.8-3.0V']++;
            else if (v.voltage < 3.2) voltBuckets['3.0-3.2V']++;
            else voltBuckets['>3.2V']++;
        });

        // Sort monthly timeline
        const months = Object.keys(monthMap).sort();

        // Sort alerts by voltage ascending (most critical first)
        batteryAlerts.sort((a, b) => a.voltage - b.voltage);

        return {
            modeLabels: modeSorted.map(e => e[0]),
            modeValues: modeSorted.map(e => e[1]),
            voltLabels: Object.keys(voltBuckets),
            voltValues: Object.values(voltBuckets),
            monthLabels: months,
            monthValues: months.map(m => monthMap[m]),
            afLabels: Object.keys(afBuckets),
            afValues: Object.values(afBuckets),
            batteryAlerts,
            batteryReviewCount
        };
    }

    function renderDeepCharts() {
        const ds = aggregateDeepStats();
        if (!ds) return;

        const tc = getThemeColors();
        const cm = getChartMetrics();
        const chartPalette = getChartPalette();

        // Destroy old deep charts
        deepCharts.forEach(c => c.destroy());
        deepCharts = [];

        const commonTooltip = makeTooltipConfig(tc);

        // 1. Pacing Mode - Doughnut
        const modeColors = tc.isPixel ? chartPalette : [
            '#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
            '#EC4899', '#06B6D4', '#F97316', '#14B8A6', '#6366F1',
            '#84CC16', '#E11D48', '#0EA5E9', '#A855F7', '#22D3EE'
        ];
        deepCharts.push(new Chart(document.getElementById('chartPacingMode'), {
            type: 'doughnut',
            data: {
                labels: ds.modeLabels,
                datasets: [{
                    data: ds.modeValues,
                    backgroundColor: modeColors.slice(0, ds.modeLabels.length),
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, padding: cm.legendPadding, usePointStyle: true, pointStyleWidth: 8, font: { size: cm.legendFont } } },
                    tooltip: commonTooltip
                }
            }
        }));

        // 2. Battery Voltage Distribution - descriptive only; not a clinical alert threshold.
        const voltColors = tc.isPixel ? chartPalette.slice(0, 6) : ['#94A3B8', '#60A5FA', '#38BDF8', '#34D399', '#818CF8', '#A78BFA'];
        deepCharts.push(new Chart(document.getElementById('chartBatteryVolt'), {
            type: 'bar',
            data: {
                labels: ds.voltLabels,
                datasets: [{
                    label: '患者数',
                    data: ds.voltValues,
                    backgroundColor: voltColors.map(c => c + '99'),
                    borderColor: voltColors,
                    borderWidth: 1,
                    borderRadius: tc.isPixel ? 0 : 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: commonTooltip },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 3. Monthly Trend - Area
        deepCharts.push(new Chart(document.getElementById('chartMonthlyTrend'), {
            type: 'line',
            data: {
                labels: ds.monthLabels,
                datasets: [{
                    label: '程控次数',
                    data: ds.monthValues,
                    borderColor: tc.isPixel ? chartPalette[0] : '#10B981',
                    backgroundColor: tc.isPixel ? 'rgba(77,155,138,0.15)' : (tc.isDark ? 'rgba(16,185,129,0.15)' : 'rgba(16,185,129,0.1)'),
                    fill: true,
                    tension: tc.isPixel ? 0 : 0.3,
                    pointStyle: tc.isPixel ? 'rect' : 'circle',
                    pointBackgroundColor: tc.isPixel ? chartPalette[0] : '#10B981',
                    pointRadius: 3,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: commonTooltip },
                scales: {
                    x: { grid: { color: tc.grid }, ticks: { color: tc.text, maxRotation: cm.mobile ? 35 : 45, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 4. AT/AF Burden - Polar/Bar
        const afColors = tc.isPixel ? chartPalette.slice(0, 6) : ['#94A3B8', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#DC2626'];
        deepCharts.push(new Chart(document.getElementById('chartAfBurden'), {
            type: 'bar',
            data: {
                labels: ds.afLabels,
                datasets: [{
                    label: '患者数',
                    data: ds.afValues,
                    backgroundColor: afColors.map(c => c + '99'),
                    borderColor: afColors,
                    borderWidth: 1,
                    borderRadius: tc.isPixel ? 0 : 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: commonTooltip },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 5. Battery Alert List
        const listEl = document.getElementById('batteryAlertList');
        if (ds.batteryAlerts.length === 0) {
            listEl.innerHTML = `<div class="alert-empty">未发现报告中明确的 ERI/EOS/EOL 提示。${ds.batteryReviewCount > 0 ? `另有 ${ds.batteryReviewCount} 位患者需按品牌/型号和原始报告人工核对。` : ''}</div>`;
        } else {
            let html = `<div class="alert-count">[!] 发现 <b>${ds.batteryAlerts.length}</b> 位患者存在报告中明确的电池/更换提示</div>`;
            html += '<div class="alert-table-scroll"><table class="alert-table"><thead><tr><th>姓名</th><th>登记号</th><th>电压</th><th>状态</th></tr></thead><tbody>';
            ds.batteryAlerts.forEach(a => {
                const vClass = 'volt-critical';
                html += `<tr class="alert-row clickable" data-file="${escapeHtml(a.file_name)}">`;
                html += `<td>${escapeHtml(a.name)}</td>`;
                html += `<td class="mono">${escapeHtml(a.id)}</td>`;
                html += `<td class="${vClass}">${Number.isFinite(a.voltage) ? `${a.voltage.toFixed(2)}V` : '--'}</td>`;
                html += `<td>${escapeHtml(a.status || a.life || '--')}</td>`;
                html += '</tr>';
            });
            html += '</tbody></table></div>';
            listEl.innerHTML = html;

            // Make alert rows clickable to jump to patient
            listEl.querySelectorAll('.alert-row.clickable').forEach(row => {
                row.addEventListener('click', () => {
                    const fn = row.dataset.file;
                    if (fn) loadPatientDetails(fn);
                });
            });
        }
    }

    // --- Lead Parameters & Compliance Charts ---

    let leadParamCharts = [];

    function renderLeadCharts() {
        const records = window.PACEMAKER_DATA?.records;
        if (!detailedAnalyticsLoaded || !records) return;

        const tc = getThemeColors();
        const cm = getChartMetrics();

        // Collect impedance & threshold data
        const impRA = [], impRV = [], impLV = [];
        const thrRA = [], thrRV = [], thrLV = [];
        let singleVisit = 0, multiVisit = 0;

        Object.values(records).forEach(patient => {
            const recs = patient['程控记录'] || [];
            if (recs.length === 0) return;

            // Compliance
            if (recs.length === 1) singleVisit++;
            else multiVisit++;

            const latest = getLatestRawRecord(recs);
            const thresh = latest.test_params?.threshold_tests || {};

            // Impedance
            const parseV = (s) => { const n = parseFloat(s); return (!isNaN(n) && n > 0) ? n : null; };
            const ra_imp = parseV(thresh['心房_阻抗']);
            const rv_imp = parseV(thresh['右心室_阻抗']);
            const lv_imp = parseV(thresh['左心室_阻抗']);
            if (ra_imp) impRA.push(ra_imp);
            if (rv_imp) impRV.push(rv_imp);
            if (lv_imp) impLV.push(lv_imp);

            // Threshold
            const ra_thr = parseV(thresh['心房_阈值']);
            const rv_thr = parseV(thresh['右心室_阈值']);
            const lv_thr = parseV(thresh['左心室_阈值']);
            if (ra_thr) thrRA.push(ra_thr);
            if (rv_thr) thrRV.push(rv_thr);
            if (lv_thr) thrLV.push(lv_thr);
        });

        // Destroy old
        leadParamCharts.forEach(c => c.destroy());
        leadParamCharts = [];

        const commonTooltip = makeTooltipConfig(tc);

        // Helper: bucket an array into ranges
        function bucketize(arr, ranges) {
            const counts = ranges.map(() => 0);
            arr.forEach(v => {
                for (let i = 0; i < ranges.length; i++) {
                    if (v >= ranges[i][0] && v < ranges[i][1]) { counts[i]++; break; }
                }
            });
            return counts;
        }

        // 1. Impedance Distribution - Grouped Bar (RA/RV/LV)
        const impRanges = [[0, 200], [200, 400], [400, 600], [600, 800], [800, 1000], [1000, 2000]];
        const impLabels = ['<200', '200-400', '400-600', '600-800', '800-1000', '1000+'];
        leadParamCharts.push(new Chart(document.getElementById('chartImpedance'), {
            type: 'bar',
            data: {
                labels: impLabels.map(l => l + ' Ω'),
                datasets: [
                    { label: 'RA (心房)', data: bucketize(impRA, impRanges), backgroundColor: '#3B82F699', borderColor: '#3B82F6', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 },
                    { label: 'RV (右室)', data: bucketize(impRV, impRanges), backgroundColor: '#10B98199', borderColor: '#10B981', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 },
                    { label: 'LV (左室)', data: bucketize(impLV, impRanges), backgroundColor: '#F59E0B99', borderColor: '#F59E0B', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { color: tc.text, usePointStyle: true, pointStyleWidth: 8, padding: cm.legendPadding, font: { size: cm.legendFont } } },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 2. Threshold Distribution - Grouped Bar
        const thrRanges = [[0, 0.5], [0.5, 1.0], [1.0, 1.5], [1.5, 2.0], [2.0, 3.0], [3.0, 10]];
        const thrLabels = ['<0.5', '0.5-1.0', '1.0-1.5', '1.5-2.0', '2.0-3.0', '3.0+'];
        leadParamCharts.push(new Chart(document.getElementById('chartThreshold'), {
            type: 'bar',
            data: {
                labels: thrLabels.map(l => l + ' V'),
                datasets: [
                    { label: 'RA', data: bucketize(thrRA, thrRanges), backgroundColor: '#3B82F699', borderColor: '#3B82F6', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 },
                    { label: 'RV', data: bucketize(thrRV, thrRanges), backgroundColor: '#10B98199', borderColor: '#10B981', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 },
                    { label: 'LV', data: bucketize(thrLV, thrRanges), backgroundColor: '#F59E0B99', borderColor: '#F59E0B', borderWidth: 1, borderRadius: tc.isPixel ? 0 : 4 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { color: tc.text, usePointStyle: true, pointStyleWidth: 8, padding: cm.legendPadding, font: { size: cm.legendFont } } },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text, font: { size: cm.tickFont } } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, font: { size: cm.tickFont }, stepSize: 1 }, beginAtZero: true }
                }
            }
        }));

        // 3. Follow-up Compliance Doughnut
        leadParamCharts.push(new Chart(document.getElementById('chartCompliance'), {
            type: 'doughnut',
            data: {
                labels: ['多次程控 (≥2次)', '仅单次程控'],
                datasets: [{
                    data: [multiVisit, singleVisit],
                    backgroundColor: ['#10B981', '#F59E0B'],
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, padding: cm.legendPadding, usePointStyle: true, pointStyleWidth: 8, font: { size: cm.legendFont } } },
                    tooltip: {
                        ...commonTooltip,
                        callbacks: {
                            label: function (ctx) {
                                const total = multiVisit + singleVisit;
                                const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return `${ctx.label}: ${ctx.raw} 人 (${pct}%)`;
                            }
                        }
                    }
                }
            }
        }));
    }


    function renderList(patients) {
        dom.list.innerHTML = '';
        dom.count.textContent = patients.length;

        const fragment = document.createDocumentFragment();

        patients.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'patient-item';
            const safeName = escapeHtml(p.name);
            const safeId = escapeHtml(p.id);
            const initial = safeName ? safeName[0] : '?';
            item.setAttribute('aria-label', `${p.name}，登记号 ${p.id}`);
            item.innerHTML = `
                <div class="patient-avatar">${initial}</div>
                <div class="patient-meta">
                    <span class="patient-name">${safeName}</span>
                    <span class="patient-id">登记号 ${safeId}</span>
                </div>
            `;
            item.addEventListener('click', () => {
                document.querySelectorAll('.patient-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                loadPatientDetails(p.file_name);
            });
            fragment.appendChild(item);
        });

        dom.list.appendChild(fragment);
    }

    function renderPatient(patient) {
        const lat = patient.history && patient.history.length > 0 ? patient.history[0] : null;
        if (!lat) return;

        // Header
        dom.pName.textContent = patient.name;
        dom.pId.textContent = `登记号 ${patient.id}`;
        dom.dBrand.textContent = patient.brand;
        dom.dModel.textContent = patient.model;
        dom.dDate.textContent = patient.implantDate;

        // Battery
        const v = lat.battery.voltage;
        dom.batStatus.textContent = v !== null ? v.toFixed(2) : '--';
        const batLife = lat.battery.life;
        dom.batLife.textContent = batLife && batLife !== '--' ? `预估剩余：${batLife}` : '预估剩余：--';

        // Mode
        dom.pacingMode.textContent = lat.mode || '--';
        dom.lowerRate.textContent = lat.lowerRate || '--';
        dom.upperRate.textContent = lat.upperRate || '--';

        // Core conclusion and follow-up: keep the original text, only add visual hierarchy.
        const conclusion = lat.events.conclusion || '无记录';
        const nextVisit = lat.events.next_visit || '未指定';
        dom.visitConclusion.textContent = conclusion;
        dom.visitConclusion.classList.toggle('is-empty', !lat.events.conclusion);
        dom.nextVisitDate.textContent = nextVisit;
        dom.nextVisitDate.classList.toggle('is-empty', !lat.events.next_visit);

        // Events
        const ev = lat.events;

        let amsDisplay = '无';
        if (ev.ams_count) {
            amsDisplay = ev.ams_count;
            if (ev.ams_duration) amsDisplay += ` (最长 ${ev.ams_duration})`;
        }
        dom.amsSwitch.textContent = amsDisplay;

        let atafDisplay = '无';
        if (ev.ataf_load) {
            const burden = String(ev.ataf_load);
            atafDisplay = burden.includes('%') ? burden : `${burden}%`;
            if (ev.ataf_desc && !isWithheldText(ev.ataf_desc)) atafDisplay += ` - ${ev.ataf_desc}`;
        } else if (ev.ataf_count) {
            atafDisplay = `${ev.ataf_count} 次`;
            if (ev.ataf_desc && !isWithheldText(ev.ataf_desc)) atafDisplay += ` - ${ev.ataf_desc}`;
        }
        dom.atafLoad.textContent = atafDisplay;

        let vtDisplay = '无';
        if (ev.vt_count) {
            vtDisplay = `${ev.vt_count} 次`;
            if (ev.vt_desc && !isWithheldText(ev.vt_desc)) vtDisplay += ` - ${ev.vt_desc}`;
        } else if (ev.vt_desc && !isWithheldText(ev.vt_desc)) {
            vtDisplay = ev.vt_desc;
        }
        dom.vtEvents.textContent = vtDisplay;

        dom.otherEvents.textContent = ev.other || '无';

        // Lead Table - use DocumentFragment
        dom.leadTableBody.innerHTML = '';
        const leadFragment = document.createDocumentFragment();

        const chambers = [
            { name: 'RA (右房)', imp: lat.ra_impedance, sens: lat.ra_sense, thr: lat.ra_threshold, out: lat.ra_output },
            { name: 'RV (右室)', imp: lat.rv_impedance, sens: lat.rv_sense, thr: lat.rv_threshold, out: lat.rv_output },
            { name: 'LV (左室)', imp: lat.lv_impedance, sens: lat.lv_sense, thr: lat.lv_threshold, out: lat.lv_output }
        ];

        let renderedChambers = 0;
        chambers.forEach(c => {
            const hasData = (c.imp && c.imp !== '--') || (c.sens && c.sens !== '--') || (c.thr && c.thr !== '--') || (c.out && c.out !== '--');
            if (hasData) {
                renderedChambers += 1;
                const safeName = escapeHtml(c.name);
                const safeImp = escapeHtml(c.imp || '--');
                const safeSens = escapeHtml(c.sens || '--');
                const safeThr = escapeHtml(c.thr || '--');
                const safeOut = escapeHtml(c.out || '--');
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${safeName}</td>
                    <td>${safeImp}</td>
                    <td>${safeSens}</td>
                    <td>${safeThr}</td>
                    <td>${safeOut}</td>
                `;
                leadFragment.appendChild(tr);
            }
        });
        if (renderedChambers === 0) {
            const emptyRow = document.createElement('tr');
            emptyRow.innerHTML = '<td colspan="5" class="medical-empty">本次报告未提供可展示的导线阈值参数。</td>';
            leadFragment.appendChild(emptyRow);
        }
        dom.leadTableBody.appendChild(leadFragment);

        // Records Timeline - use DocumentFragment
        dom.recordTimeline.innerHTML = '';
        const timelineFragment = document.createDocumentFragment();

        patient.history.forEach((rec, index) => {
            const div = document.createElement('div');
            div.className = 'history-card';
            const collapseId = `rec-${index}`;
            const safeDate = escapeHtml(rec.dateStr);
            const safeMode = escapeHtml(rec.mode || '');
            const safeVoltage = rec.battery.voltage ? escapeHtml(String(rec.battery.voltage)) : '';

            div.innerHTML = `
                <button type="button" class="history-header" data-toggle="${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                    <div class="history-main-meta">
                        <span class="history-date">程控日期: ${safeDate}</span>
                        <span class="badge mode-badge">${safeMode}</span>
                    </div>
                    <div class="history-sub-meta">
                        <span>${safeVoltage ? '电池: ' + safeVoltage + 'V' : ''}</span>
                        <span class="arrow-icon">▼</span>
                    </div>
                </button>
                <div id="${collapseId}" class="history-body hidden">
                    <div class="report-sheet">
                        <div class="report-section section-header">
                            <h4 class="section-title">[I] 患者/设备信息</h4>
                            <div class="kv-grid">${renderKeyValue({ ...rec.header_raw, '程控日期': rec.dateStr })}</div>
                        </div>
                        <div class="report-section section-params">
                            <h4 class="section-title">[B] 电池与起搏参数</h4>
                            ${renderBatteryAndPacingParameters(rec)}
                        </div>
                        <div class="report-section section-thresholds">
                            <h4 class="section-title">[V] 阈值测试</h4>
                            ${renderThresholdParameters(rec)}
                        </div>
                        <div class="report-section section-events">
                            <h4 class="section-title">[!] 事件与结论</h4>
                            <div class="kv-grid">${(() => {
                    const s = {}, l = {};
                    Object.entries(rec.events_raw).forEach(([k, v]) => {
                        if (k.includes('结论') || k.includes('建议') || k.includes('说明') || (typeof v === 'string' && v.length > 20)) {
                            l[k] = v;
                        } else {
                            s[k] = v;
                        }
                    });
                    return renderKeyValue(s) + renderKeyValue(l, 'full-row');
                })()}</div>
                        </div>
                    </div>
                </div>
            `;
            const header = div.querySelector(`[data-toggle="${collapseId}"]`);
            if (header) {
                header.addEventListener('click', () => toggleHistory(collapseId));
            }
            timelineFragment.appendChild(div);
        });
        dom.recordTimeline.appendChild(timelineFragment);

        // Render Trends Chart
        renderTrendsChart(patient);
    }

    function renderTrendsChart(patient) {
        if (!dom.trendsChartCanvas) return;
        const ctx = dom.trendsChartCanvas.getContext('2d');
        if (chartInstance) {
            chartInstance.destroy();
        }

        // We need chronology: oldest to newest for charts
        const chronologicalHistory = [...patient.history].reverse();

        const labels = [];
        const rvImpData = [];
        const rvThrData = [];
        const batVolData = [];

        chronologicalHistory.forEach(rec => {
            labels.push(rec.dateStr);
            rvImpData.push(parseFloat(rec.rv_impedance) || null);
            rvThrData.push(parseFloat(rec.rv_threshold) || null);
            batVolData.push(rec.battery.voltage || null);
        });

        // Reuse shared theme color helper
        const tc = getThemeColors();
        const cm = getChartMetrics();
        const textColor = tc.text;
        const gridColor = tc.grid;

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '右室阻抗 (Ω)',
                        data: rvImpData,
                        borderColor: '#3B82F6', // Blue
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        yAxisID: 'y',
                        tension: tc.isPixel ? 0 : 0.3,
                        pointStyle: tc.isPixel ? 'rect' : 'circle',
                        spanGaps: true
                    },
                    {
                        label: '右室阈值 (V)',
                        data: rvThrData,
                        borderColor: '#10B981', // Green
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        yAxisID: 'y1',
                        tension: tc.isPixel ? 0 : 0.3,
                        pointStyle: tc.isPixel ? 'rect' : 'circle',
                        spanGaps: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        labels: { color: textColor, font: { size: cm.legendFont } }
                    },
                    tooltip: makeTooltipConfig(tc)
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, maxRotation: cm.mobile ? 35 : 45, font: { size: cm.tickFont } }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: '阻抗 (Ω)', color: textColor, font: { size: cm.tickFont } },
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: cm.tickFont } }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: '阈值 (V)', color: textColor, font: { size: cm.tickFont } },
                        grid: { drawOnChartArea: false },
                        ticks: { color: textColor, font: { size: cm.tickFont } }
                    }
                }
            }
        });
    }

    // --- Event Handlers ---

    function handleTabClick(btn) {
        dom.tabs.forEach(b => b.classList.remove('active'));
        dom.panes.forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
        currentTab = btn.dataset.tab;
        setTimeout(resizeAllCharts, 80);
    }

    const handleSearch = debounce((term) => {
        term = term.toLowerCase().trim();
        const filtered = allPatients.filter(p =>
            (p.name && p.name.toLowerCase().includes(term)) ||
            (p.id && String(p.id).toLowerCase().includes(term))
        );
        renderList(filtered);
    }, 300);

    // --- Global Functions ---
    window.toggleHistory = function (id) {
        const el = document.getElementById(id);
        const card = el.parentElement;
        const trigger = card.querySelector(`[aria-controls="${id}"]`);
        if (el.classList.contains('hidden')) {
            el.classList.remove('hidden');
            card.classList.add('expanded');
            trigger?.setAttribute('aria-expanded', 'true');
        } else {
            el.classList.add('hidden');
            card.classList.remove('expanded');
            trigger?.setAttribute('aria-expanded', 'false');
        }
    };

    // --- Initialization ---
    document.addEventListener('DOMContentLoaded', async () => {
        initDOM();
        setupDisplaySettings();
        loadQualityReviewState();
        try {
            await waitForAuthorizedSession();
            await loadIndex();
            renderDashboard();
            scheduleDrilldownHandlers();
        } catch (error) {
            console.error(error);
            if (dom.list) {
                const message = document.createElement('div');
                message.className = 'error';
                message.style.cssText = 'padding:20px; color:var(--danger);';
                message.textContent = '数据加载失败：' + (error.message || '请重新登录后重试。');
                dom.list.replaceChildren(message);
            }
        }

        // Tabs
        dom.tabs.forEach(btn => {
            btn.addEventListener('click', () => handleTabClick(btn));
        });

        // Search with debounce
        dom.search.addEventListener('input', (e) => {
            handleSearch(e.target.value);
        });

        // Data quality filters and source-path copy action.
        if (dom.qualityTypeFilter) {
            dom.qualityTypeFilter.addEventListener('change', (e) => {
                qualityState.type = e.target.value;
                renderQualityIssueList();
            });
        }
        if (dom.qualitySeverityFilter) {
            dom.qualitySeverityFilter.addEventListener('change', (e) => {
                qualityState.severity = e.target.value;
                renderQualityIssueList();
            });
        }
        if (dom.qualityStatusFilter) {
            dom.qualityStatusFilter.addEventListener('change', (e) => {
                qualityState.status = e.target.value;
                renderQualityIssueList();
            });
        }
        if (dom.qualitySearch) {
            dom.qualitySearch.addEventListener('input', (e) => {
                qualityState.search = e.target.value || '';
                renderQualityIssueList();
            });
        }
        if (dom.qualityIssueList) {
            dom.qualityIssueList.addEventListener('click', async (event) => {
                const saveButton = event.target.closest('[data-save-review]');
                if (saveButton) {
                    const issueCard = saveButton.closest('[data-quality-issue-id]');
                    const issueKey = issueCard?.getAttribute('data-quality-issue-id') || '';
                    const statusSelect = issueCard?.querySelector('[data-review-status]');
                    const noteInput = issueCard?.querySelector('[data-review-note]');
                    const status = normalizeQualityReviewStatus(statusSelect?.value);
                    const note = String(noteInput?.value || '').trim();
                    if (!issueKey) return;
                    if (status === 'ignored' && !note) {
                        if (dom.qualityStatus) dom.qualityStatus.textContent = '选择“暂时忽略”时，请填写核查备注。';
                        noteInput?.focus();
                        return;
                    }
                    qualityReviewState[issueKey] = {
                        status,
                        note,
                        updatedAt: new Date().toISOString(),
                    };
                    const saved = saveQualityReviewState();
                    renderQualitySummary(window.PACEMAKER_DATA?.quality?.summary || {});
                    updateQualityPendingBadge();
                    renderQualityIssueList();
                    if (dom.qualityStatus) {
                        dom.qualityStatus.textContent = saved
                            ? `已保存：${qualityReviewStatusLabel(status)}。核查状态仅保存在本机浏览器。`
                            : '核查状态保存失败，请检查浏览器本地存储权限。';
                    }
                    return;
                }
                const openButton = event.target.closest('[data-open-path]');
                if (openButton) {
                    const path = openButton.getAttribute('data-open-path') || '';
                    const fileUrl = pathToFileUrl(path);
                    if (!fileUrl) return;
                    const opened = window.open(fileUrl, '_blank', 'noopener');
                    if (dom.qualityStatus) {
                        dom.qualityStatus.textContent = opened
                            ? '已请求打开原始报告；若系统未响应，请使用“复制路径”。'
                            : '浏览器拦截了直接打开，请使用“复制路径”后在资源管理器中打开。';
                    }
                    return;
                }
                const button = event.target.closest('[data-copy-path]');
                if (!button) return;
                const path = button.getAttribute('data-copy-path') || '';
                if (!path) return;
                let copied = false;
                try {
                    if (navigator.clipboard?.writeText) {
                        await navigator.clipboard.writeText(path);
                        copied = true;
                    }
                } catch (_) {
                    copied = false;
                }
                if (!copied) {
                    const helper = document.createElement('textarea');
                    helper.value = path;
                    helper.style.position = 'fixed';
                    helper.style.opacity = '0';
                    document.body.appendChild(helper);
                    helper.focus();
                    helper.select();
                    try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
                    helper.remove();
                }
                const original = button.textContent;
                button.textContent = copied ? '已复制' : '请手动复制';
                if (dom.qualityStatus && copied) dom.qualityStatus.textContent = '来源路径已复制到剪贴板。';
                window.setTimeout(() => { button.textContent = original; }, 1600);
            });
        }

        const researchButton = document.getElementById('loadResearchAnalytics');
        if (researchButton) {
            researchButton.addEventListener('click', () => {
                loadResearchAnalytics().then(() => scheduleDrilldownHandlers());
            });
        }

        window.addEventListener('resize', debounce(resizeAllCharts, 150));

        // Back to Dashboard
        if (dom.backBtn) {
            dom.backBtn.addEventListener('click', showDashboard);
        }

        // Theme Toggle Logic: 像素 / 浅色 / 深色三套视觉，共用同一套数据与交互。
        const themeBtn = document.getElementById('themeToggleBtn');
        if (themeBtn) {
            const themes = ['pixel', 'light', 'dark'];
            const themeMeta = {
                pixel: { icon: '▦', label: '像素主题', title: '当前为像素主题，点击切换浅色主题' },
                light: { icon: '☀', label: '浅色主题', title: '当前为浅色主题，点击切换深色主题' },
                dark: { icon: '◐', label: '深色主题', title: '当前为深色主题，点击切换像素主题' }
            };

            function updateThemeButton(theme) {
                const meta = themeMeta[theme] || themeMeta.pixel;
                const icon = themeBtn.querySelector('.icon');
                const label = themeBtn.querySelector('.theme-label');
                if (icon) icon.textContent = meta.icon;
                if (label) label.textContent = meta.label;
                themeBtn.title = meta.title;
                themeBtn.setAttribute('aria-label', meta.title);
            }

            function applyTheme(theme) {
                const nextTheme = themes.includes(theme) ? theme : 'pixel';
                document.documentElement.setAttribute('data-theme', nextTheme);
                localStorage.setItem('pm_theme', nextTheme);
                localStorage.setItem('pm_theme_version', 'pixel-v2');
                updateThemeButton(nextTheme);

                if (window.Chart?.defaults?.font) {
                    window.Chart.defaults.font.family = nextTheme === 'pixel'
                        ? "'SimSun', 'Cascadia Mono', serif"
                        : "'Inter', 'PingFang SC', 'Microsoft YaHei UI', sans-serif";
                }
            }

            const initialTheme = document.documentElement.getAttribute('data-theme') || 'pixel';
            applyTheme(initialTheme);

            themeBtn.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-theme') || 'pixel';
                const currentIndex = themes.indexOf(currentTheme);
                applyTheme(themes[(currentIndex + 1) % themes.length]);

                // Re-render charts to update colors
                if (currentPatient) {
                    renderTrendsChart(currentPatient);
                } else {
                    renderDashboard();
                    if (detailedAnalyticsLoaded) {
                        renderDeepCharts();
                        renderLeadCharts();
                    }
                    scheduleDrilldownHandlers();
                }
            });
        }


        // --- Fullscreen / Digital Dashboard Mode ---
        const fullscreenBtn = document.getElementById('fullscreenBtn');
        let isFullscreen = false;
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener('click', () => {
                isFullscreen = !isFullscreen;
                document.body.classList.toggle('fullscreen-mode', isFullscreen);
                fullscreenBtn.textContent = isFullscreen ? '× 退出大屏' : '□ 大屏模式';

                // Resize charts after layout change
                setTimeout(() => {
                    dashboardCharts.forEach(c => c.resize());
                    deepCharts.forEach(c => c.resize());
                    leadParamCharts.forEach(c => c.resize());
                    attachDrilldownHandlers();
                }, 350);
            });
        }

        // --- Drill-down Modal ---
        const ddModal = document.getElementById('drilldownModal');
        const ddTitle = document.getElementById('drilldownTitle');
        const ddContent = document.getElementById('drilldownContent');
        const ddClose = document.getElementById('drilldownClose');

        function openDrilldown(title, patients) {
            ddTitle.textContent = title;
            let html = `<div class="drilldown-summary">共 <b>${patients.length}</b> 位患者匹配此筛选条件</div>`;
            html += '<table class="drilldown-table"><thead><tr>';
            html += '<th>姓名</th><th>登记号</th><th>品牌</th><th>型号</th><th>植入日期</th><th>程控次数</th>';
            html += '</tr></thead><tbody>';
            patients.forEach(p => {
                html += `<tr data-file="${escapeHtml(p.file_name || '')}">`;
                html += `<td>${escapeHtml(p.name || p['姓名'] || '--')}</td>`;
                html += `<td class="mono" style="font-family:var(--font-mono);font-size:0.78rem;color:var(--text-secondary)">${escapeHtml(p.id || p['登记号'] || '--')}</td>`;
                html += `<td>${escapeHtml(p.brand || '--')}</td>`;
                html += `<td>${escapeHtml(p.model || '--')}</td>`;
                html += `<td>${escapeHtml(formatDate(p.implant_date) || '--')}</td>`;
                html += `<td>${p.count || 1}</td>`;
                html += '</tr>';
            });
            html += '</tbody></table>';
            ddContent.innerHTML = html;

            // Make rows clickable
            ddContent.querySelectorAll('tr[data-file]').forEach(row => {
                row.addEventListener('click', () => {
                    const fn = row.dataset.file;
                    if (fn) {
                        ddModal.classList.add('hidden');
                        loadPatientDetails(fn);
                    }
                });
            });

            ddModal.classList.remove('hidden');
        }

        if (ddClose) {
            ddClose.addEventListener('click', () => ddModal.classList.add('hidden'));
        }
        if (ddModal) {
            ddModal.addEventListener('click', (e) => {
                if (e.target === ddModal) ddModal.classList.add('hidden');
            });
        }

        // --- Wire drill-down to charts ---
        // Attach click handlers after charts are rendered
        function wireDrilldownChart(chart, onSelect) {
            if (!chart) return;
            chart.options.events = ['mousemove', 'mouseout', 'click', 'touchstart', 'touchmove', 'touchend'];
            chart.options.onHover = (evt, elements) => {
                if (chart.canvas) {
                    chart.canvas.style.cursor = elements && elements.length > 0 ? 'pointer' : 'default';
                }
            };
            chart.options.onClick = (evt, elements) => {
                if (elements && elements.length > 0) {
                    onSelect(elements[0].index);
                }
            };
            if (chart.canvas) {
                chart.canvas.style.touchAction = 'manipulation';
            }
            chart.update('none');
        }

        function scheduleDrilldownHandlers() {
            setTimeout(attachDrilldownHandlers, 80);
        }

        function attachDrilldownHandlers() {
            // 1. Brand Distribution chart → filter by brand
            const brandChart = dashboardCharts[0]; // first chart is brand doughnut
            wireDrilldownChart(brandChart, (idx) => {
                const brandName = brandChart.data.labels[idx];
                const filtered = allPatients.filter(p => (p.brand || '未知') === brandName);
                openDrilldown(`品牌: ${brandName} (${filtered.length}人)`, filtered);
            });

            // 2. Model Top 10 chart → filter by model
            const modelChart = dashboardCharts[1];
            wireDrilldownChart(modelChart, (idx) => {
                const modelName = modelChart.data.labels[idx];
                const filtered = allPatients.filter(p => (p.model || '未知') === modelName);
                openDrilldown(`型号: ${modelName} (${filtered.length}人)`, filtered);
            });

            // 3. Pacing Mode chart → filter by mode
            const modeChart = deepCharts[0];
            wireDrilldownChart(modeChart, (idx) => {
                const modeName = modeChart.data.labels[idx];
                // Need to match from records
                const records = window.PACEMAKER_DATA.records;
                const matched = [];
                Object.entries(records).forEach(([fn, patient]) => {
                    const recs = patient['程控记录'] || [];
                    if (recs.length === 0) return;
                    const latest = getLatestRawRecord(recs);
                    const mode = latest.basic_params?.settings?.['模式'];
                    if (mode && mode.trim().toUpperCase() === modeName) {
                        matched.push({
                            name: patient['姓名'],
                            id: patient['登记号'],
                            brand: latest.header?.['品牌'] || '--',
                            model: latest.header?.['型号'] || '--',
                            implant_date: latest.header?.['植入日期'] || '--',
                            count: recs.length,
                            file_name: fn
                        });
                    }
                });
                openDrilldown(`起搏模式: ${modeName} (${matched.length}人)`, matched);
            });

            // 4. Battery Voltage chart → filter by voltage range
            const voltChart = deepCharts[1];
            wireDrilldownChart(voltChart, (idx) => {
                const rangeLabel = voltChart.data.labels[idx];
                const ranges = [[0, 2.4], [2.4, 2.6], [2.6, 2.8], [2.8, 3.0], [3.0, 3.2], [3.2, 99]];
                const [lo, hi] = ranges[idx];
                const records = window.PACEMAKER_DATA.records;
                const matched = [];
                Object.entries(records).forEach(([fn, patient]) => {
                    const recs = patient['程控记录'] || [];
                    if (recs.length === 0) return;
                    const latest = getLatestRawRecord(recs);
                    const batt = latest.test_params?.battery_and_leads;
                    const vStr = batt?.['电池电压（V）'] || batt?.['电池电压(V)'] || batt?.['电池电压'];
                    if (vStr) {
                        const v = parseFloat(vStr);
                        if (!isNaN(v) && v >= lo && v < hi) {
                            matched.push({
                                name: patient['姓名'],
                                id: patient['登记号'],
                                brand: latest.header?.['品牌'] || '--',
                                model: latest.header?.['型号'] || '--',
                                implant_date: latest.header?.['植入日期'] || '--',
                                count: recs.length,
                                file_name: fn
                            });
                        }
                    }
                });
                openDrilldown(`电池电压: ${rangeLabel} (${matched.length}人)`, matched);
            });
        }

        // Attach drill-down after initial render
        setTimeout(attachDrilldownHandlers, 200);
    });

})();
