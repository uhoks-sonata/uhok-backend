from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user_optional
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.stream_crud import (
    get_homeshopping_live_url,
    get_homeshopping_stream_info,
)
from services.homeshopping.schemas.stream_schema import HomeshoppingStreamResponse

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()


@router.get("/schedule/live-stream", response_model=HomeshoppingStreamResponse)
async def get_live_stream(
    request: Request,
    homeshopping_id: int | None = Query(
        None, description="라이브 스트림 URL 조회용 홈쇼핑 ID"
    ),
    src: str | None = Query(
        None, description="직접 재생할 스트림 URL(m3u8/mp4)"
    ),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    라이브 스트림 메타데이터를 JSON으로 반환합니다.

    `homeshopping_id` 또는 `src` 중 하나는 반드시 필요합니다.
    """
    logger.debug(
        f"라이브 스트림 요청 수신: homeshopping_id={homeshopping_id}, src={src}"
    )

    if not src and not homeshopping_id:
        logger.warning("src와 homeshopping_id가 모두 없습니다")
        raise HTTPException(
            status_code=400, detail="src 또는 homeshopping_id 중 하나가 필요합니다."
        )

    stream_url = src
    if not stream_url and homeshopping_id:
        try:
            stream_url = await get_homeshopping_live_url(db, homeshopping_id)
        except Exception as e:
            logger.error(
                "homeshopping_id 기준 라이브 URL 조회 실패: homeshopping_id=%s, error=%s",
                homeshopping_id,
                str(e),
            )
            raise HTTPException(
                status_code=500, detail="라이브 스트림 정보를 조회하지 못했습니다."
            ) from e

        if not stream_url:
            logger.warning(
                f"homeshopping_id에 해당하는 라이브 URL이 없습니다: homeshopping_id={homeshopping_id}"
            )
            raise HTTPException(
                status_code=404, detail="라이브 스트림 URL을 찾을 수 없습니다."
            )

    try:
        stream_info = await get_homeshopping_stream_info(db, stream_url)
    except Exception as e:
        logger.error(f"스트림 메타데이터 조회 실패: stream_url={stream_url}, error={str(e)}")
        raise HTTPException(
            status_code=500, detail="라이브 스트림 메타데이터를 조회하지 못했습니다."
        ) from e

    current_user = await get_current_user_optional(request)
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="homeshopping_live_stream_view",
            event_data={"stream_url": stream_url, "homeshopping_id": homeshopping_id},
            **http_info,
        )

    source = "src" if src else "homeshopping_id"

    if stream_info:
        return HomeshoppingStreamResponse(
            homeshopping_id=stream_info.get("homeshopping_id") or homeshopping_id,
            homeshopping_name=stream_info.get("homeshopping_name"),
            live_id=stream_info.get("live_id"),
            product_id=stream_info.get("product_id"),
            product_name=stream_info.get("product_name"),
            stream_url=stream_info.get("stream_url", stream_url),
            live_url=stream_info.get("stream_url", stream_url),
            source=source,
            is_live=bool(stream_info.get("is_live")),
            live_date=stream_info.get("live_date"),
            live_start_time=stream_info.get("live_start_time"),
            live_end_time=stream_info.get("live_end_time"),
            thumb_img_url=stream_info.get("thumb_img_url"),
        )

    return HomeshoppingStreamResponse(
        homeshopping_id=homeshopping_id,
        stream_url=stream_url,
        live_url=stream_url,
        source=source,
        is_live=False,
    )
