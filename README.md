# 🏆 World Cup 2026 Office Sweepstake

Streamlit app that auto-scores your sweepstake from live World Cup results.

## Scoring

| Event | Points |
|---|---|
| Win (incl. penalties) | 3 |
| Draw (group stage) | 1 |
| Goal scored | 1 |
| Clean sheet | 2 |
| Reach Round of 32 | +4 |
| Reach Round of 16 | +8 |
| Reach Quarter-final | +15 |
| Reach Semi-final | +25 |
| Reach Final | +40 |
| **Win the World Cup** | **+60** |
| Win 3rd-place match | +10 |

Side prizes: 🥄 **Wooden Spoon** (most goals conceded) and 👟 **Golden Boot** (most goals scored by your teams).

Tweak any value in `RULES` at the top of `scoring.py`.

## Setup

1. **Edit `assignments.json`** with your players and their teams. Team names must match football-data.org names (open the app's "Results" tab to see the exact names — e.g. "Spain", "USA").
2. **Get a free API key** at https://www.football-data.org/client/register (free tier includes the World Cup).
3. Run locally:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
   Paste the API key in the sidebar, or create `.streamlit/secrets.toml`:
   ```toml
   FOOTBALL_DATA_API_KEY = "your-key"
   ```
   Without a key the app runs in demo mode with sample data.

## Deploy to Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo.
2. Go to https://share.streamlit.io → New app → pick the repo, main file `app.py`.
3. In the app's Settings → Secrets, add: `FOOTBALL_DATA_API_KEY = "your-key"`.
4. Share the URL with colleagues.

Note: edits made in the app's Setup tab are temporary on Streamlit Cloud — download the updated `assignments.json` and commit it to the repo to make changes permanent.
