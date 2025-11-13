# Health Agentic Use-Case Flow

This repository contains a demo implementation of the Patient Transition from Hospital to Community Mental-Health Care scenario using agentic services and local MCP mock servers for Epic and Health Connect Australia (HCA).

## Structure (planned)

- services/
  - ownership-trigger
  - care-orchestration
  - task-delegation
  - patient-engagement
  - risk-prediction
  - policy
- libs/
  - common
  - fhir
  - adapters
- mcp/
  - mcp-epic-mock
  - mcp-hca-mock
- infra/
  - docker-compose.yml (NATS, Postgres, Prometheus, Grafana, Jaeger)

## Next Steps

1. Implement two MCP mock servers with hardcoded responses for Epic and HCA.
2. Scaffold FastAPI services for each agent with health endpoints.
3. Define common schemas (CloudEvents, tasks, audit) and FHIR helpers.
4. Wire services to MCP via adapters and provide an end-to-end demo script.

## Path

New workspace: /Users/steveduncan/CascadeProjects/Health
