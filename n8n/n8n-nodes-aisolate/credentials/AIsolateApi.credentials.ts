import type {
	IAuthenticateGeneric,
	ICredentialDataDecryptedObject,
	ICredentialTestRequest,
	ICredentialType,
	IHttpRequestHelper,
	INodeProperties,
} from 'n8n-workflow';

import { signIn, tokenEndpoint, type Request } from '../nodes/AIsolate/client';

/** An application's sign-in to AIsolate: the release URL, a client id and its secret (client-credentials grant). */
export class AIsolateApi implements ICredentialType {
	name = 'aisolateApi';

	displayName = 'AIsolate API';

	icon = 'file:aisolate.svg' as const;

	documentationUrl = 'https://aisolate.ai/docs/integrate';

	properties: INodeProperties[] = [
		{
			displayName: 'AIsolate URL',
			name: 'url',
			type: 'string',
			default: 'http://aisolate.localhost',
			description: 'The release, e.g. https://aisolate.example.com. The identity provider is found from it.',
		},
		{
			displayName: 'Client ID',
			name: 'clientId',
			type: 'string',
			default: '',
			description: "The application's client id at the identity provider, listed in the airlock's access.clients",
		},
		{
			displayName: 'Client Secret',
			name: 'clientSecret',
			type: 'string',
			typeOptions: { password: true },
			default: '',
		},
		{
			displayName: 'Access Token',
			name: 'accessToken',
			type: 'hidden',
			typeOptions: { expirable: true },
			default: '',
		},
	];

	// n8n calls this when the token is missing or a request answered 401, then sends the new token
	async preAuthentication(this: IHttpRequestHelper, credentials: ICredentialDataDecryptedObject) {
		const request: Request = (options) => this.helpers.httpRequest(options);
		const url = credentials.url as string;
		const accessToken = await signIn(
			request,
			await tokenEndpoint(request, url),
			credentials.clientId as string,
			credentials.clientSecret as string,
		);
		return { accessToken };
	}

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: { headers: { Authorization: '=Bearer {{$credentials.accessToken}}' } },
	};

	test: ICredentialTestRequest = {
		request: { baseURL: '={{$credentials.url}}', url: '/v1/airlocks' },
	};
}
