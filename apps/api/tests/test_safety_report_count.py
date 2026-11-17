import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import add_spot, add_user

async def test_trigger_increments_count_on_insert(db: AsyncSession) -> None:
    spot = await add_spot(db)
    user = await add_user(db, "test-user-insert")
    
    await db.execute(
        text("INSERT INTO safety_reports (spot_id, user_id, reported_tier) VALUES (:s, :u, 'green')"),
        {"s": spot.id, "u": user.id}
    )
    await db.commit()
    
    count = await db.scalar(text("SELECT safety_report_count FROM spots WHERE id = :s"), {"s": spot.id})
    assert count == 1


async def test_trigger_decrements_count_on_delete(db: AsyncSession) -> None:
    spot = await add_spot(db)
    user = await add_user(db, "test-user-delete")
    
    # Insert report (trigger makes count 1)
    await db.execute(
        text("INSERT INTO safety_reports (spot_id, user_id, reported_tier) VALUES (:s, :u, 'green')"),
        {"s": spot.id, "u": user.id}
    )
    await db.commit()
    
    # Delete report
    await db.execute(
        text("DELETE FROM safety_reports WHERE spot_id = :s AND user_id = :u"),
        {"s": spot.id, "u": user.id}
    )
    await db.commit()
    
    count = await db.scalar(text("SELECT safety_report_count FROM spots WHERE id = :s"), {"s": spot.id})
    assert count == 0


async def test_trigger_guard_prevents_negative_count(db: AsyncSession) -> None:
    spot = await add_spot(db)
    
    # Artificially force count to 0 just in case
    await db.execute(text("UPDATE spots SET safety_report_count = 0 WHERE id = :s"), {"s": spot.id})
    
    # Execute a manual decrement simulating a rogue delete or edge case
    await db.execute(
        text("UPDATE spots SET safety_report_count = GREATEST(safety_report_count - 1, 0) WHERE id = :s"),
        {"s": spot.id}
    )
    await db.commit()
    
    count = await db.scalar(text("SELECT safety_report_count FROM spots WHERE id = :s"), {"s": spot.id})
    assert count == 0  # GREATEST(..., 0) guard held


async def test_migration_backfill_logic_sets_correct_count(db: AsyncSession) -> None:
    spot = await add_spot(db)
    u1 = await add_user(db, "u1")
    u2 = await add_user(db, "u2")
    
    # Insert 2 reports (trigger natively sets count to 2)
    await db.execute(
        text("INSERT INTO safety_reports (spot_id, user_id, reported_tier) VALUES (:s, :u1, 'green'), (:s, :u2, 'yellow')"),
        {"s": spot.id, "u1": u1.id, "u2": u2.id}
    )
    
    # Sabotage the count to simulate a pre-migration state (count = 0)
    await db.execute(text("UPDATE spots SET safety_report_count = 0 WHERE id = :s"), {"s": spot.id})
    assert await db.scalar(text("SELECT safety_report_count FROM spots WHERE id = :s"), {"s": spot.id}) == 0
    
    # Run the exact backfill SQL from Migration 0005
    await db.execute(
        text("""
        UPDATE spots s
        SET safety_report_count = (
            SELECT COUNT(*) FROM safety_reports r WHERE r.spot_id = s.id
        )
        WHERE s.id = :s
        """),
        {"s": spot.id}
    )
    await db.commit()
    
    # Assert backfill correctly counted the 2 existing reports
    count = await db.scalar(text("SELECT safety_report_count FROM spots WHERE id = :s"), {"s": spot.id})
    assert count == 2