#!/bin/bash
# setup-homepod.sh — Configure Linux to use a HomePod Mini as an AirPlay audio sink
# Sets up PipeWire RAOP discovery and firewall rules, then prints the sink name
# for use as PIPEWIRE_SINK in your MCP config.
set -euo pipefail

# --- Prompt for HomePod IP ---
read -rp "HomePod IP address (e.g. 192.168.1.15): " HOMEPOD_IP
[[ -z "$HOMEPOD_IP" ]] && { echo "Error: no IP entered."; exit 1; }

# --- Firewall ---
echo ""
echo "Configuring firewall..."
sudo ufw allow from "$HOMEPOD_IP" comment "HomePod Mini audio"
sudo ufw allow 5353/udp comment "AirPlay mDNS"
sudo ufw enable

# --- PipeWire RAOP discovery ---
echo ""
echo "Writing PipeWire config..."
CONFIG_FILE="$HOME/.config/pipewire/pipewire.conf.d/raop-discover.conf"
mkdir -p "$(dirname "$CONFIG_FILE")"

cat > "$CONFIG_FILE" << 'EOF'
context.modules = [
    {
        name = libpipewire-module-raop-discover
        args = { }
    }
]
EOF

echo "Saved: $CONFIG_FILE"

# --- Restart audio services ---
echo ""
echo "Restarting audio services..."
systemctl --user restart wireplumber pipewire

# --- Discover sink name ---
echo ""
echo "Waiting for HomePod to appear (10s)..."
sleep 10

echo ""
echo "Available sinks:"
pw-cli list-objects | grep -E "node.name|media.class" | grep -B1 "Audio/Sink"

echo ""
echo "=== Done ==="
echo ""
echo "Find your HomePod sink name above (look for 'raop' or your device name),"
echo "then set it in your MCP config or environment:"
echo ""
echo "  export PIPEWIRE_SINK=\"<sink-name-from-above>\""
echo ""
echo "Or in .mcp.json / claude_desktop_config.json:"
echo "  \"PIPEWIRE_SINK\": \"<sink-name-from-above>\""
