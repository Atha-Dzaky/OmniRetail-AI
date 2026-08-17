"""
OmniRetail AI — Streamlit Chatbot UI
=====================================
A modern chat interface that connects to the FastAPI + LangGraph backend.
Run with:  streamlit run app_ui.py
"""

import json

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OmniRetail AI 🤖",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_URL = "http://127.0.0.1:8000/graph/query"
BACKEND_BASE_URL = "http://127.0.0.1:8000"

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Header gradient text ──────────────────────────────────── */
    .gradient-header {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 0.95rem;
        margin-top: -0.5rem;
        margin-bottom: 1.5rem;
    }

    /* ── Sidebar ───────────────────────────────────────────────── */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.5rem;
    }

    .sidebar-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #a78bfa;
        letter-spacing: 0.02em;
    }

    .thought-label {
        color: #c084fc;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.3rem;
    }

    /* ── Welcome card ──────────────────────────────────────────── */
    .welcome-card {
        background: linear-gradient(135deg, rgba(102,126,234,0.08) 0%, rgba(118,75,162,0.08) 100%);
        border: 1px solid rgba(102,126,234,0.2);
        border-radius: 16px;
        padding: 1.8rem 2rem;
        margin-bottom: 1rem;
    }

    .welcome-card h3 {
        margin-top: 0;
    }

    /* ── Status badge ──────────────────────────────────────────── */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .status-ok {
        background: rgba(34,197,94,0.15);
        color: #22c55e;
        border: 1px solid rgba(34,197,94,0.25);
    }

    .status-err {
        background: rgba(239,68,68,0.15);
        color: #ef4444;
        border: 1px solid rgba(239,68,68,0.25);
    }

    .dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-green { background: #22c55e; }
    .dot-red   { background: #ef4444; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session State Initialisation
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thought_processes" not in st.session_state:
    st.session_state.thought_processes = []

# ---------------------------------------------------------------------------
# Helper: check backend health
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def _check_backend() -> bool:
    try:
        r = requests.get(f"{BACKEND_BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Sidebar — Agent's Thought Process
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<p class="sidebar-title">🧠 Agent\'s Thought Process</p>', unsafe_allow_html=True)
    st.caption("Lihat bagaimana AI memproses setiap pertanyaan Anda.")

    # Backend status
    backend_ok = _check_backend()
    if backend_ok:
        st.markdown(
            '<span class="status-badge status-ok"><span class="dot dot-green"></span> Backend Connected</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-badge status-err"><span class="dot dot-red"></span> Backend Offline</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Thought process expanders (newest first)
    if not st.session_state.thought_processes:
        st.info("Belum ada query. Mulai bertanya untuk melihat proses berpikir AI! 💡")
    else:
        for i, tp in enumerate(reversed(st.session_state.thought_processes)):
            idx = len(st.session_state.thought_processes) - i
            query_preview = tp["query"][:55] + ("…" if len(tp["query"]) > 55 else "")

            with st.expander(f"🔍 #{idx}  {query_preview}", expanded=(i == 0)):
                # -- SQL Result --
                st.markdown(
                    '<p class="thought-label">📊 SQL Result</p>',
                    unsafe_allow_html=True,
                )
                if tp.get("sql_result"):
                    try:
                        parsed = json.loads(tp["sql_result"])
                        st.json(parsed, expanded=False)
                    except (json.JSONDecodeError, TypeError):
                        st.code(tp["sql_result"], language="sql")
                else:
                    st.caption("— tidak ada hasil SQL —")

                st.markdown("---")

                # -- Python Code --
                st.markdown(
                    '<p class="thought-label">🐍 Python Code</p>',
                    unsafe_allow_html=True,
                )
                if tp.get("python_code") and not tp["python_code"].startswith("Error"):
                    st.code(tp["python_code"], language="python")
                else:
                    st.caption("— tidak ada kode Python —")

    st.markdown("---")

    # Clear chat
    if st.button("🗑️  Bersihkan Chat", use_container_width=True):
        st.session_state.messages.clear()
        st.session_state.thought_processes.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Main Area — Header
# ---------------------------------------------------------------------------
st.markdown('<h1 class="gradient-header">OmniRetail AI 🤖</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Asisten AI untuk analisis data e-commerce — tanya dalam bahasa Indonesia!</p>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Display Chat History
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("chart_url"):
            st.image(msg["chart_url"], caption="📊 Generated Chart", use_container_width=True)

# ---------------------------------------------------------------------------
# Welcome Message (shown only when chat is empty)
# ---------------------------------------------------------------------------
if not st.session_state.messages:
    st.markdown(
        """
        <div class="welcome-card">
        <h3>👋 Selamat datang!</h3>
        <p>Saya <strong>OmniRetail AI</strong>, asisten cerdas untuk menganalisis data e-commerce Anda.
        Saya bisa membuat query SQL, menganalisis data, dan menghasilkan visualisasi — semuanya dari pertanyaan bahasa alami.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📊 Visualisasi**")
        st.caption("*\"Buatkan pie chart distribusi penjualan berdasarkan ukuran\"*")
    with col2:
        st.markdown("**🔍 Analisis**")
        st.caption("*\"Tampilkan 5 produk dengan stok paling sedikit\"*")
    with col3:
        st.markdown("**📈 Tren**")
        st.caption("*\"Bagaimana tren penjualan Amazon Maret – Mei 2022?\"*")

# ---------------------------------------------------------------------------
# Chat Input & API Call
# ---------------------------------------------------------------------------
if prompt := st.chat_input("💬 Tanyakan sesuatu tentang data e-commerce…"):
    # -- Show user message --
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # -- Call backend & show assistant response --
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔄 Sedang menganalisis pertanyaan Anda…"):
            try:
                resp = requests.post(API_URL, json={"query": prompt}, timeout=120)

                if resp.status_code == 200:
                    data = resp.json()

                    final_response = data.get("final_response", "Tidak ada respons dari AI.")
                    chart_path = data.get("chart_path", "")
                    sql_result = data.get("sql_result", "")
                    python_code = data.get("python_code", "")

                    # Display text response
                    st.markdown(final_response)

                    # Display chart image when available
                    chart_url = ""
                    if chart_path and chart_path.strip():
                        chart_url = BACKEND_BASE_URL + chart_path
                        st.image(
                            chart_url,
                            caption="📊 Generated Chart",
                            use_container_width=True,
                        )

                    # Persist assistant message
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": final_response,
                            "chart_url": chart_url or None,
                        }
                    )

                    # Persist thought process
                    st.session_state.thought_processes.append(
                        {
                            "query": prompt,
                            "sql_result": sql_result,
                            "python_code": python_code,
                        }
                    )

                else:
                    # Attempt to extract detail from error response
                    try:
                        err = resp.json()
                        detail = err.get("detail", {})
                        msg = detail.get("message", resp.text[:300]) if isinstance(detail, dict) else str(detail)[:300]
                    except Exception:
                        msg = resp.text[:300]

                    error_msg = f"⚠️ Server error (HTTP {resp.status_code}): {msg}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except requests.exceptions.Timeout:
                error_msg = "⏰ Request timeout! Backend membutuhkan waktu lebih dari 2 menit. Coba pertanyaan yang lebih sederhana."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except requests.exceptions.ConnectionError:
                error_msg = (
                    "❌ Tidak dapat terhubung ke backend.\n\n"
                    "Pastikan FastAPI sudah berjalan:\n"
                    "```\nuvicorn app.main:app --reload\n```"
                )
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except Exception as exc:
                error_msg = f"❌ Terjadi kesalahan: {exc}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

    # Rerun so the sidebar thought-process list updates immediately
    st.rerun()
