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
DEVICE_ID=AD-WEIGH-01
WORKSTATION_ID=PRODUCTION-PC-01
SERIAL_PORT=AUTO
SERIAL_BAUD_RATE=9600
PUSH_INTERVAL_MS=500
STALE_AFTER_SECONDS=5
SCALE_BRIDGE_STALE_AFTER_SECONDS=5
```
