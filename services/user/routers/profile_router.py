"""User profile endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from services.user.schemas.profile_schema import UserOut

router = APIRouter()

@router.get("/info", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_user_info(
    request: Request,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    로그인한 사용자의 기본 정보를 반환합니다.
    - JWT 토큰 인증 필요 (헤더: Authorization: Bearer <token>)
    - 응답: user_id, username, email
    """
    # 사용자 정보 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="user_info_view",
            event_data={
                "email": current_user.email,
                "username": current_user.username
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return current_user
