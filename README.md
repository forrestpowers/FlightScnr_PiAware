# FlightScnr Pi

Round **1080×1080 touch display** flight tracker for Raspberry Pi. UI modeled after [FlightScnr](https://github.com/yashmulgaonkar/FlightScnr). Uses FR24 gRPC, ADS-B, weather APIs, and a built-in web portal.

**API keys:** `FR24_API_KEY` and `TOMORROW_API_KEY` are required for the full experience (flight details + clock weather). Without FR24, the radar can still show ADS-B positions only (`ADSB_ENABLED=True`).

**Quick setup:** `sudo bash install-pi.sh` (after clone)

---

## Hardware

- Raspberry Pi with desktop/X11 (tested on Pi 3/4 class boards)
- Round 1080×1080 touch LCD
- Network connection for flight data and map tiles

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yashmulgaonkar/FlightScnr_Pi.git ~/FlightScnr_Pi
cd ~/FlightScnr_Pi
sudo bash install-pi.sh
```

This installs system packages, creates a virtualenv, downloads UI assets (fonts, weather icons, aircraft icons), extracts airline logos from `logo.zip`, creates `config.h` from `config.h.example`, creates `/var/lib/flightscnr/`, installs `/etc/flightscnr.env`, and registers the `flightscnr` systemd service.

**Requires:** Raspberry Pi OS with desktop (X11), round touch display, network on first install.

### Updates (git pull)

After the initial install, updates are a single command:

```bash
bash ~/FlightScnr_Pi/install-pi.sh update
```

That runs `git pull --ff-only`, refreshes Python dependencies if `requirements.txt` changed, reinstalls the systemd unit if needed, and restarts the service (skips `apt` for speed). For a full re-sync including system packages: `sudo bash install-pi.sh install`.

Or manually:

```bash
cd ~/FlightScnr_Pi
git pull
sudo bash install-pi.sh
```

**What stays outside git** (safe across updates):

| Path | Purpose |
|------|---------|
| `config.h` | Local API keys and home location (created from `config.h.example`; not in git) |
| `/etc/flightscnr.env` | Systemd environment (never overwritten by install) |
| `/var/lib/flightscnr/secrets.json` | API keys saved from the web portal |
| `/var/lib/flightscnr/` | Runtime data, maps, web portal state |
| `flightscnr-venv/` | Python packages for this app (created by `install-pi.sh`) |
| `logo/` | Extracted from `logo.zip` on install |
| `flightscnr/airlines.json` etc. | Downloaded on first app run |

### 2. Configure

**Easiest:** open the web portal from any device on your LAN — `http://raspberrypi.local` → **API Keys** → Save.

**Or edit `config.h`** in the project folder (created automatically on first install):

```bash
nano ~/FlightScnr_Pi/config.h
sudo systemctl restart flightscnr
```

**Config priority** (highest wins):

1. `/etc/flightscnr.env` (systemd — advanced)
2. Web portal → `/var/lib/flightscnr/secrets.json`
3. `config.h` in the repo root

| Setting | Required? | What it does |
|---------|-----------|--------------|
| `FR24_API_KEY` | **Yes** (full app) | FR24 gRPC feed — routes, airlines, flight details, tracked flights |
| `TOMORROW_API_KEY` | **Yes** (clock weather) | Temperature on the clock screen |
| `HOME_LAT` / `HOME_LON` | **Yes** | Radar center and search zone |
| `AIRLABS_API_KEY` | Optional | Pre-departure schedule when a flight isn't airborne yet |

Without `FR24_API_KEY`, the app still starts but only shows ADS-B aircraft (callsign, position, altitude — no routes or rich flight-detail screens). See `config.h.example` and `.env.example` for all options.

**Advanced:** edit `/etc/flightscnr.env` directly (`sudo nano /etc/flightscnr.env`). Created from `.env.example` on first install if it does not already exist.

Display settings for the round panel:

```bash
DISPLAY_WIDTH=1080
DISPLAY_HEIGHT=1080
DISPLAY_FULLSCREEN=True
```

### 3. Run

```bash
sudo systemctl start flightscnr
sudo systemctl status flightscnr
sudo journalctl -u flightscnr -f
```

---

## Round touch UI

Visual design follows FlightScnr: dark green radar background, animated sweep, map tiles, amber aircraft icons, and altitude tags.

### Screens & navigation

| Screen | How to open | Gestures |
|--------|-------------|----------|
| **Radar** (home) | Boot → radar | Tap aircraft → flight detail; **tap range label (top)** → cycle zoom |
| **Clock** | Swipe down from radar | Swipe up → radar |
| **About** | Swipe up from radar | Swipe down → radar |
| **Settings** | Swipe left from radar | PREV/NEXT footer buttons between pages; tap rows on Display page |
| **Flight detail** | Tap aircraft on radar | PREV/NEXT or swipe to cycle flights; RADAR → back |
| **Tracked flight** | Web portal | RADAR footer → back |

Radar center can be set in `/etc/flightscnr.env` or from the web portal (saved to `/var/lib/flightscnr/location.json`).

---

## Web portal

Open from any device on the same LAN:

**`http://<hostname>.local`**

(e.g. `http://raspberrypi.local` — port 80 by default; set `WEB_PORT` in `/etc/flightscnr.env` to change.)

- Set radar center coordinates
- Track a specific flight (shown on the **Tracked** screen)
- View closest / farthest flight maps and logs
- **Flight Statistics** — daily overhead flight counts and charts

UI preferences (brightness, units, theme, min height) are stored on-device in `/var/lib/flightscnr/round_touch_settings.json`.

---

## Data & caching

Runtime data lives in `/var/lib/flightscnr/`:

| File | Purpose |
|------|---------|
| `location.json` | Radar center (web portal override) |
| `round_touch_settings.json` | Display settings |
| `flight_counter.json` | Flight statistics |
| `tracked_flight.json` | Web-selected tracked flight |
| `close.txt` / `farthest.txt` | Closest / farthest flight logs |
| `maps/` | Cached map tiles and generated maps |

Offline databases (`airports.json`, `airlines.json`, `icao_types.json`) download automatically on first run into `flightscnr/`.

API caching (FR24 feed ~90s, flight details ~30min, weather ~1hr) reduces quota usage during 24/7 operation.

---

## Configuration reference

All settings are environment variables — see `.env.example`. Production values go in `/etc/flightscnr.env`.

| Area | Examples |
|------|----------|
| API keys (required) | `FR24_API_KEY`, `TOMORROW_API_KEY` |
| API keys (optional) | `AIRLABS_API_KEY` |
| Location | `HOME_LAT`, `HOME_LON`, `SEARCH_RADIUS_NM` |
| Display | `DISPLAY_WIDTH`, `DISPLAY_HEIGHT`, `BRIGHTNESS`, `NIGHT_START` |
| Web | `WEB_PORT` (default `80`) |
| Data sources | `ADSB_ENABLED`, `MIN_HEIGHT` |

---

## Credits

- [FlightScnr](https://github.com/yashmulgaonkar/FlightScnr) — round radar UI design
- Parts of this repo are based on code by [c0wsaysmoo](https://github.com/c0wsaysmoo), used with their prior written permission. Thank you!!