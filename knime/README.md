# KNIME: ask an airlock

`aisolate-ask.knwf` is a KNIME Analytics Platform workflow of five nodes that signs in, asks an airlock one
question and returns the answer as one row: the answer, its provenance and its evidence. `aisolate-ask/` next to it
is the same workflow unpacked, so a change shows in a diff. It was run headless in KNIME 5.12 against a
local stand-in of the two endpoints (the token call and the chat call, in the shapes of
`docs/integrate.md` in the `control-plane` repository) and against the realm `acme` of a local cluster. It is saved for
KNIME 5.12.

## Open it

1. In KNIME, import `aisolate-ask.knwf` into a space: drag the file onto the space explorer, or use the explorer's
   import button (File, Import KNIME Workflow in the classic interface).
2. Set the values in the nodes (open a node, change the setting):

   | Node | Setting | Default | What it is |
   |---|---|---|---|
   | Credentials Configuration `client` | Client ID, Client secret | `etl`, `change-me` | The client the workflow signs in with |
   | Credentials Configuration `user` | User, Password | `nora@example.com`, `change-me` | The user the workflow asks as |
   | OAuth2 Authenticator `sign in` | Token endpoint URL | `http://keycloak.aisolate.localhost/realms/acme/protocol/openid-connect/token` | The realm's token endpoint; another realm is another path |
   | POST Request `ask` | URL | `http://aisolate.localhost/v1/spaces/acme/airlocks/hr/chat` | The release, space and airlock |
   | POST Request `ask` | Request body | `{"message": "What is my gross salary?"}` | The question |

3. Execute the last node, JSON Path, and open its output table.

For the demo realm, the client, user and secret are the ones the [README](../README.md) names. The HR
contracts airlock is `hr-contracts` in the space `hr-space`, the Sales airlock `sales` in `acme-financial-group`.

## The nodes

```
Credentials Configuration (client) → Credentials Configuration (user)
   → OAuth2 Authenticator (Password) → POST Request (ask) → JSON Path (the answer)
```

- **Sign in**: OAuth2 Authenticator (Password) takes the client and the user from the two credentials flow
  variables, `client` and `user`, and posts the password grant with `scope=openid profile email` to the token
  endpoint, the client id and secret as HTTP Basic. Its output is a credential, not a column: the token never
  reaches a table.
- **Ask**: POST Request takes the credential on its credential port, which sets `Authorization: Bearer …`, and
  posts the body to the URL with `Content-Type: application/json` and `Accept: application/json` (that value alone,
  or the airlock streams). Its read timeout is 600 seconds, above the airlock's eight-minute exchange budget. Both
  steps fail on a 4xx or 5xx answer, so a wrong secret stops the run at the sign-in.
- **The answer**: JSON Path reads `answer`, `dont_know`, `provenance.status` (as `provenance`) with its four
  counts `sourced`, `computed`, `unsourced` and `mismatch`, `revision`, `trace_id` and `$.evidence[*]` as a list
  of JSON (`id`, `source`, `name`, `rows`, a count: the answer never carries rows, and `data_source`). An answer
  without evidence (`dont_know: true`) has an empty list.

The secret and the password are saved in the Credentials Configuration nodes with KNIME's own encryption, which
hides them from a casual reader but is not a secret store; `docs/integrate.md` in the `control-plane` repository says how to
run it in production.

The same two calls as a shell script, to try the values first:

```bash
TOKEN=$(curl -s -X POST "$KEYCLOAK_REALM_URL/protocol/openid-connect/token" \
  -d grant_type=password -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET" \
  -d username="$USER_NAME" -d password="$USER_PASSWORD" -d 'scope=openid profile email' | jq -r .access_token)
curl -s -X POST "$AISOLATE/v1/spaces/$SPACE/airlocks/$AIRLOCK/chat" \
  -H "Authorization: Bearer $TOKEN" -H 'Accept: application/json' -H 'Content-Type: application/json' \
  -d "{\"message\": \"$QUESTION\"}"
```
