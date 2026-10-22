# n8n: ask an airlock

The node, two workflows built with it, and one with n8n's own nodes only:

| File | What it is |
|---|---|
| [`n8n-nodes-aisolate/`](n8n-nodes-aisolate/README.md) | A community node package: the **AIsolate API** credential and the **AIsolate** node (Ask airlock, List airlocks), also usable as a tool by n8n's AI Agent |
| `aisolate-helpdesk.json`, `hr-helpdesk-tickets.xlsx` | An HR helpdesk with the node: read the open tickets, ask the airlock each one, route any answer that is not fully sourced to a person |
| `aisolate-agent.json` | A chat agent with the node as its tool: a local model (Ollama) calls the airlock for anything about a contract |
| `aisolate-ask.json` | The same calls with n8n's own HTTP Request nodes only, no package to install |

Every one signs in as an application: a client id and its secret, the client-credentials grant, no user and no
password. The airlock admits the client when its id is in the airlock's `access.clients` (`clients: [n8n]` in the
demo); the audit records the exchange with the client id. n8n itself comes under its Sustainable Use License; the
files here are Apache-2.0.

## The node

Build it and give it to n8n (a self-hosted n8n loads packages from `~/.n8n/nodes`):

```bash
cd n8n-nodes-aisolate && npm install && npm run build      # npm test also runs the client's tests
mkdir -p ~/.n8n/nodes/node_modules/n8n-nodes-aisolate
cp -R package.json dist ~/.n8n/nodes/node_modules/n8n-nodes-aisolate/
```

Then in n8n: **Credentials → AIsolate API** with the release URL (`http://aisolate.localhost`), the client id and
the secret; the identity provider is found from the release. The **AIsolate** node's *Airlock* lists the
airlocks that client may ask; *Question* takes expressions, e.g. `What is {{ $json.employee }}'s notice period?`.
The output is the item with the airlock's answer added: `answer`, `provenance` (`status` and the four counts),
`evidence`, `figures`, `revision`, `trace_id`. For the AI Agent, start n8n with
`N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`; the node then appears as a tool.

The demo run, with the local cluster's hosts mapped into the container:

```bash
docker run -d --name aisolate-n8n -p 5678:5678 \
  --add-host aisolate.localhost:host-gateway --add-host keycloak.aisolate.localhost:host-gateway \
  -e N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true -e N8N_RESTRICT_FILE_ACCESS_TO=/data \
  -v ~/.n8n/nodes:/home/node/.n8n/nodes -v "$PWD":/data n8nio/n8n:2.44.5
```

`aisolate-helpdesk.json` reads `/data/hr-helpdesk-tickets.xlsx` (the mount above); `aisolate-agent.json` uses the
model `granite4.1:8b` on the host's Ollama (credential **Ollama**, base URL `http://host.docker.internal:11434`).
Both were imported and run with n8n 2.44.5 against the HR airlock of a local cluster: the helpdesk answered the four
tickets with no mismatch, the agent called the airlock and answered from it.

## The HTTP-only workflow

`aisolate-ask.json` is one workflow:

```
Run → Parameters → Sign in → Ask AIsolate → Evidence table
```

| Node | Does |
|---|---|
| Run | Manual trigger |
| Parameters | A Set node holding every setting: `aisolateUrl`, `keycloakUrl`, `realm`, `clientId`, `clientSecret`, `space`, `airlock`, `question` |
| Sign in | `POST {keycloakUrl}/realms/{realm}/protocol/openid-connect/token`, form body with the client-credentials grant and the scope `openid profile email` |
| Ask AIsolate | `POST {aisolateUrl}/v1/spaces/{space}/airlocks/{airlock}/chat` with `Authorization: Bearer …`, `Accept: application/json` and a 600-second timeout |
| Evidence table | A Code node: one item per evidence entry, each carrying `answer`, `dont_know`, `provenance` (the answer's `provenance.status`) with its four counts, `revision`, `trace_id` and the entry's `evidence_id`, `source`, `name` and `rows` |

`rows` is a count: the airlock's JSON answer never carries rows (`docs/integrate.md` in the `control-plane`
repository, section *What the workflow sees*). `provenance` is the gate: `all_sourced` when every figure is written
in from the evidence or computed from it, `has_unsourced` or `has_mismatch` when a person should look first,
`no_figures` when the answer states none.

In the n8n editor: **Workflows → Import from file**, pick `aisolate-ask.json`, open **Parameters**, replace the
defaults (the hosts point at a local cluster; the client `n8n` and its secret `change-me`), and run. The client
secret sits in the Set node so the file is self-contained; for a workflow that stays, use the node and its
credential instead. The nodes use `n8n-nodes-base.httpRequest` 4.2, `n8n-nodes-base.set` 3.4 and
`n8n-nodes-base.code` 2; imported and run with n8n 2.44.5.
