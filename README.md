<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/aisolate-white.png">
    <img src="docs/assets/aisolate-black.png" alt="AIsolate" width="480">
  </picture>
</p>

<p align="center"><strong>Ask an AIsolate airlock from n8n and KNIME.</strong></p>

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

`n8n/` holds a community node that asks an airlock as an application, not a user, and three example workflows. `knime/` holds
an extension with the Connector, Selector and Prompter nodes, a workflow that uses them, and a REST-only workflow.

## n8n

Build the node and give it to a self-hosted n8n, which loads packages from `~/.n8n/nodes`. The demo run starts n8n with it and
maps the local cluster's hosts in; `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true` lets the AI Agent use the node as a tool:

```bash
cd n8n/n8n-nodes-aisolate && npm ci && npm run build
mkdir -p ~/.n8n/nodes/node_modules/n8n-nodes-aisolate && cp -R package.json dist ~/.n8n/nodes/node_modules/n8n-nodes-aisolate/
cd .. && docker run -d --name aisolate-n8n -p 5678:5678 \
  --add-host aisolate.localhost:host-gateway --add-host keycloak.aisolate.localhost:host-gateway \
  -e N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true -e N8N_RESTRICT_FILE_ACCESS_TO=/data \
  -v ~/.n8n/nodes:/home/node/.n8n/nodes -v "$PWD":/data n8nio/n8n:2.44.5
```

**Credentials → AIsolate API** takes the **AIsolate URL** (the release, `http://aisolate.localhost` on the local cluster), the
**Client ID** (it must be in the airlock's `access.clients`) and the **Client Secret**. The local demo realm's clients `n8n` and
`knime` use the secret `change-me`: replace it. Import the workflows in `n8n/` with **Workflows → Import from file**:

- `aisolate-helpdesk.json` with `hr-helpdesk-tickets.xlsx`: an HR helpdesk that routes any answer not `all_sourced` to a person.
- `aisolate-agent.json`: a chat agent with the node as its tool, on `granite4.1:8b` (**Ollama** credential,
  `http://host.docker.internal:11434`).
- `aisolate-ask.json`: the same calls with HTTP Request nodes only, no package to install; its **Parameters** hold the secret
  too, so use the node for a workflow that stays.

## KNIME

The extension runs in development mode and needs KNIME 5.12 with **KNIME Python Extension Development (Labs)** and
[pixi](https://pixi.sh): run `pixi install` in `knime/aisolate-extension/` for the nodes' Python environment, then add
`-Dknime.python.extension.debug_knime_yaml_list=/path/to/integrations/knime/aisolate-extension/knime.yml` on a line after
`-vmargs` in `knime.ini` (on macOS `KNIME 5.12.app/Contents/Eclipse/knime.ini`), restart KNIME and find three nodes in the **AIsolate** category:

- **AIsolate Connector** signs in with the client's id and secret (a credentials flow variable) and lists the airlocks it may ask.
- **Airlock Selector** picks one airlock from that list.
- **Airlock Prompter** asks its own question, or one per row of a connected table, and adds columns such as `answer`, `provenance` and `evidence`.

Drag `knime/aisolate-ask-nodes.knwf`, an HR helpdesk, onto the space explorer. Set the client id and secret in Credentials
Configuration and the release in AIsolate Connector, execute it, pick the airlock in Airlock Selector and execute Airlock Prompter.
`knime/aisolate-ask.knwf` needs no extension and signs in as a user: set its client, user, token endpoint and request (the demo's
airlock is `hr-contracts` in `hr-space`). KNIME's own encryption of the saved secrets hides them from a casual reader only.

## Documentation

- The product's [`docs/integrate.md`](https://github.com/reportix/aisolate/blob/main/docs/integrate.md): the token and chat calls and
  what a workflow sees; [`docs/api.md`](https://github.com/reportix/aisolate/blob/main/docs/api.md) has `GET /v1/airlocks`.
- The website: [aisolate.ai](https://aisolate.ai)
