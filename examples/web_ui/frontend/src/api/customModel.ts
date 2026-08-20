import { client } from './client';
import type {
	AddCustomModelRequest,
	CustomModelListResponse,
	TestModelRequest,
	TestModelResponse,
} from './types';

export const customModelApi = {
	list: (credentialId: string) =>
		client.get<CustomModelListResponse>(`/custom-model/${credentialId}`),

	add: (credentialId: string, body: AddCustomModelRequest) =>
		client.post<CustomModelListResponse>(`/custom-model/${credentialId}`, body),

	remove: (credentialId: string, modelName: string) =>
		client.delete<CustomModelListResponse>(
			`/custom-model/${credentialId}/${encodeURIComponent(modelName)}`,
		),

	test: (body: TestModelRequest) =>
		client.post<TestModelResponse>('/custom-model/test', body),
};
