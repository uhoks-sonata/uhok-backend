"""
수정된 ACID 로직 단위 테스트
1. toggle_kok_likes          — with_for_update() 적용
2. toggle_homeshopping_likes — with_for_update() 적용
3. create_orders_from_selected_carts — with_for_update() + SERIALIZABLE 적용
4. apply_payment_webhook_v2  — SERIALIZABLE 적용
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────

def make_db(scalar_return=None):
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_return
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    db.execute.return_value = result
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _select_chain():
    """select(...).where(...).with_for_update() 체인 mock."""
    chain = MagicMock()
    chain.join.return_value = chain
    chain.where.return_value = chain
    chain.with_for_update.return_value = chain
    return chain


# ─────────────────────────────────────────────────────────────
# 1 · toggle_kok_likes — with_for_update()
# ─────────────────────────────────────────────────────────────

import services.kok.crud.likes_crud as kok_likes_mod


class _FakeKokLike:
    pass


@pytest.mark.asyncio
async def test_toggle_kok_likes_for_update_existing():
    """찜이 있을 때 SELECT FOR UPDATE → 해제 → False 반환."""
    existing = _FakeKokLike()
    db = make_db()
    db.execute.return_value.scalar_one_or_none.return_value = existing

    chain = _select_chain()
    with patch.object(kok_likes_mod, "select", return_value=chain):
        result = await kok_likes_mod.toggle_kok_likes(db, user_id=1, kok_product_id=10)

    chain.with_for_update.assert_called_once()
    assert result is False
    db.delete.assert_called_once_with(existing)


@pytest.mark.asyncio
async def test_toggle_kok_likes_for_update_new():
    """찜이 없을 때 SELECT FOR UPDATE → 등록 → True 반환."""
    db = make_db()
    db.execute.return_value.scalar_one_or_none.return_value = None

    chain = _select_chain()
    with patch.object(kok_likes_mod, "select", return_value=chain):
        result = await kok_likes_mod.toggle_kok_likes(db, user_id=1, kok_product_id=10)

    chain.with_for_update.assert_called_once()
    assert result is True
    db.add.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 2 · toggle_homeshopping_likes — with_for_update()
# ─────────────────────────────────────────────────────────────

import services.homeshopping.crud.likes_crud as hs_likes_mod


class _FakeHsLike:
    homeshopping_like_id = 99


@pytest.mark.asyncio
async def test_toggle_homeshopping_likes_for_update_existing():
    """홈쇼핑 찜 해제 경로에서 with_for_update() 호출."""
    existing = _FakeHsLike()
    db = make_db()
    db.execute.return_value.scalar_one_or_none.return_value = existing

    chain = _select_chain()
    with (
        patch.object(hs_likes_mod, "select", return_value=chain),
        patch.object(hs_likes_mod, "delete_broadcast_notification", new_callable=AsyncMock),
    ):
        result = await hs_likes_mod.toggle_homeshopping_likes(db, user_id=1, homeshopping_live_id=5)

    chain.with_for_update.assert_called_once()
    assert result is False
    db.delete.assert_called_once_with(existing)


@pytest.mark.asyncio
async def test_toggle_homeshopping_likes_for_update_new():
    """홈쇼핑 찜 등록 경로에서 with_for_update() 호출."""
    db = make_db()
    db.execute.return_value.scalar_one_or_none.return_value = None

    chain = _select_chain()
    with (
        patch.object(hs_likes_mod, "select", return_value=chain),
        patch.object(hs_likes_mod, "create_broadcast_notification", new_callable=AsyncMock),
    ):
        result = await hs_likes_mod.toggle_homeshopping_likes(db, user_id=1, homeshopping_live_id=5)

    chain.with_for_update.assert_called_once()
    assert result is True
    db.add.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 3 · create_orders_from_selected_carts — FOR UPDATE + SERIALIZABLE
# ─────────────────────────────────────────────────────────────

import services.order.crud.kok.kok_order_create_crud as order_create_mod


@pytest.mark.asyncio
async def test_create_orders_raises_on_empty_items():
    """selected_items가 비어있으면 ValueError를 발생시킨다."""
    db = make_db()
    with pytest.raises(ValueError, match="선택된 항목이 없습니다"):
        await order_create_mod.create_orders_from_selected_carts(db, user_id=1, selected_items=[])


@pytest.mark.asyncio
async def test_create_orders_uses_for_update_and_serializable():
    """
    - KokCart 조회 시 with_for_update() 체인 호출
    - db.execute에 SERIALIZABLE SET이 포함된 호출이 있어야 함
    """
    fake_order = MagicMock()
    fake_order.order_id = 1
    fake_order.order_time = datetime.now()

    execute_calls = []
    db = AsyncMock(spec=AsyncSession)
    db.flush = AsyncMock()
    db.add = MagicMock()

    async def fake_execute(stmt, *a, **kw):
        execute_calls.append(str(stmt))
        result = MagicMock()
        result.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    db.execute.side_effect = fake_execute

    chain = _select_chain()

    with (
        patch.object(order_create_mod, "Order", return_value=fake_order),
        patch.object(order_create_mod, "select", return_value=chain),
        patch.object(order_create_mod, "debug_cart_status", new_callable=AsyncMock, return_value={}),
    ):
        with pytest.raises(ValueError):
            await order_create_mod.create_orders_from_selected_carts(
                db, user_id=1, selected_items=[{"kok_cart_id": 1, "quantity": 2}]
            )

    assert any("SERIALIZABLE" in c for c in execute_calls), \
        f"SERIALIZABLE 미호출. execute_calls={execute_calls}"
    chain.with_for_update.assert_called_once()


# ─────────────────────────────────────────────────────────────
# 4 · apply_payment_webhook_v2 — SERIALIZABLE
# ─────────────────────────────────────────────────────────────

import services.order.crud.payment_v2_crud as payment_v2_mod


def _patch_payment_v2(mod):
    """테스트용 모듈 수준 변수 설정."""
    mod.PAYMENT_WEBHOOK_SECRET = "secret"
    mod.SERVICE_AUTH_TOKEN = None
    mod._verify_webhook_signature = MagicMock(return_value=True)
    ww = MagicMock()
    ww.verify_callback_token = AsyncMock(return_value=True)
    ww.resolve = AsyncMock(return_value=1)
    ww.discard_callback_token = AsyncMock()
    ww.register_callback_token = AsyncMock()
    ww.subscribe = AsyncMock()
    ww.cleanup = AsyncMock()
    mod.webhook_waiters = ww


@pytest.mark.asyncio
async def test_webhook_completed_sets_serializable():
    """payment.completed 웹훅에서 SERIALIZABLE이 db.execute에 전달된다."""
    import json

    _patch_payment_v2(payment_v2_mod)

    execute_calls = []
    db = AsyncMock(spec=AsyncSession)

    async def fake_execute(stmt, *a, **kw):
        execute_calls.append(str(stmt))
        return MagicMock()

    db.execute.side_effect = fake_execute

    payload = json.dumps({"order_id": 42, "payment_id": "pay_1", "user_id": 1}).encode()

    with (
        patch.object(payment_v2_mod, "_ensure_order_access", new_callable=AsyncMock,
                     return_value={"kok_orders": [], "homeshopping_orders": []}),
        patch.object(payment_v2_mod, "_mark_all_children_payment_completed", new_callable=AsyncMock),
    ):
        result = await payment_v2_mod.apply_payment_webhook_v2(
            db=db,
            tx_id="tx_42_abc",
            raw_body=payload,
            signature_b64="any",
            event="payment.completed",
            callback_token="tok",
        )

    assert result.get("ok") is True
    assert any("SERIALIZABLE" in c for c in execute_calls), \
        f"SERIALIZABLE 미호출. calls={execute_calls}"


@pytest.mark.asyncio
async def test_webhook_failed_sets_serializable():
    """payment.failed 웹훅에서도 SERIALIZABLE이 db.execute에 전달된다."""
    import json

    _patch_payment_v2(payment_v2_mod)

    execute_calls = []
    db = AsyncMock(spec=AsyncSession)

    async def fake_execute(stmt, *a, **kw):
        execute_calls.append(str(stmt))
        return MagicMock()

    db.execute.side_effect = fake_execute

    payload = json.dumps({
        "order_id": 42, "payment_id": "pay_1", "failure_reason": "insufficient_funds"
    }).encode()

    with patch.object(payment_v2_mod, "cancel_order", new_callable=AsyncMock):
        result = await payment_v2_mod.apply_payment_webhook_v2(
            db=db,
            tx_id="tx_42_abc",
            raw_body=payload,
            signature_b64="any",
            event="payment.failed",
            callback_token="tok",
        )

    assert result.get("ok") is True
    assert any("SERIALIZABLE" in c for c in execute_calls), \
        f"SERIALIZABLE 미호출. calls={execute_calls}"
