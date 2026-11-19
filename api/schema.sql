-- One row per install per day. No IP, no name, no device info: the install ID is random.
CREATE TABLE IF NOT EXISTS daily (
  install_id TEXT NOT NULL,
  day        TEXT NOT NULL,          -- YYYY-MM-DD
  version    TEXT, language TEXT, theme TEXT, demo INTEGER,
  breaks     INTEGER, active_min INTEGER,
  work INTEGER, browse INTEGER, game INTEGER, watch INTEGER, read INTEGER,   -- minutes per activity type
  received   TEXT,
  PRIMARY KEY (install_id, day)
);
CREATE INDEX IF NOT EXISTS daily_day ON daily(day);
