const ICONS = {
    server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    gateway: '<path d="M12 3l8 4v5c0 4.5-3.4 8.4-8 9-4.6-.6-8-4.5-8-9V7z"/><path d="M9 12l2 2 4-4"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13"/><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    users: '<path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20"/><circle cx="10" cy="8" r="3.5"/><path d="M20 20v-1.5a3.5 3.5 0 0 0-2.5-3.35M15.5 4.6a3.5 3.5 0 0 1 0 6.8"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.8-4.2L4 8.5"/><path d="M4 4v4.5h4.5"/><path d="M4 13a8 8 0 0 0 14.8 4.2L20 15.5"/><path d="M20 20v-4.5h-4.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    fit: '<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4"/>',
    layout: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="8.5" y="14" width="7" height="7" rx="1.5"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    collapse: '<path d="M5 12h14"/>',
    expand: '<path d="M6 9l6 6 6-6"/>',
    arrowUp: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    left: '<path d="M15 18l-6-6 6-6"/>',
    right: '<path d="M9 18l6-6-6-6"/>',
};

function icon(name) {
    return `<svg class="i" viewBox="0 0 24 24">${ICONS[name]}</svg>`;
}

const DEFAULT_LAYOUT = {
    clients: { x: 0, y: 545 },
    gateway: { x: 400, y: 515 },
    lockers: { x: 820, y: 0 },
    requests: { x: 820, y: 260 },
    catalog: { x: 820, y: 520 },
    stats: { x: 820, y: 780 },
    users: { x: 820, y: 1040 },
    lockers_db: { x: 1180, y: 20 },
    catalog_db: { x: 1180, y: 545 },
    requests_db: { x: 1640, y: 540 },
    users_db: { x: 1180, y: 1060 },
};

const EDGE_ROUTES = {
    "gateway>lockers": { from: ["right", 0.15], to: ["left", 0.5] },
    "gateway>requests": { from: ["right", 0.32], to: ["left", 0.5] },
    "gateway>catalog": { from: ["right", 0.5], to: ["left", 0.5] },
    "gateway>stats": { from: ["right", 0.68], to: ["left", 0.5] },
    "gateway>users": { from: ["right", 0.85], to: ["left", 0.5] },
    "requests>stats": { from: ["right", 0.75, 560], to: ["right", 0.25, 560] },
    "requests>requests_db": { from: ["right", 0.25, 500], to: ["left", 0.3, 60] },
    "stats>requests_db": { from: ["right", 0.75, 500], to: ["left", 0.7, 60] },
};

const EDGE_KINDS = {
    external: {
        name: "Внешняя",
        mode: "HTTPS, синхронно",
        hint: "Связь системы с внешним миром. Пользователи ходят только через опубликованный API gateway и ничего не знают о сервисах внутри.",
    },
    pass: {
        name: "Сквозная",
        mode: "REST, синхронно",
        hint: "Запрос проходит сквозь gateway в сервис. Gateway сам данные не использует: проверяет токен и роль, добавляет X-User-Id и передаёт запрос дальше.",
    },
    domain: {
        name: "Предметная",
        mode: "REST /internal, синхронно",
        hint: "Одному сервису нужны данные или действие из чужой предметной области, и он спрашивает об этом сервис-владельца. Нормальная и неизбежная связь.",
    },
    common: {
        name: "Общая",
        mode: "через общую БД",
        hint: "Сервисы не вызывают друг друга, а опираются на одни и те же данные. Если поменять общие данные, это заденет обоих.",
    },
    own: {
        name: "Внутренняя",
        mode: "чтение и запись",
        hint: "Сервис работает со своей собственной базой. Другие сервисы в неё не ходят, поэтому связи между сервисами здесь нет.",
    },
};

function termHtml(kind) {
    const info = EDGE_KINDS[kind];
    if (!info) return esc(kind);
    return `<span class="term" tabindex="0">${esc(info.name)}<span class="term-def">${esc(info.hint)}</span></span>`;
}

const LAYOUT_KEY = "panel-layout-v3";
const POLL_MS = 5000;

const state = {
    topology: null,
    services: {},
    databases: {},
    endpoints: {},
    tables: {},
    positions: {},
    view: { x: 0, y: 0, scale: 1 },
    selected: null,
    hover: null,
    hoverEdge: null,
    auto: true,
    checkedAt: null,
    summaryCollapsed: false,
};

const el = {
    viewport: document.getElementById("viewport"),
    world: document.getElementById("world"),
    edges: document.getElementById("edges"),
    labels: document.getElementById("edge-labels"),
    nodes: document.getElementById("nodes"),
    summary: document.getElementById("summary"),
    drawer: document.getElementById("drawer"),
    zoomValue: document.getElementById("zoom-value"),
    searchInput: document.getElementById("search-input"),
    searchResults: document.getElementById("search-results"),
};

function esc(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

async function api(path, options) {
    const resp = await fetch(path, options);
    if (!resp.ok) {
        let detail = resp.statusText;
        try {
            detail = (await resp.json()).detail || detail;
        } catch (e) {}
        throw new Error(detail);
    }
    return resp.json();
}

function toast(text) {
    const node = document.createElement("div");
    node.className = "toast";
    node.textContent = text;
    document.body.appendChild(node);
    setTimeout(() => node.classList.add("out"), 1600);
    setTimeout(() => node.remove(), 2000);
}

function flash(node) {
    if (!node || node.nodeType !== 1) return;
    node.classList.remove("swap");
    void node.offsetWidth;
    node.classList.add("swap");
}

function patchChildren(oldParent, newParent) {
    const oldKids = [...oldParent.childNodes];
    const newKids = [...newParent.childNodes];
    if (oldKids.length !== newKids.length) {
        oldParent.replaceChildren(...newKids);
        flash(oldParent);
        return;
    }
    for (let i = 0; i < newKids.length; i++) {
        const a = oldKids[i];
        const b = newKids[i];
        if (a.nodeType !== b.nodeType || a.nodeName !== b.nodeName) {
            a.replaceWith(b);
            flash(b);
            continue;
        }
        if (a.nodeType === 3) {
            if (a.textContent !== b.textContent) {
                a.textContent = b.textContent;
                flash(a.parentNode);
            }
            continue;
        }
        if (a.nodeType !== 1 || a.outerHTML === b.outerHTML) continue;
        for (const attr of [...a.attributes]) {
            if (attr.name === "class") continue;
            if (!b.hasAttribute(attr.name)) a.removeAttribute(attr.name);
        }
        for (const attr of [...b.attributes]) {
            if (attr.name === "class") continue;
            if (a.getAttribute(attr.name) !== attr.value) a.setAttribute(attr.name, attr.value);
        }
        const keep = a.classList.contains("swap");
        a.className = b.className;
        if (keep) a.classList.add("swap");
        patchChildren(a, b);
    }
}

function patchHtml(target, html) {
    if (!target.firstChild) {
        target.innerHTML = html;
        return;
    }
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    patchChildren(target, tmp);
}

function highlightJson(text) {
    let pretty = text;
    try {
        pretty = JSON.stringify(JSON.parse(text), null, 2);
    } catch (e) {
        return esc(text);
    }
    return esc(pretty).replace(
        /(&quot;(?:\\.|[^&\\]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
        (match, str, colon, bool) => {
            if (str) {
                return colon ? `<span class="j-key">${str}</span>${colon}` : `<span class="j-str">${str}</span>`;
            }
            if (bool) return `<span class="j-bool">${match}</span>`;
            if (match === "null") return `<span class="j-null">null</span>`;
            return `<span class="j-num">${match}</span>`;
        }
    );
}

function plural(n, one, few, many) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return `${n} ${one}`;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return `${n} ${few}`;
    return `${n} ${many}`;
}


function serviceById(id) {
    return state.topology.services.find((s) => s.id === id);
}

function databaseById(id) {
    return state.topology.databases.find((d) => d.id === id);
}

function serviceStatus(id) {
    return state.services[id] || { status: "unknown", online: false };
}

function isOnline(id) {
    if (id === "clients") return true;
    if (state.databases[id]) return state.databases[id].online;
    return serviceStatus(id).status === "online";
}

function dbEngine(url) {
    if (url.startsWith("sqlite")) return "SQLite";
    if (url.startsWith("postgres")) return "PostgreSQL";
    return url.split(":")[0];
}

function endpointStats(id) {
    const data = state.endpoints[id];
    if (!data) return null;
    let implemented = 0;
    for (const ep of data.endpoints) {
        if (ep.state === "implemented" || ep.state === "proxy") implemented++;
    }
    return { implemented, total: data.endpoints.length, source: data.source };
}

async function loadEndpoints(id) {
    try {
        state.endpoints[id] = await api(`/api/services/${id}/endpoints`);
    } catch (e) {
        return;
    }
    renderNode(id);
    renderSummary();
}

async function loadTables(id) {
    try {
        state.tables[id] = await api(`/api/databases/${id}/tables`);
    } catch (e) {
        return;
    }
    renderNode(id);
    layoutEdges();
}

async function refreshStatus(manual) {
    const btn = document.getElementById("refresh-btn");
    btn.classList.add("spin");
    try {
        const data = await api("/api/status");
        for (const s of data.services) {
            const before = state.services[s.id];
            state.services[s.id] = s;
            if (!before || before.status !== s.status) loadEndpoints(s.id);
        }
        for (const d of data.databases) {
            const before = state.databases[d.id];
            state.databases[d.id] = d;
            if (!before || before.online !== d.online || before.rows !== d.rows || before.tables !== d.tables) {
                loadTables(d.id);
            }
        }
        state.checkedAt = data.checked_at;
        renderAllNodes();
        renderSummary();
        updateDrawerHeader();
        if (manual) toast("Статусы обновлены");
    } catch (e) {
        if (manual) toast("Панель не отвечает: " + e.message);
    } finally {
        setTimeout(() => btn.classList.remove("spin"), 300);
    }
}


function allNodeIds() {
    const ids = ["clients"];
    for (const s of state.topology.services) ids.push(s.id);
    for (const d of state.topology.databases) ids.push(d.id);
    return ids;
}

function statusLine(id) {
    const s = serviceStatus(id);
    if (s.status === "online") {
        return `<div class="node-status online"><span class="dot pulse"></span>Работает, ${s.latency_ms} мс</div>`;
    }
    if (s.status === "error") {
        return `<div class="node-status error"><span class="dot"></span>Ошибка /health</div>`;
    }
    if (s.status === "timeout") {
        return `<div class="node-status error"><span class="dot"></span>Не отвечает</div>`;
    }
    if (s.status === "offline") {
        return `<div class="node-status offline"><span class="dot"></span>Не запущен</div>`;
    }
    return `<div class="node-status static"><span class="dot"></span>Проверка...</div>`;
}

function serviceNodeHtml(service) {
    const s = serviceStatus(service.id);
    const url = new URL(service.url);
    const stats = endpointStats(service.id);
    let endpointsText = plural(service.endpoints.length, "ручка", "ручки", "ручек") + " в плане";
    if (stats && stats.source === "openapi") {
        endpointsText = `${stats.implemented} из ${stats.total}`;
    }
    const db = service.database ? databaseById(service.database) : null;
    const iconName = service.id === "gateway" ? "gateway" : "server";
    return `
        <div class="node-head">
            <div>
                <div class="node-title">${esc(service.name)}</div>
                ${statusLine(service.id)}
            </div>
        </div>
        <div class="rows">
            <div class="row"><span class="k">Адрес</span><span class="v mono">${esc(url.host)}</span></div>
            <div class="row"><span class="k">${service.id === "gateway" ? "Маршруты" : "Ручки"}</span><span class="v">${esc(endpointsText)}</span></div>
            <div class="row"><span class="k">База данных</span><span class="v">${db ? esc(db.name) : "нет"}</span></div>
            ${s.status === "online" && s.health && s.health.status ? `<div class="row"><span class="k">/health</span><span class="v mono">${esc(s.health.status)}</span></div>` : ""}
        </div>`;
}

function databaseNodeHtml(db) {
    const status = state.databases[db.id];
    const tables = state.tables[db.id];
    let statusHtml = `<div class="node-status static"><span class="dot"></span>Проверка...</div>`;
    if (status && status.online) {
        statusHtml = `<div class="node-status online"><span class="dot"></span>${dbEngine(db.url)}, ${plural(status.rows, "строка", "строки", "строк")}</div>`;
    } else if (status) {
        statusHtml = `<div class="node-status offline"><span class="dot"></span>Не создана</div>`;
    }

    let lines = "";
    if (tables && tables.online) {
        for (const t of tables.tables) {
            lines += `<div class="table-line"><span class="name">${esc(t.name)}</span><span class="count">${t.rows}</span></div>`;
        }
    } else {
        for (const t of db.tables) {
            lines += `<div class="table-line"><span class="name">${esc(t.name)}</span><span class="plan">план</span></div>`;
        }
    }
    return `
        <div class="node-head">
            <div>
                <div class="node-title">${esc(db.name)}</div>
                ${statusHtml}
            </div>
        </div>
        <div class="rows">${lines || '<div class="table-line"><span class="plan">таблиц нет</span></div>'}</div>`;
}

function clientsNodeHtml() {
    return `
        <div class="node-head">
            <div>
                <div class="node-title">Клиенты</div>
                <div class="node-status static"><span class="dot"></span>Веб-кабинеты, HTTPS</div>
            </div>
        </div>
        <div class="chips">
            <span class="chip">Клиент</span><span class="chip">Сотрудник</span><span class="chip">Начальник</span>
        </div>`;
}

function renderNode(id) {
    let node = document.getElementById("node-" + id);
    if (!node) {
        node = document.createElement("div");
        node.id = "node-" + id;
        node.className = "node";
        node.dataset.id = id;
        node.style.animationDelay = allNodeIds().indexOf(id) * 40 + "ms";
        el.nodes.appendChild(node);
        attachNodeEvents(node);
    }

    let html = "";
    let offline = false;
    if (id === "clients") {
        html = clientsNodeHtml();
    } else if (serviceById(id)) {
        html = serviceNodeHtml(serviceById(id));
        offline = serviceStatus(id).status === "offline";
    } else {
        const db = databaseById(id);
        html = databaseNodeHtml(db);
        node.style.width = "220px";
        offline = state.databases[id] && !state.databases[id].online;
    }

    patchHtml(node, html);
    node.classList.toggle("offline", Boolean(offline));
    node.classList.toggle("selected", state.selected === id);
    placeNode(node, id);
}

function renderAllNodes() {
    for (const id of allNodeIds()) renderNode(id);
    layoutEdges();
}

function placeNode(node, id) {
    const pos = state.positions[id];
    node.style.left = pos.x - node.offsetWidth / 2 + "px";
    node.style.top = pos.y + "px";
}

function nodeBox(id) {
    const node = document.getElementById("node-" + id);
    const pos = state.positions[id];
    const w = node.offsetWidth;
    const h = node.offsetHeight;
    return { left: pos.x - w / 2, right: pos.x + w / 2, top: pos.y, bottom: pos.y + h, cx: pos.x, cy: pos.y + h / 2 };
}


function anchor(box, side, frac = 0.5) {
    const w = box.right - box.left;
    const h = box.bottom - box.top;
    if (side === "top") return { x: box.left + w * frac, y: box.top, dx: 0, dy: -1 };
    if (side === "bottom") return { x: box.left + w * frac, y: box.bottom, dx: 0, dy: 1 };
    if (side === "left") return { x: box.left, y: box.top + h * frac, dx: -1, dy: 0 };
    return { x: box.right, y: box.top + h * frac, dx: 1, dy: 0 };
}

function pickSides(a, b) {
    if (b.left > a.right + 20) return ["right", "left"];
    if (b.right < a.left - 20) return ["left", "right"];
    return b.cy > a.cy ? ["bottom", "top"] : ["top", "bottom"];
}

function edgeGeometry(edge) {
    const a = nodeBox(edge.from);
    const b = nodeBox(edge.to);
    const route = EDGE_ROUTES[edge.from + ">" + edge.to];
    let from = [];
    let to = [];
    if (route) {
        from = route.from;
        to = route.to;
    } else {
        const sides = pickSides(a, b);
        from = [sides[0]];
        to = [sides[1]];
    }
    const p0 = anchor(a, from[0], from[1] ?? 0.5);
    const p3 = anchor(b, to[0], to[1] ?? 0.5);
    const horizontal = p0.dx !== 0;
    const span = horizontal ? Math.abs(p3.x - p0.x) : Math.abs(p3.y - p0.y);
    const k0 = from[2] ?? Math.max(30, span * 0.5);
    const k3 = to[2] ?? Math.max(30, span * 0.5);
    const p1 = { x: p0.x + p0.dx * k0, y: p0.y + p0.dy * k0 };
    const p2 = { x: p3.x + p3.dx * k3, y: p3.y + p3.dy * k3 };
    const mid = {
        x: 0.125 * p0.x + 0.375 * p1.x + 0.375 * p2.x + 0.125 * p3.x,
        y: 0.125 * p0.y + 0.375 * p1.y + 0.375 * p2.y + 0.125 * p3.y,
    };
    const d = `M${p0.x},${p0.y} C${p1.x},${p1.y} ${p2.x},${p2.y} ${p3.x},${p3.y}`;
    return { d, mid };
}

function nodeName(id) {
    if (id === "clients") return "Клиенты";
    return (serviceById(id) || databaseById(id)).name;
}

function edgeState(edge) {
    const fromOnline = isOnline(edge.from);
    const toOnline = isOnline(edge.to);
    if (fromOnline && toOnline) return "live";
    if (fromOnline) return "down";
    return "idle";
}

function buildEdges() {
    const svgNs = "http://www.w3.org/2000/svg";
    el.edges.innerHTML = "";
    el.labels.innerHTML = "";
    state.topology.edges.forEach((edge, i) => {
        const line = document.createElementNS(svgNs, "path");
        line.dataset.i = i;
        const hit = document.createElementNS(svgNs, "path");
        hit.setAttribute("class", "edge-hit");
        hit.dataset.i = i;
        hit.addEventListener("pointerenter", (e) => showEdgeTip(i, e));
        hit.addEventListener("pointerleave", scheduleHideTip);
        el.edges.appendChild(line);
        el.edges.appendChild(hit);
        const label = document.createElement("div");
        label.dataset.i = i;
        label.textContent = edge.label || "";
        el.labels.appendChild(label);
    });
}

function layoutEdges() {
    if (!state.topology) return;
    if (el.edges.childNodes.length !== state.topology.edges.length * 2) buildEdges();
    const focus = state.hover || state.selected;
    state.topology.edges.forEach((edge, i) => {
        const { d, mid } = edgeGeometry(edge);
        const line = el.edges.querySelector(`path[data-i="${i}"]:not(.edge-hit)`);
        const hit = el.edges.querySelector(`path.edge-hit[data-i="${i}"]`);
        const label = el.labels.querySelector(`div[data-i="${i}"]`);
        const st = edgeState(edge);
        let dim = focus && edge.from !== focus && edge.to !== focus;
        if (state.hoverEdge !== null && state.hoverEdge !== i) dim = true;
        const hot = state.hoverEdge === i;
        const kind = edge.kind === "common" ? " common" : "";
        line.setAttribute("d", d);
        hit.setAttribute("d", d);
        line.setAttribute("class", `edge ${st}${kind}${dim ? " dim" : ""}${hot ? " hot" : ""}`);
        label.className = `edge-label ${st}${dim ? " dim" : ""}${hot ? " hot" : ""}`;
        label.style.display = edge.label ? "" : "none";
        label.style.left = mid.x + "px";
        label.style.top = mid.y + "px";
    });
}

let tipTimer = null;

function showEdgeTip(i, event) {
    clearTimeout(tipTimer);
    if (state.hoverEdge === i) return;
    const edge = state.topology.edges[i];
    const kind = EDGE_KINDS[edge.kind];
    const st = edgeState(edge);
    let stateText = '<span class="badge green">обе стороны работают</span>';
    if (st === "down") stateText = `<span class="badge red">${esc(nodeName(edge.to))} выключен</span>`;
    if (st === "idle") stateText = '<span class="badge">не активна</span>';
    const tip = document.getElementById("edge-tip");
    tip.innerHTML = `
        <div class="tip-title">${termHtml(edge.kind)} связанность</div>
        <div class="tip-route">${esc(nodeName(edge.from))} <span>-></span> ${esc(nodeName(edge.to))}</div>
        <div class="tip-row"><span class="k">Взаимодействие</span><span class="v">${esc(kind.mode)}</span></div>
        ${edge.endpoint ? `<div class="tip-row"><span class="k">Метод</span><span class="v mono">${esc(edge.endpoint)}</span></div>` : ""}
        ${edge.data ? `<div class="tip-data">${esc(edge.data)}</div>` : ""}
        <div class="tip-state">${stateText}</div>`;
    state.hoverEdge = i;
    layoutEdges();
    tip.classList.add("show");
    moveEdgeTip(event);
}

function moveEdgeTip(event) {
    const tip = document.getElementById("edge-tip");
    let x = event.clientX + 12;
    let y = event.clientY + 12;
    if (x + tip.offsetWidth > window.innerWidth - 10) x = event.clientX - tip.offsetWidth - 16;
    if (y + tip.offsetHeight > window.innerHeight - 10) y = event.clientY - tip.offsetHeight - 16;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
}

function scheduleHideTip() {
    clearTimeout(tipTimer);
    tipTimer = setTimeout(hideEdgeTip, 220);
}

function hideEdgeTip() {
    state.hoverEdge = null;
    document.getElementById("edge-tip").classList.remove("show");
    layoutEdges();
}

function setupEdgeTip() {
    const tip = document.getElementById("edge-tip");
    tip.addEventListener("pointerenter", () => clearTimeout(tipTimer));
    tip.addEventListener("pointerleave", scheduleHideTip);
}

function applyView(animated) {
    const v = state.view;
    el.world.classList.toggle("animated", Boolean(animated));
    el.world.style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.scale})`;
    el.viewport.style.backgroundSize = `${24 * v.scale}px ${24 * v.scale}px`;
    el.viewport.style.backgroundPosition = `${v.x}px ${v.y}px`;
    el.zoomValue.textContent = Math.round(v.scale * 100) + "%";
    clearTimeout(applyView.timer);
    if (animated) applyView.timer = setTimeout(() => el.world.classList.remove("animated"), 560);
}

function visibleArea() {
    let right = window.innerWidth;
    if (el.drawer.classList.contains("open")) {
        right -= el.drawer.offsetWidth + 36;
    } else if (!state.summaryCollapsed && window.innerWidth > 900) {
        right -= el.summary.offsetWidth + 30;
    }
    return { left: 0, top: 70, right, bottom: window.innerHeight - 90 };
}

function fitView(animated) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of allNodeIds()) {
        const b = nodeBox(id);
        minX = Math.min(minX, b.left);
        minY = Math.min(minY, b.top);
        maxX = Math.max(maxX, b.right);
        maxY = Math.max(maxY, b.bottom);
    }
    const area = visibleArea();
    const w = area.right - area.left - 80;
    const h = area.bottom - area.top - 40;
    const scale = Math.min(1.1, Math.max(0.3, Math.min(w / (maxX - minX), h / (maxY - minY))));
    state.view.scale = scale;
    state.view.x = area.left + (area.right - area.left) / 2 - ((minX + maxX) / 2) * scale;
    state.view.y = area.top + (area.bottom - area.top) / 2 - ((minY + maxY) / 2) * scale;
    applyView(animated);
}

function focusNode(id) {
    const b = nodeBox(id);
    const area = visibleArea();
    const scale = Math.max(state.view.scale, 0.8);
    state.view.scale = scale;
    state.view.x = (area.left + area.right) / 2 - b.cx * scale;
    state.view.y = (area.top + area.bottom) / 2 - b.cy * scale;
    applyView(true);
}

function zoomAt(factor, cx, cy, animated) {
    const v = state.view;
    const next = Math.min(2, Math.max(0.25, v.scale * factor));
    v.x = cx - (cx - v.x) * (next / v.scale);
    v.y = cy - (cy - v.y) * (next / v.scale);
    v.scale = next;
    applyView(Boolean(animated));
}

function animatePositions(target, done) {
    const start = {};
    for (const id of Object.keys(target)) start[id] = { ...state.positions[id] };
    const t0 = performance.now();
    const ms = 550;
    const ease = (t) => 1 - Math.pow(1 - t, 4);
    const step = (now) => {
        const t = Math.min(1, (now - t0) / ms);
        const k = ease(t);
        for (const id of Object.keys(target)) {
            state.positions[id] = {
                x: start[id].x + (target[id].x - start[id].x) * k,
                y: start[id].y + (target[id].y - start[id].y) * k,
            };
            placeNode(document.getElementById("node-" + id), id);
        }
        layoutEdges();
        if (t < 1) requestAnimationFrame(step);
        else if (done) done();
    };
    requestAnimationFrame(step);
}

function savePositions() {
    try {
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(state.positions));
    } catch (e) {}
}

function loadPositions() {
    let saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "{}");
    } catch (e) {}
    for (const id of Object.keys(DEFAULT_LAYOUT)) {
        state.positions[id] = saved[id] || { ...DEFAULT_LAYOUT[id] };
    }
}

function attachNodeEvents(node) {
    const id = node.dataset.id;
    node.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        event.stopPropagation();
        const startX = event.clientX;
        const startY = event.clientY;
        const startPos = { ...state.positions[id] };
        let moved = false;
        node.setPointerCapture(event.pointerId);

        const move = (e) => {
            const dx = (e.clientX - startX) / state.view.scale;
            const dy = (e.clientY - startY) / state.view.scale;
            if (!moved && Math.hypot(dx, dy) < 4) return;
            moved = true;
            node.classList.add("dragging");
            state.positions[id] = { x: startPos.x + dx, y: startPos.y + dy };
            placeNode(node, id);
            layoutEdges();
        };
        const up = () => {
            node.removeEventListener("pointermove", move);
            node.removeEventListener("pointerup", up);
            node.classList.remove("dragging");
            if (moved) {
                savePositions();
            } else {
                if (drawer.id === id) closeDrawer();
                else openNode(id);
            }
        };
        node.addEventListener("pointermove", move);
        node.addEventListener("pointerup", up);
    });
    node.addEventListener("mouseenter", () => {
        state.hover = id;
        layoutEdges();
    });
    node.addEventListener("mouseleave", () => {
        state.hover = null;
        layoutEdges();
    });
}

function setupCanvas() {
    el.viewport.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        const startX = event.clientX;
        const startY = event.clientY;
        const startView = { ...state.view };
        el.viewport.classList.add("panning");
        el.viewport.setPointerCapture(event.pointerId);
        const move = (e) => {
            state.view.x = startView.x + e.clientX - startX;
            state.view.y = startView.y + e.clientY - startY;
            applyView(false);
        };
        const up = () => {
            el.viewport.classList.remove("panning");
            el.viewport.removeEventListener("pointermove", move);
            el.viewport.removeEventListener("pointerup", up);
        };
        el.viewport.addEventListener("pointermove", move);
        el.viewport.addEventListener("pointerup", up);
    });

    el.viewport.addEventListener("wheel", (event) => {
        event.preventDefault();
        zoomAt(Math.exp(-event.deltaY * 0.0015), event.clientX, event.clientY);
    }, { passive: false });

    const center = () => [window.innerWidth / 2, window.innerHeight / 2];
    document.getElementById("zoom-in").innerHTML = icon("plus");
    document.getElementById("zoom-out").innerHTML = icon("minus");
    document.getElementById("zoom-fit").innerHTML = icon("fit");
    document.getElementById("layout-reset").innerHTML = icon("layout");
    document.getElementById("zoom-in").onclick = () => zoomAt(1.25, ...center(), true);
    document.getElementById("zoom-out").onclick = () => zoomAt(1 / 1.25, ...center(), true);
    document.getElementById("zoom-fit").onclick = () => fitView(true);
    document.getElementById("layout-reset").onclick = () => {
        animatePositions(DEFAULT_LAYOUT, () => {
            savePositions();
            fitView(true);
        });
    };
    window.addEventListener("resize", () => layoutEdges());
}


function renderSummary() {
    if (!state.topology) return;
    const services = state.topology.services;
    const dbs = state.topology.databases;
    const onlineServices = services.filter((s) => serviceStatus(s.id).status === "online").length;
    const onlineDbs = dbs.filter((d) => state.databases[d.id] && state.databases[d.id].online).length;

    let implemented = 0;
    let planned = 0;
    for (const s of services) {
        if (s.id === "gateway") continue;
        const stats = endpointStats(s.id);
        planned += s.endpoints.length;
        if (stats && stats.source === "openapi") implemented += stats.implemented;
    }

    const badgeClass = onlineServices === services.length ? "green" : onlineServices === 0 ? "red" : "amber";
    const gw = serviceStatus("gateway").status === "online";

    let serviceLines = "";
    for (const s of services) {
        const st = serviceStatus(s.id);
        let meta = "...";
        if (st.status === "online") meta = st.latency_ms + " мс";
        if (st.status === "offline") meta = "offline";
        if (st.status === "error") meta = "ошибка";
        if (st.status === "timeout") meta = "таймаут";
        serviceLines += `<div class="svc-line ${st.status}" data-open="${s.id}"><span class="dot"></span><span class="name">${esc(s.name)}</span><span class="meta">${meta}</span></div>`;
    }
    let dbLines = "";
    for (const d of dbs) {
        const st = state.databases[d.id];
        const online = st && st.online;
        dbLines += `<div class="svc-line ${online ? "online" : "offline"}" data-open="${d.id}"><span class="dot"></span><span class="name">${esc(d.name)}</span><span class="meta">${online ? plural(st.rows, "строка", "строки", "строк") : "нет"}</span></div>`;
    }

    el.summary.classList.toggle("collapsed", state.summaryCollapsed);
    patchHtml(el.summary, `
        <div class="panel-head">
            <span class="panel-title">Общая сводка</span>
            <span class="badge ${badgeClass}">${onlineServices}/${services.length}</span>
            <span class="spacer"></span>
            <button class="ghost-btn" data-toggle="summary" title="Свернуть">${icon("expand")}</button>
        </div>
        <div class="summary-collapse">
            <div class="summary-body">
                <div class="section-label">Ключевые факты</div>
                <div class="fact"><span class="k">Сервисы онлайн</span><span class="v">${onlineServices} из ${services.length}</span></div>
                <div class="fact"><span class="k">Базы данных</span><span class="v">${onlineDbs} из ${dbs.length}</span></div>
                <div class="fact"><span class="k">Ручки сервисов</span><span class="v">${implemented} из ${planned}</span></div>
                <div class="fact"><span class="k">Gateway</span><span class="v">${gw ? '<span class="badge green">работает</span>' : '<span class="badge red">выключен</span>'}</span></div>
                <div class="divider"></div>
                <div class="section-label">Сервисы</div>
                ${serviceLines}
                <div class="section-label">Базы данных</div>
                ${dbLines}
                <div class="checked">${state.checkedAt ? "Проверено в " + state.checkedAt.slice(11) : "Проверка..."}${state.auto ? ", каждые 5 с" : ""}</div>
            </div>
        </div>`);
}

function setupSummary() {
    el.summary.addEventListener("click", (event) => {
        if (event.target.closest("[data-toggle]")) {
            state.summaryCollapsed = !state.summaryCollapsed;
            el.summary.classList.toggle("collapsed", state.summaryCollapsed);
            return;
        }
        const line = event.target.closest("[data-open]");
        if (line) openNode(line.dataset.open, { focus: true });
    });
}


const drawer = {
    id: null,
    kind: null,
    tab: null,
    openEndpoint: null,
    table: null,
    search: "",
    offset: 0,
    limit: 50,
};

function openNode(id, options = {}) {
    if (id === "clients") return;
    state.selected = id;
    drawer.id = id;
    drawer.kind = serviceById(id) ? "service" : "database";
    drawer.tab = options.tab || (drawer.kind === "service" ? "api" : "tables");
    drawer.openEndpoint = options.endpoint || null;
    drawer.table = options.table || null;
    drawer.search = "";
    drawer.offset = 0;
    el.drawer.classList.add("open");
    el.summary.classList.add("hidden");
    document.body.classList.add("drawer-open");
    renderAllNodes();
    renderDrawer();
    if (options.focus) setTimeout(() => focusNode(id), 50);
}

function closeDrawer() {
    state.selected = null;
    drawer.id = null;
    el.drawer.classList.remove("open");
    el.summary.classList.remove("hidden");
    document.body.classList.remove("drawer-open");
    renderAllNodes();
}

function statusBadge(id) {
    if (drawer.kind === "database") {
        const st = state.databases[id];
        if (!st) return '<span class="badge">проверка</span>';
        return st.online ? '<span class="badge teal">доступна</span>' : '<span class="badge red">не создана</span>';
    }
    const st = serviceStatus(id);
    if (st.status === "online") return `<span class="badge green">работает, ${st.latency_ms} мс</span>`;
    if (st.status === "error") return '<span class="badge amber">ошибка /health</span>';
    if (st.status === "timeout") return '<span class="badge amber">не отвечает</span>';
    if (st.status === "offline") return '<span class="badge red">не запущен</span>';
    return '<span class="badge">проверка</span>';
}

function updateDrawerHeader() {
    if (!drawer.id) return;
    const holder = document.getElementById("drawer-status");
    if (holder) holder.innerHTML = statusBadge(drawer.id);
    const tabs = document.getElementById("drawer-tabs");
    if (tabs && drawer.kind === "service") {
        const stats = endpointStats(drawer.id);
        const count = document.getElementById("api-count");
        if (count && stats) count.textContent = stats.total;
    }
}

function renderDrawer() {
    if (drawer.kind === "service") renderServiceDrawer();
    else renderDatabaseDrawer();
}

function renderServiceDrawer() {
    const service = serviceById(drawer.id);
    const st = serviceStatus(service.id);
    const stats = endpointStats(service.id);
    const online = st.status === "online";
    el.drawer.innerHTML = `
        <div class="drawer-head">
            <div class="drawer-title">
                <div style="flex:1;min-width:0">
                    <div class="drawer-name">${esc(service.name)}</div>
                    <div class="drawer-sub">${esc(service.description)}</div>
                </div>
                <button class="ghost-btn" id="drawer-close" title="Закрыть (Esc)">${icon("close")}</button>
            </div>
            <div class="drawer-meta">
                <span id="drawer-status">${statusBadge(service.id)}</span>
                <span class="mono-pill">${esc(service.url)}</span>
                ${online ? `<a class="link-pill" href="${esc(service.url)}/docs" target="_blank" rel="noopener">Swagger ${icon("external")}</a>` : ""}
            </div>
            <div class="tabs" id="drawer-tabs" data-active="${drawer.tab === "overview" ? 1 : 0}">
                <button class="tab ${drawer.tab === "api" ? "active" : ""}" data-tab="api">API <span class="badge" id="api-count">${stats ? stats.total : service.endpoints.length}</span></button>
                <button class="tab ${drawer.tab === "overview" ? "active" : ""}" data-tab="overview">Обзор</button>
            </div>
        </div>
        <div class="drawer-body enter" id="drawer-body"></div>`;

    document.getElementById("drawer-close").onclick = closeDrawer;
    const tabs = document.getElementById("drawer-tabs");
    for (const tab of el.drawer.querySelectorAll(".tab")) {
        tab.onclick = () => {
            if (drawer.tab === tab.dataset.tab) return;
            drawer.tab = tab.dataset.tab;
            tabs.dataset.active = drawer.tab === "overview" ? 1 : 0;
            for (const t of tabs.querySelectorAll(".tab")) t.classList.toggle("active", t === tab);
            const body = document.getElementById("drawer-body");
            body.classList.remove("enter");
            void body.offsetWidth;
            body.classList.add("enter");
            if (drawer.tab === "overview") renderServiceOverview(service);
            else renderEndpointList(service);
        };
    }

    if (drawer.tab === "overview") renderServiceOverview(service);
    else renderEndpointList(service);
}

function renderServiceOverview(service) {
    const st = serviceStatus(service.id);
    const stats = endpointStats(service.id);
    const db = service.database ? databaseById(service.database) : null;
    const body = document.getElementById("drawer-body");
    let html = "";
    if (st.status === "offline") {
        html += `<div class="notice red">Сервис не отвечает на <code>${esc(service.url)}/health</code>. Запустите его: <code>uvicorn main:app --port ${service.port}</code></div>`;
    }
    html += `
        <div class="card-block">
            <div class="fact"><span class="k">Порт</span><span class="v">${service.port}</span></div>
            <div class="fact"><span class="k">Переменная адреса</span><span class="v" style="font-family:var(--mono);font-size:11.5px">${esc(service.env)}</span></div>
            <div class="fact"><span class="k">База данных</span><span class="v">${db ? esc(db.name) : "нет"}</span></div>
            <div class="fact"><span class="k">Ручки</span><span class="v">${stats && stats.source === "openapi" ? `${stats.implemented} реализовано из ${stats.total}` : `${service.endpoints.length} в плане`}</span></div>
            <div class="fact"><span class="k">Источник списка ручек</span><span class="v">${stats && stats.source === "openapi" ? "openapi.json" : "архитектурный план"}</span></div>
        </div>`;
    if (st.health) {
        html += `<div class="section-label">Ответ /health</div><div class="card-block"><pre class="code">${highlightJson(JSON.stringify(st.health))}</pre></div>`;
    }
    const related = state.topology.edges.filter((e) => e.from === service.id || e.to === service.id);
    if (related.length) {
        html += '<div class="section-label">Связи</div><div class="card-block">';
        for (const e of related) {
            const other = e.from === service.id ? e.to : e.from;
            const name = other === "clients" ? "Клиенты" : (serviceById(other) || databaseById(other)).name;
            const dir = e.from === service.id ? "->" : "<-";
            html += `<div class="fact"><span class="k">${dir} ${esc(name)}</span><span class="v">${termHtml(e.kind)}</span></div>`;
        }
        html += "</div>";
    }
    body.innerHTML = html;
}

function endpointKey(ep) {
    return ep.method + " " + ep.path;
}

function findTargetEndpoint(ep) {
    if (!ep.target || !state.endpoints[ep.target]) return null;
    const norm = (p) => p.replace(/\{[^/]+\}/g, "{}");
    return state.endpoints[ep.target].endpoints.find(
        (x) => x.method === ep.method && norm(x.path) === norm(ep.path) && x.state === "implemented"
    );
}

function renderEndpointList(service) {
    const body = document.getElementById("drawer-body");
    const data = state.endpoints[service.id];
    const st = serviceStatus(service.id);
    if (!data) {
        body.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
        return;
    }
    let html = "";
    if (st.status !== "online") {
        html += `<div class="notice red">Сервис не запущен, поэтому показан список ручек из архитектурного плана. Отправить запрос не получится.</div>`;
    } else if (service.id === "gateway") {
        html += `<div class="notice blue">Запросы идут через gateway: токен выбирается ниже. Ручка работает, только если запущен сервис, в который она ведёт.</div>`;
    }
    for (const ep of data.endpoints) {
        const key = endpointKey(ep);
        let tag = "";
        if (ep.state === "planned") tag = '<span class="ep-tag planned">план</span>';
        if (ep.state === "proxy") {
            tag = isOnline(ep.target)
                ? `<span class="ep-tag proxy">-> ${esc(serviceById(ep.target).name)}</span>`
                : `<span class="ep-tag down">${esc(serviceById(ep.target).name)} выключен</span>`;
        }
        const open = drawer.openEndpoint === key;
        html += `
            <div class="ep ${ep.state} ${open ? "open" : ""}" data-key="${esc(key)}">
                <div class="ep-head">
                    <span class="method ${ep.method}">${ep.method}</span>
                    <span class="ep-path">${esc(ep.path)}</span>
                    ${tag}
                </div>
                ${ep.summary && !open ? `<div class="ep-summary">${esc(ep.summary)}</div>` : ""}
                ${open ? '<div class="ep-collapse"><div class="ep-body"></div></div>' : ""}
            </div>`;
    }
    body.innerHTML = html;

    for (const item of body.querySelectorAll(".ep")) {
        item.querySelector(".ep-head").onclick = () => {
            body.classList.remove("enter");
            const opened = body.querySelector(".ep.open");
            const next = drawer.openEndpoint === item.dataset.key ? null : item.dataset.key;
            if (opened) {
                opened.classList.remove("expanded");
                setTimeout(() => {
                    drawer.openEndpoint = next;
                    renderEndpointList(service);
                }, 260);
            } else {
                drawer.openEndpoint = next;
                renderEndpointList(service);
            }
        };
    }
    const openItem = body.querySelector(".ep.open");
    if (openItem) {
        const ep = data.endpoints.find((x) => endpointKey(x) === drawer.openEndpoint);
        renderRequestBuilder(service, ep, openItem.querySelector(".ep-body"));
        void openItem.offsetHeight;
        openItem.classList.add("expanded");
        setTimeout(() => openItem.scrollIntoView({ block: "nearest", behavior: "smooth" }), 280);
    }
}

function defaultToken(roles) {
    if (!roles || roles === "без токена") return "";
    if (roles.includes("CLIENT") || roles.includes("все")) return "client";
    if (roles.includes("EMPLOYEE")) return "employee";
    if (roles.includes("MANAGER")) return "manager";
    return "admin";
}

function renderRequestBuilder(service, ep, holder) {
    const isGateway = service.id === "gateway";
    const source = isGateway ? findTargetEndpoint(ep) || ep : ep;
    const params = source.parameters || [];
    const pathNames = [...ep.path.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]);
    const queryParams = params.filter((p) => p.in === "query");
    const headerParams = params.filter((p) => p.in === "header");
    const hasBody = ["POST", "PUT", "PATCH"].includes(ep.method);
    const bodyText = source.body_example != null ? JSON.stringify(source.body_example, null, 2) : hasBody ? "{\n  \n}" : "";

    let html = "";
    if (source.description) html += `<div class="ep-summary" style="padding:10px 0 0">${esc(source.description)}</div>`;
    if (ep.roles) html += `<div class="field"><label>Роли</label><div style="color:var(--muted);font-size:12px">${esc(ep.roles)}</div></div>`;

    if (isGateway) {
        let segs = `<button class="seg" data-token="">без токена</button>`;
        for (const t of state.topology.mock_tokens) segs += `<button class="seg" data-token="${t}">${t}</button>`;
        html += `<div class="field"><label>Токен <span class="hint">Authorization: Bearer ...</span></label><div class="segmented" id="token-seg">${segs}</div></div>`;
    }
    if (pathNames.length) {
        html += '<div class="field"><label>Параметры пути</label><div class="param-grid">';
        for (const name of pathNames) {
            html += `<span class="pname">${esc(name)}<b>*</b></span><input class="input" data-path="${esc(name)}" placeholder="${esc(name)}">`;
        }
        html += "</div></div>";
    }
    if (queryParams.length || headerParams.length) {
        html += '<div class="field"><label>Query и заголовки</label><div class="param-grid">';
        for (const p of queryParams) {
            html += `<span class="pname" title="${esc(p.description)}">?${esc(p.name)}</span><input class="input" data-query="${esc(p.name)}" value="${esc(p.default ?? "")}" placeholder="${esc(p.description || p.name)}">`;
        }
        for (const p of headerParams) {
            html += `<span class="pname" title="${esc(p.description)}">${esc(p.name)}</span><input class="input" data-header="${esc(p.name)}" value="${esc(p.default ?? "")}">`;
        }
        html += "</div></div>";
    }
    html += `<div class="field"><label>Доп. query <span class="hint">key=value&amp;key2=value2</span></label><input class="input" id="extra-query" placeholder="key=value"></div>`;
    if (hasBody) {
        html += `<div class="field"><label>Тело запроса <span class="hint">JSON</span></label><textarea class="textarea" id="req-body" spellcheck="false">${esc(bodyText)}</textarea></div>`;
    }
    const online = serviceStatus(service.id).status === "online";
    html += `
        <div class="send-row">
            <button class="btn-primary" id="send-btn" ${online ? "" : "disabled"}>Отправить ${icon("send")}</button>
            <span class="url-preview" id="url-preview"></span>
        </div>
        <div id="response"></div>`;
    holder.innerHTML = html;

    let token = isGateway ? defaultToken(ep.roles) : "";
    const segs = holder.querySelectorAll("#token-seg .seg");
    const markToken = () => segs.forEach((s) => s.classList.toggle("active", s.dataset.token === token));
    segs.forEach((s) => (s.onclick = () => { token = s.dataset.token; markToken(); }));
    markToken();

    const buildPath = () => {
        let path = ep.path;
        for (const input of holder.querySelectorAll("[data-path]")) {
            path = path.replace(`{${input.dataset.path}}`, encodeURIComponent(input.value.trim()) || `{${input.dataset.path}}`);
        }
        return path;
    };
    const buildQuery = () => {
        const query = {};
        for (const input of holder.querySelectorAll("[data-query]")) {
            if (input.value.trim() !== "") query[input.dataset.query] = input.value.trim();
        }
        const extra = holder.querySelector("#extra-query").value.trim();
        if (extra) {
            for (const [k, v] of new URLSearchParams(extra)) query[k] = v;
        }
        return query;
    };
    const updatePreview = () => {
        const qs = new URLSearchParams(buildQuery()).toString();
        holder.querySelector("#url-preview").textContent = ep.method + " " + buildPath() + (qs ? "?" + qs : "");
    };
    holder.addEventListener("input", updatePreview);
    updatePreview();

    holder.querySelector("#send-btn").onclick = async () => {
        const btn = holder.querySelector("#send-btn");
        const out = holder.querySelector("#response");
        const headers = {};
        for (const input of holder.querySelectorAll("[data-header]")) {
            if (input.value.trim() !== "") headers[input.dataset.header] = input.value.trim();
        }
        if (token) headers["Authorization"] = "Bearer " + token;
        let body = null;
        const bodyInput = holder.querySelector("#req-body");
        if (bodyInput && bodyInput.value.trim()) {
            body = bodyInput.value;
            try {
                JSON.parse(body);
            } catch (e) {
                out.innerHTML = `<div class="notice amber" style="margin-top:12px">Тело запроса - невалидный JSON: ${esc(e.message)}</div>`;
                return;
            }
            headers["Content-Type"] = "application/json";
        }
        btn.disabled = true;
        out.innerHTML = '<div class="skeleton" style="margin-top:14px"></div>';
        try {
            const result = await api(`/api/services/${service.id}/request`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ method: ep.method, path: buildPath(), query: buildQuery(), headers, body }),
            });
            renderResponse(out, result);
        } catch (e) {
            out.innerHTML = `<div class="notice red" style="margin-top:12px">${esc(e.message)}</div>`;
        } finally {
            btn.disabled = false;
        }
    };
}

function renderResponse(out, result) {
    if (!result.ok) {
        out.innerHTML = `<div class="notice red" style="margin-top:12px">${esc(result.error)}</div>`;
        return;
    }
    const cls = result.status < 300 ? "green" : result.status < 500 ? "amber" : "red";
    out.innerHTML = `
        <div class="response">
            <div class="response-head">
                <span class="badge ${cls}">${result.status}</span>
                <span class="time">${result.elapsed_ms} мс, ${(result.body.length / 1024).toFixed(1)} КБ</span>
                <span class="spacer"></span>
                <button class="small-btn" id="copy-btn">${icon("copy")} Копировать</button>
            </div>
            <div class="card-block"><pre class="code">${highlightJson(result.body) || '<span class="j-null">пустой ответ</span>'}</pre></div>
        </div>`;
    out.querySelector("#copy-btn").onclick = () => {
        navigator.clipboard.writeText(result.body).then(() => toast("Скопировано"));
    };
}


function renderDatabaseDrawer() {
    const db = databaseById(drawer.id);
    const data = state.tables[db.id];
    let tabs = "";
    if (data && data.online) {
        if (!drawer.table && data.tables.length) drawer.table = data.tables[0].name;
        for (const t of data.tables) {
            tabs += `<button class="seg ${drawer.table === t.name ? "active" : ""}" data-table="${esc(t.name)}">${esc(t.name)} <span style="color:var(--dim)">${t.rows}</span></button>`;
        }
    }
    el.drawer.innerHTML = `
        <div class="drawer-head">
            <div class="drawer-title">
                <div style="flex:1;min-width:0">
                    <div class="drawer-name">${esc(db.name)}</div>
                    <div class="drawer-sub">${esc(db.owner)}</div>
                </div>
                <button class="ghost-btn" id="drawer-close" title="Закрыть (Esc)">${icon("close")}</button>
            </div>
            <div class="drawer-meta">
                <span id="drawer-status">${statusBadge(db.id)}</span>
                <span class="badge">${dbEngine(db.url)}</span>
                <span class="mono-pill" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%">${esc(db.url)}</span>
            </div>
            ${tabs ? `<div class="table-tabs" style="margin-top:16px">${tabs}</div>` : ""}
        </div>
        <div class="drawer-body enter" id="drawer-body"></div>`;

    document.getElementById("drawer-close").onclick = closeDrawer;
    for (const btn of el.drawer.querySelectorAll("[data-table]")) {
        btn.onclick = () => {
            drawer.table = btn.dataset.table;
            drawer.search = "";
            drawer.offset = 0;
            renderDatabaseDrawer();
        };
    }

    const body = document.getElementById("drawer-body");
    if (!data) {
        body.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
        return;
    }
    if (!data.online) {
        let html = `<div class="notice red">База ещё не создана или недоступна. Она появится, когда сервис-владелец создаст таблицы при первом запуске. Адрес задаётся переменной <code>${esc(db.env)}</code>.</div>`;
        html += '<div class="section-label">Таблицы по плану</div>';
        for (const t of data.planned) {
            html += `<div class="card-block planned-table"><div class="tname">${esc(t.name)}</div><div class="chips" style="margin-top:0">${t.columns.map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div></div>`;
        }
        body.innerHTML = html;
        return;
    }
    if (!data.tables.length) {
        body.innerHTML = '<div class="empty">В базе пока нет таблиц</div>';
        return;
    }
    body.innerHTML = `
        <div class="table-tools">
            <div class="search-mini">${icon("search")}<input class="input" id="table-search" placeholder="Поиск по всем колонкам..." value="${esc(drawer.search)}"></div>
        </div>
        <div id="table-view"><div class="skeleton"></div><div class="skeleton"></div></div>`;

    let timer = null;
    const input = document.getElementById("table-search");
    input.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            drawer.search = input.value;
            drawer.offset = 0;
            loadRows();
        }, 250);
    };
    loadRows();
}

function markText(text, search) {
    const safe = esc(text);
    if (!search) return safe;
    const idx = String(text).toLowerCase().indexOf(search.toLowerCase());
    if (idx < 0) return safe;
    const raw = String(text);
    return esc(raw.slice(0, idx)) + "<mark>" + esc(raw.slice(idx, idx + search.length)) + "</mark>" + esc(raw.slice(idx + search.length));
}

async function loadRows() {
    const view = document.getElementById("table-view");
    if (!view) return;
    const db = drawer.id;
    const table = drawer.table;
    const params = new URLSearchParams({ search: drawer.search, limit: drawer.limit, offset: drawer.offset });
    let data;
    try {
        data = await api(`/api/databases/${db}/tables/${encodeURIComponent(table)}?${params}`);
    } catch (e) {
        view.innerHTML = `<div class="notice red">${esc(e.message)}</div>`;
        return;
    }
    if (drawer.id !== db || drawer.table !== table) return;

    const info = state.tables[db].tables.find((t) => t.name === table);
    const types = {};
    if (info) for (const c of info.columns) types[c.name] = c.type;

    let head = "";
    for (const c of data.columns) head += `<th>${esc(c)}<span class="type">${esc((types[c] || "").toLowerCase())}</span></th>`;
    let rows = "";
    for (const row of data.rows) {
        rows += "<tr>";
        for (const value of row) {
            if (value === null) rows += '<td class="null">null</td>';
            else rows += `<td title="${esc(value)}">${markText(value, drawer.search.trim())}</td>`;
        }
        rows += "</tr>";
    }
    const from = data.total ? drawer.offset + 1 : 0;
    const to = Math.min(drawer.offset + drawer.limit, data.total);
    view.innerHTML = `
        ${data.rows.length ? `<div class="grid-wrap"><table class="grid"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>` : `<div class="empty">${drawer.search ? "Ничего не найдено" : "Таблица пустая"}</div>`}
        <div class="pager">
            <span>${from}-${to} из ${data.total}${drawer.search ? " найдено" : ""}</span>
            <div class="btns">
                <button class="small-btn" id="prev-page" ${drawer.offset === 0 ? "disabled" : ""}>${icon("left")}</button>
                <button class="small-btn" id="next-page" ${to >= data.total ? "disabled" : ""}>${icon("right")}</button>
            </div>
        </div>`;
    document.getElementById("prev-page").onclick = () => {
        drawer.offset = Math.max(0, drawer.offset - drawer.limit);
        loadRows();
    };
    document.getElementById("next-page").onclick = () => {
        drawer.offset += drawer.limit;
        loadRows();
    };
}


let searchItems = [];
let searchIndex = 0;

function buildSearchItems(query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const services = [];
    const endpoints = [];
    const tables = [];
    for (const s of state.topology.services) {
        if ((s.name + " " + s.description + " " + s.id).toLowerCase().includes(q)) {
            services.push({ group: "Сервисы", title: s.name, sub: serviceStatus(s.id).status, open: () => openNode(s.id, { focus: true, tab: "overview" }) });
        }
        const list = state.endpoints[s.id] ? state.endpoints[s.id].endpoints : s.endpoints;
        for (const ep of list) {
            if ((ep.method + " " + ep.path + " " + (ep.summary || "")).toLowerCase().includes(q)) {
                endpoints.push({ group: "Ручки", method: ep.method, title: ep.path, sub: s.name, open: () => openNode(s.id, { focus: true, tab: "api", endpoint: endpointKey(ep) }) });
            }
        }
    }
    for (const d of state.topology.databases) {
        if (d.name.toLowerCase().includes(q)) {
            tables.push({ group: "Базы данных", title: d.name, sub: dbEngine(d.url), open: () => openNode(d.id, { focus: true }) });
        }
        const data = state.tables[d.id];
        const list = data && data.online ? data.tables : d.tables;
        for (const t of list) {
            if (t.name.toLowerCase().includes(q)) {
                tables.push({ group: "Базы данных", title: t.name, mono: true, sub: d.name, open: () => openNode(d.id, { focus: true, table: t.name }) });
            }
        }
    }
    return [...services.slice(0, 5), ...endpoints.slice(0, 8), ...tables.slice(0, 6)];
}

function renderSearch() {
    const box = el.searchResults;
    if (!searchItems.length) {
        box.classList.toggle("show", el.searchInput.value.trim() !== "");
        box.innerHTML = '<div class="empty">Ничего не найдено</div>';
        return;
    }
    let html = "";
    let group = "";
    searchItems.forEach((item, i) => {
        if (item.group !== group) {
            group = item.group;
            html += `<div class="sr-group">${esc(group)}</div>`;
        }
        html += `<div class="sr-item ${i === searchIndex ? "active" : ""}" data-i="${i}">
            ${item.method ? `<span class="method ${item.method}">${item.method}</span>` : ""}
            <span class="title ${item.method || item.mono ? "mono" : ""}">${esc(item.title)}</span>
            <span class="sub">${esc(item.sub)}</span>
        </div>`;
    });
    box.innerHTML = html;
    box.classList.add("show");
    for (const node of box.querySelectorAll(".sr-item")) {
        node.onmousedown = (e) => {
            e.preventDefault();
            pickSearch(Number(node.dataset.i));
        };
    }
}

function pickSearch(i) {
    const item = searchItems[i];
    if (!item) return;
    el.searchInput.value = "";
    searchItems = [];
    el.searchResults.classList.remove("show");
    el.searchInput.blur();
    item.open();
}

function setupSearch() {
    document.getElementById("search-go").innerHTML = icon("arrowUp");
    el.searchInput.addEventListener("input", () => {
        searchItems = buildSearchItems(el.searchInput.value);
        searchIndex = 0;
        renderSearch();
    });
    el.searchInput.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!searchItems.length) return;
            searchIndex = (searchIndex + (e.key === "ArrowDown" ? 1 : -1) + searchItems.length) % searchItems.length;
            renderSearch();
        }
        if (e.key === "Escape") {
            el.searchInput.value = "";
            el.searchResults.classList.remove("show");
            el.searchInput.blur();
        }
    });
    el.searchInput.addEventListener("blur", () => setTimeout(() => el.searchResults.classList.remove("show"), 100));
    document.getElementById("search-form").addEventListener("submit", (e) => {
        e.preventDefault();
        pickSearch(searchIndex);
    });
    document.addEventListener("keydown", (e) => {
        const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
        if (e.key === "/" && !typing) {
            e.preventDefault();
            el.searchInput.focus();
        }
        if (e.key === "Escape" && !typing && drawer.id) closeDrawer();
    });
}


function renderLegend() {
    const line = (cls, color, dash) =>
        `<svg viewBox="0 0 26 6"><path d="M1 3H25" stroke="${color}" stroke-width="2" ${dash ? 'stroke-dasharray="4 4"' : ""}/></svg>`;
    document.getElementById("legend").innerHTML = `
        <div class="legend-item">${line("live", "#5a5a5a")}связь</div>
        <div class="legend-item">${line("common", "#5a5a5a", true)}общая связанность</div>
        <div class="legend-item">${line("down", "var(--red)")}ведёт в выключенный узел</div>
        <div class="legend-item">${line("idle", "#333", true)}оба узла выключены</div>`;
}

function setupTopButtons() {
    const refresh = document.getElementById("refresh-btn");
    refresh.innerHTML = icon("refresh");
    refresh.onclick = () => refreshStatus(true);
    const auto = document.getElementById("auto-btn");
    auto.onclick = () => {
        state.auto = !state.auto;
        auto.classList.toggle("off", !state.auto);
        document.getElementById("auto-label").textContent = state.auto ? "Авто 5с" : "Авто выкл";
        renderSummary();
    };
}

async function start() {
    renderLegend();
    setupTopButtons();
    setupCanvas();
    setupSearch();
    setupSummary();
    setupEdgeTip();
    loadPositions();

    state.topology = await api("/api/topology");
    renderAllNodes();
    renderSummary();
    requestAnimationFrame(() => {
        layoutEdges();
        fitView(false);
    });

    await refreshStatus(false);
    setInterval(() => {
        if (state.auto && !document.hidden) refreshStatus(false);
    }, POLL_MS);
}

start();
