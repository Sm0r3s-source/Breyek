// Breyek usage API: receives the once-a-day opt-in report and stores it in D1, serves the privacy policy.
import PRIVACY from "./privacy.html";
const CATS = ["work", "browse", "game", "watch", "read"];
const ID = /^[0-9a-f]{32}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const MAX_DAYS = 70;

const reply = (text, status = 200) => new Response(text, { status });
const int = (v, max) => (Number.isInteger(v) && v >= 0 && v <= max ? v : null);
const str = (v, len) => (typeof v === "string" && v.length <= len ? v : null);

export default {
  async fetch(req, env) {
    if (req.method !== "POST") {
      if (new URL(req.url).pathname.replace(/\/$/, "") === "/privacy")
        return new Response(PRIVACY, { headers: { "content-type": "text/html; charset=utf-8" } });
      return reply("Breyek API");
    }
    if (Number(req.headers.get("content-length") || 0) > 32768) return reply("too large", 413);

    let p;
    try { p = await req.json(); } catch { return reply("bad json", 400); }
    if (!p || !ID.test(p.install_id ?? "")) return reply("bad id", 400);

    if (p.delete === true) {                       // user switched sharing off: forget this install
      await env.DB.prepare("DELETE FROM daily WHERE install_id = ?").bind(p.install_id).run();
      return reply("deleted");
    }

    const now = Date.now(), oldest = new Date(now - MAX_DAYS * 864e5).toISOString().slice(0, 10);
    const newest = new Date(now + 864e5).toISOString().slice(0, 10);   // time zones
    const days = typeof p.days === "object" && p.days ? p.days : {};
    const act = typeof p.activity === "object" && p.activity ? p.activity : {};
    const keys = [...new Set([...Object.keys(days), ...Object.keys(act)])]
      .filter((d) => DAY.test(d) && d >= oldest && d <= newest).slice(0, MAX_DAYS);
    if (!keys.length) return reply("nothing");

    const meta = [str(p.version, 20), str(p.language, 10), str(p.theme, 10), p.demo === true ? 1 : 0];
    const sql = `INSERT INTO daily (install_id, day, version, language, theme, demo, breaks, active_min,
                   work, browse, game, watch, read, received)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT (install_id, day) DO UPDATE SET
                   version = excluded.version, language = excluded.language, theme = excluded.theme,
                   demo = excluded.demo, received = excluded.received,
                   breaks = COALESCE(excluded.breaks, breaks), active_min = COALESCE(excluded.active_min, active_min),
                   work = COALESCE(excluded.work, work), browse = COALESCE(excluded.browse, browse),
                   game = COALESCE(excluded.game, game), watch = COALESCE(excluded.watch, watch),
                   read = COALESCE(excluded.read, read)`;
    const stamp = new Date(now).toISOString();
    const rows = keys.map((d) => {
      const u = days[d] || {}, a = act[d] || {};
      return [int(u.breaks, 500), int(u.active_min, 1440), ...CATS.map((c) => int(a[c], 1440))];
    });
    const valid = keys.filter((d, i) => rows[i].some((v) => v !== null));     // skip days with nothing usable
    if (!valid.length) return reply("nothing", 400);
    await env.DB.batch(valid.map((d) =>
      env.DB.prepare(sql).bind(p.install_id, d, ...meta, ...rows[keys.indexOf(d)], stamp)));
    return reply("ok");
  },

  async scheduled(event, env) {                     // daily: keep at most 12 months (privacy policy)
    await env.DB.prepare("DELETE FROM daily WHERE day < date('now', '-365 days')").run();
  },
};
