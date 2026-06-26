# Scale Bridge

Local bridge process for reading a USB/serial weighing scale on the operator PC and pushing the latest weight to the live WPE backend.

## Run

```bash
cd scale-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bridge.py
```

## Required config

Set these values in `../.env` (`wpe-backend/.env`). The bridge reads the same env file as the backend; do not create a second env file inside `scale-bridge`.

```env
WPE_SERVER_URL=http://127.0.0.1:8000
SCALE_BRIDGE_API_KEY=replace-with-bridge-api-key
DEVICE_ID=SCALE-01
WORKSTATION_ID=PRODUCTION-PC-01
BRIDGE_CLIENT_ID=production-pc-01
SERIAL_PORT=AUTO
SERIAL_BAUD_RATE=9600
PUSH_INTERVAL_MS=500
STALE_AFTER_SECONDS=5
SCALE_BRIDGE_STALE_AFTER_SECONDS=5
```

Use a unique `DEVICE_ID`, `WORKSTATION_ID`, and `BRIDGE_CLIENT_ID` on every client PC. Example:

- `SCALE-01` / `PRODUCTION-PC-01` / `production-pc-01`
- `SCALE-02` / `BLENDING-PC` / `blending-pc`
- `SCALE-03` / `GRANULATION-PC` / `granulation-pc`

If `BRIDGE_CLIENT_ID` is omitted, `bridge.py` falls back to the local machine hostname.
