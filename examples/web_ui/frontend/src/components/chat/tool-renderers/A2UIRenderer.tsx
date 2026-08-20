import { Layout } from 'lucide-react';
import type { ReactNode } from 'react';

import { A2UISurface } from '@/components/a2ui';
import { toolArgClass, toolLabelClass } from './_shared';
import type { TFunction, ToolCallWithResult } from './types';

/**
 * Renderer for the A2UI tool. The tool result contains a DataBlock with
 * ``media_type="application/a2ui+json"`` holding base64-encoded JSONL
 * messages. This renderer extracts that block and feeds it to the
 * ``A2UISurface`` component, which uses the official ``@a2ui/react``
 * renderer to display the surface inline in the chat.
 */
export const A2UIRenderer = {
	renderHeader(pair: ToolCallWithResult, t: TFunction): ReactNode {
		return (
			<>
				<Layout className="size-3 shrink-0 text-primary" />
				<span className={toolLabelClass}>{t('tool.callGeneric')}</span>
				<span className={toolArgClass}>A2UI</span>
			</>
		);
	},

	renderBody(pair: ToolCallWithResult): ReactNode {
		const { result } = pair;
		if (!result || result.state === 'running') return null;

		// The tool result output is an array of content blocks.
		// Find the DataBlock with media_type "application/a2ui+json".
		if (typeof result.output === 'string') return null;

		const a2uiBlock = result.output.find(
			(b) => b.type === 'data' && b.source.media_type === 'application/a2ui+json',
		);
		if (!a2uiBlock || a2uiBlock.type !== 'data') return null;

		const rawA2UI =
			a2uiBlock.source.type === 'url'
				? a2uiBlock.source.url
				: atob(a2uiBlock.source.data ?? '');

		return <A2UISurface rawA2UI={rawA2UI} />;
	},
};
