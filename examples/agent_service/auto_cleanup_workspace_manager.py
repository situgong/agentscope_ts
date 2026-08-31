# -*- coding: utf-8 -*-
"""DockerWorkspaceManager subclass with orphan-container cleanup.

On startup the base :class:`DockerWorkspaceManager` starts its TTL
sweeper but does **not** look for containers left behind by a previous
process.  Because the cache is purely in-memory, a restart orphans
every running container — the sweeper has nothing to evict.

This subclass scans Docker for containers labelled
``agentscope.workspace=true`` during ``__aenter__`` and removes any
that are not tracked in the cache, so a restart reclaims leaked
resources instead of letting them run forever.
"""
import asyncio
import logging

from agentscope.app.workspace_manager import DockerWorkspaceManager

logger = logging.getLogger(__name__)


class AutoCleanupDockerWorkspaceManager(DockerWorkspaceManager):
    """DockerWorkspaceManager that reaps orphaned containers on startup.

    On ``__aenter__`` (before the sweeper and pre-warm buffer start)
    this manager queries Docker for every container carrying the
    ``agentscope.workspace=true`` label and force-removes any whose
    ``agentscope.workspace.id`` is not in the in-memory cache.

    The scan is best-effort: if Docker is unreachable the manager
    still starts normally — the containers will simply remain until
    a manual ``docker rm``.
    """

    async def _cleanup_orphaned_containers(self) -> None:
        """Remove Docker containers not tracked in the cache.

        Queries the Docker API for containers labelled
        ``agentscope.workspace=true``, compares their
        ``agentscope.workspace.id`` label against ``self._cache``, and
        force-kills + deletes any that are not tracked.
        """
        import aiodocker

        client: aiodocker.Docker | None = None
        try:
            client = aiodocker.Docker()
            containers = await client.containers.list(
                filters={"label": ["agentscope.workspace=true"]},
            )
        except Exception:
            logger.exception(
                "AutoCleanup: failed to list Docker containers; "
                "skipping orphan cleanup",
            )
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    pass
            return

        if not containers:
            logger.info("AutoCleanup: no labelled containers found")
            await client.close()
            return

        # Snapshot the cache keys once — no lock needed because the
        # sweeper hasn't started yet and no requests can arrive before
        # lifespan startup completes.
        tracked_ids = set(self._cache.keys())

        orphaned: list = []
        for c in containers:
            try:
                info = await c.show()
            except Exception:
                logger.warning(
                    "AutoCleanup: failed to inspect container %s, skipping",
                    c._id,
                )
                continue
            labels = info.get("Config", {}).get("Labels", {}) or {}
            ws_id = labels.get("agentscope.workspace.id", "")
            name = (info.get("Name") or "").lstrip("/")
            if ws_id and ws_id not in tracked_ids:
                orphaned.append((c, ws_id, name))

        if not orphaned:
            logger.info(
                "AutoCleanup: all %d container(s) are tracked, "
                "nothing to clean",
                len(containers),
            )
            await client.close()
            return

        logger.warning(
            "AutoCleanup: found %d orphaned container(s): %s",
            len(orphaned),
            [name for _, _, name in orphaned],
        )

        async def _remove(c: object, ws_id: str, name: str) -> None:
            """Force-kill and delete one orphaned container."""
            try:
                await c.kill()
            except Exception:
                pass  # container may already be stopped
            try:
                await c.delete(force=True)
                logger.info(
                    "AutoCleanup: removed orphaned container %s "
                    "(workspace_id=%s)",
                    name,
                    ws_id,
                )
            except Exception:
                logger.exception(
                    "AutoCleanup: failed to remove container %s",
                    name,
                )

        await asyncio.gather(
            *(_remove(c, ws_id, name) for c, ws_id, name in orphaned),
            return_exceptions=True,
        )

        await client.close()

    async def __aenter__(self) -> "AutoCleanupDockerWorkspaceManager":
        """Clean up orphans, then delegate to the base ``__aenter__``.

        The cleanup runs *before* the sweeper starts so there is no
        race between the orphan scan and a sweeper tick.
        """
        await self._cleanup_orphaned_containers()
        await super().__aenter__()
        return self
