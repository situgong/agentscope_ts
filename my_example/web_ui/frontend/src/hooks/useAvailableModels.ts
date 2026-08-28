import { useState, useEffect, useCallback } from 'react';

import { credentialApi, customCredentialApi, customModelApi, modelApi } from '@/api';
import type { CredentialView, CustomModelCard, ModelCard } from '@/api';

export interface CredentialWithModels {
	credential: CredentialView;
	models: ModelCard[];
}

/**
 * Convert a :class:`CustomModelCard` (from the custom-model API) into a
 * shape that is structurally compatible with :class:`ModelCard` so the
 * downstream selectors can treat both uniformly.
 */
function toModelCard(card: CustomModelCard): ModelCard {
	return {
		type: 'chat_model',
		name: card.name,
		label: card.label,
		status: card.status as ModelCard['status'],
		deprecated_at: null,
		input_types: card.input_types,
		output_types: card.output_types,
		context_size: card.context_size ?? 0,
		output_size: card.output_size ?? 0,
		parameter_schema: {},
		parameters_overrides: {},
	};
}

/**
 * Fetches all credentials and their available models, grouped by provider type.
 * Provider type is read from `credential.data.type`.
 *
 * Custom credentials are detected via the custom-credential store and their
 * models are loaded from the custom-model API (YAML + user-added models)
 * instead of the built-in model list.
 *
 * Credentials without a `type` field or whose model fetch fails are silently skipped.
 */
export function useAvailableModels() {
	const [groups, setGroups] = useState<Record<string, CredentialWithModels[]>>({});
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<Error | null>(null);

	const refetch = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const [credRes, customCredRes] = await Promise.all([
				credentialApi.list(),
				customCredentialApi.list(),
			]);
			const { credentials } = credRes;
			const customIds = new Set(customCredRes.credentials.map((c) => c.credential_id));
			const result: Record<string, CredentialWithModels[]> = {};

			await Promise.all(
				credentials.map(async (credential) => {
					const type = credential.data.type as string | undefined;
					if (!type) return;
					if (!result[type]) result[type] = [];

					// Custom credentials: load YAML/user-added models only.
					if (customIds.has(credential.id)) {
						try {
							const { models } = await customModelApi.list(credential.id);
							result[type].push({
								credential,
								models: models.map(toModelCard),
							});
						} catch {
							result[type].push({ credential, models: [] });
						}
						return;
					}

					// Standard credentials: load built-in model list.
					try {
						const { models } = await modelApi.list(type);
						result[type].push({ credential, models });
					} catch {
						result[type].push({ credential, models: [] });
					}
				}),
			);

			setGroups(result);
		} catch (e) {
			setError(e as Error);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		refetch();
	}, [refetch]);

	return { groups, loading, error, refetch };
}
