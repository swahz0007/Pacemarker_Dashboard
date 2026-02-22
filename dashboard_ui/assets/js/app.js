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
    let searchDebounceTimer = null;

    // --- Cached DOM Elements ---
    const dom = {
        list: null,
        search: null,
        count: null,
        detail: null,
        tabs: null,
        panes: null,
        // Dashboard view
        dashboardView: null,
        backBtn: null,
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

    // --- Utility Functions ---

    function debounce(func, wait) {
        return function (...args) {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function parseToTimestamp(dateInput) {
        if (!dateInput) return 0;
        if (/^\d{5}$/.test(dateInput)) {
            return new Date((dateInput - 25569) * 86400 * 1000).getTime();
        }
        const str = String(dateInput).replace(/\./g, '-').replace(/年|月/g, '-').replace(/日|号/g, '');
        const ts = Date.parse(str);
        return isNaN(ts) ? 0 : ts;
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
                    life: batt['预估寿命'] || '--',
                    status: batt['电池状态'] || 'OK'
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
            if (k.includes('日期') || k.includes('时间')) {
                displayVal = formatDate(v);
            } else if (typeof v === 'object') {
                displayVal = `<pre style="margin:0; font-size:0.75rem">${JSON.stringify(v, null, 2)}</pre>`;
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
                    displayVal = `${v} <span style="font-size:0.8em; color:var(--text-muted)">${unit}</span>`;
                }
            }

            const label = k.replace(/（.*?）|\(.*?\)/g, '').replace(/_/g, ' ').replace('电池预估寿命', '预估寿命');
            return `<div class="kv-row ${extraClass}"><span class="kv-key">${label}</span><span class="kv-val">${displayVal}</span></div>`;
        }).join('');
    }

    // --- Initialization ---

    function initDOM() {
        dom.list = document.getElementById('patientList');
        dom.search = document.getElementById('patientSearch');
        dom.count = document.getElementById('patientCount');
        dom.dashboardView = document.getElementById('dashboardView');
        dom.detail = document.getElementById('patientDetail');
        dom.backBtn = document.getElementById('backToDashboard');
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

    function loadIndex() {
        try {
            if (!window.PACEMAKER_DATA) {
                throw new Error('Data bundle not found. Please run dashboard_ui/scripts/generate_data.py');
            }
            allPatients = window.PACEMAKER_DATA.index;
            renderList(allPatients);
        } catch (err) {
            console.error(err);
            dom.list.innerHTML = `<div class="error" style="padding:20px; color:var(--accent-rose)">Error loading data.<br>Make sure data_bundle.js exists.<br>${err.message}</div>`;
        }
    }

    function loadPatientDetails(filename) {
        try {
            const data = window.PACEMAKER_DATA.records[filename];
            if (!data) throw new Error('Record not found in bundle');

            currentPatient = parsePatientData(data);
            renderPatient(currentPatient);

            showPatientDetail();
        } catch (err) {
            console.error(err);
            alert('Could not load patient data: ' + err.message);
        }
    }

    // --- View Switching ---

    function showDashboard() {
        dom.dashboardView.classList.remove('hidden');
        dom.detail.classList.add('hidden');
        document.querySelectorAll('.patient-item').forEach(i => i.classList.remove('active'));
        currentPatient = null;
    }

    function showPatientDetail() {
        dom.dashboardView.classList.add('hidden');
        dom.detail.classList.remove('hidden');
    }

    // --- Dashboard Statistics ---

    function getThemeColors() {
        const ct = document.documentElement.getAttribute('data-theme');
        const isSysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const isDark = ct === 'dark' || (!ct && isSysDark);
        return {
            isDark,
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

    function aggregateStats(patients) {
        const brandMap = {};
        const modelMap = {};
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

        // KPI animation
        animateValue(document.getElementById('kpiTotalPatients'), stats.total);
        animateValue(document.getElementById('kpiBrandCount'), stats.brandCount);
        animateValue(document.getElementById('kpiAvgVisits'), stats.avgVisits);
        document.getElementById('kpiLatestImplant').textContent = stats.latestDate;

        // Destroy old charts
        dashboardCharts.forEach(c => c.destroy());
        dashboardCharts = [];

        const commonTooltip = {
            backgroundColor: tc.tooltipBg,
            titleColor: tc.tooltipTitle,
            bodyColor: tc.tooltipBody,
            borderColor: tc.tooltipBorder,
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8
        };

        // 1. Brand Doughnut
        dashboardCharts.push(new Chart(document.getElementById('chartBrand'), {
            type: 'doughnut',
            data: {
                labels: stats.brandLabels,
                datasets: [{
                    data: stats.brandValues,
                    backgroundColor: CHART_PALETTE.slice(0, stats.brandLabels.length),
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, padding: 16, usePointStyle: true, pointStyleWidth: 8, font: { size: 12 } } },
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
                    backgroundColor: CHART_PALETTE.slice(0, stats.modelLabels.length).map(c => c + '99'),
                    borderColor: CHART_PALETTE.slice(0, stats.modelLabels.length),
                    borderWidth: 1,
                    borderRadius: 4,
                    barThickness: 18
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { color: tc.grid }, ticks: { color: tc.text, stepSize: 1 }, beginAtZero: true },
                    y: { grid: { display: false }, ticks: { color: tc.text, font: { family: "'JetBrains Mono', monospace", size: 11 } } }
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
                    borderColor: '#3B82F6',
                    backgroundColor: tc.isDark ? 'rgba(59,130,246,0.15)' : 'rgba(59,130,246,0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#3B82F6',
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
                    x: { grid: { color: tc.grid }, ticks: { color: tc.text } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, stepSize: 1 }, beginAtZero: true }
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
                    backgroundColor: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'].map(c => c + '99'),
                    borderColor: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'],
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: commonTooltip
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tc.text } },
                    y: { grid: { color: tc.grid }, ticks: { color: tc.text, stepSize: 1 }, beginAtZero: true }
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
                    legend: { position: 'bottom', labels: { color: tc.text, padding: 12, usePointStyle: true, pointStyleWidth: 8, font: { size: 11 } } },
                    tooltip: commonTooltip
                }
            }
        }));
    }

    // --- UI Rendering ---

    function renderList(patients) {
        dom.list.innerHTML = '';
        dom.count.textContent = patients.length;

        const fragment = document.createDocumentFragment();

        patients.forEach(p => {
            const item = document.createElement('div');
            item.className = 'patient-item';
            item.innerHTML = `
                <div class="patient-avatar">${p.name[0]}</div>
                <div class="patient-meta">
                    <span class="patient-name">${p.name}</span>
                    <span class="patient-id">ID: ${p.id}</span>
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
        dom.pId.textContent = `ID: ${patient.id}`;
        dom.dBrand.textContent = patient.brand;
        dom.dModel.textContent = patient.model;
        dom.dDate.textContent = patient.implantDate;

        // Battery
        const v = lat.battery.voltage;
        dom.batStatus.textContent = v !== null ? v.toFixed(2) : '--';
        const batLife = lat.battery.life;
        dom.batLife.textContent = batLife ? `预估剩余: ${batLife}` : '预估剩余: --';

        // Mode
        dom.pacingMode.textContent = lat.mode;
        dom.lowerRate.textContent = lat.lowerRate;
        dom.upperRate.textContent = lat.upperRate;

        // Summary Card
        dom.visitConclusion.textContent = lat.events.conclusion || '无记录';
        dom.nextVisitDate.textContent = lat.events.next_visit || '未指定';

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
            atafDisplay = `${ev.ataf_load}%`;
            if (ev.ataf_desc) atafDisplay += ` - ${ev.ataf_desc}`;
        } else if (ev.ataf_count) {
            atafDisplay = `${ev.ataf_count} 次`;
            if (ev.ataf_desc) atafDisplay += ` - ${ev.ataf_desc}`;
        }
        dom.atafLoad.textContent = atafDisplay;

        let vtDisplay = '无';
        if (ev.vt_count) {
            vtDisplay = `${ev.vt_count} 次`;
            if (ev.vt_desc) vtDisplay += ` - ${ev.vt_desc}`;
        } else if (ev.vt_desc) {
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

        chambers.forEach(c => {
            const hasData = (c.imp && c.imp !== '--') || (c.sens && c.sens !== '--') || (c.thr && c.thr !== '--') || (c.out && c.out !== '--');
            if (hasData) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${c.name}</td>
                    <td>${c.imp || '--'}</td>
                    <td>${c.sens || '--'}</td>
                    <td>${c.thr || '--'}</td>
                    <td>${c.out || '--'}</td>
                `;
                leadFragment.appendChild(tr);
            }
        });
        dom.leadTableBody.appendChild(leadFragment);

        // Records Timeline - use DocumentFragment
        dom.recordTimeline.innerHTML = '';
        const timelineFragment = document.createDocumentFragment();

        patient.history.forEach((rec, index) => {
            const div = document.createElement('div');
            div.className = 'history-card';
            const collapseId = `rec-${index}`;

            div.innerHTML = `
                <div class="history-header" onclick="toggleHistory('${collapseId}')">
                    <div class="history-main-meta">
                        <span class="history-date">程控日期: ${rec.dateStr}</span>
                        <span class="badge mode-badge">${rec.mode}</span>
                    </div>
                    <div class="history-sub-meta">
                        <span>${rec.battery.voltage ? '电池: ' + rec.battery.voltage + 'V' : ''}</span>
                        <span class="arrow-icon">▼</span>
                    </div>
                </div>
                <div id="${collapseId}" class="history-body hidden">
                    <div class="report-sheet">
                        <div class="report-section section-header">
                            <h4 class="section-title">📋 患者/设备信息</h4>
                            <div class="kv-grid">${renderKeyValue({ ...rec.header_raw, '程控日期': rec.dateStr })}</div>
                        </div>
                        <div class="report-section section-params">
                            <h4 class="section-title">⚡ 电池与起搏参数</h4>
                            <div class="kv-grid">${renderKeyValue(rec.battery_raw)}${renderKeyValue(rec.settings_raw)}${renderKeyValue(rec.measurement_raw)}</div>
                        </div>
                        <div class="report-section section-thresholds">
                            <h4 class="section-title">🔌 阈值测试</h4>
                            <div class="kv-grid">${renderKeyValue(rec.thresholds_raw)}</div>
                        </div>
                        <div class="report-section section-events">
                            <h4 class="section-title">⚠️ 事件与结论</h4>
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

        // Determine Text Color based on theme
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const isSystemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const isDark = currentTheme === 'dark' || (!currentTheme && isSystemDark);
        const textColor = isDark ? '#CBD5E1' : '#718096';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)';

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
                        tension: 0.3,
                        spanGaps: true
                    },
                    {
                        label: '右室阈值 (V)',
                        data: rvThrData,
                        borderColor: '#10B981', // Green
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        yAxisID: 'y1',
                        tension: 0.3,
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
                        labels: { color: textColor }
                    },
                    tooltip: {
                        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)',
                        titleColor: isDark ? '#F8FAFC' : '#1E293B',
                        bodyColor: isDark ? '#CBD5E1' : '#64748B',
                        borderColor: isDark ? '#334155' : '#E2E8F0',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { color: textColor }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: '阻抗 (Ω)', color: textColor },
                        grid: { color: gridColor },
                        ticks: { color: textColor }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: '阈值 (V)', color: textColor },
                        grid: { drawOnChartArea: false },
                        ticks: { color: textColor }
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
        if (el.classList.contains('hidden')) {
            el.classList.remove('hidden');
            card.classList.add('expanded');
        } else {
            el.classList.add('hidden');
            card.classList.remove('expanded');
        }
    };

    // --- Initialization ---
    document.addEventListener('DOMContentLoaded', () => {
        initDOM();
        setTimeout(() => {
            loadIndex();
            renderDashboard();
        }, 50);

        // Tabs
        dom.tabs.forEach(btn => {
            btn.addEventListener('click', () => handleTabClick(btn));
        });

        // Search with debounce
        dom.search.addEventListener('input', (e) => {
            handleSearch(e.target.value);
        });

        // Back to Dashboard
        if (dom.backBtn) {
            dom.backBtn.addEventListener('click', showDashboard);
        }

        // Theme Toggle Logic
        const themeBtn = document.getElementById('themeToggleBtn');
        if (themeBtn) {
            const savedTheme = localStorage.getItem('pm_theme');
            if (savedTheme) {
                document.documentElement.setAttribute('data-theme', savedTheme);
            }

            themeBtn.addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-theme');
                const isSystemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                const isDark = currentTheme === 'dark' || (!currentTheme && isSystemDark);
                const newTheme = isDark ? 'light' : 'dark';

                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('pm_theme', newTheme);

                // Re-render charts to update colors
                if (currentPatient) {
                    renderTrendsChart(currentPatient);
                } else {
                    renderDashboard();
                }
            });
        }
    });

})();
