"""Main Streamlit app — dark glassmorphism UI redesign."""
import time

import httpx
import streamlit as st

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="AgentOS — Multi-Agent Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:           #080B18;
  --bg-card:      rgba(255,255,255,0.04);
  --bg-card-h:    rgba(255,255,255,0.07);
  --border:       rgba(255,255,255,0.07);
  --border-h:     rgba(124,58,237,0.5);
  --purple:       #7C3AED;
  --purple-light: #A78BFA;
  --cyan:         #06B6D4;
  --cyan-light:   #67E8F9;
  --amber:        #F59E0B;
  --green:        #10B981;
  --red:          #EF4444;
  --text:         #F1F5F9;
  --text-2:       #94A3B8;
  --text-3:       #475569;
}

/* ── Core reset ── */
#MainMenu, footer, header, .stDeployButton { visibility: hidden !important; display: none !important; }
.block-container { padding: 2rem 3rem !important; max-width: 1300px !important; }

/* ── App background + animated orbs ── */
.stApp {
  background: var(--bg) !important;
  font-family: 'Inter', sans-serif !important;
  min-height: 100vh;
}

/* Top-right orb */
[data-testid="stAppViewContainer"]::before {
  content: '';
  position: fixed;
  width: 700px; height: 700px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(124,58,237,0.13) 0%, transparent 65%);
  top: -250px; right: -200px;
  pointer-events: none; z-index: 0;
  animation: orb1 9s ease-in-out infinite;
}
/* Bottom-left orb */
[data-testid="stAppViewContainer"]::after {
  content: '';
  position: fixed;
  width: 600px; height: 600px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(6,182,212,0.10) 0%, transparent 65%);
  bottom: -200px; left: -150px;
  pointer-events: none; z-index: 0;
  animation: orb2 12s ease-in-out infinite;
}
@keyframes orb1 { 0%,100%{transform:scale(1) translate(0,0);} 50%{transform:scale(1.15) translate(-30px,20px);} }
@keyframes orb2 { 0%,100%{transform:scale(1.1) translate(0,0);} 50%{transform:scale(0.9) translate(20px,-30px);} }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background: rgba(8,11,24,0.97) !important;
  border-right: 1px solid var(--border) !important;
  backdrop-filter: blur(24px) !important;
  padding-top: 0 !important;
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* Sidebar radio buttons styled as nav items */
section[data-testid="stSidebar"] .stRadio > div { gap: 0.25rem !important; }
section[data-testid="stSidebar"] .stRadio label {
  color: var(--text-2) !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  padding: 0.6rem 1rem !important;
  border-radius: 10px !important;
  margin: 0 !important;
  transition: all 0.2s ease !important;
  cursor: pointer !important;
  letter-spacing: 0.01em;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  background: var(--bg-card-h) !important;
  color: var(--text) !important;
}
section[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] span { display: none; }

/* ── Typography ── */
h1 { color: var(--text) !important; font-weight: 800 !important; letter-spacing: -0.03em !important; font-size: 2.2rem !important; }
h2 { color: var(--text) !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h3 { color: var(--text) !important; font-weight: 600 !important; }
p, span, li { color: var(--text-2); font-family: 'Inter', sans-serif; }
label, .stMarkdown p { color: var(--text-2) !important; }

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.9rem !important;
  transition: all 0.2s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--purple) !important;
  box-shadow: 0 0 0 3px rgba(124,58,237,0.18) !important;
  background: rgba(255,255,255,0.06) !important;
}
.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder { color: var(--text-3) !important; }

/* ── Buttons ── */
.stButton > button {
  background: linear-gradient(135deg, var(--purple) 0%, #4F46E5 50%, var(--cyan) 100%) !important;
  background-size: 200% 200% !important;
  color: #fff !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  padding: 0.55rem 1.4rem !important;
  font-family: 'Inter', sans-serif !important;
  letter-spacing: 0.01em !important;
  transition: all 0.3s ease !important;
  box-shadow: 0 4px 20px rgba(124,58,237,0.35) !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 30px rgba(124,58,237,0.55) !important;
}
.stButton > button:active { transform: translateY(0) !important; }
button[kind="secondary"], .stButton > button[kind="secondary"] {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--border) !important;
  box-shadow: none !important;
  color: var(--text-2) !important;
}
button[kind="secondary"]:hover { background: var(--bg-card-h) !important; color: var(--text) !important; }

/* ── Form container ── */
[data-testid="stForm"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 18px !important;
  padding: 1.75rem !important;
  backdrop-filter: blur(12px) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  padding: 1.1rem 1.25rem !important;
  backdrop-filter: blur(12px) !important;
  transition: all 0.25s !important;
}
[data-testid="stMetric"]:hover { border-color: var(--border-h) !important; background: var(--bg-card-h) !important; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-weight: 700 !important; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: var(--text-2) !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.06em; }

/* ── Expanders ── */
details {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  margin-bottom: 0.5rem !important;
}
details summary {
  color: var(--text) !important;
  font-weight: 500 !important;
  padding: 0.9rem 1.1rem !important;
  font-size: 0.9rem !important;
  cursor: pointer !important;
}
details[open] { border-color: var(--border-h) !important; }
details > div { padding: 0.75rem 1.1rem 1rem !important; border-top: 1px solid var(--border) !important; }

/* ── Alerts ── */
[data-testid="stNotification"],
.element-container div[class*="stAlert"] {
  border-radius: 12px !important;
  border-width: 1px !important;
  font-size: 0.9rem !important;
}
div[data-testid="stNotification"][data-baseweb="notification"][kind="positive"] {
  background: rgba(16,185,129,0.1) !important; border-color: rgba(16,185,129,0.3) !important;
}
div[data-testid="stNotification"][data-baseweb="notification"][kind="negative"] {
  background: rgba(239,68,68,0.1) !important; border-color: rgba(239,68,68,0.3) !important;
}
div[data-testid="stNotification"][data-baseweb="notification"][kind="warning"] {
  background: rgba(245,158,11,0.1) !important; border-color: rgba(245,158,11,0.3) !important;
}
div[data-testid="stNotification"][data-baseweb="notification"][kind="info"] {
  background: rgba(6,182,212,0.1) !important; border-color: rgba(6,182,212,0.3) !important;
}

/* ── Dividers ── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── JSON / code ── */
.stJson { background: rgba(0,0,0,0.5) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
code, pre { font-family: 'JetBrains Mono', monospace !important; font-size: 0.82rem !important; }

/* ── Checkbox ── */
.stCheckbox span { color: var(--text-2) !important; font-size: 0.88rem !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--purple) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-3); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-2); }

/* ── Utility classes (rendered via st.markdown) ── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.5rem;
  backdrop-filter: blur(12px);
  transition: border-color 0.25s, background 0.25s;
}
.card:hover { border-color: var(--border-h); background: var(--bg-card-h); }

.badge {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.25rem 0.8rem; border-radius: 999px;
  font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase;
}
.badge-purple { background: rgba(124,58,237,0.15); color: #A78BFA; border: 1px solid rgba(124,58,237,0.3); }
.badge-cyan   { background: rgba(6,182,212,0.15); color: #67E8F9; border: 1px solid rgba(6,182,212,0.3); }
.badge-green  { background: rgba(16,185,129,0.15); color: #34D399; border: 1px solid rgba(16,185,129,0.3); }
.badge-red    { background: rgba(239,68,68,0.15); color: #FCA5A5; border: 1px solid rgba(239,68,68,0.3); }
.badge-amber  { background: rgba(245,158,11,0.15); color: #FCD34D; border: 1px solid rgba(245,158,11,0.3); }
.badge-red.pulse { animation: glow-red 2s infinite; }
@keyframes glow-red { 0%,100%{box-shadow:0 0 4px rgba(239,68,68,0.3);} 50%{box-shadow:0 0 14px rgba(239,68,68,0.7);} }

.gradient-text {
  background: linear-gradient(135deg, #A78BFA 0%, #67E8F9 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ── Timeline trace ── */
.timeline { display: flex; flex-direction: column; gap: 0; }
.tl-item { display: flex; gap: 1rem; padding: 0.6rem 0; position: relative; }
.tl-item:not(:last-child)::after {
  content: ''; position: absolute;
  left: 9px; top: 28px;
  width: 2px; height: calc(100% - 10px);
  background: var(--border);
}
.tl-dot { width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0; margin-top: 2px; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; }
.tl-content { flex: 1; min-width: 0; }
.tl-header { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.15rem; }
.tl-agent { font-weight: 600; font-size: 0.85rem; color: var(--text); }
.tl-event { font-size: 0.78rem; color: var(--text-2); }
.tl-latency { font-size: 0.72rem; color: var(--text-3); font-family: 'JetBrains Mono', monospace; margin-left: auto; }

/* ── Health grid ── */
.health-item {
  display: flex; align-items: center; gap: 1rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.1rem 1.25rem;
}
.health-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
.health-dot.ok  { background: var(--green); box-shadow: 0 0 8px rgba(16,185,129,0.5); }
.health-dot.err { background: var(--red); box-shadow: 0 0 8px rgba(239,68,68,0.5); }
.health-label { font-weight: 600; font-size: 0.9rem; color: var(--text); }
.health-sub   { font-size: 0.78rem; color: var(--text-3); }

/* ── Example task cards ── */
.ex-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.25rem;
  margin-bottom: 0.6rem; cursor: pointer;
  transition: all 0.2s; position: relative; overflow: hidden;
}
.ex-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px; background: linear-gradient(180deg, var(--purple), var(--cyan));
  border-radius: 3px 0 0 3px;
}
.ex-card:hover { border-color: var(--border-h); background: var(--bg-card-h); transform: translateX(4px); }
.ex-title { font-size: 0.88rem; color: var(--text); font-weight: 500; line-height: 1.4; }
.ex-tag { font-size: 0.72rem; color: var(--text-3); margin-top: 0.25rem; }

/* ── Hero section ── */
.hero { padding: 2.5rem 0 2rem; }
.hero-eyebrow { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--purple-light); margin-bottom: 0.75rem; }
.hero h1 { font-size: 2.6rem !important; line-height: 1.15 !important; margin-bottom: 0.75rem; }
.hero-sub { font-size: 1rem; color: var(--text-2); line-height: 1.6; max-width: 560px; }

/* ── Tool stat row ── */
.tool-row {
  display: flex; align-items: center; gap: 1rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 0.9rem 1.25rem; margin-bottom: 0.5rem;
}
.tool-name { font-weight: 600; font-size: 0.9rem; color: var(--text); min-width: 140px; }
.tool-stat { font-size: 0.82rem; color: var(--text-2); }
.tool-bar-wrap { flex: 1; height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; }
.tool-bar { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--purple), var(--cyan)); }
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────
def api_get(path: str) -> dict:
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def api_post(path: str, data: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return {}


def status_badge(status: str) -> str:
    MAP = {
        "completed":     ("badge-green",  "✓ Completed"),
        "failed":        ("badge-red",    "✕ Failed"),
        "pending":       ("badge-amber",  "◌ Pending"),
        "planning":      ("badge-purple", "◎ Planning"),
        "executing":     ("badge-cyan",   "▶ Executing"),
        "reviewing":     ("badge-purple", "⊙ Reviewing"),
        "awaiting_human":("badge-red pulse", "⚠ Needs Review"),
    }
    cls, label = MAP.get(status, ("badge-cyan", status.upper()))
    return f'<span class="badge {cls}">{label}</span>'


def agent_color(agent: str) -> str:
    return {
        "supervisor": "#A78BFA",
        "researcher": "#67E8F9",
        "analyst":    "#FCD34D",
        "writer":     "#6EE7B7",
        "coder":      "#FCA5A5",
        "reviewer":   "#C4B5FD",
    }.get(agent, "#94A3B8")


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 1.5rem 0 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.07); margin-bottom: 1.25rem;">
      <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.3rem;">
        <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#7C3AED,#06B6D4);display:flex;align-items:center;justify-content:center;font-size:1rem;">⚡</div>
        <span style="font-size:1.1rem;font-weight:800;color:#F1F5F9;letter-spacing:-0.02em;">AgentOS</span>
      </div>
      <div style="font-size:0.72rem;color:#475569;letter-spacing:0.05em;padding-left:2px;">MULTI-AGENT PLATFORM</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;color:#475569;text-transform:uppercase;padding:0 0.25rem;margin-bottom:0.4rem;">Navigation</div>', unsafe_allow_html=True)

    page = st.radio(
        "nav",
        ["⚡  Submit Task", "📡  Task Monitor", "🔔  Review Queue",
         "🔬  Trace Explorer", "🧠  Memory", "💚  System Health"],
        label_visibility="collapsed",
    )
    page = page.split("  ", 1)[1]  # strip icon prefix

    st.markdown("<br>" * 4, unsafe_allow_html=True)
    st.divider()
    st.markdown("""
    <div style="background:rgba(124,58,237,0.1);border:1px solid rgba(124,58,237,0.2);border-radius:10px;padding:0.75rem 1rem;">
      <div style="font-size:0.72rem;font-weight:600;color:#A78BFA;margin-bottom:0.2rem;">LOCAL MODE</div>
      <div style="font-size:0.7rem;color:#475569;">fakeredis · no docker</div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# SUBMIT TASK
# ════════════════════════════════════════════════════════════════════════════
if page == "Submit Task":
    st.markdown("""
    <div class="hero">
      <div class="hero-eyebrow">⚡ Multi-Agent Orchestration</div>
      <h1>What should your<br><span class="gradient-text">agents work on?</span></h1>
      <p class="hero-sub">Describe any complex task. The Supervisor agent decomposes it, delegates to specialists, and synthesizes a final answer.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("task_form", clear_on_submit=False):
        user_id = st.text_input("User ID", value=st.session_state.get("user_id", "default"),
                                placeholder="your-user-id")
        request = st.text_area(
            "Task Description",
            value=st.session_state.pop("example_task", ""),
            height=130,
            placeholder="e.g. Research the top LLM providers, compare pricing and capabilities, write a 300-word executive summary for a CTO audience.",
        )
        submitted = st.form_submit_button("⚡  Run Agents", use_container_width=True)

    if submitted:
        if not request.strip():
            st.warning("Please enter a task description.")
        else:
            st.session_state["user_id"] = user_id
            with st.spinner("Dispatching to agent graph…"):
                result = api_post("/tasks", {"request": request, "user_id": user_id})
            if result:
                tid = result["task_id"]
                st.session_state["last_task_id"] = tid
                st.markdown(f"""
                <div class="card" style="border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.06);">
                  <div style="font-weight:700;color:#34D399;font-size:1rem;margin-bottom:0.4rem;">✓ Task submitted</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.8rem;color:#94A3B8;">{tid}</div>
                  <div style="margin-top:0.75rem;font-size:0.85rem;color:#94A3B8;">Open <strong style="color:#F1F5F9;">Task Monitor</strong> in the sidebar to track progress.</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.78rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#475569;margin-bottom:0.75rem;">Try an example</div>', unsafe_allow_html=True)

    examples = [
        ("Research the top 5 AI companies by valuation in 2024, analyze their revenue models, and write a comparative summary.", "Research + Analysis + Writing"),
        ("Write a Python script that generates a Fibonacci sequence up to 1000 and plots it, then explain the output.", "Code Generation + Explanation"),
        ("Find recent news about climate change policy, extract key statistics, and produce a structured brief for policy makers.", "Research + Extraction + Synthesis"),
        ("Compare GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro on coding benchmarks and price. Recommend one for a startup.", "Research + Analysis + Recommendation"),
    ]
    for text, tag in examples:
        if st.button(f"  {text[:75]}…  ", key=text, use_container_width=True):
            st.session_state["example_task"] = text
            st.rerun()
        # label underneath
        st.markdown(f'<div style="font-size:0.72rem;color:#475569;margin:-0.4rem 0 0.4rem 0.25rem;">{tag}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TASK MONITOR
# ════════════════════════════════════════════════════════════════════════════
elif page == "Task Monitor":
    st.markdown("## 📡 Task Monitor")
    st.markdown('<p style="color:#475569;margin-top:-0.5rem;margin-bottom:1.25rem;">Live status and output for any submitted task.</p>', unsafe_allow_html=True)

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        task_id = st.text_input("Task ID", value=st.session_state.get("last_task_id", ""),
                                placeholder="Paste a task UUID…", label_visibility="collapsed")
    with col_btn:
        auto = st.checkbox("Auto", value=True, help="Auto-refresh every 3 seconds")

    if not task_id:
        st.markdown("""
        <div class="card" style="text-align:center;padding:3rem;">
          <div style="font-size:2.5rem;margin-bottom:0.75rem;">📡</div>
          <div style="font-weight:600;color:#F1F5F9;margin-bottom:0.4rem;">No task selected</div>
          <div style="font-size:0.88rem;color:#475569;">Submit a task first, then paste its ID above.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        data = api_get(f"/tasks/{task_id}")
        if not data:
            st.error("Task not found or API unavailable.")
        else:
            status = data.get("status", "unknown")

            # ── Status banner ──
            st.markdown(f"""
            <div class="card" style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;">
              <div style="flex:1;">
                <div style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.35rem;">Current Status</div>
                {status_badge(status)}
              </div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#475569;">{task_id[:16]}…</div>
            </div>
            """, unsafe_allow_html=True)

            # ── Metrics ──
            m = data.get("metrics") or {}
            c1, c2, c3 = st.columns(3)
            c1.metric("Tokens Used", f"{m.get('total_tokens', 0):,}")
            c2.metric("Est. Cost", f"${m.get('total_cost_usd', 0):.4f}")
            c3.metric("Wall Clock", f"{m.get('wall_clock_seconds', 0):.1f}s" if m else "—")

            st.markdown("<br>", unsafe_allow_html=True)

            if status == "awaiting_human":
                st.warning("⚠️ Agent paused — human review required. Open **Review Queue** to approve.")

            if data.get("final_output"):
                st.markdown('<div style="font-weight:700;color:#F1F5F9;font-size:1rem;margin-bottom:0.75rem;">Final Output</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="card" style="border-color:rgba(16,185,129,0.2);">
                  <div style="color:#E2E8F0;line-height:1.7;font-size:0.92rem;">{data["final_output"].replace(chr(10), "<br>")}</div>
                </div>
                """, unsafe_allow_html=True)

            if data.get("error"):
                st.error(f"**Error:** {data['error']}")

            if auto and status not in ("completed", "failed"):
                time.sleep(3)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# REVIEW QUEUE
# ════════════════════════════════════════════════════════════════════════════
elif page == "Review Queue":
    st.markdown("## 🔔 Review Queue")
    st.markdown('<p style="color:#475569;margin-top:-0.5rem;margin-bottom:1.25rem;">Tasks paused here need your decision before execution continues.</p>', unsafe_allow_html=True)

    data = api_get("/reviews")
    pending = data.get("pending", [])
    stats = data.get("stats", {})

    c1, c2, c3 = st.columns(3)
    c1.metric("Pending", stats.get("pending_reviews", 0))
    c2.metric("Total Reviews", stats.get("total_reviews", 0))
    c3.metric("Queue Status", "🔴 Active" if stats.get("pending_reviews", 0) else "✅ Clear")

    st.markdown("<br>", unsafe_allow_html=True)

    if not pending:
        st.markdown("""
        <div class="card" style="text-align:center;padding:3rem;border-color:rgba(16,185,129,0.2);background:rgba(16,185,129,0.05);">
          <div style="font-size:2.5rem;margin-bottom:0.75rem;">✅</div>
          <div style="font-weight:600;color:#34D399;margin-bottom:0.4rem;">All clear!</div>
          <div style="font-size:0.88rem;color:#475569;">No pending reviews. Agents are running autonomously.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for review in pending:
            rid = review["id"]
            with st.expander(f"⚠️  Review {rid[:8]}…  ·  {review['level']}  ·  Task {review['task_id'][:8]}…", expanded=True):
                st.markdown(f"""
                <div style="display:grid;gap:0.6rem;margin-bottom:1rem;">
                  <div><span style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Trigger</span><br>
                       <span style="color:#F1F5F9;font-size:0.9rem;">{review['trigger_reason']}</span></div>
                  <div><span style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Proposed Action</span><br>
                       <span style="color:#F1F5F9;font-size:0.9rem;">{review['proposed_action']}</span></div>
                  <div><span style="font-size:0.72rem;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Agent Reasoning</span><br>
                       <span style="color:#94A3B8;font-size:0.88rem;">{review.get('agent_reasoning','—')}</span></div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("View context JSON"):
                    st.json(review.get("context", {}))

                notes = st.text_area("Resolution notes (optional)", key=f"notes_{rid}", height=80)
                col_a, col_r = st.columns(2)
                with col_a:
                    if st.button("✅  Approve", key=f"approve_{rid}", use_container_width=True):
                        res = api_post(f"/reviews/{rid}/resolve", {"approved": True, "resolution": "Approved by operator", "notes": notes})
                        if res:
                            st.success("Approved — task will resume.")
                            st.rerun()
                with col_r:
                    if st.button("✕  Reject", key=f"reject_{rid}", type="secondary", use_container_width=True):
                        res = api_post(f"/reviews/{rid}/resolve", {"approved": False, "resolution": "Rejected by operator", "notes": notes})
                        if res:
                            st.error("Task cancelled.")
                            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TRACE EXPLORER
# ════════════════════════════════════════════════════════════════════════════
elif page == "Trace Explorer":
    st.markdown("## 🔬 Trace Explorer")
    st.markdown('<p style="color:#475569;margin-top:-0.5rem;margin-bottom:1.25rem;">Inspect every agent decision, LLM call, and tool invocation.</p>', unsafe_allow_html=True)

    task_id = st.text_input("Task ID", value=st.session_state.get("last_task_id", ""),
                            placeholder="Paste a task UUID…", label_visibility="collapsed")

    if not task_id:
        st.markdown("""
        <div class="card" style="text-align:center;padding:3rem;">
          <div style="font-size:2.5rem;margin-bottom:0.75rem;">🔬</div>
          <div style="font-weight:600;color:#F1F5F9;">Enter a task ID to explore its trace</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        trace_data = api_get(f"/tasks/{task_id}/trace")
        events = trace_data.get("trace_events", [])

        if not events:
            st.info("No trace events yet — task may still be running.")
        else:
            # Summary row
            agents_seen = list(dict.fromkeys(e.get("agent") for e in events))
            total_ms = sum(e.get("latency_ms") or 0 for e in events)
            llm_calls = sum(1 for e in events if e.get("event_type") == "llm_call")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Events", len(events))
            c2.metric("LLM Calls", llm_calls)
            c3.metric("Total Latency", f"{total_ms/1000:.1f}s")
            c4.metric("Agents", len(agents_seen))

            st.markdown("<br>", unsafe_allow_html=True)

            # Agent legend
            legend_html = '<div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-bottom:1.25rem;">'
            for ag in agents_seen:
                color = agent_color(ag)
                icon = {"supervisor":"🧠","researcher":"🔍","analyst":"📊","writer":"✍️","coder":"💻","reviewer":"🔎"}.get(ag,"⚙️")
                legend_html += f'<span style="display:inline-flex;align-items:center;gap:0.35rem;padding:0.2rem 0.7rem;border-radius:999px;border:1px solid {color}30;background:{color}15;font-size:0.75rem;font-weight:600;color:{color};">{icon} {ag}</span>'
            legend_html += '</div>'
            st.markdown(legend_html, unsafe_allow_html=True)

            # Timeline
            tl_html = '<div class="timeline">'
            for ev in events:
                agent = ev.get("agent", "?")
                etype = ev.get("event_type", "?")
                lat   = ev.get("latency_ms") or 0
                color = agent_color(agent)
                icon  = {"supervisor":"🧠","researcher":"🔍","analyst":"📊","writer":"✍️","coder":"💻","reviewer":"🔎"}.get(agent,"⚙️")
                lat_str = f"{lat:.0f}ms" if lat else ""
                tl_html += f"""
                <div class="tl-item">
                  <div class="tl-dot" style="background:{color}20;border:1.5px solid {color}60;">{icon}</div>
                  <div class="tl-content">
                    <div class="tl-header">
                      <span class="tl-agent" style="color:{color};">{agent}</span>
                      <span class="tl-event">{etype.replace("_"," ")}</span>
                      {f'<span class="tl-latency">{lat_str}</span>' if lat_str else ''}
                    </div>
                  </div>
                </div>"""
            tl_html += '</div>'
            st.markdown(f'<div class="card" style="padding:1.25rem 1.5rem;">{tl_html}</div>', unsafe_allow_html=True)

            # Detailed expandable events
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div style="font-weight:700;color:#F1F5F9;margin-bottom:0.75rem;">Event Details</div>', unsafe_allow_html=True)
            for i, ev in enumerate(events):
                agent = ev.get("agent","?")
                etype = ev.get("event_type","?")
                lat   = ev.get("latency_ms") or 0
                icon  = {"supervisor":"🧠","researcher":"🔍","analyst":"📊","writer":"✍️","coder":"💻","reviewer":"🔎"}.get(agent,"⚙️")
                with st.expander(f"{icon} [{i+1}] {agent} · {etype.replace('_',' ')} · {lat:.0f}ms"):
                    c1, c2 = st.columns(2)
                    c1.markdown(f"**Agent:** `{agent}`  \n**Event:** `{etype}`")
                    c2.markdown(f"**Latency:** `{lat:.1f}ms`")
                    d = ev.get("data", {})
                    if d:
                        st.json(d)


# ════════════════════════════════════════════════════════════════════════════
# MEMORY DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
elif page == "Memory":
    st.markdown("## 🧠 Memory Dashboard")
    st.markdown('<p style="color:#475569;margin-top:-0.5rem;margin-bottom:1.25rem;">Semantic long-term memory per user (ChromaDB).</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-color:rgba(6,182,212,0.2);background:rgba(6,182,212,0.05);margin-bottom:1.5rem;">
      <span class="badge badge-cyan">ℹ Info</span>
      <span style="font-size:0.88rem;color:#94A3B8;margin-left:0.75rem;">ChromaDB is not running in local mode — memory features require Docker.</span>
    </div>
    """, unsafe_allow_html=True)

    col_in, col_btn = st.columns([4, 1])
    with col_in:
        user_id = st.text_input("User ID", value="default", label_visibility="collapsed", placeholder="User ID")
    with col_btn:
        load = st.button("Load", use_container_width=True)

    if load:
        stats = api_get(f"/memory/stats?user_id={user_id}")
        if stats:
            c1, c2 = st.columns(2)
            c1.metric("Total Memories", stats.get("total_memories", 0))
            c2.metric("User", user_id)
            most = stats.get("most_accessed", [])
            if most:
                st.markdown("### Most Accessed")
                for mem in most:
                    with st.expander(f"Access count: {mem.get('access_count', 0)}"):
                        st.json(mem)

    st.divider()
    st.markdown('<div style="font-weight:600;color:#F1F5F9;margin-bottom:0.75rem;">Delete User Data (GDPR)</div>', unsafe_allow_html=True)
    del_user = st.text_input("User ID to delete", key="del_user", placeholder="user-id-to-erase")
    if st.button("🗑️  Delete All Memories", type="secondary"):
        try:
            r = httpx.delete(f"{API_BASE}/memory/{del_user}")
            if r.status_code == 200:
                st.success(f"Deleted {r.json().get('deleted_count', 0)} memories for `{del_user}`")
        except Exception as e:
            st.error(str(e))


# ════════════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH
# ════════════════════════════════════════════════════════════════════════════
elif page == "System Health":
    c_title, c_refresh = st.columns([5, 1])
    c_title.markdown("## 💚 System Health")
    if c_refresh.button("↺ Refresh", use_container_width=True):
        st.rerun()

    st.markdown('<p style="color:#475569;margin-top:-0.5rem;margin-bottom:1.5rem;">Infrastructure and tool status for the local deployment.</p>', unsafe_allow_html=True)

    health = api_get("/health")
    if health:
        overall = health.get("status", "unknown")
        banner_color = "rgba(16,185,129,0.08)" if overall == "healthy" else "rgba(245,158,11,0.08)"
        banner_border = "rgba(16,185,129,0.3)" if overall == "healthy" else "rgba(245,158,11,0.3)"
        banner_text = "#34D399" if overall == "healthy" else "#FCD34D"
        banner_label = "✓ All systems healthy" if overall == "healthy" else "⚠ Some services unavailable"
        st.markdown(f"""
        <div class="card" style="background:{banner_color};border-color:{banner_border};margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem;">
          <div style="font-size:1.5rem;">{"💚" if overall=="healthy" else "⚠️"}</div>
          <div>
            <div style="font-weight:700;color:{banner_text};font-size:1rem;">{banner_label}</div>
            <div style="font-size:0.8rem;color:#475569;">Local mode — fakeredis active</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        services = [
            ("Redis",      health.get("redis"),    "In-memory (fakeredis)"),
            ("ChromaDB",   health.get("chroma"),   "Requires Docker"),
            ("PostgreSQL", health.get("postgres"), "Requires Docker"),
        ]
        health_html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.75rem;margin-bottom:1.5rem;">'
        for name, ok, note in services:
            dot_cls = "ok" if ok else "err"
            val_color = "#34D399" if ok else "#EF4444"
            health_html += f"""
            <div class="health-item">
              <div class="health-dot {dot_cls}"></div>
              <div>
                <div class="health-label">{name}</div>
                <div class="health-sub">{note}</div>
              </div>
              <div style="margin-left:auto;font-weight:700;font-size:0.85rem;color:{val_color};">{"UP" if ok else "DOWN"}</div>
            </div>"""
        health_html += '</div>'
        st.markdown(health_html, unsafe_allow_html=True)

        pending = health.get("pending_reviews", 0)
        st.metric("Pending Human Reviews", pending, delta="action needed" if pending else None,
                  delta_color="inverse" if pending else "off")

    st.divider()

    tool_stats = api_get("/tools/stats")
    stats_map = tool_stats.get("stats", {})
    if stats_map:
        st.markdown('<div style="font-weight:700;color:#F1F5F9;margin-bottom:0.75rem;">Tool Usage</div>', unsafe_allow_html=True)
        max_calls = max((v.get("calls", 0) for v in stats_map.values()), default=1) or 1
        icons = {"web_search":"🌐","file_read":"📄","file_write":"💾","file_list":"📁","execute_python":"🐍","database_query":"🗄️"}
        for tool_name, s in stats_map.items():
            calls = s.get("calls", 0)
            lat   = s.get("avg_latency_ms", 0)
            sr    = s.get("success_rate", 1)
            pct   = int(calls / max_calls * 100)
            icon  = icons.get(tool_name, "🔧")
            sr_color = "#34D399" if sr >= 0.9 else "#FCD34D" if sr >= 0.7 else "#EF4444"
            st.markdown(f"""
            <div class="tool-row">
              <div class="tool-name">{icon} {tool_name.replace("_"," ")}</div>
              <div class="tool-bar-wrap"><div class="tool-bar" style="width:{pct}%;"></div></div>
              <div class="tool-stat" style="min-width:60px;text-align:right;">{calls} calls</div>
              <div class="tool-stat" style="min-width:60px;text-align:right;">{lat:.0f}ms avg</div>
              <div style="font-size:0.8rem;font-weight:600;color:{sr_color};min-width:50px;text-align:right;">{sr*100:.0f}%</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#475569;font-size:0.88rem;">No tool usage data yet — submit a task first.</div>', unsafe_allow_html=True)
