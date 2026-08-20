import { client } from './client';
import type { PipelineStepResult, RunPipelineRequest, RunPipelineResponse } from './types';

/** SSE event emitted by the pipeline streaming endpoint. */
export type PipelineStreamEvent =
	| { type: 'step_start'; step_index: number; agent_id: string; agent_name: string }
	| { type: 'step_done'; step_index: number; agent_id: string; agent_name: string; instruction: string; reply: Record<string, unknown> }
	| { type: 'sub_step_done'; step_index: number; sub_step_index: number; agent_id: string; agent_name: string; instruction: string; reply: Record<string, unknown> }
	| { type: 'step_final'; step_index: number; agent_id: string; agent_name: string; reply: Record<string, unknown> }
	| { type: 'pipeline_done'; total_steps: number }
	| { type: 'error'; message: string; step_index?: number; sub_step_index?: number };

export const pipelineApi = {
	run: (body: RunPipelineRequest) =>
		client.post<RunPipelineResponse>('/pipeline/run', body),

	/**
	 * Run a pipeline with streaming SSE output.
	 *
	 * Yields events as each step/sub-step completes, so the UI can
	 * display results progressively.
	 *
	 * @param body - The pipeline request.
	 * @param signal - Optional abort signal to cancel the stream.
	 */
	runStream: async function* (
		body: RunPipelineRequest,
		signal?: AbortSignal,
	): AsyncGenerator<PipelineStreamEvent> {
		const res = await client.stream('/pipeline/run/stream', {
			method: 'POST',
			body,
			signal,
		});

		const reader = res.body!.getReader();
		const decoder = new TextDecoder();
		let buffer = '';

		try {
			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() ?? '';

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						const json = line.slice(6).trim();
						if (json) yield JSON.parse(json) as PipelineStreamEvent;
					}
				}
			}
		} finally {
			reader.releaseLock();
		}
	},
};
