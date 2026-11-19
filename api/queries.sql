-- Paste one of these into the D1 console (Cloudflare dashboard -> D1 -> breyek -> Console).

-- Users who shared data, per day
SELECT day, COUNT(*) AS users FROM daily GROUP BY day ORDER BY day DESC LIMIT 30;

-- Average minutes per activity type and breaks per user, last 30 days
SELECT ROUND(AVG(work)) AS work, ROUND(AVG(browse)) AS browse, ROUND(AVG(game)) AS game,
       ROUND(AVG(watch)) AS watch, ROUND(AVG(read)) AS read, ROUND(AVG(breaks), 1) AS breaks
FROM daily WHERE day >= date('now', '-30 days') AND demo = 0;

-- Languages and versions in use (last 7 days)
SELECT language, COUNT(DISTINCT install_id) AS users FROM daily
WHERE day >= date('now', '-7 days') GROUP BY language ORDER BY users DESC;
SELECT version, COUNT(DISTINCT install_id) AS users FROM daily
WHERE day >= date('now', '-7 days') GROUP BY version ORDER BY users DESC;

-- Delete data older than one year (run now and then)
DELETE FROM daily WHERE day < date('now', '-365 days');
