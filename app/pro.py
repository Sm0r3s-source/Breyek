"""Breyek Pro: license check (Polar), call detection, break sounds."""
import datetime
import json
import math
import os
import struct
import threading
import urllib.error
import urllib.request
import wave

# Fill these in after creating the product on polar.sh (Settings -> General shows the organization ID).
POLAR_ORG_ID = "0529b23b-519c-42e5-824f-79437ff07f2f"   # empty = test mode (key BREYEK-TEST-PRO)
POLAR_BENEFIT_ID = ""             # optional: only keys from this license-key benefit count
PRO_BUY_URL = "https://buy.polar.sh/polar_cl_HbAxycxEYMQYRtr9tvJnY1ya0wIzmjiZcEOTD0cQU48"                  # Polar checkout link for the 1.99 / month product
PRO_PORTAL_URL = "https://polar.sh/breyek/portal"               # https://polar.sh/<your-org>/portal - customers cancel / manage here
POLAR_SANDBOX = False             # True while testing with sandbox.polar.sh (fake payments)
TEST_KEY = "BREYEK-TEST-PRO"
VALIDATE_URL = f"https://{'sandbox-api' if POLAR_SANDBOX else 'api'}.polar.sh/v1/customer-portal/license-keys/validate"
GRACE_DAYS = 7                    # Pro keeps working offline this long after the last successful check


class ProLicense:
    """Key + last result in license.json. Checked once a day; offline it trusts the last answer for a week."""

    def __init__(self, folder):
        self.path = os.path.join(folder, "license.json")
        self.data = {"key": "", "ok": False, "checked": ""}
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    @property
    def active(self):
        if not (self.data["key"] and self.data["ok"]):
            return False
        try:
            age = datetime.date.today() - datetime.date.fromisoformat(self.data["checked"])
        except ValueError:
            return False
        return age.days <= GRACE_DAYS

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except OSError:
            pass

    @staticmethod
    def check(key):
        """True = valid, False = not valid / ended, None = server not reachable."""
        if not POLAR_ORG_ID:
            return key == TEST_KEY
        body = {"key": key, "organization_id": POLAR_ORG_ID}
        if POLAR_BENEFIT_ID:
            body["benefit_id"] = POLAR_BENEFIT_ID
        req = urllib.request.Request(VALIDATE_URL, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "Breyek"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
            return d.get("status") == "granted" and d.get("organization_id") == POLAR_ORG_ID
        except urllib.error.HTTPError as e:
            return False if e.code in (404, 422) else None
        except Exception:
            return None

    def set_key(self, key):
        """Checks a typed key now. Returns the same True / False / None as check()."""
        key = key.strip()
        result = self.check(key)
        if result is not None:
            self.data = {"key": key if result else "", "ok": bool(result),
                         "checked": datetime.date.today().isoformat()}
            self._save()
        return result

    def remove(self):
        self.data = {"key": "", "ok": False, "checked": ""}
        self._save()

    def refresh(self, done=None):
        """Daily background re-check: a cancelled subscription turns Pro off, offline changes nothing."""
        today = datetime.date.today().isoformat()
        if not self.data["key"] or self.data["checked"] == today:
            return

        def run():
            result = self.check(self.data["key"])
            if result is not None:
                self.data.update(ok=bool(result), checked=today)
                self._save()
                if done:
                    done()

        threading.Thread(target=run, daemon=True).start()


def in_call():
    """True while any app is using the microphone or camera (Windows privacy registry, no audio is read)."""
    try:
        import winreg
    except ImportError:
        return False
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"

    def busy(path):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                    except OSError:
                        return False
                    i += 1
                    if sub == "NonPackaged":
                        if busy(path + "\\NonPackaged"):
                            return True
                        continue
                    try:
                        with winreg.OpenKey(k, sub) as app:
                            start = winreg.QueryValueEx(app, "LastUsedTimeStart")[0]
                            stop = winreg.QueryValueEx(app, "LastUsedTimeStop")[0]
                        if start and not stop:           # started and not stopped yet = in use now
                            return True
                    except OSError:
                        pass
        except OSError:
            return False

    return busy(base + r"\microphone") or busy(base + r"\webcam")


SOUNDS = ("none", "chime", "bell")


def _tone(path, notes, rate=22050):
    """notes = [(frequency, start s, length s)], soft attack and long fade: easy on the ears."""
    total = max(s + l for _, s, l in notes)
    frames = bytearray()
    for i in range(int(total * rate)):
        t, v = i / rate, 0.0
        for f, s, l in notes:
            if s <= t < s + l:
                x = t - s
                env = min(1.0, x / 0.01) * math.exp(-4.0 * x / l)
                v += env * (math.sin(2 * math.pi * f * x) + 0.25 * math.sin(4 * math.pi * f * x))
        frames += struct.pack("<h", int(max(-1, min(1, v * 0.28)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def play(name, folder, ending=False):
    """Plays a short sound without waiting. Files are made once in the settings folder."""
    if name not in SOUNDS[1:]:
        return
    try:
        import winsound
    except ImportError:
        return
    notes = {"chime": [(659, 0, 0.9), (880, 0.18, 1.1)], "bell": [(523, 0, 1.6)]}[name]
    if ending:                               # the end of the break: the same sound, going down / higher
        notes = {"chime": [(880, 0, 0.9), (659, 0.18, 1.1)], "bell": [(784, 0, 1.4)]}[name]
    path = os.path.join(folder, f"sound_{name}{'_end' if ending else ''}.wav")
    try:
        if not os.path.exists(path):
            os.makedirs(folder, exist_ok=True)
            _tone(path, notes)
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass
