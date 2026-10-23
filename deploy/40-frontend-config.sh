#!/bin/sh
set -eu

policy_url=${PUBLIC_PRIVACY_POLICY_URL:-}
case "$policy_url" in
    '') policy_json=null ;;
    http://*|https://*)
        # JSON escaping also prevents quotes/backslashes in a configured URL
        # from turning into executable JavaScript.
        policy_json=$(printf '%s' "$policy_url" | awk '
            BEGIN { printf "\"" }
            {
                if (NR > 1) printf "\\n";
                for (i = 1; i <= length($0); i++) {
                    c = substr($0, i, 1);
                    if (c == "\\") printf "\\\\";
                    else if (c == "\"") printf "\\\"";
                    else if (c == "\t") printf "\\t";
                    else if (c == "\r") printf "\\r";
                    else if (c == "\b") printf "\\b";
                    else if (c == "\f") printf "\\f";
                    else printf "%s", c;
                }
            }
            END { printf "\"" }
        ')
        ;;
    *)
        printf '%s\n' 'PUBLIC_PRIVACY_POLICY_URL must be empty or an absolute http(s) URL.' >&2
        exit 1
        ;;
esac

mkdir -p /etc/nginx/generated
config_tmp=$(mktemp /etc/nginx/generated/config.js.XXXXXX)
trap 'rm -f "$config_tmp"' EXIT HUP INT TERM
printf 'window.ASTRO_CONFIG = { apiBaseUrl: "", privacyPolicyUrl: %s };\n' "$policy_json" > "$config_tmp"
chmod 644 "$config_tmp"
mv "$config_tmp" /etc/nginx/generated/config.js
