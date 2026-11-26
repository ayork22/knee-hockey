# Knee Hockey League — project guide for Claude Code

A scores, standings and tournament site for Jaxon (10) and his buddies' knee hockey games. It's used mostly on an iPad, by kids. It uses Lafayette Locomotives (Jaxon's 10U team) branding. Owner: Alex (Jaxon's dad).

It was built as a Claude.ai artifact and is now moving to **GitHub Pages**, with **Firebase Firestore** for shared data.

## Goal of the migration

1. Serve the site from GitHub Pages at a public URL anyone can open with no login.
2. Everyone can **read** the standings, games, teams and tournaments.
3. Only approved scorekeepers (Alex, plus anyone he adds) can **write**.
4. Import the existing league data from `data/league-export.json`.
5. Keep the look and every feature exactly as they are now.

## Files

| Path | What it is |
|---|---|
| `index.html` | The whole app: HTML, CSS and vanilla JS in one file. No build step. Fonts load from Google Fonts. |
| `assets/logo.png` | Lafayette Locomotive YMCA logo, cropped from a screenshot (160px, a bit soft). **Swap in the original high-res file when Alex provides it.** |
| `data/league-export.json` | The full league data as of 2026-11-25. |
| `.nojekyll` | Tells Pages to serve the files as they are. |

## How the app is put together (index.html)

- One `<script>` block wrapped in `{ }`. State lives in `S = { name, seasons, cur, teams, games, tournaments }`, and `render()` redraws every view from `S`.
- Navigation uses the hash: `#standings`, `#games`, `#tournaments`, `#teams`, `#leaders`. Team and tournament detail views are in-memory state (`curTeam`, `curT`).
- **The storage layer is the only part that has to change.** It's small and isolated:
  - `loadLocal()` / `saveLocal()`: localStorage key `kh-locos-v3`, the full `S` object.
  - `put(coll, obj)`, `del(coll, id)`, `setMeta(partial)`: every write goes through these three. When `db` is set they write to the remote store. Otherwise they change `S`, save locally and re-render.
  - The `// ---------- boot ----------` IIFE at the bottom: `window.claude.use('db')` is the Claude artifact runtime. It subscribes with `onSnapshot` to `teams`, `games` and `tournaments` and to the doc `meta/league`, replaces `S[coll]` on each snapshot, and updates the `#sync` pill ("Live ✓", "Saved on this device", and so on).
  - On GitHub Pages `window.claude` doesn't exist, so the app falls back to localStorage (per-device) mode. It works on day one, just not shared.
- **Replace that boot block with Firestore.** The data shapes and paths already match Firestore exactly (`teams/{id}`, `games/{id}`, `tournaments/{id}`, `meta/league`), and the `db.collection(x).doc(id).set/delete` and `onSnapshot` calls in `put`/`del`/`setMeta` follow Firestore v8-style naming. Use the modular SDK from `https://www.gstatic.com/firebasejs/<pinned version>/` as ES modules, wrapped in a tiny adapter with the same `collection().doc().set()/delete()/onSnapshot()` surface, so `put`/`del`/`setMeta` barely change. Load the SDK lazily so a Firebase outage doesn't blank the page.
- Live-game state (clock, score in progress) stays in localStorage under `kh-live-v1`, on purpose: it's per-device, and only the finished game gets written.

## Data model

```
meta/league   { name, cur: <seasonId>, seasons: [Season] }
Season        { id, name, start:'YYYY-MM-DD'|'', end:''|date, teams:[teamId] (empty = all),
                w:2|3, otl:0|1, t:0|1,
                base:{ teamId:{w,l,otl,t,gf,ga} } }   // imported/adjusted records added to standings
teams/{id}    { id, name, owner (kid's name), color (from COLORS list), icon (emoji from ICONS list),
                players:[{id,name,num}] }
games/{id}    { id, a, b (team ids), sa, sb (scores), ot:bool, date, ts (ISO, ordering), season (seasonId),
                goals:[{t: teamId, p: playerId|null}],
                tid? (tournament id), stage?:'rr' (round robin), r?/k? (bracket round/slot) }
tournaments/{id} { id, name, teams:[ids in seed order], format:'ko'|'rr', adv:0|2|4 (rr playoff size),
                   date, ts, season }
```

The bracket is never stored. It's derived from the tournament's seed order plus the games that have `tid`/`r`/`k` (see `bracketOf`).

## Current data, and quirks to keep

- One season, `2026–27 Season` (the id contains an en dash). Five teams: Aliens (Tucker), Dragons (Murphy), Pirates (Jaxon), Scorpions (Knox), Wolfs (Vinnie). "Wolfs" is spelled that way on purpose; it matches the kids' old app.
- 8 historical games imported from the kids' previous Bolt app. One of them, `hist-1108-pir-dra` (Pirates 5–4 Dragons, Nov 8), was **inferred** from the old standings totals because it was hidden in the screenshot.
- The season's `base` gives the Aliens +1 W and the Pirates +1 L. That was a manual adjustment Alex asked for, with no score known. Keep it unless Alex says otherwise.
- No rosters or goal scorers yet, so the Leaders tab is empty until players are added.

## Step-by-step plan

1. **Repo and Pages.** Create the repo (e.g. `knee-hockey`), commit these files, and enable Pages from the `main` branch root. Confirm the site loads in localStorage mode.
2. **Firebase project** (Alex needs to do this part in the console; walk him through it):
   - Create the project, add a Web app, and copy the config. The config is safe to commit; access is enforced by the security rules.
   - Turn on Firestore (production mode) and Authentication with the **Google** provider.
   - In Authentication → Settings → Authorized domains, add `<username>.github.io` (and any custom domain).
3. **Adapter.** Add `firebase-config.js` (config object), then replace the boot block with a Firestore adapter as described above. Keep the localStorage fallback for when Firebase can't load.
4. **Scorekeeper sign-in.** Add a small "Scorekeeper sign in" button, e.g. in the League settings dialog opened from the title. Signed-out visitors get a **read-only** UI: hide or disable Add game, Play live's save, edit and delete buttons, the add-team form, the roster form, and the season editor. Show a friendly "Ask a grown-up to sign in to save games" message instead of failing silently.
5. **Security rules** (publish in the Firebase console, or keep them in `firestore.rules`):
   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{db}/documents {
       function scorekeeper() {
         return request.auth != null &&
           request.auth.token.email in ['ALEX_EMAIL_HERE'];   // ask Alex for emails to allow
       }
       match /{document=**} {
         allow read: if true;
         allow write: if scorekeeper();
       }
     }
   }
   ```
6. **Import the data.** Add a one-time admin action ("Import backup" in League settings, only for signed-in scorekeepers) that reads a chosen JSON file and writes `meta/league`, `teams/*`, `games/*` and `tournaments/*` with batched writes. Also add **Export backup** (download JSON in this same format), so Alex can always take a backup.
7. **Home-screen polish.** Add `manifest.webmanifest` (name "Knee Hockey", theme `#aa3d32`, background `#f5f6f8`, display `standalone`), plus 180/192/512px icons made from the logo, so the iPad home-screen icon looks right.
8. **Test** on iPad-width (1024×768) and phone (390×844) screens: add teams with "Name (Kid)", quick game with scorers, a live game (1-min periods), knockout and round-robin tournaments, a new custom season, power rankings, head-to-head, and team pages. Then sign out and confirm read-only mode and that writes are rejected by the rules.

## Style rules (keep the look)

- Colors: brick red `#aa3d32` (header band), gold `#e5a34d` (accents, rules), espresso `#3a211b` (score chips and dark panels), rink-ice ground `#f5f6f8`. Dark mode is supported via `light-dark()`.
- Fonts: Teko (numbers, headings) and Barlow (body).
- Kid-friendly: 44px+ tap targets, big +/- score steppers, two-tap confirm for deletes (no `confirm()` dialogs), celebrations with a WebAudio horn.
- Every user-provided value must be escaped (`esc()`), and colors and icons are whitelisted (`okColor`, `okIcon`). Keep it that way. Once this is public, anyone can view the site.

## Don't

- Don't add a framework or build step unless Alex asks. One static file is the point.
- Don't make writes open to the public.
- Don't invent games or scores. Ask Alex.
