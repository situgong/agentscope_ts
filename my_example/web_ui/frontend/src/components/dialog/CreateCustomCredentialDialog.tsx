import { Loader2, PlusCircle } from 'lucide-react';
import { useState, useEffect } from 'react';

import { customCredentialApi } from '@/api';
import { Button } from '@/components/ui/button';
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogDescription,
	DialogFooter,
} from '@/components/ui/dialog';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field.tsx';
import { Input } from '@/components/ui/input';
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from '@/components/ui/select';
import { useTranslation } from '@/i18n/useI18n.ts';

/** API type options determining the request/response format. */
const API_TYPES: Array<{ value: string; label: string }> = [
	{ value: 'chat_completions', label: 'Chat Completions' },
	{ value: 'responses', label: 'Responses' },
	{ value: 'messages', label: 'Messages' },
];

interface Props {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCreated?: () => void;
}

export function CreateCustomCredentialDialog({
	open,
	onOpenChange,
	onCreated,
}: Props) {
	const { t } = useTranslation();
	const [name, setName] = useState('');
	const [baseUrl, setBaseUrl] = useState('');
	const [apiKey, setApiKey] = useState('');
	const [apiType, setApiType] = useState('chat_completions');
	const [submitting, setSubmitting] = useState(false);

	// Reset form when dialog opens
	useEffect(() => {
		if (open) {
			setName('');
			setBaseUrl('');
			setApiKey('');
			setApiType('chat_completions');
		}
	}, [open]);

	const handleSubmit = async () => {
		const trimmedName = name.trim();
		const trimmedUrl = baseUrl.trim();
		const trimmedKey = apiKey.trim();
		if (!trimmedName || !trimmedUrl || !trimmedKey) return;

		setSubmitting(true);
		try {
			await customCredentialApi.create({
				name: trimmedName,
				base_url: trimmedUrl,
				api_key: trimmedKey,
				api_type: apiType,
			});
			onOpenChange(false);
			onCreated?.();
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="!w-[500px] !max-w-[500px]">
				<DialogHeader>
					<DialogTitle>
						{t('dialog-custom-credential-create.title')}
					</DialogTitle>
					<DialogDescription>
						{t('dialog-custom-credential-create.description')}
					</DialogDescription>
				</DialogHeader>
				<FieldGroup>
					<Field>
						<FieldLabel>
							{t('dialog-custom-credential-create.apiType')}
						</FieldLabel>
						<Select value={apiType} onValueChange={setApiType}>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{API_TYPES.map((opt) => (
									<SelectItem key={opt.value} value={opt.value}>
										{opt.label}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</Field>
					<Field>
						<FieldLabel>
							{t('dialog-custom-credential-create.name')}
						</FieldLabel>
						<Input
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder={t(
								'dialog-custom-credential-create.namePlaceholder',
							)}
							className="h-8 text-sm"
							autoFocus
						/>
					</Field>
					<Field>
						<FieldLabel>
							{t('dialog-custom-credential-create.baseUrl')}
						</FieldLabel>
						<Input
							value={baseUrl}
							onChange={(e) => setBaseUrl(e.target.value)}
							placeholder={t(
								'dialog-custom-credential-create.baseUrlPlaceholder',
							)}
							className="h-8 text-sm font-mono"
						/>
					</Field>
					<Field>
						<FieldLabel>
							{t('dialog-custom-credential-create.apiKey')}
						</FieldLabel>
						<Input
							type="password"
							value={apiKey}
							onChange={(e) => setApiKey(e.target.value)}
							placeholder={t(
								'dialog-custom-credential-create.apiKeyPlaceholder',
							)}
							className="h-8 text-sm font-mono"
						/>
					</Field>
				</FieldGroup>
				<DialogFooter>
					<Button
						variant="ghost"
						onClick={() => onOpenChange(false)}
						disabled={submitting}
					>
						{t('common.cancel')}
					</Button>
					<Button
						onClick={handleSubmit}
						disabled={
							submitting || !name.trim() || !baseUrl.trim() || !apiKey.trim()
						}
					>
						{submitting ? (
							<Loader2 className="size-3.5 animate-spin" />
						) : (
							<PlusCircle className="size-3.5" />
						)}
						{submitting ? t('common.creating') : t('common.create')}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
