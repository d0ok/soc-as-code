import sys
import json
import logging
import urllib.request
import urllib.error

logging.basicConfig(
    filename="/var/ossec/logs/integrations.log",
    level=logging.INFO,
    format="%(asctime)s custom-n8n: %(message)s",
)


def main():
    # Wazuh calls integration scripts as:
    #   custom-n8n <alert_file> <user/api_key> <hook_url> [options] [alert_file_diff]
    # argv[1] = alert file path
    # argv[2] = user / api_key placeholder (often "-" or empty) — not used here
    # argv[3] = hook_url (this is what we actually need)
    if len(sys.argv) < 4:
        logging.error(
            f"Missing arguments. Got argv={sys.argv}. "
            f"Expected: <alert_file> <user> <hook_url>"
        )
        sys.exit(1)

    alert_file_path = sys.argv[1]
    hook_url = sys.argv[3]

    try:
        with open(alert_file_path, "r") as f:
            alert_json = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read/parse alert file {alert_file_path}: {e}")
        sys.exit(1)

    payload = build_payload(alert_json)

    try:
        send_to_n8n(hook_url, payload)
        logging.info(
            f"Forwarded alert rule={payload.get('rule_id')} "
            f"level={payload.get('rule_level')} to n8n"
        )
    except Exception as e:
        logging.error(f"Failed to POST to n8n webhook {hook_url}: {e}")
        sys.exit(1)


def build_payload(alert):
    """Flatten the fields the n8n workflow actually needs."""
    rule = alert.get("rule", {})
    agent = alert.get("agent", {})
    data = alert.get("data", {})
    return {
        "timestamp": alert.get("timestamp"),
        "rule_id": rule.get("id"),
        "rule_level": rule.get("level"),
        "rule_description": rule.get("description"),
        "mitre": rule.get("mitre", {}),
        "agent_name": agent.get("name"),
        "agent_ip": agent.get("ip"),
        "src_ip": data.get("srcip"),
        "dest_ip": data.get("dstip"),
        "url": data.get("url"),
        "full_alert": alert,
    }


def send_to_n8n(hook_url, payload):
    body = json.dumps(payload).encode("utf8")
    req = urllib.request.Request(
        hook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status > 300:
            raise RuntimeError(f"n8n webhook returned HTTP {resp.status}")


if __name__ == "__main__":
    main()
