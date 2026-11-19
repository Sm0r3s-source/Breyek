Breyek API (Cloudflare Worker + D1) – receives the opt-in usage reports. Free plan is enough.

ONE-TIME SETUP (about 20 min, Windows)
1. Make a free account at https://dash.cloudflare.com/sign-up (use breyek@protonmail.com).
2. Install Node.js LTS from https://nodejs.org (default options).
3. Open PowerShell in this folder (Shift + right-click the folder -> "Open PowerShell window here").
4. npx wrangler login
      -> a browser opens, click "Allow".
5. npx wrangler d1 create breyek --location=weur
      -> it prints a database_id. Paste it into wrangler.toml instead of PASTE-YOUR-DATABASE-ID-HERE.
6. npx wrangler d1 execute breyek --remote --file=schema.sql
      -> creates the table.
7. npx wrangler deploy
      -> prints your address, e.g. https://breyek-api.<your-name>.workers.dev
      Opening it in a browser should show "Breyek API".
8. In breyek.py set:  TELEMETRY_URL = "https://breyek-api.<your-name>.workers.dev"
   then build the app again with build.bat.

LOOKING AT THE DATA
- Cloudflare dashboard -> Storage & Databases -> D1 -> breyek -> Console, paste a query from queries.sql.
- Or: npx wrangler d1 execute breyek --remote --command "SELECT COUNT(*) FROM daily"
- Export everything: npx wrangler d1 export breyek --remote --output=backup.sql

CHANGING THE API LATER
Edit src/index.js and run "npx wrangler deploy" again. The data stays.

PRIVACY POLICY PAGE
src/privacy.html is served at https://breyek-api.breyek-api.workers.dev/privacy (?lang=lt or ?lang=en).
Edit it there and run "npx wrangler deploy". If the change is important, raise POLICY_VERSION in breyek.py
so every user is asked to agree again.
A daily job (see [triggers] in wrangler.toml) deletes rows older than 12 months, as the policy promises.

WHAT IS STORED
One row per install per day: random install ID, app version, language, theme, breaks, minutes of use,
minutes per activity type (work/browse/game/watch/read). No IP address, name, device or what was typed/seen.
When a user turns sharing off, the app asks the API to delete all rows of that install.
