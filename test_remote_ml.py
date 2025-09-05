#!/usr/bin/env python3
"""
백엔드에서 원격 ML 서비스 연동 테스트 스크립트
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 환경 변수 설정 (테스트용)
os.environ["ML_MODE"] = "remote_embed"
os.environ["ML_INFERENCE_URL"] = "http://localhost:8001"
os.environ["ML_TIMEOUT"] = "5.0"
os.environ["ML_RETRIES"] = "2"

async def test_remote_ml_adapter():
    """원격 ML 어댑터 테스트"""
    print("🚀 백엔드 원격 ML 어댑터 테스트 시작")
    print("=" * 50)
    
    try:
        # 1. 어댑터 임포트 및 생성
        print("📦 원격 ML 어댑터 임포트...")
        from services.recipe.utils.remote_ml_adapter import RemoteMLAdapter, MLServiceHealthChecker
        
        adapter = RemoteMLAdapter()
        print("✅ 어댑터 생성 성공")
        
        # 2. 헬스체크 테스트
        print("\n🔍 ML 서비스 헬스체크...")
        health_info = await MLServiceHealthChecker.check_health()
        print(f"헬스체크 결과: {health_info}")
        
        if health_info.get("status") != "ok":
            print("❌ ML 서비스가 정상 상태가 아닙니다")
            return False
        
        # 3. 임베딩 생성 테스트
        print("\n🔍 임베딩 생성 테스트...")
        test_query = "갈비탕"
        
        start_time = time.time()
        embedding = await adapter._get_embedding_from_ml_service(test_query)
        execution_time = time.time() - start_time
        
        print(f"✅ 임베딩 생성 성공:")
        print(f"   - 쿼리: '{test_query}'")
        print(f"   - 차원: {len(embedding)}")
        print(f"   - 실행시간: {execution_time:.3f}초")
        print(f"   - 임베딩 미리보기: {embedding[:5]}")
        
        # 4. 팩토리 함수 테스트
        print("\n🔍 팩토리 함수 테스트...")
        from services.recipe.utils.recommend_service import get_db_vector_searcher
        
        searcher = await get_db_vector_searcher()
        print(f"✅ 벡터 검색 어댑터 생성 성공: {type(searcher).__name__}")
        
        # 5. 환경 변수 확인
        print("\n🔍 환경 변수 확인...")
        print(f"   - ML_MODE: {os.getenv('ML_MODE')}")
        print(f"   - ML_INFERENCE_URL: {os.getenv('ML_INFERENCE_URL')}")
        print(f"   - ML_TIMEOUT: {os.getenv('ML_TIMEOUT')}")
        print(f"   - ML_RETRIES: {os.getenv('ML_RETRIES')}")
        
        print("\n✅ 모든 테스트 통과!")
        return True
        
    except ImportError as e:
        print(f"❌ 임포트 실패: {e}")
        print("   - 의존성 패키지가 설치되어 있는지 확인하세요")
        print("   - httpx 패키지: pip install httpx")
        return False
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_local_vs_remote():
    """로컬 모드와 원격 모드 비교 테스트"""
    print("\n🔄 로컬 vs 원격 모드 비교 테스트")
    print("=" * 50)
    
    # 원격 모드 테스트
    print("1️⃣ 원격 모드 테스트...")
    os.environ["ML_MODE"] = "remote_embed"
    
    try:
        from services.recipe.utils.recommend_service import get_db_vector_searcher
        remote_searcher = await get_db_vector_searcher()
        print(f"   ✅ 원격 모드 어댑터: {type(remote_searcher).__name__}")
    except Exception as e:
        print(f"   ❌ 원격 모드 실패: {e}")
    
    # 로컬 모드 테스트
    print("\n2️⃣ 로컬 모드 테스트...")
    os.environ["ML_MODE"] = "local"
    
    try:
        from services.recipe.utils.recommend_service import get_db_vector_searcher
        local_searcher = await get_db_vector_searcher()
        print(f"   ✅ 로컬 모드 어댑터: {type(local_searcher).__name__}")
    except Exception as e:
        print(f"   ❌ 로컬 모드 실패: {e}")
    
    print("\n✅ 모드 비교 테스트 완료!")

async def main():
    """메인 테스트 함수"""
    print("🧪 백엔드 ML 서비스 연동 테스트")
    print("=" * 60)
    
    # 기본 테스트
    success = await test_remote_ml_adapter()
    
    if success:
        # 모드 비교 테스트
        await test_local_vs_remote()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
        print("\n📋 다음 단계:")
        print("   1. ML 서비스 실행: docker-compose --profile with-ml up -d")
        print("   2. 백엔드 환경변수 설정: ML_MODE=remote_embed")
        print("   3. 통합 테스트 실행")
    else:
        print("❌ 일부 테스트가 실패했습니다.")
        print("\n🔧 문제 해결:")
        print("   1. ML 서비스가 실행 중인지 확인")
        print("   2. 네트워크 연결 상태 확인")
        print("   3. 의존성 패키지 설치 확인")

if __name__ == "__main__":
    asyncio.run(main())
