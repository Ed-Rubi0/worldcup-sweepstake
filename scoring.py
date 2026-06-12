"""Scoring engine for the World Cup 2026 office sweepstake.

All rules live in RULES so they are easy to tweak.
"""

from collections import defaultdict

RULES = {
    "win": 3,
    "draw": 1,            # group stage only (knockouts always have a winner)
    "goal": 1,
    "clean_sheet": 2,
    # Cumulative progression bonuses, awarded once per team per stage reached
    "stage_bonus": {
        "LAST_32": 4,
        "LAST_16": 8,
        "QUARTER_FINALS": 15,
        "SEMI_FINALS": 25,
        "FINAL": 40,
    },
    "champion": 60,        # extra for winning the final
    "third_place": 10,     # extra for winning the 3rd-place match
}

STAGE_LABELS = {
    "GROUP_STAGE": "Group stage",
    "LAST_32": "Round of 32",
    "LAST_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-final",
    "SEMI_FINALS": "Semi-final",
    "THIRD_PLACE": "3rd-place match",
    "FINAL": "Final",
}


import unicodedata

# Groups of equivalent team names — first entry is the canonical key.
# Handles spelling differences between the draw sheet and the API.
ALIASES = [
    ["cote d'ivoire", "ivory coast", "cote divoire"],
    ["united states", "usa", "united states of america"],
    ["south korea", "korea republic", "korean republic"],
    ["dr congo", "congo dr", "democratic republic of the congo",
     "dr congo", "congo, democratic republic"],
    ["czech republic", "czechia"],
    ["turkey", "turkiye"],
    ["cape verde", "cape verde islands", "cabo verde"],
    ["iran", "ir iran", "iran, islamic republic"],
    ["bosnia and herzegovina", "bosnia & herzegovina",
     "bosnia-herzegovina", "bosnia"],
    ["netherlands", "holland"],
    ["new zealand", "nz"],
    ["saudi arabia", "ksa"],
]
_CANON = {variant: group[0] for group in ALIASES for variant in group}


def _norm(name):
    """Lowercase, trim and strip accents so e.g. Curaçao == Curacao,
    then collapse known aliases to one canonical key."""
    s = (name or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _CANON.get(s, s)


def build_owner_lookup(assignments):
    """assignments: {player: [team, ...]} -> {normalised team: player}"""
    lookup = {}
    for player, teams in assignments.items():
        for t in teams:
            lookup[_norm(t)] = player
    return lookup


def compute_scores(matches, assignments):
    """Returns (totals, events, team_stats, unmatched_teams).

    matches: list of football-data.org v4 match dicts.
    totals: {player: points}
    events: list of dicts (player, team, points, reason, stage, match, date)
    team_stats: {team: {owner, played, won, drawn, lost, gf, ga,
                        clean_sheets, points, best_stage}}
    """
    owner_of = build_owner_lookup(assignments)
    totals = defaultdict(int)
    events = []
    team_stats = {}
    seen_stage_bonus = set()   # (team, stage)
    unmatched = set()

    def stats(team):
        if team not in team_stats:
            team_stats[team] = dict(owner=owner_of.get(_norm(team)),
                                    played=0, won=0, drawn=0, lost=0,
                                    gf=0, ga=0, clean_sheets=0, points=0,
                                    best_stage="GROUP_STAGE")
        return team_stats[team]

    def add(player, team, pts, reason, stage, match_label, date):
        totals[player] += pts
        stats(team)["points"] += pts
        events.append(dict(player=player, team=team, points=pts,
                           reason=reason, stage=STAGE_LABELS.get(stage, stage),
                           match=match_label, date=date))

    stage_order = ["GROUP_STAGE", "LAST_32", "LAST_16", "QUARTER_FINALS",
                   "SEMI_FINALS", "THIRD_PLACE", "FINAL"]

    for m in matches:
        stage = m.get("stage", "GROUP_STAGE")
        if stage not in stage_order:
            stage = "GROUP_STAGE"
        home = m.get("homeTeam", {}).get("name")
        away = m.get("awayTeam", {}).get("name")
        date = (m.get("utcDate") or "")[:10]
        label = f"{home or 'TBD'} vs {away or 'TBD'}"

        # --- progression bonuses: awarded as soon as a team is slotted
        # into a knockout-stage match ---
        bonus = RULES["stage_bonus"].get(stage, 0)
        for team in (home, away):
            if not team:
                continue
            owner = owner_of.get(_norm(team))
            if owner is None:
                unmatched.add(team)
                continue
            s = stats(team)
            if stage_order.index(stage) > stage_order.index(s["best_stage"]):
                s["best_stage"] = stage
            if bonus and (team, stage) not in seen_stage_bonus:
                seen_stage_bonus.add((team, stage))
                add(owner, team, bonus, f"Reached {STAGE_LABELS[stage]}",
                    stage, label, date)

        if m.get("status") != "FINISHED" or not home or not away:
            continue

        score = m.get("score", {})
        ft = score.get("fullTime", {})
        hg, ag = ft.get("home"), ft.get("away")
        if hg is None or ag is None:
            continue
        winner = score.get("winner")  # HOME_TEAM / AWAY_TEAM / DRAW
        label = f"{home} {hg}-{ag} {away}"

        for team, opp, gf, ga, side in ((home, away, hg, ag, "HOME_TEAM"),
                                        (away, home, ag, hg, "AWAY_TEAM")):
            owner = owner_of.get(_norm(team))
            s = stats(team)
            s["played"] += 1
            s["gf"] += gf
            s["ga"] += ga
            if ga == 0:
                s["clean_sheets"] += 1
            won = winner == side
            drew = winner == "DRAW"
            if won:
                s["won"] += 1
            elif drew:
                s["drawn"] += 1
            else:
                s["lost"] += 1
            if owner is None:
                continue
            if won:
                add(owner, team, RULES["win"], "Win", stage, label, date)
            elif drew:
                add(owner, team, RULES["draw"], "Draw", stage, label, date)
            if gf:
                add(owner, team, gf * RULES["goal"],
                    f"{gf} goal{'s' if gf > 1 else ''}", stage, label, date)
            if ga == 0:
                add(owner, team, RULES["clean_sheet"], "Clean sheet",
                    stage, label, date)
            # champion / third-place extras
            if won and stage == "FINAL":
                add(owner, team, RULES["champion"], "WORLD CHAMPIONS 🏆",
                    stage, label, date)
            if won and stage == "THIRD_PLACE":
                add(owner, team, RULES["third_place"], "Won 3rd place",
                    stage, label, date)

    # make sure every player appears even with 0 points
    for p in assignments:
        totals.setdefault(p, 0)

    return dict(totals), events, team_stats, sorted(unmatched)


def side_prizes(team_stats, assignments):
    """Wooden spoon (most goals conceded) and golden boot (most scored)."""
    conceded = defaultdict(int)
    scored = defaultdict(int)
    for team, s in team_stats.items():
        if s["owner"]:
            conceded[s["owner"]] += s["ga"]
            scored[s["owner"]] += s["gf"]
    for p in assignments:
        conceded.setdefault(p, 0)
        scored.setdefault(p, 0)
    spoon = max(conceded, key=conceded.get) if conceded else None
    boot = max(scored, key=scored.get) if scored else None
    return (spoon, conceded.get(spoon, 0)), (boot, scored.get(boot, 0))
