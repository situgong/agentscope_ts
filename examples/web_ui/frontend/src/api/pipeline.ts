import { client } from './client';
import type { RunPipelineRequest, RunPipelineResponse } from './types';

export const pipelineApi = {
	run: (body: RunPipelineRequest) =>
		client.post<RunPipelineResponse>('/pipeline/run', body),
};
