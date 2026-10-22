// AIsolate's HTTP calls for the n8n node: discovery, sign-in, the airlocks, the chat. The caller passes the
// request function (n8n's helpers in the node, fetch in the tests), so this file needs nothing from n8n.

export interface HttpRequest {
	method: 'GET' | 'POST';
	url: string;
	headers?: Record<string, string>;
	body?: string;
	timeout?: number;
}

export type Request = (options: HttpRequest) => Promise<unknown>;

export interface Choice {
	name: string;
	value: string;
	description: string;
}

const ASK_TIMEOUT_MS = 600_000; // above the airlock's eight-minute exchange budget
const SCOPE = 'openid profile email';

// n8n's helpers return parsed JSON for a JSON response, a string otherwise
function parse(body: unknown): any {
	return typeof body === 'string' ? JSON.parse(body) : body;
}

/** The identity provider's token endpoint, found from AIsolate's RFC 9728 metadata. */
export async function tokenEndpoint(request: Request, aisolateUrl: string): Promise<string> {
	const resource = parse(
		await request({ method: 'GET', url: new URL('/.well-known/oauth-protected-resource', aisolateUrl).href }),
	);
	const issuer = String(resource.authorization_servers[0]).replace(/\/$/, '');
	const configuration = parse(await request({ method: 'GET', url: `${issuer}/.well-known/openid-configuration` }));
	return configuration.token_endpoint;
}

/** An access token for the client itself: the client-credentials grant, no user. */
export async function signIn(request: Request, tokenUrl: string, clientId: string, clientSecret: string): Promise<string> {
	const pair = `${encodeURIComponent(clientId)}:${encodeURIComponent(clientSecret)}`;
	const answer = parse(
		await request({
			method: 'POST',
			url: tokenUrl,
			headers: {
				Authorization: `Basic ${Buffer.from(pair).toString('base64')}`,
				'Content-Type': 'application/x-www-form-urlencoded',
			},
			body: new URLSearchParams({ grant_type: 'client_credentials', scope: SCOPE }).toString(),
		}),
	);
	return answer.access_token;
}

/** The airlocks that admit this client, each with its chat endpoint. `request` adds the token. */
export async function airlocks(request: Request, aisolateUrl: string): Promise<any[]> {
	return parse(
		await request({ method: 'GET', url: new URL('/v1/airlocks', aisolateUrl).href, headers: { Accept: 'application/json' } }),
	);
}

/** One choice per airlock, for the node's dropdown. */
export function choices(found: any[]): Choice[] {
	return found.map((airlock) => ({
		name: airlock.name,
		value: airlock.endpoint,
		description: `Space ${airlock.space}${airlock.description ? `: ${airlock.description}` : ''}`,
	}));
}

/** The airlock's answer to one question, without `dont_know` (the answer text says so). `request` adds the token. */
export async function ask(request: Request, aisolateUrl: string, endpoint: string, question: string): Promise<object> {
	const answer = parse(
		await request({
			method: 'POST',
			url: new URL(endpoint, aisolateUrl).href,
			// that value alone: anything listing */* or text/event-stream gets the stream
			headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
			body: JSON.stringify({ message: question }),
			timeout: ASK_TIMEOUT_MS,
		}),
	);
	const { dont_know: _, ...rest } = answer;
	return { question, ...rest };
}
