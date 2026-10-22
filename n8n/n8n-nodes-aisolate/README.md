# n8n-nodes-aisolate

The AIsolate node for n8n: ask an AIsolate airlock and get its answer with the provenance and evidence it rests on.

- **AIsolate API** credential: the release URL, a client id and its secret. The node signs in as that application
  (client-credentials grant), finding the identity provider from the release's `/.well-known/oauth-protected-resource`.
- **AIsolate** node: *Ask Airlock* (pick the airlock from the ones the client may ask, write the question,
  with expressions) and *List Airlocks*. Usable as a tool by the AI Agent (`N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`).

The airlock admits the client when its id is in the airlock's `access.clients`. Build with `npm install && npm run
build`; `npm test` runs the client's tests against a stand-in. See `../README.md` for installing it and the example
workflows. Apache-2.0.
