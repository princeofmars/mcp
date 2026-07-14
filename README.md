# Enterprise MCP Health Gateway

A runnable MVP for onboarding enterprise tenants and agents, exposing governed health capabilities through MCP, storing downstream credentials, and monitoring tool activity from an analytics dashboard.

## Included

- Multi-tenant enterprise onboarding
- One-time admin and agent keys, stored only as SHA-256 hashes
- Per-agent tool and purpose permissions
- Encrypted downstream credential vault using Fernet
- Streamable HTTP MCP server using the stable official Python SDK line
- Deterministic policy enforcement outside the model
- Provider-neutral demo health tools
- Pseudonymized, structured audit events
- Dashboard for calls, success rate, denials, p95 latency, active agents and tool usage
- Docker Compose deployment
- Unit tests

## Architecture

```text
Enterprise agent
    |
    | Bearer token
    v
MCP service :8001
    | identity + tool/purpose policy + audit
    v
Health capability services
    v
Provider adapter interface

Admin browser / enterprise control plane
    |
    v
Admin API + dashboard :8000
    |
    v
Shared database and encrypted credential store
```

The included health connector is synthetic and deterministic. Replace `app/connectors/demo.py` with a production adapter for Thryve or another health data provider.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open the dashboard at `http://localhost:8000`.

Local demo credentials:

```text
Admin key: adm_demo_change_me
Agent token: mcp_demo_change_me
MCP endpoint: http://localhost:8001/mcp
```

Change all demo keys and `SECRET_KEY` before using the project outside local development.

## Test the MCP service

```bash
MCP_AGENT_TOKEN=mcp_demo_change_me python examples/client.py
```

The example client lists tools and calls `prepare_prevention_brief` for a synthetic member. The tool call appears in the dashboard within the next refresh.

## Run without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
mkdir -p data
cp .env.example .env

uvicorn app.api:app --reload --port 8000
python -m app.mcp_server
```

## Admin API examples

Create a tenant:

```bash
curl -X POST http://localhost:8000/api/v1/onboard \
  -H 'Content-Type: application/json' \
  -d '{"organization_name":"Example Insurer","admin_email":"admin@example.com"}'
```

Create an agent:

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Key: adm_demo_change_me' \
  -d '{
    "name":"Prevention Agent",
    "environment":"production",
    "allowed_tools":["list_authorized_capabilities","get_member_activity_summary","assess_data_quality","prepare_prevention_brief"],
    "allowed_purposes":["operational","prevention"]
  }'
```

Store a downstream credential:

```bash
curl -X POST http://localhost:8000/api/v1/credentials \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Key: adm_demo_change_me' \
  -d '{"provider":"garmin","name":"production-oauth","secret":"replace-me"}'
```

## Production hardening still required

This repository is an MVP, not a compliance certification. Before production, add:

- An external OAuth 2.1 / OIDC authorization server and protected-resource metadata
- Workload identity or signed JWT validation instead of opaque demo bearer keys
- PostgreSQL, schema migrations, backups and tenant-level database controls
- A managed KMS or secret manager instead of application-derived Fernet keys
- Consent and legal-basis records linked to each member and purpose
- Retention, deletion, data-subject request and regional processing workflows
- Signed tool manifests and deployment approvals
- Immutable or tamper-evident audit storage and SIEM export
- Rate limits, circuit breakers, batch limits and human approval services
- Provider-specific OAuth and token refresh handling
- Security testing for prompt injection, tool poisoning, SSRF and confused-deputy attacks

## Important design choices

- The model never authorizes itself. Tool and purpose policy is checked by deterministic code.
- Provider credentials never enter MCP tool output or model context.
- Member identifiers are hashed before audit storage.
- Tools return evidence, confidence, limitations and explicit non-diagnostic boundaries.
- Reward and prevention outputs require human review in this MVP.
