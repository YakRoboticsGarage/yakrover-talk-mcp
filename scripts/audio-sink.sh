#!/bin/bash
# audio-sink.sh — Connect/disconnect audio sinks via WirePlumber
# Usage:
#   ./scripts/audio-sink.sh list          List available sinks
#   ./scripts/audio-sink.sh connect       Set a sink as default output
#   ./scripts/audio-sink.sh disconnect    Unset default sink (stops routing to HomePod)
#   ./scripts/audio-sink.sh status        Show current default sink
set -euo pipefail

cmd="${1:-help}"

list_sinks() {
    echo "Available audio sinks:"
    echo ""
    wpctl status | sed -n '/^Audio/,/^Video/p' | sed -n '/Sinks:/,/Sink endpoints:/p' | grep -E '^\s+│\s+' | head -20
}

get_default_sink() {
    wpctl inspect @DEFAULT_AUDIO_SINK@ 2>/dev/null | grep -E "node.name|node.description" || true
}

case "$cmd" in
    list)
        list_sinks
        ;;

    status)
        echo "Default sink:"
        DEFAULT_INFO=$(get_default_sink)
        if [[ -n "$DEFAULT_INFO" ]]; then
            echo "$DEFAULT_INFO"
        else
            echo "  (none)"
        fi
        ;;

    connect)
        list_sinks
        echo ""
        read -rp "Enter the sink ID number to connect: " SINK_ID
        [[ -z "$SINK_ID" ]] && { echo "Error: no ID entered."; exit 1; }
        wpctl set-default "$SINK_ID"
        echo ""
        echo "Default sink set to ID $SINK_ID:"
        wpctl inspect "$SINK_ID" 2>/dev/null | grep -E "node.name|node.description"
        ;;

    disconnect)
        # Clear the default sink — audio stops routing to HomePod
        wpctl clear-default @DEFAULT_AUDIO_SINK@ 2>/dev/null || true
        # Find any non-RAOP sink to switch to
        LOCAL_SINK=$(list_sinks | grep -vi "raop\|airplay\|living room" | grep -oP '\d+(?=\.)' | head -1)
        if [[ -n "$LOCAL_SINK" ]]; then
            wpctl set-default "$LOCAL_SINK"
            echo "Switched to local sink (ID $LOCAL_SINK):"
            wpctl inspect "$LOCAL_SINK" 2>/dev/null | grep -E "node.name|node.description"
        else
            echo "No local sink available. HomePod is the only sink."
            echo "Audio routing cleared — no default sink set."
        fi
        ;;

    *)
        echo "Usage: $0 {list|connect|disconnect|status}"
        ;;
esac
