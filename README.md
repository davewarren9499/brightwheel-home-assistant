# Brightwheel for Home Assistant

[![Validate](https://github.com/pmartindev/brightwheel-home-assistant/actions/workflows/validate.yml/badge.svg)](https://github.com/pmartindev/brightwheel-home-assistant/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for [Brightwheel](https://mybrightwheel.com/) — a daycare management app used by childcare providers to share activity updates (bottles, diapers, naps, check-ins, photos) with parents.

## Features

- 🍼 **Bottle Tracking** — amount (oz), type, and timestamps for each bottle
- 🧷 **Diaper Tracking** — wet, dirty, or both with timestamps
- 💤 **Nap Tracking** — start/end times with duration, current sleep status
- 🚪 **Check-in/Check-out** — arrival and departure times
- 📷 **Photo & Video** — activity feed from daycare
- 📊 **Activity Count** — total daily activity summary with per-type breakdowns

## How It Works

Brightwheel uses PerimeterX bot protection which prevents standard email/password API authentication. This integration uses **cookie-based authentication** — you extract your `_brightwheel_v2` session cookie from your browser and provide it during setup.

> **Cookie Lifetime**: Cookies typically last ~1 year. If your integration stops working, simply re-extract the cookie.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/pmartindev/brightwheel-home-assistant` with category **Integration**
4. Search for "Brightwheel" and click **Install**
5. Restart Home Assistant

### Manual

1. Download the latest release
2. Copy `custom_components/brightwheel/` to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Prerequisites

Extract your Brightwheel session cookie:

1. Open [schools.mybrightwheel.com](https://schools.mybrightwheel.com) in Chrome/Chromium
2. Log in to your account
3. Open DevTools (F12) → Application → Cookies → `schools.mybrightwheel.com`
4. Copy the value of `_brightwheel_v2`

### Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Brightwheel**
3. Paste your session cookie
4. Select your child from the list

### Refreshing the Cookie

If the integration stops updating, your cookie may have expired:
1. Go to **Settings** → **Devices & Services**
2. Find **Brightwheel** → click **Configure**
3. Paste a fresh cookie

## Entities

The integration creates the following sensors per child:

| Entity | Description | Attributes |
|--------|-------------|------------|
| `sensor.<name>_last_bottle` | Last bottle time & amount | `all_bottles` (today's list), `amount`, `amount_type`, `food_type` |
| `sensor.<name>_last_diaper` | Last diaper change | `all_diapers` (today's list), `diaper_extras` (wet/bm), `diaper_count` |
| `sensor.<name>_last_nap` | Last nap status (sleeping/ended) | `all_naps` (today's list with start/end), `nap_count` |
| `sensor.<name>_last_checkin` | Last check-in/check-out | `action_type`, `actor_name` |
| `sensor.<name>_activity_count` | Total activities today | `activity_type_counts` (per-type breakdown) |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Integration shows "unavailable" | Cookie may have expired — reconfigure with a fresh cookie |
| No activities showing | Check that `end_date` includes today (the API uses exclusive end dates) |
| Only seeing some activity types | Solid food is filtered out by default; only bottles are tracked for food |

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.
