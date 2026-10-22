import assert from 'node:assert/strict';
import { createServer, type IncomingMessage, type Server } from 'node:http';
import { after, before, test } from 'node:test';

import { airlocks, ask, choices, signIn, tokenEndpoint, type Request } from '../nodes/AIsolate/client';

const ENDPOINT = '/v1/spaces/hr-space/airlocks/hr-contracts/chat';
const ANSWER = {
	answer: "John Doe's annual gross salary is 82,000 EUR.",
	dont_know: false,
	provenance: { status: 'all_sourced', sourced: 1, computed: 0, unsourced: 0, mismatch: 0 },
	evidence: [{ id: 'ev-1', source: 'read_contract_terms', name: 'hr.contract_terms', rows: 1, data_source: 'hr' }],
	revision: '1267f9441ccd',
	trace_id: 'b91423c795d60915fc069233f7ad556c',
};
const seen: { method: string; url: string; headers: IncomingMessage['headers']; body: string }[] = [];
let server: Server;
let base: string;

// Keycloak and AIsolate on one port, recording each request
before(async () => {
	server = createServer((req, res) => {
		let body = '';
		req.on('data', (chunk) => (body += chunk));
		req.on('end', () => {
			seen.push({ method: req.method!, url: req.url!, headers: req.headers, body });
			const reply = (code: number, doc: unknown) => {
				res.writeHead(code, { 'Content-Type': 'application/json' });
				res.end(JSON.stringify(doc));
			};
			const route = `${req.method} ${req.url}`;
			if (route === 'GET /.well-known/oauth-protected-resource') return reply(200, { authorization_servers: [`${base}/realms/acme/`] });
			if (route === 'GET /realms/acme/.well-known/openid-configuration') return reply(200, { token_endpoint: `${base}/realms/acme/token` });
			if (route === 'POST /realms/acme/token') {
				const ok = req.headers.authorization === `Basic ${Buffer.from('n8n:s3cret').toString('base64')}`;
				return ok ? reply(200, { access_token: 'tok' }) : reply(401, { error: 'unauthorized_client' });
			}
			if (route === 'GET /v1/airlocks') {
				return reply(200, [{ id: 'hr-contracts', space: 'hr-space', name: 'HR contracts',
					description: 'Contracts', endpoint: ENDPOINT, tools: [] }]);
			}
			if (route === `POST ${ENDPOINT}`) return reply(200, ANSWER);
			reply(404, { title: 'Not Found' });
		});
	});
	await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
	const address = server.address();
	base = `http://127.0.0.1:${typeof address === 'object' && address ? address.port : 0}`;
});

after(() => server.close());

// fetch in the shape of n8n's helpers: parsed JSON back, an error on a 4xx/5xx
const request: Request = async (options) => {
	const response = await fetch(options.url, { method: options.method, headers: options.headers, body: options.body });
	const body = await response.json();
	if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(body)}`);
	return body;
};

test('givenProtectedResourceMetadata_whenTokenEndpoint_thenTheIssuersTokenUrl', async () => {
	// Arrange
	const url = base;

	// Act
	const tokenUrl = await tokenEndpoint(request, url);

	// Assert
	assert.equal(tokenUrl, `${base}/realms/acme/token`);
});

test('givenClient_whenSignIn_thenClientCredentialsGrantWithBasicAuth', async () => {
	// Arrange
	const tokenUrl = `${base}/realms/acme/token`;

	// Act
	const token = await signIn(request, tokenUrl, 'n8n', 's3cret');

	// Assert
	assert.equal(token, 'tok');
	const form = new URLSearchParams(seen.at(-1)!.body);
	assert.deepEqual(Object.fromEntries(form), { grant_type: 'client_credentials', scope: 'openid profile email' });
});

test('givenWrongSecret_whenSignIn_thenRejected', async () => {
	// Arrange
	const tokenUrl = `${base}/realms/acme/token`;

	// Act
	const attempt = signIn(request, tokenUrl, 'n8n', 'wrong');

	// Assert
	await assert.rejects(attempt, /401/);
});

test('givenAdmittedClient_whenAirlocks_thenOneChoicePerAirlock', async () => {
	// Arrange
	const url = base;

	// Act
	const found = choices(await airlocks(request, url));

	// Assert
	assert.deepEqual(found, [{ name: 'HR contracts', value: ENDPOINT, description: 'Space hr-space: Contracts' }]);
});

test('givenQuestion_whenAsk_thenJsonAcceptMessageBodyAndTheAnswerWithoutDontKnow', async () => {
	// Arrange
	const question = "What is John Doe's annual gross salary?";

	// Act
	const answer = await ask(request, base, ENDPOINT, question);

	// Assert
	const { headers, body } = seen.at(-1)!;
	assert.equal(headers.accept, 'application/json');
	assert.deepEqual(JSON.parse(body), { message: question });
	const { dont_know: _, ...expected } = ANSWER;
	assert.deepEqual(answer, { question, ...expected });
});
