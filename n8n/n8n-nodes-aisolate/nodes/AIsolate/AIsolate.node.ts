import {
	NodeConnectionTypes,
	NodeOperationError,
	type IExecuteFunctions,
	type IHttpRequestOptions,
	type ILoadOptionsFunctions,
	type INodeExecutionData,
	type INodePropertyOptions,
	type INodeType,
	type INodeTypeDescription,
} from 'n8n-workflow';

import { airlocks, ask, choices, type Request } from './client';

const CREDENTIALS = 'aisolateApi';

function authenticated(context: IExecuteFunctions | ILoadOptionsFunctions): Request {
	return (options) =>
		context.helpers.httpRequestWithAuthentication.call(context, CREDENTIALS, options as IHttpRequestOptions);
}

export class AIsolate implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'AIsolate',
		name: 'aisolate',
		icon: 'file:aisolate.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] === "list" ? "List airlocks" : "Ask airlock"}}',
		description: 'Ask an AIsolate airlock: governed answers with their provenance and evidence',
		defaults: { name: 'AIsolate' },
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		usableAsTool: true,
		credentials: [{ name: CREDENTIALS, required: true }],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Ask Airlock',
						value: 'ask',
						action: 'Ask an airlock',
						description: 'Ask the airlock a question; the answer comes with its provenance and evidence',
					},
					{
						name: 'List Airlocks',
						value: 'list',
						action: 'List the airlocks',
						description: 'The airlocks this client may ask',
					},
				],
				default: 'ask',
			},
			{
				displayName: 'Airlock Name or ID',
				name: 'endpoint',
				type: 'options',
				typeOptions: { loadOptionsMethod: 'getAirlocks' },
				default: '',
				required: true,
				displayOptions: { show: { operation: ['ask'] } },
				description:
					'The airlock to ask, from the ones this client may ask. Choose from the list, or specify an ID using an <a href="https://docs.n8n.io/code/expressions/">expression</a>.',
			},
			{
				displayName: 'Question',
				name: 'question',
				type: 'string',
				typeOptions: { rows: 3 },
				default: '',
				required: true,
				displayOptions: { show: { operation: ['ask'] } },
				description: "The question, e.g. What is {{ $json.employee }}'s notice period?",
			},
		],
	};

	methods = {
		loadOptions: {
			async getAirlocks(this: ILoadOptionsFunctions): Promise<INodePropertyOptions[]> {
				const { url } = await this.getCredentials(CREDENTIALS);
				return choices(await airlocks(authenticated(this), url as string));
			},
		},
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const { url } = await this.getCredentials(CREDENTIALS);
		const request = authenticated(this);
		const items = this.getInputData();
		const out: INodeExecutionData[] = [];
		for (let i = 0; i < items.length; i++) {
			try {
				if (this.getNodeParameter('operation', i) === 'list') {
					for (const choice of choices(await airlocks(request, url as string))) {
						out.push({ json: { airlock: choice.name, endpoint: choice.value, space: choice.description }, pairedItem: i });
					}
					continue;
				}
				const question = (this.getNodeParameter('question', i) as string).trim();
				if (!question) {
					throw new NodeOperationError(this.getNode(), 'The question is empty.', { itemIndex: i });
				}
				const endpoint = this.getNodeParameter('endpoint', i) as string;
				// the item's own fields (a ticket id, an employee) stay, the answer is added next to them
				out.push({ json: { ...items[i].json, ...(await ask(request, url as string, endpoint, question)) }, pairedItem: i });
			} catch (error) {
				if (this.continueOnFail()) {
					out.push({ json: { error: (error as Error).message }, pairedItem: i });
					continue;
				}
				throw error;
			}
		}
		return [out];
	}
}
