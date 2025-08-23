"""
홈쇼핑 방송 알림 스케줄러 서비스
- 찜한 상품의 방송 시작 시간에 알림을 발송하는 스케줄러
"""

import asyncio
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from services.homeshopping.crud.homeshopping_crud import get_pending_broadcast_notifications
from common.logger import get_logger

logger = get_logger("broadcast_notification_scheduler")


class BroadcastNotificationScheduler:
    """홈쇼핑 방송 알림 스케줄러"""
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 60  # 1분마다 체크
    
    async def check_and_send_notifications(self):
        """발송 대기 중인 알림을 확인하고 발송"""
        logger.info("방송 알림 발송 체크 시작")
        
        try:
            # 데이터베이스 연결
            from common.database.mariadb_service import SessionLocal
            
            async with SessionLocal() as db:
                # 현재 시간 기준으로 발송해야 할 알림 조회
                current_time = datetime.now()
                pending_notifications = await get_pending_broadcast_notifications(db, current_time)
                
                if not pending_notifications:
                    logger.info("발송할 방송 알림이 없습니다.")
                    return
                
                logger.info(f"발송할 방송 알림 {len(pending_notifications)}건 발견")
                
                # 각 알림에 대해 발송 처리
                for notification in pending_notifications:
                    await self._send_notification(notification)
            
        except Exception as e:
            logger.error(f"방송 알림 발송 체크 중 오류 발생: {str(e)}")
    
    async def _send_notification(self, notification: Dict[str, Any]):
        """개별 알림 발송 처리"""
        try:
            notification_id = notification["notification_id"]
            user_id = notification["user_id"]
            product_name = notification["product_name"]
            broadcast_date = notification["broadcast_date"]
            broadcast_start_time = notification["broadcast_start_time"]
            
            logger.info(f"방송 알림 발송 시작: notification_id={notification_id}, user_id={user_id}, product={product_name}")
            
            # 실제 알림 발송 로직 (푸시 알림, 이메일, SMS 등)
            # 여기서는 로그만 남기고 실제 발송은 별도 구현 필요
            await self._send_push_notification(user_id, product_name, broadcast_date, broadcast_start_time)
            
            logger.info(f"방송 알림 발송 완료: notification_id={notification_id}")
            
        except Exception as e:
            logger.error(f"방송 알림 발송 실패: notification_id={notification['notification_id']}, error={str(e)}")
    
    async def _send_push_notification(self, user_id: int, product_name: str, broadcast_date, broadcast_start_time):
        """푸시 알림 발송 (실제 구현 필요)"""
        # TODO: 실제 푸시 알림 발송 로직 구현
        # - FCM, APNS 등 푸시 서비스 연동
        # - 사용자 디바이스 토큰 조회
        # - 알림 메시지 생성 및 발송
        
        message = f"🎬 {product_name} 방송이 시작됩니다!\n방송시간: {broadcast_date} {broadcast_start_time}"
        
        logger.info(f"푸시 알림 발송 (시뮬레이션): user_id={user_id}, message={message}")
        
        # 실제 발송 로직은 여기에 구현
        # await push_service.send_notification(user_id, message)
    
    def start(self):
        """스케줄러 시작"""
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다.")
            return
        
        logger.info("방송 알림 스케줄러 시작")
        self.is_running = True
        
        # 1분마다 알림 체크
        schedule.every(self.check_interval).seconds.do(
            lambda: asyncio.create_task(self.check_and_send_notifications())
        )
        
        # 스케줄러 루프 실행
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """스케줄러 중지"""
        logger.info("방송 알림 스케줄러 중지")
        self.is_running = False
        schedule.clear()


# 스케줄러 인스턴스
scheduler = BroadcastNotificationScheduler()


def start_scheduler():
    """스케줄러 시작 함수"""
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 스케줄러가 중지되었습니다.")
        scheduler.stop()
    except Exception as e:
        logger.error(f"스케줄러 실행 중 오류 발생: {str(e)}")
        scheduler.stop()


if __name__ == "__main__":
    # 스케줄러 직접 실행 (테스트용)
    start_scheduler()
