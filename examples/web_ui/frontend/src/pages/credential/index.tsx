import { Eye, EyeOff, Plus, Trash2, Pen, Zap, CheckCircle2, XCircle, Loader2, Info, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';

import {
	credentialApi,
	customModelApi,
	embeddingModelApi,
	modelApi,
	ttsModelApi,
} from '@/api';
import type {
	CredentialView,
	CredentialSchema,
	CustomModelCard,
	EmbeddingModelCard,
	ModelCard,
	TTSModelCard,
} from '@/api';
import { CreateCredentialDialog } from '@/components/dialog/CreateCredentialDialog';
import { DeleteDialog } from '@/components/dialog/DeleteDialog';
import { EditCredentialDialog } from '@/components/dialog/EditCredentialDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from '@/components/ui/dialog';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
	Sidebar,
	SidebarContent,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCredentials } from '@/hooks/useCredentials';
import { useTranslation } from '@/i18n/useI18n';
import { cn } from '@/lib/utils';
import { formatNumber } from '@/utils/common.ts';

/** Which model list the detail panel is showing. */
type ModelTab = 'llm' | 'tts' | 'embedding' | 'custom';

/** A row in the model table — one of the three card shapes. */
type ModelRow = ModelCard | TTSModelCard | EmbeddingModelCard;

// ─── Masked value ─────────────────────────────────────────────────────────────

function MaskedValue({ value }: { value: string }) {
	const [visible, setVisible] = useState(false);
	const masked = value.length > 8 ? value.slice(0, 4) + '••••••••' + value.slice(-4) : '••••••••';
	return (
		<span className="flex items-center gap-x-1.5 font-mono text-sm">
			{visible ? value : masked}
			<Button
				size={'icon-sm'}
				className="text-text-tertiary hover:text-foreground"
				variant={'ghost'}
				onClick={() => setVisible((v) => !v)}
			>
				{visible ? <EyeOff /> : <Eye />}
			</Button>
		</span>
	);
}

// ─── Model table ──────────────────────────────────────────────────────────────

/** MIME main-types that stand on their own in the ACCEPTS / OUTPUTS cells. */
const MODALITIES = new Set(['text', 'image', 'video', 'audio']);

/** Marks a model as reasoning-capable; not a real input modality. */
const THINKING_TYPE = 'application/x-thinking';

/** Dense-vector output of an embedding model. */
const EMBEDDING_TYPE = 'application/x-embedding';

/**
 * Collapse a model's MIME list into short modality labels. Anything
 * outside the four media types (PDFs, office documents, …) folds into a
 * single `file` entry so the cell stays one line.
 *
 * @param types - MIME types straight off the model card.
 * @returns De-duplicated labels in encounter order.
 */
function modalities(types: string[]): string[] {
	const out = new Set<string>();
	for (const type of types) {
		if (type === THINKING_TYPE) continue;
		if (type === EMBEDDING_TYPE) {
			out.add('vector');
			continue;
		}
		const main = type.split('/')[0];
		out.add(MODALITIES.has(main) ? main : 'file');
	}
	return [...out];
}

/** Inline pill sitting next to a model name (reasoning, realtime, status). */
function ModelTag({ children }: { children: React.ReactNode }) {
	return (
		<span className="rounded bg-surface-muted px-1.75 py-0.5 font-mono text-[9px] tracking-[0.06em] uppercase text-text-secondary">
			{children}
		</span>
	);
}

function HeadCell({ children }: { children: React.ReactNode }) {
	return (
		<TableHead className="h-auto bg-muted px-4 py-2.25 font-mono text-[9.5px] font-normal tracking-widest uppercase text-text-tertiary">
			{children}
		</TableHead>
	);
}

/** Numeric / modality cell — mono, one step darker than the head row. */
function DataCell({ children, size }: { children: React.ReactNode; size: '11' | '11.5' }) {
	return (
		<TableCell
			className={cn(
				'px-4 py-2.5 font-mono text-text-secondary',
				size === '11' ? 'text-[11px]' : 'text-[11.5px]',
			)}
		>
			{children}
		</TableCell>
	);
}

interface ModelTableProps {
	/** Rows to render; the shape must match `variant`. */
	models: ModelRow[];
	/** Drives which numeric columns sit between MODEL and ACCEPTS. */
	variant: ModelTab;
	/** Credential ID for connection tests. */
	credentialId: string;
}

// ─── Test connection button ───────────────────────────────────────────────────

type TestState = 'idle' | 'testing' | 'success' | 'failed';

function TestButton({ credentialId, modelName }: { credentialId: string; modelName: string }) {
	const { t } = useTranslation();
	const [state, setState] = useState<TestState>('idle');

	const handleTest = async () => {
		setState('testing');
		try {
			const res = await customModelApi.test({
				credential_id: credentialId,
				model_name: modelName,
			});
			setState(res.success ? 'success' : 'failed');
		} catch {
			setState('failed');
		}
		// Reset after 5 seconds so the user can re-test.
		setTimeout(() => setState('idle'), 5000);
	};

	return (
		<Button
			size="sm"
			variant="ghost"
			className="h-7 gap-x-1.5 px-2 text-[11px] font-normal text-text-tertiary"
			disabled={state === 'testing'}
			onClick={handleTest}
		>
			{state === 'testing' && <Loader2 className="size-3 animate-spin" />}
			{state === 'success' && <CheckCircle2 className="size-3 text-green-500" />}
			{state === 'failed' && <XCircle className="size-3 text-destructive" />}
			{state === 'idle' && <Zap className="size-3" />}
			<span>
				{state === 'testing'
					? t('credential.testing')
					: state === 'success'
						? t('credential.testSuccess')
						: state === 'failed'
							? t('credential.testFailed')
							: t('credential.testConnection')}
			</span>
		</Button>
	);
}

// ─── Model info dialog ────────────────────────────────────────────────────────

/** Unified shape for the info dialog — works for built-in and custom models. */
interface ModelInfoData {
	name: string;
	label: string;
	status: string;
	input_types: string[];
	output_types: string[];
	context_size: number | null;
	output_size: number | null;
	parameter_overrides?: Record<string, Record<string, unknown>>;
	deprecated_at?: string | null;
}

function ModelInfoDialog({
	open,
	onOpenChange,
	models,
	index,
	onIndexChange,
}: {
	open: boolean;
	onOpenChange: (v: boolean) => void;
	models: ModelInfoData[];
	index: number;
	onIndexChange: (i: number) => void;
}) {
	const { t } = useTranslation();
	const model = models[index];

	const goPrev = useCallback(
		() => onIndexChange((index - 1 + models.length) % models.length),
		[index, models.length, onIndexChange],
	);
	const goNext = useCallback(
		() => onIndexChange((index + 1) % models.length),
		[index, models.length, onIndexChange],
	);

	const handleKeyDown = useCallback(
		(e: KeyboardEvent) => {
			if (e.key === 'ArrowLeft') {
				e.preventDefault();
				goPrev();
			} else if (e.key === 'ArrowRight') {
				e.preventDefault();
				goNext();
			}
		},
		[goPrev, goNext],
	);

	useEffect(() => {
		if (!open) return;
		window.addEventListener('keydown', handleKeyDown);
		return () => window.removeEventListener('keydown', handleKeyDown);
	}, [open, handleKeyDown]);

	if (!model) return null;

	const overrides = model.parameter_overrides
		? Object.entries(model.parameter_overrides)
		: [];
	const hasMultiple = models.length > 1;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-[480px]">
				<DialogHeader>
					<div className="flex items-center justify-between gap-x-2">
						<DialogTitle>{t('credential.modelInfo.title')}</DialogTitle>
						{hasMultiple && (
							<div className="flex items-center gap-x-1">
								<Button
									size="icon-sm"
									variant="ghost"
									className="text-text-tertiary hover:text-foreground"
									onClick={goPrev}
									disabled={models.length <= 1}
									tooltip={t('credential.modelInfo.previous')}
								>
									<ChevronLeft className="size-4" />
								</Button>
								<span className="font-mono text-[11px] text-text-data tabular-nums">
									{index + 1} / {models.length}
								</span>
								<Button
									size="icon-sm"
									variant="ghost"
									className="text-text-tertiary hover:text-foreground"
									onClick={goNext}
									disabled={models.length <= 1}
									tooltip={t('credential.modelInfo.next')}
								>
									<ChevronRight className="size-4" />
								</Button>
							</div>
						)}
					</div>
					<DialogDescription>{model.label || model.name}</DialogDescription>
				</DialogHeader>
				<div className="flex flex-col gap-y-3 py-2">
					<div className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2.5 font-mono">
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.name')}
						</span>
						<span className="text-sm text-foreground break-all">{model.name}</span>
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.label')}
						</span>
						<span className="text-sm text-foreground break-all">{model.label}</span>
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.status')}
						</span>
						<span className="text-sm text-foreground">{model.status}</span>
						{model.deprecated_at && (
							<>
								<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
									{t('credential.modelInfo.deprecatedAt')}
								</span>
								<span className="text-sm text-foreground">{model.deprecated_at}</span>
							</>
						)}
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.inputTypes')}
						</span>
						<span className="text-sm text-foreground break-all">
							{model.input_types.join(', ') || '—'}
						</span>
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.outputTypes')}
						</span>
						<span className="text-sm text-foreground break-all">
							{model.output_types.join(', ') || '—'}
						</span>
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.contextSize')}
						</span>
						<span className="text-sm text-foreground">
							{model.context_size
								? `${formatNumber(model.context_size)} ${t('credential.modelInfo.tokens')}`
								: '—'}
						</span>
						<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
							{t('credential.modelInfo.outputSize')}
						</span>
						<span className="text-sm text-foreground">
							{model.output_size
								? `${formatNumber(model.output_size)} ${t('credential.modelInfo.tokens')}`
								: '—'}
						</span>
					</div>
					{overrides.length > 0 && (
						<div className="mt-1">
							<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase font-mono">
								{t('credential.modelInfo.parameterOverrides')}
							</span>
							<div className="mt-1.5 space-y-1.5">
								{overrides.map(([key, vals]) => (
									<div
										key={key}
										className="rounded-md border border-border bg-surface-muted px-3 py-1.5 font-mono text-[11px]"
									>
										<span className="text-text-secondary">{key}:</span>{' '}
										<span className="text-text-tertiary">
											{Object.entries(vals)
												.map(([k, v]) => `${k}=${String(v)}`)
												.join(', ')}
										</span>
									</div>
								))}
							</div>
						</div>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}

// ─── Add custom model dialog ──────────────────────────────────────────────────

function AddCustomModelDialog({
	open,
	onOpenChange,
	onAdd,
}: {
	open: boolean;
	onOpenChange: (v: boolean) => void;
	onAdd: (model: {
		name: string;
		label?: string;
		input_types?: string[];
		output_types?: string[];
		context_size?: number | null;
		output_size?: number | null;
	}) => void;
}) {
	const { t } = useTranslation();
	const [name, setName] = useState('');
	const [label, setLabel] = useState('');
	const [inputTypes, setInputTypes] = useState('');
	const [outputTypes, setOutputTypes] = useState('');
	const [contextSize, setContextSize] = useState('');
	const [outputSize, setOutputSize] = useState('');

	const reset = () => {
		setName('');
		setLabel('');
		setInputTypes('');
		setOutputTypes('');
		setContextSize('');
		setOutputSize('');
	};

	const handleSubmit = () => {
		const trimmedName = name.trim();
		if (!trimmedName) return;
		onAdd({
			name: trimmedName,
			label: label.trim() || undefined,
			input_types: inputTypes.trim()
				? inputTypes.split(',').map((s) => s.trim()).filter(Boolean)
				: undefined,
			output_types: outputTypes.trim()
				? outputTypes.split(',').map((s) => s.trim()).filter(Boolean)
				: undefined,
			context_size: contextSize.trim() ? Number(contextSize) || null : null,
			output_size: outputSize.trim() ? Number(outputSize) || null : null,
		});
		reset();
		onOpenChange(false);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-[460px]">
				<DialogHeader>
					<DialogTitle>{t('credential.addCustomModelDialog.title')}</DialogTitle>
					<DialogDescription>
						{t('credential.addCustomModelDialog.description')}
					</DialogDescription>
				</DialogHeader>
				<div className="flex flex-col gap-y-3 py-2">
					<div className="flex flex-col gap-y-1.5">
						<Label className="text-[11px] text-text-tertiary">
							{t('credential.customModelName')}
						</Label>
						<Input
							value={name}
							onChange={(e) => setName(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === 'Enter') handleSubmit();
							}}
							placeholder={t('credential.customModelNamePlaceholder')}
							className="h-8 text-sm"
							autoFocus
						/>
					</div>
					<div className="flex flex-col gap-y-1.5">
						<Label className="text-[11px] text-text-tertiary">
							{t('credential.addCustomModelDialog.labelField')}
						</Label>
						<Input
							value={label}
							onChange={(e) => setLabel(e.target.value)}
							placeholder={t('credential.addCustomModelDialog.labelPlaceholder')}
							className="h-8 text-sm"
						/>
					</div>
					<div className="flex flex-col gap-y-1.5">
						<Label className="text-[11px] text-text-tertiary">
							{t('credential.addCustomModelDialog.inputTypes')}
						</Label>
						<Input
							value={inputTypes}
							onChange={(e) => setInputTypes(e.target.value)}
							placeholder={t('credential.addCustomModelDialog.inputTypesPlaceholder')}
							className="h-8 text-sm"
						/>
					</div>
					<div className="flex flex-col gap-y-1.5">
						<Label className="text-[11px] text-text-tertiary">
							{t('credential.addCustomModelDialog.outputTypes')}
						</Label>
						<Input
							value={outputTypes}
							onChange={(e) => setOutputTypes(e.target.value)}
							placeholder={t('credential.addCustomModelDialog.outputTypesPlaceholder')}
							className="h-8 text-sm"
						/>
					</div>
					<div className="grid grid-cols-2 gap-x-3">
						<div className="flex flex-col gap-y-1.5">
							<Label className="text-[11px] text-text-tertiary">
								{t('credential.addCustomModelDialog.contextSize')}
							</Label>
							<Input
								value={contextSize}
								onChange={(e) => setContextSize(e.target.value)}
								placeholder={t('credential.addCustomModelDialog.contextSizePlaceholder')}
								className="h-8 text-sm"
								type="number"
							/>
						</div>
						<div className="flex flex-col gap-y-1.5">
							<Label className="text-[11px] text-text-tertiary">
								{t('credential.addCustomModelDialog.outputSize')}
							</Label>
							<Input
								value={outputSize}
								onChange={(e) => setOutputSize(e.target.value)}
								placeholder={t('credential.addCustomModelDialog.outputSizePlaceholder')}
								className="h-8 text-sm"
								type="number"
							/>
						</div>
					</div>
				</div>
				<DialogFooter>
					<Button variant="ghost" onClick={() => onOpenChange(false)}>
						{t('credential.addCustomModelDialog.cancel')}
					</Button>
					<Button disabled={!name.trim()} onClick={handleSubmit}>
						<Plus className="size-3.5" />
						{t('credential.addCustomModelDialog.submit')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}

// ─── Custom model table ───────────────────────────────────────────────────────

function CustomModelTable({
	models,
	credentialId,
	onAdd,
	onRemove,
}: {
	models: CustomModelCard[];
	credentialId: string;
	onAdd: (model: {
		name: string;
		label?: string;
		input_types?: string[];
		output_types?: string[];
		context_size?: number | null;
		output_size?: number | null;
	}) => void;
	onRemove: (name: string) => void;
}) {
	const { t } = useTranslation();
	const [addDialogOpen, setAddDialogOpen] = useState(false);
	const [infoIndex, setInfoIndex] = useState<number>(-1);

	return (
		<div className="space-y-3">
			{/* Add model button */}
			<div className="flex items-center gap-x-2">
				<Button
					size="sm"
					className="h-8 gap-x-1.5"
					onClick={() => setAddDialogOpen(true)}
				>
					<Plus className="size-3.5" />
					{t('credential.addCustomModel')}
				</Button>
			</div>

			{/* Add model dialog */}
			<AddCustomModelDialog
				open={addDialogOpen}
				onOpenChange={setAddDialogOpen}
				onAdd={onAdd}
			/>

			{/* Model info dialog */}
			<ModelInfoDialog
				open={infoIndex >= 0}
				onOpenChange={(v) => !v && setInfoIndex(-1)}
				models={models}
				index={Math.max(0, infoIndex)}
				onIndexChange={setInfoIndex}
			/>

			{/* Model list */}
			{models.length === 0 ? (
				<Empty className="border-none py-6">
					<EmptyHeader>
						<EmptyTitle>{t('credential.noCustomModels')}</EmptyTitle>
						<EmptyDescription>
							{t('credential.noCustomModelsDescription')}
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : (
				<div className="overflow-x-auto rounded-[16px] border border-border">
					<Table className="min-w-[500px]">
						<TableHeader>
							<TableRow className="border-border hover:bg-transparent">
								<HeadCell>{t('credential.table.model')}</HeadCell>
								<HeadCell>{t('credential.table.context')}</HeadCell>
								<HeadCell>{t('credential.table.maxOutput')}</HeadCell>
								<HeadCell>{t('credential.table.accepts')}</HeadCell>
								<HeadCell>{t('credential.table.outputs')}</HeadCell>
								<HeadCell>{t('credential.testConnection')}</HeadCell>
								<HeadCell className="w-20" />
							</TableRow>
						</TableHeader>
						<TableBody>
							{models.map((model, idx) => (
								<TableRow
									key={model.name}
									className="border-border hover:bg-row-hover"
								>
									<TableCell className="px-4 py-2.5 text-[12.5px] text-foreground">
										<span className="flex items-center gap-x-2">
											<span
												className="min-w-0 flex-1 truncate"
												title={model.name}
											>
												{model.label || model.name}
											</span>
											{model.status !== 'active' && (
												<ModelTag>{model.status}</ModelTag>
											)}
										</span>
									</TableCell>
									<DataCell size="11.5">
										{model.context_size ? formatNumber(model.context_size) : '—'}
									</DataCell>
									<DataCell size="11.5">
										{model.output_size ? formatNumber(model.output_size) : '—'}
									</DataCell>
									<DataCell size="11">
										{modalities(model.input_types).join(' · ') || '—'}
									</DataCell>
									<DataCell size="11">
										{modalities(model.output_types).join(' · ') || '—'}
									</DataCell>
									<TableCell className="px-4 py-2.5">
										<TestButton
											credentialId={credentialId}
											modelName={model.name}
										/>
									</TableCell>
									<TableCell className="px-2 py-2.5">
										<div className="flex items-center gap-x-0.5">
											<Button
												size="icon-sm"
												variant="ghost"
												className="text-text-tertiary hover:text-foreground"
												onClick={() => setInfoIndex(idx)}
											>
												<Info className="size-3.5" />
											</Button>
											<Button
												size="icon-sm"
												variant="ghost"
												className="text-text-tertiary hover:bg-destructive/8 hover:text-destructive"
												onClick={() => onRemove(model.name)}
											>
												<Trash2 className="size-3.5" />
											</Button>
										</div>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			)}
		</div>
	);
}

/**
 * The model list as a table: one row per model, sizes and modalities in
 * their own columns rather than repeated label/value pairs per card.
 *
 * @param models - Rows to render.
 * @param variant - Which column set applies.
 * @returns The bordered table plus its legend.
 */
function ModelTable({ models, variant, credentialId }: ModelTableProps) {
	const { t } = useTranslation();
	const isChat = variant === 'llm';
	const isEmbedding = variant === 'embedding';
	const [infoIndex, setInfoIndex] = useState<number>(-1);

	return (
		<div>
			<ModelInfoDialog
				open={infoIndex >= 0}
				onOpenChange={(v) => !v && setInfoIndex(-1)}
				models={models as ModelInfoData[]}
				index={Math.max(0, infoIndex)}
				onIndexChange={setInfoIndex}
			/>
			<div className="overflow-x-auto rounded-[16px] border border-border">
				<Table className="min-w-[500px]">
					<TableHeader>
						<TableRow className="border-border hover:bg-transparent">
							<HeadCell>{t('credential.table.model')}</HeadCell>
							{(isChat || isEmbedding) && (
								<HeadCell>{t('credential.table.context')}</HeadCell>
							)}
							{isChat && <HeadCell>{t('credential.table.maxOutput')}</HeadCell>}
							{isEmbedding && <HeadCell>{t('credential.table.dimensions')}</HeadCell>}
							<HeadCell>{t('credential.table.accepts')}</HeadCell>
							<HeadCell>{t('credential.table.outputs')}</HeadCell>
							{isChat && <HeadCell>{t('credential.testConnection')}</HeadCell>}
							<HeadCell className="w-10" />
						</TableRow>
					</TableHeader>
					<TableBody>
						{models.map((model, idx) => {
							const chat = isChat ? (model as ModelCard) : null;
							const embed = isEmbedding ? (model as EmbeddingModelCard) : null;
							const tts = variant === 'tts' ? (model as TTSModelCard) : null;
							const context = chat?.context_size ?? embed?.context_size;
							return (
								<TableRow
									key={model.name}
									className="border-border hover:bg-row-hover"
								>
									<TableCell className="px-4 py-2.5 text-[12.5px] text-foreground">
										<span className="flex items-center gap-x-2">
											<span
												className="min-w-0 flex-1 truncate"
												title={model.name}
											>
												{model.label || model.name}
											</span>
											{model.input_types.includes(THINKING_TYPE) && (
												<ModelTag>{t('credential.reasoning')}</ModelTag>
											)}
											{tts?.realtime && (
												<ModelTag>{t('credential.realtime')}</ModelTag>
											)}
											{model.status !== 'active' && (
												<ModelTag>{model.status}</ModelTag>
											)}
										</span>
									</TableCell>
									{(isChat || isEmbedding) && (
										<DataCell size="11.5">
											{context ? formatNumber(context) : '—'}
										</DataCell>
									)}
									{isChat && (
										<DataCell size="11.5">
											{chat?.output_size
												? formatNumber(chat.output_size)
												: '—'}
										</DataCell>
									)}
									{isEmbedding && (
										<DataCell size="11.5">{embed?.dimensions ?? '—'}</DataCell>
									)}
									<DataCell size="11">
										{modalities(model.input_types).join(' · ') || '—'}
									</DataCell>
									<DataCell size="11">
										{modalities(model.output_types).join(' · ') || '—'}
									</DataCell>
									{isChat && (
										<TableCell className="px-4 py-2.5">
											<TestButton
												credentialId={credentialId}
												modelName={model.name}
											/>
										</TableCell>
									)}
									<TableCell className="px-2 py-2.5">
										<Button
											size="icon-sm"
											variant="ghost"
											className="text-text-tertiary hover:text-foreground"
											onClick={() => setInfoIndex(idx)}
										>
											<Info className="size-3.5" />
										</Button>
									</TableCell>
								</TableRow>
							);
						})}
					</TableBody>
				</Table>
			</div>
			<p className="mt-2.5 text-[11px] text-muted-foreground">
				{t('credential.table.legend')}
			</p>
		</div>
	);
}

// ─── Detail panel ─────────────────────────────────────────────────────────────

interface DetailPanelProps {
	credential: CredentialView;
	schema: CredentialSchema | null;
	onEdit: () => void;
	onDelete: () => void;
}

function DetailPanel({ credential, schema, onEdit, onDelete }: DetailPanelProps) {
	const { t } = useTranslation();
	const [models, setModels] = useState<ModelCard[]>([]);
	const [ttsModels, setTtsModels] = useState<TTSModelCard[]>([]);
	const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModelCard[]>([]);
	const [customModels, setCustomModels] = useState<CustomModelCard[]>([]);
	const [modelsLoading, setModelsLoading] = useState(false);
	const [tab, setTab] = useState<ModelTab>('llm');

	const type = credential.data.type as string | undefined;
	const shown =
		tab === 'llm'
			? models
			: tab === 'tts'
				? ttsModels
				: tab === 'embedding'
					? embeddingModels
					: [];
	const total = models.length + ttsModels.length + embeddingModels.length + customModels.length;

	// A credential switch can land on a provider with no TTS models at
	// all, which would leave the tab pointing at an empty list.
	useEffect(() => setTab('llm'), [credential.id]);

	useEffect(() => {
		if (!type) return;
		setModelsLoading(true);
		Promise.all([
			modelApi
				.list(type)
				.then((res) => res.models)
				.catch(() => [] as ModelCard[]),
			ttsModelApi
				.list(type)
				.then((res) => res.models)
				.catch(() => [] as TTSModelCard[]),
			embeddingModelApi
				.list(type)
				.then((res) => res.models)
				.catch(() => [] as EmbeddingModelCard[]),
			customModelApi
				.list(credential.id)
				.then((res) => res.models)
				.catch(() => [] as CustomModelCard[]),
		])
			.then(([chatModels, tts, embeddings, custom]) => {
				setModels(chatModels);
				setTtsModels(tts);
				setEmbeddingModels(embeddings);
				setCustomModels(custom);
			})
			.finally(() => setModelsLoading(false));
	}, [credential.id, type]);

	const handleAddCustomModel = useCallback(
		async (model: {
			name: string;
			label?: string;
			input_types?: string[];
			output_types?: string[];
			context_size?: number | null;
			output_size?: number | null;
		}) => {
			try {
				const res = await customModelApi.add(credential.id, model);
				setCustomModels(res.models);
			} catch {
				// Error toast is handled by the API client.
			}
		},
		[credential.id],
	);

	const handleRemoveCustomModel = useCallback(
		async (name: string) => {
			try {
				const res = await customModelApi.remove(credential.id, name);
				setCustomModels(res.models);
			} catch {
				// Error toast is handled by the API client.
			}
		},
		[credential.id],
	);

	// Fields to display: use schema properties order, skip id/type/const fields
	const displayFields = schema
		? Object.entries(schema.properties).filter(
				([key, prop]) => key !== 'id' && key !== 'type' && prop.const === undefined,
			)
		: Object.entries(credential.data)
				.filter(([key]) => key !== 'id' && key !== 'type')
				.map(
					([key]) =>
						[key, { title: key, writeOnly: false }] as [
							string,
							{ title: string; writeOnly: boolean },
						],
				);

	const name = (credential.data.name as string | undefined) ?? credential.id;

	return (
		<div className="flex h-full flex-col">
			{/* Header */}
			<div className="shrink-0 flex items-start justify-between gap-x-4 p-[18px_18px_16px]">
				<div className="flex flex-col gap-y-1">
					<span className="text-foreground text-lg font-medium tracking-[-0.015em]">
						{name}
					</span>
					<span className="font-mono text-text-data text-sm">{type}</span>
					{!credential.editable && (
						<Badge variant="secondary" title={t('common.readOnlyTooltip')}>
							{t('common.readOnly')}
						</Badge>
					)}
				</div>
				<div className="flex items-center gap-x-2 shrink-0">
					<Button
						size="icon-sm"
						variant="ghost"
						className="text-text-tertiary hover:text-foreground"
						onClick={onEdit}
						disabled={!credential.editable}
						tooltip={credential.editable ? undefined : t('common.readOnlyTooltip')}
					>
						<Pen />
					</Button>
					<Button
						size="icon-sm"
						variant="ghost"
						className="text-text-tertiary hover:bg-destructive/8 hover:text-destructive"
						onClick={onDelete}
						disabled={!credential.editable}
						tooltip={credential.editable ? undefined : t('common.readOnlyTooltip')}
					>
						<Trash2 />
					</Button>
				</div>
			</div>

			<Separator className="shrink-0" />

			<div className="min-h-0 flex-1 overflow-y-auto">
				{/* Fields */}
				<div className="flex flex-col gap-y-3 p-[20px_18px_0]">
					{displayFields.map(([key, prop]) => {
						const schemaProp = prop as {
							title?: string;
							writeOnly?: boolean;
							format?: string;
						};
						const label = schemaProp.title ?? key.replace(/_/g, ' ');
						const isSecret = schemaProp.writeOnly || schemaProp.format === 'password';
						const val = credential.data[key];
						if (val === undefined || val === null) return null;
						const strVal = String(val);
						return (
							<div
								key={key}
								className="grid grid-cols-[104px_1fr] gap-x-4.5 gap-y-3 items-baseline font-mono"
							>
								<span className="text-[10px] text-text-tertiary tracking-[0.12em] uppercase">
									{label}
								</span>
								{isSecret ? (
									<MaskedValue value={strVal} />
								) : (
									<span className="text-sm text-foreground break-all">
										{strVal}
									</span>
								)}
							</div>
						);
					})}
				</div>

				{/* Available Models */}
				<Tabs
					value={tab}
					onValueChange={(v) => setTab(v as ModelTab)}
					className="gap-0 px-[18px] pb-6"
				>
					<div className="mt-[30px] mb-3 flex items-center justify-between">
						<span className="flex items-center gap-x-2 text-[13.5px] font-medium text-foreground">
							{t('credential.availableModels')}
							<span className="font-mono text-[11px] text-text-data">{total}</span>
						</span>
						<TabsList className="bg-surface-muted">
							<TabsTrigger
								value="llm"
								className="px-2.5 text-[11.5px] text-muted-foreground group-data-[variant=default]/tabs-list:data-active:shadow-tab!"
							>
								{t('common.llm')}
								<span className="font-mono text-[10px] text-text-data">
									{models.length}
								</span>
							</TabsTrigger>
							{ttsModels.length > 0 && (
								<TabsTrigger
									value="tts"
									className="px-2.5 text-[11.5px] text-muted-foreground group-data-[variant=default]/tabs-list:data-active:shadow-tab!"
								>
									{t('common.tts')}
									<span className="font-mono text-[10px] text-text-data">
										{ttsModels.length}
									</span>
								</TabsTrigger>
							)}
							{embeddingModels.length > 0 && (
								<TabsTrigger
									value="embedding"
									className="px-2.5 text-[11.5px] text-muted-foreground group-data-[variant=default]/tabs-list:data-active:shadow-tab!"
								>
									{t('common.embedding')}
									<span className="font-mono text-[10px] text-text-data">
										{embeddingModels.length}
									</span>
								</TabsTrigger>
							)}
							<TabsTrigger
								value="custom"
								className="px-2.5 text-[11.5px] text-muted-foreground group-data-[variant=default]/tabs-list:data-active:shadow-tab!"
							>
								{t('credential.custom')}
								<span className="font-mono text-[10px] text-text-data">
									{customModels.length}
								</span>
							</TabsTrigger>
						</TabsList>
					</div>

					{modelsLoading ? (
						<Skeleton className="h-40 rounded-[16px]" />
					) : tab === 'custom' ? (
						<CustomModelTable
							models={customModels}
							credentialId={credential.id}
							onAdd={handleAddCustomModel}
							onRemove={handleRemoveCustomModel}
						/>
					) : shown.length === 0 ? (
						<Empty className="border-none py-6">
							<EmptyHeader>
								<EmptyTitle>{t('credential.noModels')}</EmptyTitle>
								<EmptyDescription>
									{t('credential.noModelsDescription')}
								</EmptyDescription>
							</EmptyHeader>
						</Empty>
					) : (
						<>
							<TabsContent value="llm">
								<ModelTable
									models={models}
									variant="llm"
									credentialId={credential.id}
								/>
							</TabsContent>
							<TabsContent value="tts">
								<ModelTable
									models={ttsModels}
									variant="tts"
									credentialId={credential.id}
								/>
							</TabsContent>
							<TabsContent value="embedding">
								<ModelTable
									models={embeddingModels}
									variant="embedding"
									credentialId={credential.id}
								/>
							</TabsContent>
						</>
					)}
				</Tabs>
			</div>
		</div>
	);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export const CredentialPage = () => {
	const { t } = useTranslation();
	const { credentials, loading, remove, refetch } = useCredentials();
	const [schemas, setSchemas] = useState<CredentialSchema[]>([]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [createOpen, setCreateOpen] = useState(false);
	const [createDefaultType, setCreateDefaultType] = useState<string | undefined>();
	const [editOpen, setEditOpen] = useState(false);
	const [deleteOpen, setDeleteOpen] = useState(false);

	useEffect(() => {
		credentialApi.schemas().then((res) => setSchemas(res.schemas));
	}, []);

	// Auto-select first credential
	useEffect(() => {
		if (!selectedId && credentials.length > 0) {
			setSelectedId(credentials[0].id);
		}
	}, [credentials, selectedId]);

	const selectedCredential = credentials.find((c) => c.id === selectedId) ?? null;
	const selectedSchema = selectedCredential
		? (schemas.find(
				(s) =>
					(s.properties.type?.const as string) ===
					(selectedCredential.data.type as string),
			) ?? null)
		: null;

	// Group credentials by type, then list all schema types (even empty ones)
	const groupedByType: Array<{ type: string; title: string; records: CredentialView[] }> =
		schemas.map((s) => {
			const type = s.properties.type?.const as string;
			return {
				type,
				title: s.title,
				records: credentials.filter((c) => c.data.type === type),
			};
		});

	// Split providers so the user's actual configuration leads, and the
	// (mostly empty) "add a provider" entries don't drown it out.
	const configuredGroups = groupedByType.filter((g) => g.records.length > 0);
	const totalConfigured = configuredGroups.reduce((n, g) => n + g.records.length, 0);

	const handleOpenCreate = useCallback((type?: string) => {
		setCreateDefaultType(type);
		setCreateOpen(true);
	}, []);

	const handleDelete = useCallback(async () => {
		if (!selectedCredential) return;
		await remove(selectedCredential.id);
		setSelectedId(null);
	}, [selectedCredential, remove]);

	return (
		<div className="flex h-full w-full p-2 gap-2">
			{/* Left sidebar */}
			<Sidebar collapsible="none" className="rounded-[22px]">
				<SidebarHeader className={'flex flex-col p-[20px_18px_14px] gap-y-1'}>
					<div className="text-xl font-medium tracking-[-0.02em] text-foreground">
						{t('common.credential')}
					</div>
					<div className="text-text-tertiary text-xs">{t('credential.subtitle')}</div>
				</SidebarHeader>
				{/*<Separator />*/}
				<SidebarContent>
					{loading ? (
						<div className="flex flex-col gap-y-2 p-4">
							{Array.from({ length: 3 }).map((_, i) => (
								<Skeleton key={i} className="h-8 rounded" />
							))}
						</div>
					) : groupedByType.length === 0 ? (
						<Empty className="border-none py-8">
							<EmptyHeader>
								<EmptyTitle>{t('credential.noProviders')}</EmptyTitle>
							</EmptyHeader>
						</Empty>
					) : (
						<>
							{/* Configured credentials lead — this is what the user actually set up. */}
							{configuredGroups.length > 0 && (
								<SidebarGroup className="mt-6 px-2 py-0">
									<SidebarGroupLabel className="justify-between">
										{t('credential.configured')}
										<span className="text-[10px] text-text-data font-mono">
											{totalConfigured}
										</span>
									</SidebarGroupLabel>
									<SidebarGroupContent>
										{configuredGroups.map(({ type, title, records }) => (
											<SidebarGroup key={type} className="mt-3 px-0 py-0">
												<SidebarGroupLabel>{title}</SidebarGroupLabel>
												<SidebarGroupContent>
													<SidebarMenu>
														{records.map((rec) => {
															const name =
																(rec.data.name as
																	| string
																	| undefined) ?? rec.id;
															return (
																<SidebarMenuItem key={rec.id}>
																	<SidebarMenuButton
																		isActive={
																			selectedId === rec.id
																		}
																		onClick={() =>
																			setSelectedId(rec.id)
																		}
																	>
																		<span className="min-w-0 flex-1 truncate">
																			{name}
																		</span>
																		{!rec.editable && (
																			<Badge
																				variant="secondary"
																				className="text-[10px] px-1 py-0"
																				title={t(
																					'common.readOnlyTooltip',
																				)}
																			>
																				{t(
																					'common.readOnly',
																				)}
																			</Badge>
																		)}
																	</SidebarMenuButton>
																</SidebarMenuItem>
															);
														})}
													</SidebarMenu>
												</SidebarGroupContent>
											</SidebarGroup>
										))}
									</SidebarGroupContent>
								</SidebarGroup>
							)}

							{/* Add credential — every provider is an entry point (including
							    configured ones, to add more under the same provider). */}
							<SidebarGroup className="mt-5 px-2 py-0">
								<SidebarGroupLabel>{t('credential.addProvider')}</SidebarGroupLabel>
								<SidebarGroupContent>
									<SidebarMenu>
										{groupedByType.map(({ type, title }) => (
											<SidebarMenuItem key={type}>
												<SidebarMenuButton
													onClick={() => handleOpenCreate(type)}
												>
													<Plus />
													<span className="min-w-0 flex-1 truncate">
														{title}
													</span>
												</SidebarMenuButton>
											</SidebarMenuItem>
										))}
									</SidebarMenu>
								</SidebarGroupContent>
							</SidebarGroup>
						</>
					)}
				</SidebarContent>
			</Sidebar>

			{/* Right detail */}
			<main className="flex-1 min-h-0 overflow-hidden rounded-[22px] bg-card shadow-panel">
				{selectedCredential ? (
					<DetailPanel
						credential={selectedCredential}
						schema={selectedSchema}
						onEdit={() => setEditOpen(true)}
						onDelete={() => setDeleteOpen(true)}
					/>
				) : (
					<div className="flex h-full items-center justify-center">
						<Empty className="border-none">
							<EmptyHeader>
								<EmptyTitle>{t('credential.selectHint')}</EmptyTitle>
								<EmptyDescription>
									{t('credential.selectHintDescription')}
								</EmptyDescription>
							</EmptyHeader>
						</Empty>
					</div>
				)}
			</main>

			{/* Dialogs */}
			<CreateCredentialDialog
				open={createOpen}
				onOpenChange={setCreateOpen}
				defaultType={createDefaultType}
				onCreated={() => refetch()}
			/>
			{selectedCredential && (
				<>
					<EditCredentialDialog
						open={editOpen}
						onOpenChange={setEditOpen}
						credential={selectedCredential}
						onUpdated={() => refetch()}
					/>
					<DeleteDialog
						open={deleteOpen}
						onOpenChange={setDeleteOpen}
						title={t('common.deleteTitle', {
							entity: t('credential.deleteEntity'),
							name:
								(selectedCredential.data.name as string | undefined) ??
								selectedCredential.id,
						})}
						description={t('common.deleteDescription')}
						onConfirm={handleDelete}
					/>
				</>
			)}
		</div>
	);
};
