/* ═══════════════════════════════════════════════════════════════════════════
   OmniRetail AI — Frontend Controller (Vanilla JS)
   Talks to the FastAPI backend:
     POST /graph/query  { query }  ->  { final_response, sql_result, python_code, chart_path }
     GET  /health                    ->  backend status
   ═══════════════════════════════════════════════════════════════════════════ */

const API_BASE = "http://127.0.0.1:8000";
const API_URL = `${API_BASE}/graph/query`;
const HEALTH_URL = `${API_BASE}/health`;
const REQUEST_TIMEOUT_MS = 120000;
const STORAGE_KEY_MESSAGES = "omniretail_messages";
const STORAGE_KEY_THOUGHTS = "omniretail_thoughts";
const MAX_QUERY_LENGTH = 2000;

// ── DOM refs ────────────────────────────────────────────────────────────────
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const chatList = document.getElementById("chatList");
const chatScroll = document.getElementById("chatScroll");
const welcomeHero = document.getElementById("welcomeHero");
const thoughtList = document.getElementById("thoughtList");
const healthStatus = document.getElementById("healthStatus");
const healthText = healthStatus.querySelector(".health-text");
const clearChatBtn = document.getElementById("clearChatBtn");
const suggestionChips = document.getElementById("suggestionChips");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const charCount = document.getElementById("charCount");

let isLoading = false;
let thoughtCount = 0;

// ── Global error boundary ───────────────────────────────────────────────────
window.onerror = (msg, src, line, col, error) => {
    console.error("Global error:", { msg, src, line, col, error });
};
window.onunhandledrejection = (event) => {
    console.error("Unhandled promise rejection:", event.reason);
};

// ── Utilities ───────────────────────────────────────────────────────────────
function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function el(html) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    return template.content.firstElementChild;
}

function scrollToBottom() {
    chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: "smooth" });
}

function formatCell(value) {
    if (value === null || value === undefined || value === "NaN") return "&mdash;";
    if (typeof value === "number") {
        return Number.isInteger(value)
            ? value.toLocaleString("en-US")
            : value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return escapeHtml(value);
}

/**
 * Render markdown to sanitized HTML.
 * Falls back to escaped plain text if marked/DOMPurify not loaded.
 */
function renderMarkdown(text) {
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
        try {
            const rawHtml = marked.parse(text, { breaks: true });
            return DOMPurify.sanitize(rawHtml);
        } catch {
            return escapeHtml(text);
        }
    }
    // Fallback: plain text with line breaks
    return escapeHtml(text).replace(/\n/g, "<br>");
}

// ── LocalStorage persistence ────────────────────────────────────────────────
function saveState(messages, thoughts) {
    try {
        localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages));
        localStorage.setItem(STORAGE_KEY_THOUGHTS, JSON.stringify(thoughts));
    } catch { /* quota exceeded — silently fail */ }
}

function loadState() {
    try {
        const messages = JSON.parse(localStorage.getItem(STORAGE_KEY_MESSAGES) || "[]");
        const thoughts = JSON.parse(localStorage.getItem(STORAGE_KEY_THOUGHTS) || "[]");
        return { messages, thoughts };
    } catch {
        return { messages: [], thoughts: [] };
    }
}

function clearState() {
    localStorage.removeItem(STORAGE_KEY_MESSAGES);
    localStorage.removeItem(STORAGE_KEY_THOUGHTS);
}

// In-memory state (mirrors localStorage)
const state = loadState();

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
    healthStatus.className = "health-status checking";
    healthText.textContent = "Checking backend…";
    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        const resp = await fetch(HEALTH_URL, { signal: controller.signal });
        clearTimeout(timer);
        if (resp.ok) {
            healthStatus.className = "health-status ok";
            healthText.textContent = "Backend Connected";
        } else {
            throw new Error(`HTTP ${resp.status}`);
        }
    } catch {
        healthStatus.className = "health-status err";
        healthText.textContent = "Offline";
    }
}

// ── Rendering: chat ─────────────────────────────────────────────────────────
function hideWelcome() {
    if (welcomeHero) welcomeHero.style.display = "none";
}

function addUserMessage(text) {
    hideWelcome();
    const node = el(`
        <div class="msg user">
            <div class="msg-tag">
                <span class="tag-icon"><span class="material-symbols-outlined">person</span></span>
                <span>You</span>
            </div>
            <div class="bubble-user"></div>
        </div>
    `);
    node.querySelector(".bubble-user").textContent = text;
    chatList.appendChild(node);
    scrollToBottom();
}

function showThinking() {
    const node = el(`
        <div class="msg ai" id="thinkingMsg">
            <div class="msg-tag">
                <span class="tag-icon"><span class="material-symbols-outlined">smart_toy</span></span>
                <span>OmniRetail Agent</span>
            </div>
            <div class="bubble-thinking">
                <span class="thinking-dots">
                    <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
                </span>
                <span>Thinking… OmniRetail AI sedang menganalisis data</span>
            </div>
        </div>
    `);
    chatList.appendChild(node);
    scrollToBottom();
}

function removeThinking() {
    const node = document.getElementById("thinkingMsg");
    if (node) node.remove();
}

function addAiMessage(text, isError) {
    const bubbleClass = isError ? "bubble-error" : "bubble-ai";
    const node = el(`
        <div class="msg ai">
            <div class="msg-tag">
                <span class="tag-icon"><span class="material-symbols-outlined">smart_toy</span></span>
                <span>${isError ? "Error" : "OmniRetail Agent"}</span>
            </div>
            <div class="${bubbleClass}"></div>
        </div>
    `);
    // Use markdown rendering for AI responses, plain text for errors
    if (isError) {
        node.querySelector(`.${bubbleClass}`).textContent = text;
    } else {
        node.querySelector(`.${bubbleClass}`).innerHTML = renderMarkdown(text);
    }
    chatList.appendChild(node);
    return node;
}

// ── Rendering: table & chart ────────────────────────────────────────────────
function buildTableCard(sqlResult) {
    let rows;
    try {
        rows = JSON.parse(sqlResult);
    } catch {
        return null;
    }
    if (!Array.isArray(rows) || rows.length === 0) return null;

    const columns = Object.keys(rows[0]);
    const numericCols = new Set(
        columns.filter((col) =>
            rows.every((row) => {
                const value = row[col];
                if (value === null || value === undefined || value === "") return false;
                const num = Number(String(value).replace(/,/g, ""));
                return Number.isFinite(num);
            })
        )
    );

    const headerCells = columns
        .map((col) => `<th class="${numericCols.has(col) ? "num" : ""}">${escapeHtml(col)}</th>`)
        .join("");

    const bodyRows = rows
        .map(
            (row) =>
                `<tr>${columns
                    .map((col) => `<td class="${numericCols.has(col) ? "num" : ""}">${formatCell(row[col])}</td>`)
                    .join("")}</tr>`
        )
        .join("");

    const card = el(`
        <div class="card">
            <div class="card-head">
                <span class="card-title">Data Table</span>
                <span class="card-actions">
                    <button type="button" title="Download CSV">
                        <span class="material-symbols-outlined">download</span>
                    </button>
                </span>
            </div>
            <div class="table-wrap">
                <table class="data-table">
                    <thead><tr>${headerCells}</tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
            <div class="card-foot">1&ndash;${rows.length} of ${rows.length}</div>
        </div>
    `);

    card.querySelector("button").addEventListener("click", () => downloadCsv(rows, columns));
    return card;
}

function downloadCsv(rows, columns) {
    const csvLines = [columns.join(",")];
    for (const row of rows) {
        csvLines.push(
            columns
                .map((col) => {
                    const value = row[col] ?? "";
                    return typeof value === "string" && /[",\n]/.test(value)
                        ? `"${value.replaceAll('"', '""')}"`
                        : String(value);
                })
                .join(",")
        );
    }
    const blob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `omniretail_data_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
}

function buildChartCard(chartPath) {
    if (!chartPath || !chartPath.trim()) return null;
    const src = chartPath.startsWith("http") ? chartPath : API_BASE + chartPath;
    return el(`
        <div class="card">
            <div class="card-head">
                <span class="card-title">Visualization</span>
                <span class="card-actions">
                    <a href="${escapeHtml(src)}" target="_blank" rel="noopener" title="Open full size" style="display:inline-flex;">
                        <span class="material-symbols-outlined">fullscreen</span>
                    </a>
                </span>
            </div>
            <div class="viz-body">
                <img src="${escapeHtml(src)}" alt="Visualization generated from query result"/>
            </div>
            <p class="viz-caption">Visualisasi dihasilkan otomatis dari hasil query.</p>
        </div>
    `);
}

// ── Rendering: sidebar thought process ──────────────────────────────────────
function addThoughtProcess(query, sqlResult, pythonCode) {
    const emptyNote = thoughtList.querySelector(".empty-note");
    if (emptyNote) emptyNote.remove();

    thoughtCount += 1;
    const preview = query.length > 36 ? query.slice(0, 36) + "…" : query;

    const node = el(`
        <div class="expander open">
            <button class="expander-header" type="button">
                <span class="material-symbols-outlined">psychology</span>
                <span class="expander-label">Query #${thoughtCount} &mdash; ${escapeHtml(preview)}</span>
                <span class="material-symbols-outlined chevron">expand_more</span>
            </button>
            <div class="expander-body">
                <div class="code-section-label">SQL Result</div>
                <pre class="code-block"><code>${sqlResult ? escapeHtml(sqlResult) : "—"}</code></pre>
                <div class="code-section-label">Python Execution</div>
                <pre class="code-block"><code>${pythonCode && !pythonCode.startsWith("Error") ? escapeHtml(pythonCode) : "—"}</code></pre>
            </div>
        </div>
    `);

    node.querySelector(".expander-header").addEventListener("click", () => {
        node.classList.toggle("open");
    });

    thoughtList.querySelectorAll(".expander.open").forEach((other) => other.classList.remove("open"));
    thoughtList.prepend(node);
}

// ── Loading state ───────────────────────────────────────────────────────────
function setLoading(loading) {
    isLoading = loading;
    chatInput.disabled = loading;
    sendBtn.disabled = loading;
    if (loading) {
        chatInput.placeholder = "OmniRetail AI is thinking…";
        showThinking();
    } else {
        chatInput.placeholder = "Ask a question about your data...";
        removeThinking();
        chatInput.focus();
    }
}

// ── Main query flow ─────────────────────────────────────────────────────────
async function handleQuery(query) {
    if (isLoading || !query.trim()) return;
    if (query.trim().length > MAX_QUERY_LENGTH) {
        addAiMessage(`Query terlalu panjang. Maksimal ${MAX_QUERY_LENGTH} karakter.`, true);
        return;
    }

    const trimmedQuery = query.trim();
    addUserMessage(trimmedQuery);
    state.messages.push({ role: "user", content: trimmedQuery });
    setLoading(true);

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
        const resp = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: trimmedQuery }),
            signal: controller.signal,
        });
        clearTimeout(timer);

        if (!resp.ok) {
            let detail = "";
            try {
                const err = await resp.json();
                detail = typeof err.detail === "object" && err.detail?.message ? err.detail.message : JSON.stringify(err.detail ?? err);
            } catch {
                detail = await resp.text().catch(() => "");
            }
            const errorMsg = `Server error (HTTP ${resp.status}): ${detail.slice(0, 300)}`;
            addAiMessage(errorMsg, true);
            state.messages.push({ role: "assistant", content: errorMsg, is_error: true });
            return;
        }

        const data = await resp.json();
        const finalResponse = data.final_response || "Tidak ada respons dari AI.";
        const sqlResult = data.sql_result || "";
        const pythonCode = data.python_code || "";
        const chartPath = data.chart_path || "";

        const msgNode = addAiMessage(finalResponse, false);

        const tableCard = buildTableCard(sqlResult);
        if (tableCard) msgNode.appendChild(tableCard);

        const chartCard = buildChartCard(chartPath);
        if (chartCard) msgNode.appendChild(chartCard);

        addThoughtProcess(trimmedQuery, sqlResult, pythonCode);

        // Persist to state + localStorage
        state.messages.push({
            role: "assistant",
            content: finalResponse,
            sql_result: sqlResult,
            chart_path: chartPath,
        });
        state.thoughts.push({ query: trimmedQuery, sql_result: sqlResult, python_code: pythonCode });
        saveState(state.messages, state.thoughts);

    } catch (error) {
        let errorMsg;
        if (error.name === "AbortError") {
            errorMsg = "Request timeout! Backend membutuhkan waktu lebih dari 2 menit. Coba pertanyaan yang lebih sederhana.";
        } else if (error instanceof TypeError) {
            errorMsg = "Tidak dapat terhubung ke backend. Pastikan FastAPI sudah berjalan: uvicorn app.main:app --reload";
        } else {
            errorMsg = `Terjadi kesalahan: ${error.message}`;
        }
        addAiMessage(errorMsg, true);
        state.messages.push({ role: "assistant", content: errorMsg, is_error: true });
    } finally {
        clearTimeout(timer);
        setLoading(false);
        saveState(state.messages, state.thoughts);
        scrollToBottom();
    }
}

// ── Restore chat from localStorage ──────────────────────────────────────────
function restoreChat() {
    if (state.messages.length === 0) return;

    hideWelcome();

    for (const msg of state.messages) {
        if (msg.role === "user") {
            addUserMessage(msg.content);
        } else {
            const msgNode = addAiMessage(msg.content, !!msg.is_error);
            if (!msg.is_error) {
                if (msg.sql_result) {
                    const tableCard = buildTableCard(msg.sql_result);
                    if (tableCard) msgNode.appendChild(tableCard);
                }
                if (msg.chart_path) {
                    const chartCard = buildChartCard(msg.chart_path);
                    if (chartCard) msgNode.appendChild(chartCard);
                }
            }
        }
    }

    // Restore thought expanders
    for (const tp of state.thoughts) {
        addThoughtProcess(tp.query, tp.sql_result, tp.python_code);
    }

    scrollToBottom();
}

// ── Char count ──────────────────────────────────────────────────────────────
function updateCharCount() {
    const len = chatInput.value.length;
    if (len > MAX_QUERY_LENGTH * 0.8) {
        charCount.textContent = `${len}/${MAX_QUERY_LENGTH}`;
        charCount.style.color = len >= MAX_QUERY_LENGTH ? "var(--error)" : "var(--muted)";
    } else {
        charCount.textContent = "";
    }
}

// ── Event listeners ─────────────────────────────────────────────────────────
// Form submit covers both the Send button and pressing Enter in the input
chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = chatInput.value;
    if (!query.trim()) return;
    chatInput.value = "";
    updateCharCount();
    handleQuery(query);
});

suggestionChips.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    handleQuery(chip.dataset.query);
});

clearChatBtn.addEventListener("click", () => {
    chatList.innerHTML = "";
    thoughtList.innerHTML = `
        <div class="empty-note">
            <span class="material-symbols-outlined">psychology</span>
            Belum ada query. Mulai bertanya untuk melihat proses berpikir AI.
        </div>
    `;
    thoughtCount = 0;
    state.messages.length = 0;
    state.thoughts.length = 0;
    clearState();
    if (welcomeHero) welcomeHero.style.display = "";
});

sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    sidebarOverlay.classList.toggle("active");
});

sidebarOverlay.addEventListener("click", () => {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("active");
});

chatInput.addEventListener("input", updateCharCount);

// ── Init ────────────────────────────────────────────────────────────────────
checkHealth();
setInterval(checkHealth, 30000);
restoreChat();
chatInput.focus();
