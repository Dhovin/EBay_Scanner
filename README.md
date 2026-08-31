# eBay Deal Monitor for Unraid

A lightweight, containerized eBay Deal Monitor web application built with **FastAPI**, **SQLite**, and **HTMX + Tailwind CSS**, specifically tailored for Unraid and Docker environments.

It allows you to dynamically manage search monitors, capture deals in real-time, compute multi-factor deal scores, and dispatch instant notifications via **Discord Rich Embeds**, **Pushbullet**, or **Generic JSON Webhooks**.

---

## 🌟 Key Features

- **Port 8080 Web Portal**:
  - **Live Deals Dashboard**: Filter, sort by date found, price, and deal score. Direct "Buy on eBay" links, seller ratings, matching keywords, and quick Star / Dismiss / Delete actions.
  - **Search Monitor Manager**: Easily add, edit, toggle, or delete rules with friendly names, category filters, min/max price thresholds, and keyword logic.
  - **Keyword Filtering Engine**:
    - **Positive Keywords (Required Specs)**: E.g., `J5005`, `Pentium`, `8GB`, `power adapter` — boosts deal score and displays highlighted badges.
    - **Negative Keywords (Exclusions)**: E.g., `no ram`, `no power`, `parts only`, `as-is`, `broken` — immediately discards irrelevant listings.
  - **Weighted Deal Score (0–100)**: Multi-factor scoring calculated from price savings below your max budget (up to 50 pts), positive keyword match ratio (up to 40 pts), and seller reputation boost (up to 10 pts).
  - **Instant Webhooks**: Native Discord Rich Embeds with thumbnail preview, total price breakdown, seller score, and direct eBay link; Pushbullet link pushes; generic JSON webhooks.
  - **Settings & Diagnostic Logs**: Test webhooks with one click, inspect background logs streaming in real-time, and trigger on-demand scans.
- **Dual Data Ingestion**:
  - **Official eBay Browse API**: Connect your eBay Developer App ID & Cert ID for OAuth-authenticated queries.
  - **Zero-Config RSS Fallback**: Don't have an eBay Developer account? The application automatically falls back to eBay's RSS feeds so you can start discovering deals immediately!
- **Unraid Optimized**:
  - Embedded SQLite database persisted to `/config/dealmonitor.db`.
  - Honors Unraid `PUID` and `PGID` (default `99:100` nobody:users) with `gosu` privilege-stepping to keep host directory permissions clean.
  - Includes ready-to-use Unraid XML template and `docker-compose.yml`.

---

## 🚀 Installation on Unraid

### Method 1: Using the Unraid Docker Template (Recommended)

1. Copy [`my-ebay-deal-monitor.xml`](./my-ebay-deal-monitor.xml) to your Unraid flash drive:
   ```bash
   cp my-ebay-deal-monitor.xml /boot/config/plugins/dockerMan/templates-user/
   ```
2. In the Unraid WebUI, navigate to **Docker** &rarr; **Add Container**.
3. Select **ebay-deal-monitor** from the template dropdown.
4. The template will automatically configure:
   - **Container Port**: `8080`
   - **Host Path**: `/mnt/user/appdata/ebay-deal-monitor` &rarr; Container `/config`
   - **PUID**: `99` (nobody)
   - **PGID**: `100` (users)
5. Click **Apply**. Once started, open `http://[YOUR-UNRAID-IP]:8080`.

---

### Method 2: Docker Compose

You can deploy directly using Docker Compose on any server or Unraid with the Compose Manager plugin:

```yaml
version: '3.8'

services:
  ebay-deal-monitor:
    image: ebay-deal-monitor:latest
    build: .
    container_name: ebay-deal-monitor
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - PUID=99
      - PGID=100
      - PORT=8080
      - POLL_INTERVAL=120
    volumes:
      - /mnt/user/appdata/ebay-deal-monitor:/config
```

Launch the stack:
```bash
docker compose up -d
```

---

## 💻 Local Development Setup

To run locally outside Docker:

1. Clone repository and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Start the application:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```
3. Open `http://localhost:8080` in your web browser.

---

## ⚙️ Configuration & Webhooks

Navigate to the **Settings & Logs** tab in the web portal to configure:

### 1. eBay Authentication
- **App ID & Cert ID**: Optional. If provided, the scanner will use eBay's OAuth REST Browse API. If omitted, the application seamlessly uses eBay's RSS feed parser without any API keys.

### 2. Notifications
- **Discord Webhook**: Enter your Discord webhook URL (e.g. `https://discord.com/api/webhooks/...`). Deals will be sent as rich embeds with thumbnails, prices, and direct links.
- **Pushbullet**: Enter your Pushbullet Access Token to receive push alerts to your phone or desktop.
- **Generic Webhook**: Enter any HTTP endpoint (e.g., Home Assistant, n8n, Node-RED) to receive raw JSON deal events.
- Use the **Test** button next to any webhook input to immediately verify connectivity.

### 3. Polling Engine
- **Poll Interval**: Frequency in seconds that the background worker checks for new listings (default: `120` seconds).
- **Auto-Archive Retention**: Number of days after which old deals are cleaned up (default: `0` = keep indefinitely). Starred deals are never auto-archived.

---

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
pytest -v
```

---

## 📄 License

MIT License. Designed for personal deal monitoring and home lab automation.
