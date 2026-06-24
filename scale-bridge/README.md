# Scale Bridge

Local bridge process for reading a USB/serial weighing scale on the operator PC and pushing the latest weight to the live WPE backend.

## Run

```bash
cd scale-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bridge.py
```

## Required config

Set these values in `.env`:

```env
WPE_SERVER_URL=https://your-live-domain.com
BRIDGE_API_KEY=replace-with-bridge-api-key
DEVICE_ID=AD-WEIGH-01
WORKSTATION_ID=PRODUCTION-PC-01
SERIAL_PORT=AUTO
SERIAL_BAUD_RATE=9600
PUSH_INTERVAL_MS=500
STALE_AFTER_SECONDS=5
BRIDGE_DEMAND_POLL_SECONDS=2
```
