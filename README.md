# FlightScnr Pi

Round **1080×1080 touch display** flight tracker for Raspberry Pi. UI modeled after [FlightScnr](https://github.com/yashmulgaonkar/FlightScnr), with a flight-tracking backend derived from [plane-tracker-rgb-pi](https://github.com/c0wsaysmoo/plane-tracker-rgb-pi) (FR24 gRPC, ADS-B, weather, web portal).

A paid FR24 subscription API key is recommended but not strictly required — ADS-B fallback is available.

**Quick setup:** `its-a-plane-python/setup/update-pi.sh`

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
sudo bash its-a-plane-python/setup/update-pi.sh
```

This creates a virtualenv, installs dependencies, extracts airline logos, and installs the `plane-tracker` systemd service.

### 2. Configure

Copy and edit environment settings:

```bash
cp .env.example .env
nano .env
```

On first service install, `install-service.sh` copies `.env` → `/etc/plane-tracker.env`. After that, edit production config there:

```bash
sudo nano /etc/plane-tracker.env
sudo systemctl restart plane-tracker
```

Required: `FR24_API_KEY`, `TOMORROW_API_KEY`, and location (`HOME_LAT` / `HOME_LON` or zone corners). See `.env.example` for all options.

Display settings for the round panel:

```bash
DISPLAY_WIDTH=1080
DISPLAY_HEIGHT=1080
DISPLAY_FULLSCREEN=True
```

### 3. Run

```bash
sudo systemctl start plane-tracker
sudo systemctl status plane-tracker
sudo journalctl -u plane-tracker -f
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

Radar center can be set in `/etc/plane-tracker.env` or from the web portal (saved to `/var/lib/plane-tracker/location.json`).

---

## Web portal

Open from any device on the same LAN:

**`http://<hostname>.local`**

(e.g. `http://raspberrypi.local` — port 80 by default; set `WEB_PORT` in `/etc/plane-tracker.env` to change.)

- Set radar center coordinates
- Track a specific flight (shown on the **Tracked** screen)
- View closest / farthest flight maps and logs
- **Flight Statistics** — daily overhead flight counts and charts

UI preferences (brightness, units, theme, min height) are stored on-device in `/var/lib/plane-tracker/round_touch_settings.json`.

---

## Data & caching

Runtime data lives in `/var/lib/plane-tracker/`:

| File | Purpose |
|------|---------|
| `location.json` | Radar center (web portal override) |
| `round_touch_settings.json` | Display settings |
| `flight_counter.json` | Flight statistics |
| `tracked_flight.json` | Web-selected tracked flight |
| `close.txt` / `farthest.txt` | Closest / farthest flight logs |
| `maps/` | Cached map tiles and generated maps |

Offline databases (`airports.json`, `airlines.json`, `icao_types.json`) download automatically on first run into `its-a-plane-python/`.

API caching (FR24 feed ~90s, flight details ~30min, weather ~1hr) reduces quota usage during 24/7 operation.

---

## Configuration reference

All settings are environment variables — see `.env.example`. Production values go in `/etc/plane-tracker.env`.

| Area | Examples |
|------|----------|
| API keys | `FR24_API_KEY`, `TOMORROW_API_KEY` |
| Location | `HOME_LAT`, `HOME_LON`, `SEARCH_RADIUS_NM` |
| Display | `DISPLAY_WIDTH`, `DISPLAY_HEIGHT`, `BRIGHTNESS`, `NIGHT_START` |
| Web | `WEB_PORT` (default `80`) |
| Filtering | `MIN_HEIGHT`, `ADSB_ENABLED` |

---

## Credits

- [FlightScnr](https://github.com/yashmulgaonkar/FlightScnr) — round radar UI design
- [Colin Waddell / its-a-plane-python](https://github.com/ColinWaddell/its-a-plane-python) — original flight tracker
- [c0wsaysmoo/plane-tracker-rgb-pi](https://github.com/c0wsaysmoo/plane-tracker-rgb-pi) — RGB matrix fork and web portal foundation
- [ajplotkin/plane-tracker-rgb-pi](https://github.com/ajplotkin/plane-tracker-rgb-pi) — local airport/airline databases and pipeline improvements
