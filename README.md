# AIsolate integrations

Ask an AIsolate airlock from a workflow tool. Each integration signs in, posts the question and lays the answer out
with its provenance and evidence. The contract they rely on (the JSON answer, the sign-in, the airlocks a client may
ask, what the workflow sees, how to run it in production) is
[`docs/integrate.md` in the `aisolate` repository](https://github.com/reportix/aisolate/blob/main/docs/integrate.md).

| Tool | What is here |
|---|---|
| [KNIME extension](knime/aisolate-extension/README.md) | Three KNIME nodes, AIsolate Connector, Airlock Selector and Airlock Prompter: sign in with a client id and secret, pick the airlock from a list, ask one question or one per row; `knime/aisolate-ask-nodes.knwf` is a workflow with them |
| [KNIME workflow](knime/README.md) | `aisolate-ask.knwf`, a workflow of standard KNIME nodes (OAuth2 Authenticator, POST Request, JSON Path), and `aisolate-ask/`, the same workflow unpacked |
| [n8n](n8n/README.md) | The AIsolate community node (credential, node, AI Agent tool), an HR helpdesk and a chat-agent workflow with it, and `aisolate-ask.json`, an HTTP-only workflow |

AIsolate ships neither n8n nor KNIME, and needs neither. Each tool comes under its own licence (n8n's Sustainable
Use License, KNIME Analytics Platform's GPL-3.0 with its exceptions); install the one you run yourself.

The hosts default to a local cluster. The nodes sign in as an application, a client id and its secret (the
client-credentials grant): the demo realm has `knime` and `n8n`, both with the secret `change-me`, listed in the HR
airlock's `access.clients`. The KNIME workflow of standard nodes still signs in as a user (client `etl`, user
`nora@example.com`, which the demo realm does not have). Replace them for your installation.

## License

Apache License 2.0 (`LICENSE`, SPDX `Apache-2.0`), unlike AIsolate itself (AGPL-3.0-only): use, change and ship
these integrations inside your own workflows and extensions under any licence.

Copyright (C) 2026 Reportix.
