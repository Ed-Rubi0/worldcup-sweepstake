"""World Cup 2026 Office Sweepstake — Streamlit app.

Data source: football-data.org v4 (free tier includes the World Cup).
Put your API key in .streamlit/secrets.toml as FOOTBALL_DATA_API_KEY,
or paste it in the sidebar. Without a key the app runs in demo mode.
"""

import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from scoring import RULES, STAGE_LABELS, compute_scores, side_prizes

st.set_page_config(page_title="WC2026 Sweepstake", page_icon="🏆",
                   layout="wide")

ASSIGNMENTS_FILE = Path(__file__).parent / "assignments.json"
DEMO_FILE = Path(__file__).parent / "demo_matches.json"
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"


# ---------------------------------------------------------------- data
def load_assignments():
    if "assignments" not in st.session_state:
        st.session_state.assignments = json.loads(
            ASSIGNMENTS_FILE.read_text(encoding="utf-8"))
    return st.session_state.assignments


@st.cache_data(ttl=600, show_spinner="Fetching results…")
def fetch_matches(api_key: str):
    r = requests.get(API_URL, headers={"X-Auth-Token": api_key}, timeout=20)
    r.raise_for_status()
    return r.json().get("matches", [])


def get_matches(api_key):
    if api_key:
        try:
            return fetch_matches(api_key), "live"
        except Exception as e:
            st.sidebar.error(f"API error: {e}")
    return json.loads(DEMO_FILE.read_text(encoding="utf-8")), "demo"


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🏆 WC2026 Sweepstake")
api_key = st.secrets.get("FOOTBALL_DATA_API_KEY", "") or \
    st.sidebar.text_input("football-data.org API key", type="password")
if st.sidebar.button("🔄 Refresh results"):
    fetch_matches.clear()

matches, source = get_matches(api_key)
if source == "demo":
    st.sidebar.warning("Demo mode — sample data. Add a free API key from "
                       "football-data.org for real results.")
else:
    st.sidebar.success("Live data · refreshes every 10 min")

assignments = load_assignments()
totals, events, team_stats, unmatched = compute_scores(matches, assignments)
(spoon, spoon_ga), (boot, boot_gf) = side_prizes(team_stats, assignments)

with st.sidebar.expander("📜 Scoring rules"):
    st.markdown(f"""
- Win: **{RULES['win']} pts** · Draw: **{RULES['draw']} pt**
- Goal scored: **{RULES['goal']} pt** · Clean sheet: **{RULES['clean_sheet']} pts**
- Reach R32 **+{RULES['stage_bonus']['LAST_32']}**, R16 **+{RULES['stage_bonus']['LAST_16']}**,
  QF **+{RULES['stage_bonus']['QUARTER_FINALS']}**, SF **+{RULES['stage_bonus']['SEMI_FINALS']}**,
  Final **+{RULES['stage_bonus']['FINAL']}**
- World champions: **+{RULES['champion']}** · Win 3rd place: **+{RULES['third_place']}**
- 🥄 Wooden Spoon: most goals conceded
- 👟 Golden Boot: most goals scored
""")

if unmatched:
    st.sidebar.info("Unassigned teams: " + ", ".join(unmatched))

st.sidebar.caption("<span style='opacity:0.45;font-size:0.75em'>"
                   "Created by Eduardo Rubio del Castillo</span>",
                   unsafe_allow_html=True)

# ---------------------------------------------------------------- tabs
tab_lb, tab_daily, tab_teams, tab_results, tab_prizes, tab_rules, tab_setup = \
    st.tabs(["🏅 Leaderboard", "📈 Daily progress", "⚽ Teams",
             "📋 Results & points", "🥄 Prizes", "📜 Rules", "⚙️ Setup"])

with tab_lb:
    st.subheader("Leaderboard")
    lb = (pd.DataFrame(sorted(totals.items(), key=lambda x: -x[1]),
                       columns=["Player", "Points"]))
    lb.index = [f"{i}." for i in range(1, len(lb) + 1)]
    medals = {0: "🥇 ", 1: "🥈 ", 2: "🥉 "}
    lb["Player"] = [medals.get(i, "") + p for i, p in enumerate(lb["Player"])]
    c1, c2 = st.columns([1, 1])
    c1.dataframe(lb, use_container_width=True)
    if not lb.empty:
        c2.bar_chart(lb.set_index("Player")["Points"],
                     horizontal=True, color="#e63946")

with tab_daily:
    st.subheader("Race chart — cumulative points by day")
    if events:
        ev = pd.DataFrame(events)
        ev["date"] = pd.to_datetime(ev["date"])
        daily = (ev.groupby(["date", "player"])["points"].sum()
                   .unstack(fill_value=0)
                   .reindex(columns=sorted(assignments), fill_value=0)
                   .sort_index())
        cum = daily.cumsum()
        st.line_chart(cum, height=400)

        # daily recap
        days = list(daily.index.strftime("%Y-%m-%d"))
        sel = st.selectbox("Daily recap", list(reversed(days)))
        sel_dt = pd.to_datetime(sel)
        st.markdown(f"**Points won on {sel}**")
        cols = st.columns(len(assignments))
        standings = cum.loc[sel_dt].sort_values(ascending=False)
        prev_idx = cum.index[cum.index < sel_dt]
        prev = (cum.loc[prev_idx[-1]] if len(prev_idx) else
                pd.Series(0, index=cum.columns))
        prev_rank = prev.sort_values(ascending=False).index.tolist()
        for col, (p, total) in zip(cols, standings.items()):
            gained = int(daily.loc[sel_dt, p])
            move = prev_rank.index(p) - standings.index.get_loc(p)
            arrow = "🔼" if move > 0 else "🔽" if move < 0 else "▪️"
            col.metric(f"{arrow} {p}", f"{int(total)} pts",
                       f"+{gained} today" if gained else "no points")
        day_ev = ev[ev["date"] == sel_dt][
            ["match", "team", "player", "reason", "points"]]
        day_ev.columns = ["Match", "Team", "Player", "Reason", "Pts"]
        st.dataframe(day_ev.reset_index(drop=True), use_container_width=True)
    else:
        st.info("No finished matches yet — the race starts soon!")

with tab_teams:
    st.subheader("Team performance")
    player = st.selectbox("Player", ["All"] + sorted(assignments))
    rows = []
    for team, s in team_stats.items():
        if s["owner"] is None:
            continue
        if player != "All" and s["owner"] != player:
            continue
        rows.append({"Team": team, "Owner": s["owner"], "P": s["played"],
                     "W": s["won"], "D": s["drawn"], "L": s["lost"],
                     "GF": s["gf"], "GA": s["ga"], "CS": s["clean_sheets"],
                     "Best stage": STAGE_LABELS[s["best_stage"]],
                     "Points earned": s["points"]})
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values(
            "Points earned", ascending=False).reset_index(drop=True),
            use_container_width=True)
    else:
        st.info("No matches played by these teams yet.")

with tab_results:
    st.subheader("Points feed")
    if events:
        df = pd.DataFrame(events)[
            ["match", "stage", "team", "player", "reason", "points"]]
        df.columns = ["Match", "Stage", "Team", "Player", "Reason", "Pts"]
        f_player = st.multiselect("Filter by player", sorted(assignments))
        if f_player:
            df = df[df["Player"].isin(f_player)]
        st.dataframe(df.iloc[::-1].reset_index(drop=True),
                     use_container_width=True, height=500)
    else:
        st.info("No finished matches yet.")
    st.subheader("All fixtures")
    fx = []
    for m in matches:
        sc = m.get("score", {}).get("fullTime", {})
        fx.append({"Date": (m.get("utcDate") or "")[:10],
                   "Stage": STAGE_LABELS.get(m.get("stage"), m.get("stage")),
                   "Home": m.get("homeTeam", {}).get("name") or "TBD",
                   "Score": (f"{sc.get('home')} - {sc.get('away')}"
                             if m.get("status") == "FINISHED" else
                             m.get("status", "").replace("_", " ").title()),
                   "Away": m.get("awayTeam", {}).get("name") or "TBD"})
    st.dataframe(pd.DataFrame(fx), use_container_width=True, height=400)

with tab_prizes:
    st.subheader("Prizes — who's winning what, and why")
    st.markdown("**🏆 Main prize** — highest total points at the end of the "
                "tournament (see Leaderboard).")

    # per-player aggregates
    agg = []
    for p in sorted(assignments):
        gf = sum(s["gf"] for s in team_stats.values() if s["owner"] == p)
        ga = sum(s["ga"] for s in team_stats.values() if s["owner"] == p)
        cs = sum(s["clean_sheets"] for s in team_stats.values()
                 if s["owner"] == p)
        agg.append({"Player": p, "Goals for": gf, "Goals against": ga,
                    "Clean sheets": cs})
    agg = pd.DataFrame(agg)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🥄 Wooden Spoon")
        st.caption("Goes to the player whose teams **concede the most "
                   "goals** over the whole tournament. Current holder:")
        st.metric("Leading the spoon race", spoon or "—",
                  f"{spoon_ga} goals against", delta_color="inverse")
        spoon_tbl = agg[["Player", "Goals against"]].sort_values(
            "Goals against", ascending=False).reset_index(drop=True)
        spoon_tbl.index = [f"{i}." for i in range(1, len(spoon_tbl) + 1)]
        st.dataframe(spoon_tbl, use_container_width=True)
        with st.expander("Why? Goals conceded per team"):
            rows = [{"Team": t, "Owner": s["owner"], "Conceded": s["ga"]}
                    for t, s in team_stats.items() if s["owner"]]
            st.dataframe(pd.DataFrame(rows).sort_values(
                "Conceded", ascending=False).reset_index(drop=True),
                use_container_width=True)
    with c2:
        st.markdown("### 👟 Golden Boot")
        st.caption("Goes to the player whose teams **score the most "
                   "goals** over the whole tournament. Current holder:")
        st.metric("Leading the boot race", boot or "—",
                  f"{boot_gf} goals for")
        boot_tbl = agg[["Player", "Goals for"]].sort_values(
            "Goals for", ascending=False).reset_index(drop=True)
        boot_tbl.index = [f"{i}." for i in range(1, len(boot_tbl) + 1)]
        st.dataframe(boot_tbl, use_container_width=True)
        with st.expander("Why? Goals scored per team"):
            rows = [{"Team": t, "Owner": s["owner"], "Scored": s["gf"]}
                    for t, s in team_stats.items() if s["owner"]]
            st.dataframe(pd.DataFrame(rows).sort_values(
                "Scored", ascending=False).reset_index(drop=True),
                use_container_width=True)

    st.markdown("### 🧤 Clean sheet kings")
    cs_tbl = agg[["Player", "Clean sheets"]].sort_values(
        "Clean sheets", ascending=False).reset_index(drop=True)
    cs_tbl.index = [f"{i}." for i in range(1, len(cs_tbl) + 1)]
    st.dataframe(cs_tbl, use_container_width=True)

with tab_rules:
    sb = RULES["stage_bonus"]
    st.subheader("📜 How the sweepstake works")
    st.markdown(f"""
Each player owns several national teams (see ⚙️ Setup). Every match your
teams play earns you points — so even a minnow that nicks a goal keeps you
in the race. All scores update automatically from official results.

#### Match points (every game, group stage to final)

| Event | Points |
|---|---|
| Win (including penalty shootouts) | **{RULES['win']}** |
| Draw (group stage) | **{RULES['draw']}** |
| Each goal your team scores | **{RULES['goal']}** |
| Clean sheet (concede 0) | **{RULES['clean_sheet']}** |

#### Progression bonuses (cumulative — a deep run pays at every stage)

| Your team reaches… | Bonus |
|---|---|
| Round of 32 | **+{sb['LAST_32']}** |
| Round of 16 | **+{sb['LAST_16']}** |
| Quarter-final | **+{sb['QUARTER_FINALS']}** |
| Semi-final | **+{sb['SEMI_FINALS']}** |
| Final | **+{sb['FINAL']}** |
| **Wins the World Cup** | **+{RULES['champion']}** |
| Wins the 3rd-place match | **+{RULES['third_place']}** |

A team that wins the whole thing banks
**{sum(sb.values()) + RULES['champion']} bonus points** on top of its match
points — so the champion matters most, but it's catchable if your squad of
teams goes deep and scores freely.

#### Prizes

| Prize | How to win it |
|---|---|
| 🏆 **Main pot** | Most total points when the final whistle blows |
| 🥄 **Wooden Spoon** | Your teams concede the **most** goals (consolation prize!) |
| 👟 **Golden Boot** | Your teams score the **most** goals |

*Notes: goals in extra time count; penalty-shootout goals don't. A shootout
win counts as a win (3 pts), the loser gets nothing. Knockout draws don't
exist, so draw points only apply in the group stage.*
""")

with tab_setup:
    st.subheader("Team assignments")
    st.caption("Edit who owns which team. Team names must match "
               "football-data.org names exactly (see fixtures tab). "
               "Changes apply immediately; click Download to save the "
               "JSON and commit it to the repo so they persist.")
    txt = st.text_area("assignments.json",
                       json.dumps(assignments, indent=2, ensure_ascii=False),
                       height=350)
    c1, c2 = st.columns(2)
    if c1.button("Apply changes"):
        try:
            st.session_state.assignments = json.loads(txt)
            st.success("Applied. Reloading…")
            st.rerun()
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
    c2.download_button("⬇️ Download assignments.json", txt,
                       file_name="assignments.json", mime="application/json")
    api_teams = sorted({t for m in matches for t in
                        (m.get("homeTeam", {}).get("name"),
                         m.get("awayTeam", {}).get("name")) if t})
    if api_teams:
        st.caption("Team names in the data: " + ", ".join(api_teams))
