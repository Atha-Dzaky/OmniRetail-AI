/* ═══════════════════════════════════════════════════════════════════════════
   OmniRetail AI — Frontend Controller (Tailwind Version)
   ═══════════════════════════════════════════════════════════════════════════ */

const API_BASE = "http://127.0.0.1:8000";
const API_URL = `${API_BASE}/graph/query`;
const HEALTH_URL = `${API_BASE}/health`;
const REQUEST_TIMEOUT_MS = 120000;
const STORAGE_KEY_MESSAGES = "omniretail_chat_history";
const STORAGE_KEY_THOUGHTS = "omniretail_thought_processes";
const LEGACY_STORAGE_KEYS = ["omniretail_messages", "omniretail_thoughts"];
const STORAGE_KEY_THEME = "omniretail-theme";
const MAX_QUERY_LENGTH = 2000;

// ── Suggestion pool (dataset-specific questions) ────────────────────────────
const SUGGESTION_POOL = [
    "Bandingkan penjualan Amazon vs International",
    "Tampilkan 5 produk dengan stok paling banyak",
    "Buatkan pie chart distribusi ukuran (Size)",
    "Tampilkan tren penjualan Amazon Maret sampai Mei 2022",
    "Hitung total pendapatan dari platform Amazon",
    "Tampilkan 10 transaksi penjualan dengan quantity terbesar",
    "Bandingkan customer type B2B vs B2C",
    "Tampilkan 5 kategori produk dengan pendapatan tertinggi",
];

function getRandomSuggestions(count = 3) {
    const pool = [...SUGGESTION_POOL];
    const picked = [];
    while (picked.length < count && pool.length > 0) {
        picked.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
    }
    return picked;
}

function getChipIcon(query) {
    const q = query.toLowerCase();
    if (q.includes("pie chart")) return "pie_chart";
    if (q.includes("tren")) return "trending_up";
    if (q.includes("stok")) return "inventory_2";
    if (q.includes("transaksi")) return "receipt_long";
    if (q.includes("kategori")) return "category";
    if (q.includes("customer") || q.includes("b2b")) return "groups";
    if (q.includes("ukuran") || q.includes("size")) return "straighten";
    return "query_stats";
}

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
const healthDot = healthStatus.querySelector(".health-dot");
const clearChatBtn = document.getElementById("clearChatBtn");
const suggestionChips = document.getElementById("suggestionChips");
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const themeToggle = document.getElementById("themeToggle");
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

function renderMarkdown(text) {
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
        try {
            const rawHtml = marked.parse(text, { breaks: true });
            return DOMPurify.sanitize(rawHtml);
        } catch {
            return escapeHtml(text);
        }
    }
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
        let messages = null;
        let thoughts = null;
        // Migrate legacy keys (pre-rename) once, then purge them
        try {
            messages = JSON.parse(localStorage.getItem(STORAGE_KEY_MESSAGES) || "null");
            thoughts = JSON.parse(localStorage.getItem(STORAGE_KEY_THOUGHTS) || "null");
            if (messages === null) {
                messages = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEYS[0]) || "null");
            }
            if (thoughts === null) {
                thoughts = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEYS[1]) || "null");
            }
            LEGACY_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
        } catch { /* corrupt legacy data — start fresh */ }
        return {
            messages: Array.isArray(messages) ? messages : [],
            thoughts: Array.isArray(thoughts) ? thoughts : [],
        };
    } catch {
        return { messages: [], thoughts: [] };
    }
}

function clearState() {
    localStorage.removeItem(STORAGE_KEY_MESSAGES);
    localStorage.removeItem(STORAGE_KEY_THOUGHTS);
}

const state = loadState();

// ── Health check ────────────────────────────────────────────────────────────
async function checkHealth() {
    healthText.textContent = "Checking backend…";
    healthText.className = "health-text font-label-sm text-label-sm text-on-surface-variant dark:text-[#c7c5d3]";
    healthDot.className = "health-dot w-2 h-2 rounded-full bg-outline-variant";
    
    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 5000);
        const resp = await fetch(HEALTH_URL, { signal: controller.signal });
        clearTimeout(timer);
        if (resp.ok) {
            healthText.textContent = "Backend Connected";
            healthText.className = "health-text font-label-sm text-label-sm text-success";
            healthDot.className = "health-dot w-2 h-2 rounded-full bg-success shadow-[0_0_0_3px_rgba(34,197,94,0.15)]";
        } else {
            throw new Error(`HTTP ${resp.status}`);
        }
    } catch {
        healthText.textContent = "Offline";
        healthText.className = "health-text font-label-sm text-label-sm text-error";
        healthDot.className = "health-dot w-2 h-2 rounded-full bg-error shadow-[0_0_0_3px_rgba(239,68,68,0.15)]";
    }
}

// ── Rendering: chat ─────────────────────────────────────────────────────────
function renderSuggestionChips() {
    if (!suggestionChips) return;
    suggestionChips.innerHTML = "";
    for (const question of getRandomSuggestions(3)) {
        suggestionChips.appendChild(el(`
            <button data-query="${escapeHtml(question)}" class="chip bg-surface-container-lowest dark:bg-[#1f1f25] border border-border-std dark:border-[#334155] rounded-xl p-md text-left hover:border-primary dark:hover:border-[#c0c1ff] hover:shadow-[0_0_0_2px_rgba(21,21,125,0.12)] dark:hover:shadow-[0_0_0_2px_rgba(192,193,255,0.15)] transition-all duration-150 group">
                <span class="material-symbols-outlined text-primary dark:text-[#c0c1ff] mb-sm block group-hover:scale-110 transition-transform">${getChipIcon(question)}</span>
                <span class="font-body-sm text-body-sm text-on-surface dark:text-[#e4e1e9] block font-medium">${escapeHtml(question)}</span>
            </button>
        `));
    }
}

function hideWelcome() {
    if (welcomeHero) welcomeHero.style.display = "none";
}

function addUserMessage(text) {
    hideWelcome();
    const node = el(`
        <div class="self-end max-w-[92%] md:max-w-[72%] flex flex-col items-end">
            <div class="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant dark:text-[#94A3B8] mb-1">You</div>
            <div class="bg-user-bubble dark:bg-[#c0c1ff] text-on-surface dark:text-[#21237c] px-lg py-md rounded-xl rounded-tr-sm font-body-md text-body-md border border-border-std dark:border-transparent">
            </div>
        </div>
    `);
    node.querySelector("div:nth-child(2)").textContent = text;
    chatList.appendChild(node);
    scrollToBottom();
}

function showThinking() {
    const node = el(`
        <div class="self-start max-w-[92%] md:max-w-[72%] flex flex-col items-start w-full" id="thinkingMsg">
            <div class="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant dark:text-[#94A3B8] mb-1">OmniRetail Agent</div>
            <div class="bg-[#0F172A] dark:bg-[#39485a] text-[#EAF1FF] dark:text-[#c0c1ff] px-lg py-md rounded-xl rounded-tl-sm font-body-md text-body-md shadow-sm flex items-center gap-2">
                <span class="flex gap-1">
                    <span class="tdot w-1.5 h-1.5 rounded-full bg-[#9DA1FF] dark:bg-[#c0c1ff]"></span>
                    <span class="tdot w-1.5 h-1.5 rounded-full bg-[#9DA1FF] dark:bg-[#c0c1ff]"></span>
                    <span class="tdot w-1.5 h-1.5 rounded-full bg-[#9DA1FF] dark:bg-[#c0c1ff]"></span>
                </span>
                <span class="text-sm">Thinking… OmniRetail AI sedang menganalisis data</span>
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
    const bubbleBg = isError ? "bg-error-container dark:bg-[#93000a]" : "bg-[#0F172A] dark:bg-[#39485a]";
    const bubbleText = isError ? "text-on-error-container dark:text-[#ffdad6]" : "text-[#EAF1FF] dark:text-[#a7b6cc]";
    const bubbleBorder = isError ? "border border-error/20 dark:border-transparent" : "shadow-sm";
    
    const node = el(`
        <div class="self-start max-w-[92%] md:max-w-[72%] flex flex-col items-start w-full gap-md">
            <div class="w-full">
                <div class="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant dark:text-[#94A3B8] mb-1">${isError ? "Error" : "OmniRetail Agent"}</div>
                <div class="${bubbleBg} ${bubbleText} px-lg py-md rounded-xl rounded-tl-sm font-body-md text-body-md ${bubbleBorder} ai-prose"></div>
            </div>
        </div>
    `);
    
    const contentDiv = node.querySelector(".ai-prose");
    if (isError) {
        contentDiv.textContent = text;
    } else {
        contentDiv.innerHTML = renderMarkdown(text);
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
        .map((col) => `<th class="py-2 px-md font-medium ${numericCols.has(col) ? "text-right" : ""}">${escapeHtml(col)}</th>`)
        .join("");

    const bodyRows = rows
        .map(
            (row) =>
                `<tr class="hover:bg-surface-container-low dark:hover:bg-[#2a292f] transition-colors">` +
                columns
                    .map((col) => {
                        const isNum = numericCols.has(col);
                        return `<td class="py-3 px-md ${isNum ? "text-right font-medium" : "font-label-sm text-label-sm"} border-b border-border-std dark:border-[#334155]">${formatCell(row[col])}</td>`;
                    })
                    .join("") +
                `</tr>`
        )
        .join("");

    const card = el(`
        <div class="bg-surface-container-lowest dark:bg-[#1f1f25] border border-border-std dark:border-[#334155] rounded-lg overflow-hidden w-full mt-2">
            <div class="px-md py-sm border-b border-border-std dark:border-[#334155] bg-surface-container dark:bg-[#2a292f] flex items-center justify-between">
                <h3 class="font-label-md text-label-md font-semibold text-on-surface dark:text-[#e4e1e9] uppercase tracking-wider">Data Table</h3>
                <button type="button" class="text-on-surface-variant hover:text-primary dark:text-[#c7c5d3] dark:hover:text-[#c0c1ff] transition-colors" title="Download CSV">
                    <span class="material-symbols-outlined text-[18px]">download</span>
                </button>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left font-body-sm text-body-sm text-on-surface dark:text-[#e4e1e9] border-collapse">
                    <thead class="bg-surface-bg dark:bg-[#131318] text-on-surface-variant dark:text-[#94A3B8] font-label-md text-label-md uppercase border-b border-border-std dark:border-[#334155]">
                        <tr>${headerCells}</tr>
                    </thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
            <div class="bg-surface-bg dark:bg-[#131318] px-md py-1 font-label-sm text-label-sm text-on-surface-variant dark:text-[#94A3B8] text-right border-t border-border-std dark:border-[#334155]">
                1&ndash;${rows.length} of ${rows.length}
            </div>
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
        <div class="bg-surface-container-lowest dark:bg-[#1f1f25] border border-border-std dark:border-[#334155] rounded-lg overflow-hidden w-full mt-2 p-md">
            <div class="flex items-center justify-between mb-sm">
                <h3 class="font-label-md text-label-md font-semibold text-on-surface dark:text-[#e4e1e9] uppercase tracking-wider">Visualization</h3>
                <a href="${escapeHtml(src)}" target="_blank" rel="noopener" class="text-on-surface-variant dark:text-[#c7c5d3] hover:text-primary dark:hover:text-[#c0c1ff] transition-colors" title="Open full size">
                    <span class="material-symbols-outlined text-[18px]">fullscreen</span>
                </a>
            </div>
            <div class="w-full bg-white rounded-lg p-2 border border-border-std">
                <img src="${escapeHtml(src)}" alt="Visualization generated from query result" class="w-full h-auto rounded"/>
            </div>
            <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-[#94A3B8] text-center mt-2">
                Visualisasi dihasilkan otomatis dari hasil query.
            </p>
        </div>
    `);
}

// ── Rendering: sidebar thought process ──────────────────────────────────────
function addThoughtProcess(query, sqlQuery, sqlResult, pythonCode) {
    const emptyNote = thoughtList.querySelector(".empty-note");
    if (emptyNote) emptyNote.remove();

    thoughtCount += 1;
    const preview = query.length > 36 ? query.slice(0, 36) + "…" : query;

    const node = el(`
        <div class="expander open border border-border-std dark:border-[#334155] rounded-lg bg-surface-container-lowest dark:bg-[#1f1f25] overflow-hidden">
            <button class="w-full flex items-center justify-between p-sm text-on-surface dark:text-[#e4e1e9] hover:bg-surface-container dark:hover:bg-[#2a292f] transition-colors duration-150">
                <div class="flex items-center gap-sm overflow-hidden flex-1">
                    <span class="material-symbols-outlined text-on-surface-variant dark:text-[#c7c5d3] shrink-0">psychology</span>
                    <span class="font-bold font-label-md text-label-md truncate text-left">#${thoughtCount} &mdash; ${escapeHtml(preview)}</span>
                </div>
                <span class="material-symbols-outlined text-on-surface-variant dark:text-[#c7c5d3] text-[18px] chevron shrink-0">expand_more</span>
            </button>
            <div class="expander-body">
                <div class="px-sm pt-2 pb-1 font-label-sm text-label-sm uppercase text-on-surface-variant dark:text-[#94A3B8]">SQL Query</div>
                <div class="p-sm bg-surface-container dark:bg-[#2a292f] border-y border-border-std dark:border-[#334155] font-label-sm text-label-sm text-on-surface-variant dark:text-[#c7c5d3] overflow-x-auto max-h-[200px] overflow-y-auto">
                    <pre><code class="language-sql font-mono text-xs">${sqlQuery ? escapeHtml(sqlQuery) : "—"}</code></pre>
                </div>
                <div class="px-sm pt-2 pb-1 font-label-sm text-label-sm uppercase text-on-surface-variant dark:text-[#94A3B8]">SQL Result</div>
                <div class="p-sm bg-surface-container dark:bg-[#2a292f] border-y border-border-std dark:border-[#334155] font-label-sm text-label-sm text-on-surface-variant dark:text-[#c7c5d3] overflow-x-auto max-h-[200px] overflow-y-auto">
                    <pre><code class="font-mono text-xs">${sqlResult ? escapeHtml(sqlResult) : "—"}</code></pre>
                </div>
                <div class="px-sm pt-2 pb-1 font-label-sm text-label-sm uppercase text-on-surface-variant dark:text-[#94A3B8]">Python Execution</div>
                <div class="p-sm bg-surface-container dark:bg-[#2a292f] border-t border-border-std dark:border-[#334155] font-label-sm text-label-sm text-on-surface-variant dark:text-[#c7c5d3] overflow-x-auto max-h-[200px] overflow-y-auto">
                    <pre><code class="font-mono text-xs">${pythonCode && !pythonCode.startsWith("Error") ? escapeHtml(pythonCode) : "—"}</code></pre>
                </div>
            </div>
        </div>
    `);

    node.querySelector("button").addEventListener("click", () => {
        node.classList.toggle("open");
    });

    // Close others
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
        const sqlQuery = data.sql_query || "";
        const sqlResult = data.sql_result || "";
        const pythonCode = data.python_code || "";
        const chartPath = data.chart_path || "";

        const msgNode = addAiMessage(finalResponse, false);

        const tableCard = buildTableCard(sqlResult);
        if (tableCard) msgNode.appendChild(tableCard);

        const chartCard = buildChartCard(chartPath);
        if (chartCard) msgNode.appendChild(chartCard);

        addThoughtProcess(trimmedQuery, sqlQuery, sqlResult, pythonCode);

        // Persist
        state.messages.push({
            role: "assistant",
            content: finalResponse,
            sql_result: sqlResult,
            chart_path: chartPath,
        });
        state.thoughts.push({ query: trimmedQuery, sql_query: sqlQuery, sql_result: sqlResult, python_code: pythonCode });
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
        addThoughtProcess(tp.query, tp.sql_query || "", tp.sql_result, tp.python_code);
    }

    scrollToBottom();
}

// ── Char count ──────────────────────────────────────────────────────────────
function updateCharCount() {
    const len = chatInput.value.length;
    if (len > MAX_QUERY_LENGTH * 0.8) {
        charCount.textContent = `${len}/${MAX_QUERY_LENGTH}`;
        charCount.classList.toggle("text-error", len >= MAX_QUERY_LENGTH);
    } else {
        charCount.textContent = "";
    }
}

// ── Event listeners ─────────────────────────────────────────────────────────
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
        <div class="empty-note mt-lg p-md bg-surface-container-lowest dark:bg-[#1f1f25] rounded-xl border border-border-std dark:border-[#334155] text-center mx-2">
            <span class="material-symbols-outlined text-on-surface-variant dark:text-[#c7c5d3] mb-sm opacity-50 text-[24px]">psychology</span>
            <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-[#c7c5d3]">Belum ada query. Mulai bertanya untuk melihat proses berpikir AI.</p>
        </div>
    `;
    thoughtCount = 0;
    state.messages.length = 0;
    state.thoughts.length = 0;
    clearState();
    if (welcomeHero) welcomeHero.style.display = "";
    renderSuggestionChips();
});

sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("-left-full");
    sidebar.classList.toggle("left-0");
    sidebarOverlay.classList.toggle("hidden");
});

sidebarOverlay.addEventListener("click", () => {
    sidebar.classList.add("-left-full");
    sidebar.classList.remove("left-0");
    sidebarOverlay.classList.add("hidden");
});

// ── Theme toggle (Tailwind dark mode via class) ─────────────────────────────
function updateThemeColorMeta() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", document.documentElement.classList.contains("dark") ? "#131318" : "#f8f9ff");
}

function initThemeToggle() {
    const isDark = document.documentElement.classList.contains("dark");
    themeToggle.setAttribute("aria-pressed", String(isDark));
    updateThemeColorMeta();

    themeToggle.addEventListener("click", () => {
        const nowDark = document.documentElement.classList.toggle("dark");
        try {
            localStorage.setItem(STORAGE_KEY_THEME, nowDark ? "dark" : "light");
        } catch { /* storage unavailable */ }
        themeToggle.setAttribute("aria-pressed", String(nowDark));
        updateThemeColorMeta();
    });
}

chatInput.addEventListener("input", updateCharCount);

// ── Init ────────────────────────────────────────────────────────────────────
initThemeToggle();
checkHealth();
setInterval(checkHealth, 30000);
restoreChat();
if (state.messages.length === 0) {
    renderSuggestionChips();
}
chatInput.focus();
