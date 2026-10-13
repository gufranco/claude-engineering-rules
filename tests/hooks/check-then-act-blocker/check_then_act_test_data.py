from __future__ import annotations

HOOK = "check-then-act-blocker"


ENFORCE = {"CHECK_THEN_ACT_ENFORCE": "1"}


FIND_THEN_CREATE = (
    "export async function reserveSeat(showId: string, row: number) {\n"
    "  const existing = await db.seat.findFirst({ where: { showId, row } });\n"
    "  if (!existing) {\n"
    "    await db.seat.create({ data: { showId, row } });\n"
    "  }\n"
    "}\n"
)
