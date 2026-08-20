import { client } from './client';
import type {
	CreateCustomCredentialRequest,
	CreateCustomCredentialResponse,
	ListCustomCredentialsResponse,
} from './types';

export const customCredentialApi = {
	list: () =>
		client.get<ListCustomCredentialsResponse>('/custom-credential/'),

	create: (body: CreateCustomCredentialRequest) =>
		client.post<CreateCustomCredentialResponse>('/custom-credential/', body),

	delete: (credentialId: string) =>
		client.delete(`/custom-credential/${credentialId}`),
};
