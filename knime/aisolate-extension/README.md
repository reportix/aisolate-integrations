# KNIME extension: the AIsolate nodes

Three KNIME nodes in their own **AIsolate** category of the node repository:

```
Credentials Configuration (client) → AIsolate Connector → Airlock Selector → Airlock Prompter
                                                          Questions table (optional) ┘
```

- **AIsolate Connector** signs in with a client's id and secret and lists the airlocks that client may ask.
  It finds the identity provider from the release itself (`/.well-known/oauth-protected-resource`, then the
  issuer's OpenID configuration) and uses the client-credentials grant, so the only settings are the release's URL
  and a credentials flow variable. The token never leaves the node: nothing in the workflow file can replay it.
- **Airlock Selector** picks one airlock from that list (left empty, the first one).
- **Airlock Prompter** asks it: its own question, or one per row of a connected table (pick the question
  column; a row without a question fails the node or gets missing values, as you choose). Each row gets the
  answer, in a column you may rename, and what it rests on:

| Column | What it is |
|---|---|
| `answer` | The text, every figure written in by AIsolate from the evidence |
| `provenance` | `all_sourced`, `has_unsourced`, `has_mismatch` or `no_figures`; route anything but `all_sourced` to a person |
| `sourced`, `computed`, `unsourced`, `mismatch` | The four counts behind it |
| `evidence` | The entries the answer rests on, as JSON: id, tool, entity, row count, data source; never the rows |
| `revision`, `trace_id` | The release that answered and the exchange's trace in the audit log |

The calls are the ones `docs/integrate.md` in the `control-plane` repository describes: `GET /v1/airlocks` and the
airlock's `POST …/chat` with `Accept: application/json`. The nodes use the Python standard library only.

## The client

The nodes sign in as an application, not as a person: a client id and its secret, the client-credentials grant.

1. In the realm, a confidential client (the demo uses `knime`) that allows only the client-credentials grant and
   carries the `aisolate` scope; give the client the roles whose rows the questions need.
2. The client id in the airlock's `access.clients` (`clients: [knime]` in its project file). The airlock admits a
   token without an e-mail whose client is listed there; the audit records the exchange with the client id.

An airlock that does not admit the client is missing from the connector's list, never an error.

## Install (development mode)

Needs KNIME Analytics Platform 5.12 with **KNIME Python Extension Development (Labs)**
(`org.knime.features.python3.nodes`) and [pixi](https://pixi.sh).

```bash
pixi install                     # the nodes' Python environment, in .pixi/
```

Add one line after `-vmargs` in KNIME's `knime.ini` (on macOS `KNIME 5.12.app/Contents/Eclipse/knime.ini`) with
this folder's absolute path, then restart KNIME:

```
-Dknime.python.extension.debug_knime_yaml_list=/path/to/integrations/knime/aisolate-extension/knime.yml
```

Then import `../aisolate-ask-nodes.knwf` (`../aisolate-ask-nodes/` is the same workflow unpacked): set the client
id and secret in Credentials Configuration, the release in AIsolate Connector, execute it, pick the airlock
in Airlock Selector (left empty, the first one) and execute Airlock Prompter. The demo is an HR helpdesk: it answers
the open tickets in `data/hr-helpdesk-tickets.xlsx` (the workflow's data area, exported with it) from the
contracts behind the airlock; disconnect the Excel Reader and the prompter asks its own Question instead.

## Develop

```bash
pixi run -e test test            # the HTTP calls against an in-process stand-in of Keycloak and AIsolate
```

`markdown` is pinned to 3.10: KNIME 5.12 renders the node descriptions with a class that 3.11 removed.
`src/aisolate_client.py` holds every call and needs no KNIME; `src/aisolate_extension.py` holds the nodes.
