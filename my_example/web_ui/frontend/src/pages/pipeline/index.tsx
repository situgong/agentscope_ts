import { Loader2, Plus, Trash2, Play, GitBranch, ArrowDown, ChevronRight, ChevronDown } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { agentApi, pipelineApi, type AgentView, type ChatModelConfig, type PipelineStepResult } from '@/api';
import type { PipelineStreamEvent } from '@/api/pipeline';
import type { PipelineStep, PipelineSubStep } from '@/api/types';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import { LlmSelect } from '@/components/select/LlmSelect';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from '@/i18n/useI18n';
import { formatApiErrorForAlert } from '@/lib/api-error';

export function PipelinePage() {
	const { t } = useTranslation();
	const [agents, setAgents] = useState<AgentView[]>([]);
	const [loadingAgents, setLoadingAgents] = useState(true);
	const [steps, setSteps] = useState<PipelineStep[]>([
		{ agent_id: '', instruction: '', sub_steps: [] },
		{ agent_id: '', instruction: '', sub_steps: [] },
	]);
	const [modelConfig, setModelConfig] = useState<ChatModelConfig | null>(null);
	const [running, setRunning] = useState(false);
	const [results, setResults] = useState<PipelineStepResult[]>([]);
	const [streamingStep, setStreamingStep] = useState<number | null>(null);
	const [error, setError] = useState('');
	const [credentialOpen, setCredentialOpen] = useState(false);
	const [credentialRefetchTrigger, setCredentialRefetchTrigger] = useState(0);
	const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

	useEffect(() => {
		agentApi
			.list()
			.then((res) => setAgents(res.agents))
			.catch((e) => setError(formatApiErrorForAlert(e)))
			.finally(() => setLoadingAgents(false));
	}, []);

	const addStep = () =>
		setSteps([...steps, { agent_id: '', instruction: '', sub_steps: [] }]);
	const removeStep = (idx: number) =>
		setSteps(steps.filter((_, i) => i !== idx));
	const updateStep = (idx: number, patch: Partial<PipelineStep>) =>
		setSteps(steps.map((s, i) => (i === idx ? { ...s, ...patch } : s)));

	const toggleStepExpanded = (idx: number) => {
		setExpandedSteps((prev) => {
			const next = new Set(prev);
			if (next.has(idx)) next.delete(idx);
			else next.add(idx);
			return next;
		});
	};

	const addSubStep = (stepIdx: number) =>
		updateStep(stepIdx, {
			sub_steps: [...(steps[stepIdx].sub_steps || []), { agent_id: '', instruction: '' }],
		});

	const removeSubStep = (stepIdx: number, subIdx: number) =>
		updateStep(stepIdx, {
			sub_steps: (steps[stepIdx].sub_steps || []).filter((_, i) => i !== subIdx),
		});

	const updateSubStep = (stepIdx: number, subIdx: number, patch: Partial<PipelineSubStep>) =>
		updateStep(stepIdx, {
			sub_steps: (steps[stepIdx].sub_steps || []).map((s, i) =>
				i === subIdx ? { ...s, ...patch } : s
			),
		});

	const handleRun = async () => {
		setError('');
		setResults([]);
		setStreamingStep(null);

		const valid = steps.filter((s) => s.agent_id && s.instruction.trim());
		if (valid.length < 1) {
			setError('Each step needs an agent and an instruction.');
			return;
		}
		if (!modelConfig) {
			setError('Select a model.');
			return;
		}

		setRunning(true);
		try {
			const stream = pipelineApi.runStream(
				{
					steps: valid.map((s) => ({
						agent_id: s.agent_id,
						instruction: s.instruction.trim(),
						sub_steps: (s.sub_steps || [])
							.filter((ss) => ss.agent_id && ss.instruction.trim())
							.map((ss) => ({
								agent_id: ss.agent_id,
								instruction: ss.instruction.trim(),
							})),
					})),
					chat_model_config: modelConfig,
				},
			);

			for await (const evt of stream) {
				handleStreamEvent(evt);
			}

			toast.success('Pipeline completed.');
		} catch (e) {
			setError(formatApiErrorForAlert(e));
		} finally {
			setRunning(false);
			setStreamingStep(null);
		}
	};

	const handleStreamEvent = (evt: PipelineStreamEvent) => {
		switch (evt.type) {
			case 'step_start':
				setStreamingStep(evt.step_index);
				setResults((prev) => {
					const next = [...prev];
					next[evt.step_index] = {
						step_index: evt.step_index,
						agent_id: evt.agent_id,
						agent_name: evt.agent_name,
						instruction: '',
						reply: { content: [] } as Record<string, unknown>,
						sub_results: [],
					};
					return next;
				});
				break;
			case 'step_done':
				setResults((prev) => {
					const next = [...prev];
					next[evt.step_index] = {
						step_index: evt.step_index,
						agent_id: evt.agent_id,
						agent_name: evt.agent_name,
						instruction: evt.instruction,
						reply: evt.reply,
						sub_results: next[evt.step_index]?.sub_results || [],
					};
					return next;
				});
				break;
			case 'sub_step_done':
				setResults((prev) => {
					const next = [...prev];
					const parent = next[evt.step_index];
					if (parent) {
						next[evt.step_index] = {
							...parent,
							sub_results: [
								...(parent.sub_results || []),
								{
									step_index: evt.sub_step_index,
									agent_id: evt.agent_id,
									agent_name: evt.agent_name,
									instruction: evt.instruction,
									reply: evt.reply,
								},
							],
						};
					}
					return next;
				});
				break;
			case 'step_final':
				setResults((prev) => {
					const next = [...prev];
					const parent = next[evt.step_index];
					if (parent) {
						next[evt.step_index] = {
							...parent,
							final_reply: evt.reply as Record<string, unknown>,
						};
					}
					return next;
				});
				break;
			case 'error':
				setError(evt.message);
				break;
			case 'pipeline_done':
				break;
		}
	};

	const extractText = (reply: Record<string, unknown>): string => {
		const content = reply.content as Array<{ type: string; text?: string }> | undefined;
		if (!content) return '(empty)';
		return content
			.filter((b) => b.type === 'text' && b.text)
			.map((b) => b.text!)
			.join('\n');
	};

	return (
		<div className="flex flex-col h-full overflow-hidden">
			<div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">
				<div>
					<h1 className="text-2xl font-bold flex items-center gap-2">
						<GitBranch className="size-6" />
						Pipeline
					</h1>
					<p className="text-muted-foreground mt-1">
						Chain agents with per-step instructions. Each agent receives your instruction
						combined with the previous agent's output.
					</p>
				</div>

				{error && (
					<Alert variant="destructive">
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				)}

				{/* Model selection */}
				<Card>
					<CardHeader>
						<CardTitle>{t('common.model')}</CardTitle>
						<CardDescription>Shared by all agents in the pipeline.</CardDescription>
					</CardHeader>
					<CardContent>
						<LlmSelect
						value={modelConfig}
						onChange={setModelConfig}
						onAddCredential={() => setCredentialOpen(true)}
						refetchTrigger={credentialRefetchTrigger}
					/>
					</CardContent>
				</Card>

				{/* Pipeline steps */}
				<Card>
					<CardHeader>
						<CardTitle>Steps</CardTitle>
						<CardDescription>
							Each step runs an agent with its own instruction. The agent sees the
							instruction plus the previous step's output.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{loadingAgents ? (
							<div className="flex items-center gap-2 text-muted-foreground">
								<Loader2 className="size-4 animate-spin" /> Loading agents…
							</div>
						) : agents.length === 0 ? (
							<p className="text-sm text-muted-foreground">
								No agents found. Create an agent first.
							</p>
						) : (
							<>
								{steps.map((step, idx) => (
									<div key={idx} className="space-y-2">
										{idx > 0 && (
											<div className="flex justify-center py-1">
												<ArrowDown className="size-4 text-muted-foreground" />
											</div>
										)}
										<div className="flex items-start gap-2">
											<span className="text-sm font-medium text-muted-foreground w-6 text-right pt-2">
												{idx + 1}.
											</span>
											<div className="flex-1 space-y-2">
												<Select
													value={step.agent_id}
													onValueChange={(v) => updateStep(idx, { agent_id: v })}
												>
													<SelectTrigger>
														<SelectValue placeholder="Select an agent" />
													</SelectTrigger>
													<SelectContent>
														{agents.map((a) => (
															<SelectItem key={a.id} value={a.id}>
																{a.data.name}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
												<Textarea
													placeholder={`Instruction for step ${idx + 1}…`}
													value={step.instruction}
													onChange={(e) =>
														updateStep(idx, { instruction: e.target.value })
													}
													rows={2}
												/>
												{/* Sub-steps toggle + add button */}
												<div className="flex items-center gap-2">
													<Button
														variant="ghost"
														size="sm"
														onClick={() => toggleStepExpanded(idx)}
														className="text-xs text-muted-foreground"
													>
														{expandedSteps.has(idx) ? (
															<ChevronDown className="size-3 mr-1" />
														) : (
															<ChevronRight className="size-3 mr-1" />
														)}
														{(step.sub_steps?.length || 0) > 0
															? `${step.sub_steps!.length} sub-step${step.sub_steps!.length !== 1 ? 's' : ''}`
															: 'Sub-steps'}
													</Button>
													<Button
														variant="ghost"
														size="sm"
														onClick={() => {
															if (!expandedSteps.has(idx)) toggleStepExpanded(idx);
															addSubStep(idx);
														}}
														className="text-xs text-muted-foreground"
													>
														<Plus className="size-3 mr-1" /> Add sub-step
													</Button>
												</div>
												{/* Sub-steps list */}
												{expandedSteps.has(idx) && (step.sub_steps || []).length > 0 && (
													<div className="ml-4 space-y-2 border-l-2 border-muted pl-4">
														{step.sub_steps!.map((sub, subIdx) => (
															<div key={subIdx} className="space-y-1.5">
																<div className="flex items-center gap-2">
																	<span className="text-xs text-muted-foreground w-8">
																		{idx + 1}.{subIdx + 1}
																	</span>
																	<Select
																		value={sub.agent_id}
																		onValueChange={(v) =>
																			updateSubStep(idx, subIdx, { agent_id: v })
																		}
																	>
																		<SelectTrigger className="h-8">
																			<SelectValue placeholder="Select an agent" />
																		</SelectTrigger>
																		<SelectContent>
																			{agents.map((a) => (
																				<SelectItem key={a.id} value={a.id}>
																					{a.data.name}
																				</SelectItem>
																			))}
																		</SelectContent>
																	</Select>
																	<Button
																		variant="ghost"
																		size="icon"
																		className="size-8"
																		onClick={() => removeSubStep(idx, subIdx)}
																	>
																		<Trash2 className="size-3" />
																	</Button>
																</div>
																<Textarea
																	placeholder={`Instruction for sub-step ${idx + 1}.${subIdx + 1}…`}
																	value={sub.instruction}
																	onChange={(e) =>
																		updateSubStep(idx, subIdx, {
																			instruction: e.target.value,
																		})
																	}
																	rows={2}
																	className="text-sm"
																/>
															</div>
														))}
													</div>
												)}
											</div>
											{steps.length > 1 && (
												<Button
													variant="ghost"
													size="icon"
													onClick={() => removeStep(idx)}
													className="mt-2"
												>
													<Trash2 className="size-4" />
												</Button>
											)}
										</div>
									</div>
								))}
								<Button variant="outline" size="sm" onClick={addStep}>
									<Plus className="size-4 mr-1" /> Add step
								</Button>
							</>
						)}
					</CardContent>
				</Card>

				{/* Run button */}
				<div className="flex justify-end">
					<Button onClick={handleRun} disabled={running || loadingAgents}>
						{running ? (
							<Loader2 className="size-4 animate-spin mr-2" />
						) : (
							<Play className="size-4 mr-2" />
						)}
						{running ? 'Running…' : 'Run Pipeline'}
					</Button>
				</div>

				{/* Results */}
				{(results.length > 0 || running) && (
					<Card>
						<CardHeader>
							<CardTitle>Results</CardTitle>
							<CardDescription>
								{running
									? streamingStep !== null
										? `Running step ${streamingStep + 1}…`
										: 'Starting…'
									: `${results.length} step${results.length !== 1 ? 's' : ''} completed.`}
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{results.map((r, i) => (
								<div key={i} className="border rounded-lg p-4 space-y-3">
									<div className="flex items-center justify-between">
										<span className="font-medium flex items-center gap-2">
											{running && streamingStep === r.step_index && (
												<Loader2 className="size-4 animate-spin" />
											)}
											Step {r.step_index + 1}: {r.agent_name}
										</span>
										<code className="text-xs text-muted-foreground">{r.agent_id}</code>
									</div>
									{r.instruction && (
										<div className="text-sm text-muted-foreground border-l-2 pl-3">
											<span className="font-medium">Instruction:</span> {r.instruction}
										</div>
									)}
									<div className="text-sm whitespace-pre-wrap bg-muted/50 rounded p-3">
										{extractText(r.reply)}
									</div>
									{/* Sub-step results */}
									{r.sub_results && r.sub_results.length > 0 && (
										<div className="ml-4 space-y-3 border-l-2 border-muted pl-4">
											{r.sub_results.map((sr, si) => (
												<div key={si} className="space-y-2">
													<div className="flex items-center justify-between">
														<span className="text-sm font-medium">
															Sub-step {r.step_index + 1}.{sr.step_index + 1}: {sr.agent_name}
														</span>
														<code className="text-xs text-muted-foreground">{sr.agent_id}</code>
													</div>
													<div className="text-xs text-muted-foreground border-l-2 pl-3">
														<span className="font-medium">Instruction:</span> {sr.instruction}
													</div>
													<div className="text-sm whitespace-pre-wrap bg-muted/50 rounded p-3">
														{extractText(sr.reply)}
													</div>
												</div>
											))}
										</div>
									)}
									{/* Final reply (after sub-step synthesis) */}
									{r.final_reply && (
										<div className="space-y-2 border-t pt-3">
											<span className="text-sm font-medium text-primary">
												Final Reply (consolidated)
											</span>
											<div className="text-sm whitespace-pre-wrap bg-primary/5 rounded p-3 border border-primary/20">
												{extractText(r.final_reply as Record<string, unknown>)}
											</div>
										</div>
									)}
								</div>
							))}
						</CardContent>
					</Card>
				)}
			</div>

			<CreateCredentialDialog
				open={credentialOpen}
				onOpenChange={setCredentialOpen}
				onCreated={() => setCredentialRefetchTrigger((n) => n + 1)}
			/>
		</div>
	);
}
