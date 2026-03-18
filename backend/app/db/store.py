from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.models.agent import AgentPersona
from app.models.action import ActionEntry
from app.models.world import WorldMetrics, WorldState
from app.models.simulation import SimulationState, SimulationStatus


class SimulationStore:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.global_db_path = os.path.join(data_dir, "global.db")

    async def init(self):
        os.makedirs(self.data_dir, exist_ok=True)
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'generating_world',
                    rules_text TEXT NOT NULL DEFAULT '',
                    world_name TEXT NOT NULL DEFAULT '',
                    agent_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    is_public INTEGER NOT NULL DEFAULT 0,
                    view_count INTEGER NOT NULL DEFAULT 0,
                    fork_count INTEGER NOT NULL DEFAULT 0,
                    forked_from TEXT
                )
            """)
            await db.commit()

    def _sim_dir(self, sim_id: str) -> str:
        return os.path.join(self.data_dir, "simulations", sim_id)

    def _sim_db_path(self, sim_id: str) -> str:
        return os.path.join(self._sim_dir(sim_id), "simulation.db")

    async def _init_sim_db(self, sim_id: str):
        sim_dir = self._sim_dir(sim_id)
        os.makedirs(sim_dir, exist_ok=True)
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS agents (agent_id INTEGER PRIMARY KEY, state TEXT, updated_at TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS world_state (round INTEGER PRIMARY KEY, state TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, round INTEGER, day INTEGER, entry TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS narratives (round INTEGER PRIMARY KEY, day INTEGER, time_of_day TEXT, text TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS metrics_history (round INTEGER PRIMARY KEY, metrics TEXT)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_actions_round ON actions(round)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_narratives_day ON narratives(day)")
            await db.execute("CREATE TABLE IF NOT EXISTS report (id INTEGER PRIMARY KEY CHECK (id = 1), status TEXT DEFAULT 'pending', report_json TEXT, error TEXT)")
            await db.commit()

    async def create(self, sim_id: str, rules_text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute(
                "INSERT INTO simulations (id, rules_text, created_at) VALUES (?, ?, ?)",
                (sim_id, rules_text, now),
            )
            await db.commit()
        await self._init_sim_db(sim_id)

    async def update_status(self, sim_id: str, status: str, **kwargs) -> None:
        sets = ["status = ?"]
        vals: list[Any] = [status]
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(sim_id)
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute(f"UPDATE simulations SET {', '.join(sets)} WHERE id = ?", vals)
            await db.commit()

    async def get_simulation(self, sim_id: str) -> dict | None:
        async with aiosqlite.connect(self.global_db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM simulations WHERE id = ?", (sim_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_simulations(self, public_only: bool = False, sort: str = "recent") -> list[dict]:
        query = "SELECT * FROM simulations"
        if public_only:
            query += " WHERE is_public = 1"
        order = {"recent": "created_at DESC", "views": "view_count DESC", "forks": "fork_count DESC"}
        query += f" ORDER BY {order.get(sort, 'created_at DESC')}"
        async with aiosqlite.connect(self.global_db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            return [dict(row) for row in await cursor.fetchall()]

    async def set_meta(self, sim_id: str, key: str, value: Any) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, json.dumps(value, default=str)),
            )
            await db.commit()

    async def get_meta(self, sim_id: str, key: str) -> Any:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            cursor = await db.execute("SELECT value FROM meta WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None

    async def save_agent(self, sim_id: str, agent: AgentPersona) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO agents (agent_id, state, updated_at) VALUES (?, ?, ?)",
                (agent.id, agent.model_dump_json(), now),
            )
            await db.commit()

    async def save_agents_batch(self, sim_id: str, agents: list[AgentPersona]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.executemany(
                "INSERT OR REPLACE INTO agents (agent_id, state, updated_at) VALUES (?, ?, ?)",
                [(a.id, a.model_dump_json(), now) for a in agents],
            )
            await db.commit()

    async def get_agent(self, sim_id: str, agent_id: int) -> AgentPersona | None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            cursor = await db.execute("SELECT state FROM agents WHERE agent_id = ?", (agent_id,))
            row = await cursor.fetchone()
            return AgentPersona.model_validate_json(row[0]) if row else None

    async def get_all_agents(self, sim_id: str) -> list[AgentPersona]:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            cursor = await db.execute("SELECT state FROM agents ORDER BY agent_id")
            rows = await cursor.fetchall()
            return [AgentPersona.model_validate_json(row[0]) for row in rows]

    async def save_world_state(self, sim_id: str, round_num: int, state: WorldState) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO world_state (round, state) VALUES (?, ?)",
                (round_num, state.model_dump_json()),
            )
            await db.commit()

    async def get_world_state(self, sim_id: str, round_num: int | None = None) -> WorldState | None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            if round_num is not None:
                cursor = await db.execute("SELECT state FROM world_state WHERE round = ?", (round_num,))
            else:
                cursor = await db.execute("SELECT state FROM world_state ORDER BY round DESC LIMIT 1")
            row = await cursor.fetchone()
            return WorldState.model_validate_json(row[0]) if row else None

    async def save_action(self, sim_id: str, entry: ActionEntry) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT INTO actions (round, day, entry) VALUES (?, ?, ?)",
                (entry.round, entry.day, entry.model_dump_json()),
            )
            await db.commit()

    async def save_actions_batch(self, sim_id: str, entries: list[ActionEntry]) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.executemany(
                "INSERT INTO actions (round, day, entry) VALUES (?, ?, ?)",
                [(e.round, e.day, e.model_dump_json()) for e in entries],
            )
            await db.commit()

    async def get_actions(self, sim_id: str, from_round: int = 0, to_round: int | None = None) -> list[ActionEntry]:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            if to_round is not None:
                cursor = await db.execute(
                    "SELECT entry FROM actions WHERE round >= ? AND round <= ? ORDER BY id",
                    (from_round, to_round),
                )
            else:
                cursor = await db.execute(
                    "SELECT entry FROM actions WHERE round >= ? ORDER BY id", (from_round,)
                )
            rows = await cursor.fetchall()
            return [ActionEntry.model_validate_json(row[0]) for row in rows]

    async def save_narrative(self, sim_id: str, round_num: int, day: int, time_of_day: str, text: str) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO narratives (round, day, time_of_day, text) VALUES (?, ?, ?, ?)",
                (round_num, day, time_of_day, text),
            )
            await db.commit()

    async def get_narratives(self, sim_id: str, from_day: int = 0, to_day: int | None = None) -> list[dict]:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            db.row_factory = aiosqlite.Row
            if to_day is not None:
                cursor = await db.execute(
                    "SELECT * FROM narratives WHERE day >= ? AND day <= ? ORDER BY round",
                    (from_day, to_day),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM narratives WHERE day >= ? ORDER BY round", (from_day,)
                )
            return [dict(row) for row in await cursor.fetchall()]

    async def save_metrics(self, sim_id: str, round_num: int, metrics: WorldMetrics) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO metrics_history (round, metrics) VALUES (?, ?)",
                (round_num, metrics.model_dump_json()),
            )
            await db.commit()

    async def get_metrics_history(self, sim_id: str) -> list[dict]:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            cursor = await db.execute("SELECT round, metrics FROM metrics_history ORDER BY round")
            rows = await cursor.fetchall()
            return [{"round": row[0], **json.loads(row[1])} for row in rows]

    async def increment_view_count(self, sim_id: str) -> None:
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute("UPDATE simulations SET view_count = view_count + 1 WHERE id = ?", (sim_id,))
            await db.commit()

    async def increment_fork_count(self, sim_id: str) -> None:
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute("UPDATE simulations SET fork_count = fork_count + 1 WHERE id = ?", (sim_id,))
            await db.commit()

    async def publish(self, sim_id: str) -> None:
        async with aiosqlite.connect(self.global_db_path) as db:
            await db.execute("UPDATE simulations SET is_public = 1 WHERE id = ?", (sim_id,))
            await db.commit()

    async def copy_state_at_round(self, source_sim_id: str, target_sim_id: str, round_num: int) -> None:
        await self._init_sim_db(target_sim_id)
        src_db_path = self._sim_db_path(source_sim_id)
        tgt_db_path = self._sim_db_path(target_sim_id)

        async with aiosqlite.connect(src_db_path) as src_db:
            async with aiosqlite.connect(tgt_db_path) as tgt_db:
                cursor = await src_db.execute("SELECT key, value FROM meta")
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", rows)

                cursor = await src_db.execute("SELECT agent_id, state, updated_at FROM agents")
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT OR REPLACE INTO agents (agent_id, state, updated_at) VALUES (?, ?, ?)", rows)

                cursor = await src_db.execute("SELECT round, state FROM world_state WHERE round <= ?", (round_num,))
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT OR REPLACE INTO world_state (round, state) VALUES (?, ?)", rows)

                cursor = await src_db.execute("SELECT round, day, entry FROM actions WHERE round <= ?", (round_num,))
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT INTO actions (round, day, entry) VALUES (?, ?, ?)", rows)

                cursor = await src_db.execute("SELECT round, day, time_of_day, text FROM narratives WHERE round <= ?", (round_num,))
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT OR REPLACE INTO narratives (round, day, time_of_day, text) VALUES (?, ?, ?, ?)", rows)

                cursor = await src_db.execute("SELECT round, metrics FROM metrics_history WHERE round <= ?", (round_num,))
                rows = await cursor.fetchall()
                await tgt_db.executemany("INSERT OR REPLACE INTO metrics_history (round, metrics) VALUES (?, ?)", rows)

                await tgt_db.commit()

    async def set_report_status(self, sim_id: str, status: str, error: str | None = None) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO report (id, status, error) VALUES (1, ?, ?)",
                (status, error),
            )
            await db.commit()

    async def save_report(self, sim_id: str, report: dict) -> None:
        async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
            await db.execute(
                "INSERT OR REPLACE INTO report (id, status, report_json) VALUES (1, 'ready', ?)",
                (json.dumps(report, default=str),),
            )
            await db.commit()

    async def get_report(self, sim_id: str) -> dict | None:
        try:
            async with aiosqlite.connect(self._sim_db_path(sim_id)) as db:
                cursor = await db.execute("SELECT status, report_json, error FROM report WHERE id = 1")
                row = await cursor.fetchone()
                if not row:
                    return {"status": "pending"}
                status, report_json, error = row
                if status == "ready" and report_json:
                    return {"status": "ready", "report": json.loads(report_json)}
                return {"status": status, "error": error}
        except Exception:
            return {"status": "pending"}
