#!/bin/sh
set -e

# Default to Unraid nobody:users (PUID=99, PGID=100)
PUID=${PUID:-99}
PGID=${PGID:-100}

echo "Starting eBay Deal Monitor with PUID=${PUID} and PGID=${PGID}"

# Create or modify group
if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" appgroup 2>/dev/null || addgroup -g "$PGID" appgroup 2>/dev/null || true
fi

# Create or modify user
if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /config -s /bin/sh -M appuser 2>/dev/null || adduser -u "$PUID" -G appgroup -h /config -s /bin/sh -D appuser 2>/dev/null || true
fi

# Ensure /config exists and set proper permissions
mkdir -p /config
chown -R "${PUID}:${PGID}" /config

# Execute command as target user via gosu
exec gosu "${PUID}:${PGID}" "$@"
