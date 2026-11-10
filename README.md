# SOC-as-Code

Automated security monitoring, threat intelligence enrichment, and incident management, deployed as code.

A lightweight Security Operations Center pipeline built around **Wazuh** (SIEM), **n8n** (SOAR/workflow automation), and **DFIR-IRIS** (case management). Alerts are detected, enriched with threat intelligence, scored, and turned into structured incident cases automatically. All services run in Docker and are provisioned with Ansible.

---

## Architecture

```
 Monitored host (Linux / Windows)
            │
       Wazuh Agent
            │
      Wazuh Manager ── detection rules, MITRE ATT&CK mapping
        │        │
        │        └── Active Response (firewall-drop on brute force)
        ▼
 Custom integration script (custom-n8n)
            │  HTTP POST (JSON)
            ▼
     n8n webhook workflow
   ┌────────┼────────┐
VirusTotal AbuseIPDB  OTX      (queried in parallel)
   └────────┼────────┘
            ▼
   Merge → Score verdict
            │
   Worth a case?  ── no ──▶ no action
            │ yes
            ▼
   DFIR-IRIS case (via API)
```

<img width="1408" height="768" alt="soc_as_code_architecture" src="https://github.com/user-attachments/assets/8de9d062-8367-4f52-97f8-ef080dcf1338" />

## Features

- **Detection:** Wazuh agents on Linux and Windows hosts, with built-in rules for SSH brute force, file integrity monitoring, and system logs.
- **Custom integration:** a Wazuh `<integration>` script forwards alerts to an n8n webhook as structured JSON.
- **Threat intel enrichment:** VirusTotal, AbuseIPDB, and AlienVault OTX are queried in parallel and merged into one verdict.
- **Automated case creation:** alerts above a score threshold become DFIR-IRIS cases with rule, severity, agent, source IP, and enrichment data filled in.
- **Active Response:** repeated failed logins (rule 2502, MITRE T1110) trigger `firewall-drop` to block the source IP for 600 s.
- **Resilient workflow:** alerts without a source IP take a fallback branch instead of failing the pipeline.
- **Infrastructure as code:** Docker Compose services, idempotent Ansible playbooks, and Ansible Vault for secrets.

## Tech stack

| Role | Tool |
|---|---|
| SIEM / endpoint detection | Wazuh |
| SOAR / workflow automation | n8n |
| Incident management | DFIR-IRIS |
| Threat intelligence | VirusTotal, AbuseIPDB, AlienVault OTX |
| Containers | Docker, Docker Compose |
| Provisioning | Ansible (Terraform was evaluated, not used for deployment) |
| Version control | Git |

## Design decisions

The target was a single 8 GB RAM VM, so the stack is deliberately light:

- **IRIS instead of TheHive + Cortex:** smaller footprint with comparable case management.
- **n8n instead of Shuffle:** Shuffle needs its own dedicated OpenSearch instance.
- **No MISP / IntelOwl:** both need a full self-hosted platform. Reputation lookups go through public APIs instead.
- **Ansible instead of Terraform for services:** the services run on a single VM, so VM provisioning added little.

## Repository structure

```
soc-as-code/
├── ansible/
│   └── playbooks/
│       ├── deploy-iris.yml
│       ├── deploy-n8n.yml
│       └── vars/
│           └── n8n_secrets.vault.yml     # encrypted with Ansible Vault
├── wazuh-docker/
│   └── single-node/
│       ├── docker-compose.yml
│       ├── custom-n8n                    # integration wrapper script
│       ├── custom/n8n.py                 # integration script (forwards alerts to n8n)
│       └── config/wazuh_cluster/
│           └── wazuh_manager.conf        # integration + active-response config
└── iris-web/                             # DFIR-IRIS deployment
```

## Prerequisites

- Ubuntu Server VM with at least 8 GB RAM
- Docker and Docker Compose
- Ansible
- API keys for VirusTotal, AbuseIPDB, and AlienVault OTX

## Getting started

```bash
git clone https://github.com/d0ok/soc-as-code.git
cd soc-as-code
```

1. **Wazuh:** from `wazuh-docker/single-node/`, generate the indexer certificates with Wazuh's cert generator, then `docker compose up -d`.
2. **IRIS:** `ansible-playbook ansible/playbooks/deploy-iris.yml`
3. **n8n:** create your own vault file from the template, then run `ansible-playbook ansible/playbooks/deploy-n8n.yml --ask-vault-pass`
4. **n8n workflow:** import the workflow, add your API keys as credentials, and **publish** it. Wazuh must call the **Production** webhook URL (`/webhook/...`), not the Test URL.
5. **Wazuh integration:** set the n8n `hook_url` in `wazuh_manager.conf`, then recreate the manager container.

## Configuration notes

- **Apply Wazuh config changes with `docker compose down && up`.** The config is bind-mounted and copied at container start, so `restart` does not pick it up.
- **Integration scripts need mode `755`.** Wazuh runs them as a different UID than the host user, so `750` fails silently with `Couldn't execute command` in `ossec.log`.
- **Active Response needs `NET_ADMIN` and `iptables`.** The manager service adds `cap_add: [NET_ADMIN, SYS_PTRACE]`, and `iptables` is installed inside the container (`dnf`, Amazon Linux 2023 base).
- **Use a stable VM IP.** The VM runs on VMware NAT networking. Bridged mode broke the Wazuh `hook_url`, the n8n IRIS node URL, and the agent manager addresses on every network change.
- **Never suspend the VM.** Suspend corrupts Docker's bridge networking. Shut it down cleanly.

## Validation

| Path | Status |
|---|---|
| Wazuh → n8n webhook delivery | Verified |
| n8n → VirusTotal / AbuseIPDB / OTX | Verified |
| n8n → IRIS case creation (correct rule, level, verdict) | Verified |
| SSH brute-force detection in Wazuh (rule 2502, T1110) | Verified with a real attack |
| Active Response block following rule 2502 | Verified in live alert logs (rule 651 within ~1 s) |
| Single uninterrupted live attack through the **entire** chain to an IRIS case | **Not demonstrated** |

Components were validated individually and through controlled test events. A single continuous live attack traversing the whole pipeline in one run was not demonstrated.

## Security

- No secrets are committed. `.gitignore` excludes `.env`, TLS certificates, and key material.
- Ansible Vault encrypts the n8n secrets file.
- Redact API keys, tokens, and credentials from any screenshot before publishing.

## Limitations

- Single-node deployment, no high availability
- Three threat intel sources
- Basic threshold-based scoring with manual tuning
- No multi-tenant support

## Roadmap

- Alert correlation engine
- More SOAR playbooks (account disable, endpoint isolation)
- Production hardening and HA
- Performance monitoring
- Additional threat intel integrations
- Automated resilience testing
