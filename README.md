# AIsolate integrations

Ask an AIsolate airlock from n8n or KNIME. Each integration signs in, posts the question and returns the answer with its
provenance and evidence. The token and chat calls and what the workflow sees are described in
[`docs/integrate.md` in the `aisolate` repository](https://github.com/reportix/aisolate/blob/main/docs/integrate.md); the
airlock listing, `GET /v1/airlocks`, is in [`docs/api.md`](https://github.com/reportix/aisolate/blob/main/docs/api.md) there.
The answer's `provenance` has a `status` (`all_sourced`, `has_unsourced`, `has_mismatch` or `no_figures`) and the counts
`sourced`, `computed`, `unsourced` and `mismatch`: route anything but `all_sourced` to a person. `evidence` lists what the
answer rests on (`id`, `source`, `name`, `rows` as a count, `data_source`), never the rows.

AIsolate ships neither n8n nor KNIME and needs neither. n8n comes under its Sustainable Use License, KNIME Analytics Platform
under GPL-3.0 with its exceptions; install the one you run yourself.

## The client

The n8n node and the KNIME extension sign in as an application: a client id and its secret (the client-credentials grant), no
user. They find the identity provider from the release (`/.well-known/oauth-protected-resource`, then the issuer's OpenID
configuration). The airlock admits the client when its id is in the airlock's `access.clients`; the audit records the exchange
with the client id. The hosts default to a local cluster, whose demo realm has the clients `knime` and `n8n`, both with the
secret `change-me`, in the HR airlock's `access.clients`. Replace them for your installation.

## n8n

`n8n/n8n-nodes-aisolate/` is a community node package: the **AIsolate API** credential and the **AIsolate** node (*Ask
Airlock*, *List Airlocks*), also usable as a tool by n8n's AI Agent. Build it and give it to a self-hosted n8n, which loads
packages from `~/.n8n/nodes`:

```bash
cd n8n/n8n-nodes-aisolate && npm ci && npm run build
mkdir -p ~/.n8n/nodes/node_modules/n8n-nodes-aisolate
cp -R package.json dist ~/.n8n/nodes/node_modules/n8n-nodes-aisolate/
```

In n8n, **Credentials → AIsolate API** takes the release URL (`http://aisolate.localhost`), the client id and the secret. The
node's *Airlock* lists the airlocks that client may ask; *Question* takes expressions, e.g. `What is {{ $json.employee }}'s
notice period?`. The output is the item with the airlock's JSON answer (without `dont_know`) plus `question` added. For the
AI Agent, start n8n with `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`. The demo run, from `n8n/`, with the local
cluster's hosts mapped into the container:

```bash
docker run -d --name aisolate-n8n -p 5678:5678 \
  --add-host aisolate.localhost:host-gateway --add-host keycloak.aisolate.localhost:host-gateway \
  -e N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true -e N8N_RESTRICT_FILE_ACCESS_TO=/data \
  -v ~/.n8n/nodes:/home/node/.n8n/nodes -v "$PWD":/data n8nio/n8n:2.44.5
```

The workflows in `n8n/` (**Workflows → Import from file**):

| File | What it is |
|---|---|
| `aisolate-helpdesk.json`, `hr-helpdesk-tickets.xlsx` | An HR helpdesk with the node: read the open tickets (`/data` above), ask the airlock each one, route any answer that is not fully sourced to a person |
| `aisolate-agent.json` | A chat agent with the node as its tool: a local model (`granite4.1:8b` on the host's Ollama, credential **Ollama**, base URL `http://host.docker.internal:11434`) calls the airlock for anything about a contract |
| `aisolate-ask.json` | The same calls with n8n's own HTTP Request nodes only, no package to install: Run → Parameters → Sign in → Ask AIsolate → Evidence table. **Parameters** holds every setting, the client secret too so the file is self-contained; for a workflow that stays, use the node and its credential |

## KNIME

Two workflows in `knime/`, both saved for KNIME Analytics Platform 5.12: import a `.knwf` into a space (drag the file onto the
space explorer, or use the explorer's import button).

**The extension** (`knime/aisolate-extension/`) adds three nodes in an **AIsolate** category of the node repository, wired
Credentials Configuration (client) → AIsolate Connector → Airlock Selector → Airlock Prompter, with an optional questions table
into the prompter:

- **AIsolate Connector** signs in with the client's id and secret (a credentials flow variable) and lists the airlocks that
  client may ask; one that does not admit the client is missing from the list, never an error. The token never leaves the node.
- **Airlock Selector** picks one airlock from that list (left empty, the first one).
- **Airlock Prompter** asks it: its own question, or one per row of a connected table (pick the question column; a row without
  a question fails the node or gets missing values, as you choose). Each row gets `answer` (a column name you may change),
  `provenance` (the status), `sourced`, `computed`, `unsourced`, `mismatch`, `evidence` as JSON, `revision` and `trace_id`.

Install it in development mode. It needs KNIME 5.12 with **KNIME Python Extension Development (Labs)**
(`org.knime.features.python3.nodes`) and [pixi](https://pixi.sh): run `pixi install` in `knime/aisolate-extension/` (the
nodes' Python environment, in `.pixi/`), add one line after `-vmargs` in KNIME's `knime.ini` (on macOS
`KNIME 5.12.app/Contents/Eclipse/knime.ini`) and restart KNIME:

```
-Dknime.python.extension.debug_knime_yaml_list=/path/to/integrations/knime/aisolate-extension/knime.yml
```

Then import `aisolate-ask-nodes.knwf`, an HR helpdesk: it answers the open tickets in its data area (the same
`hr-helpdesk-tickets.xlsx` as the n8n helpdesk) from the contracts behind the airlock. Set the client id and secret in
Credentials Configuration and the release in AIsolate Connector, execute it, pick the airlock in Airlock Selector and execute
Airlock Prompter. Disconnect the Excel Reader and the prompter asks its own Question instead.

**Standard nodes only**, no extension to install: `aisolate-ask.knwf` runs Credentials Configuration (`client`, `user`) →
OAuth2 Authenticator (Password) → POST Request → JSON Path. It signs in as a user (the password grant, the client id and secret
as HTTP Basic), posts the question with `Accept: application/json` (that value alone, or the airlock streams) and a 600-second
read timeout, and returns one row: the answer, its provenance and its evidence. Set the client and the user in the two
Credentials Configuration nodes, the realm's token endpoint in OAuth2 Authenticator, and the URL and request body in POST
Request, then execute JSON Path. The defaults are placeholders the demo realm does not have (client `etl`, user
`nora@example.com`, space `acme`, airlock `hr`; the demo's HR airlock is `hr-contracts` in `hr-space`). The secret and the
password are saved with KNIME's own encryption, which hides them from a casual reader but is not a secret store.

## Develop

```bash
cd n8n/n8n-nodes-aisolate && npm ci && npm test        # the client's calls against an in-process stand-in; builds first
cd knime/aisolate-extension && pixi run -e test test   # the same for the KNIME client
```

## License

Apache License 2.0 (`LICENSE`, SPDX `Apache-2.0`), unlike AIsolate itself (AGPL-3.0-only): use, change and ship these
integrations inside your own workflows and extensions under any licence.

Copyright (C) 2026 Reportix.
