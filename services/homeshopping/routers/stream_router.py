from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user_optional
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.stream_crud import get_homeshopping_live_url

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/schedule/live-stream", response_class=HTMLResponse)
async def live_stream_html(
    request: Request,
    homeshopping_id: int | None = Query(None, description="홈쇼핑 ID (백엔드에서 m3u8 스트림 조회용)"),
    src: str | None = Query(None, description="직접 재생할 m3u8 URL (바로 재생용)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    HLS.js HTML 템플릿 렌더링
    - src(직접 m3u8) 또는 homeshopping_id 중 하나를 받아서 재생 페이지 렌더
    - homeshopping_id가 주어지면 get_homeshopping_stream_info()로 m3u8 등 실제 스트림을 조회
    - 비동기 템플릿 렌더링, 인증은 선택적
    """
    logger.debug(f"라이브 스트림 HTML 요청: homeshopping_id={homeshopping_id}, src={src}")
    
    stream_url = src
    title = "홈쇼핑 라이브"

    # homeshopping_id가 오면 백엔드에서 live_url 조회
    if not stream_url and homeshopping_id:
        logger.debug(f"homeshopping_id로 라이브 URL 조회: homeshopping_id={homeshopping_id}")
        try:
            live_url = await get_homeshopping_live_url(db, homeshopping_id)
            if not live_url:
                logger.warning(f"라이브 URL을 찾을 수 없음: homeshopping_id={homeshopping_id}")
                raise HTTPException(status_code=404, detail="방송을 찾을 수 없습니다.")
            stream_url = live_url
            logger.debug(f"라이브 URL 조회 성공: {stream_url}")
        except Exception as e:
            logger.error(f"라이브 URL 조회 실패: homeshopping_id={homeshopping_id}, error={str(e)}")
            raise HTTPException(status_code=500, detail="라이브 URL 조회 중 오류가 발생했습니다.")

    if not stream_url:
        logger.warning("stream_url과 homeshopping_id 모두 없음")
        raise HTTPException(status_code=400, detail="src 또는 homeshopping_id 중 하나는 필수입니다.")

    # 선택: 사용자 로깅
    current_user = await get_current_user_optional(request)
    if current_user:
        # 비동기 백그라운드 처리: FastAPI BackgroundTasks를 사용
        logger.info(f"[라이브 HTML] user_id={current_user.user_id}, stream={stream_url}")
        # 사용자 로그 전송을 백그라운드 태스크로 처리
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=current_user.user_id,
                event_type="homeshopping_live_html_view",
                event_data={"stream_url": stream_url, "homeshopping_id": homeshopping_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
    else:
        logger.debug("인증되지 않은 사용자의 라이브 스트림 요청")

    # 템플릿 렌더
    logger.debug(f"라이브 스트림 HTML 템플릿 렌더링: stream_url={stream_url}")
    return templates.TemplateResponse(
        "live_stream.html",
        {"request": request, "src": stream_url, "title": title},
    )
