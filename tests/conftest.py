import sys
import os
from unittest.mock import MagicMock, AsyncMock

# uhok-backend를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 실제 DB 연결 없이 import 가능하도록 common.* stub 등록 ──────────────────
import types

def _stub(name, **attrs):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__path__ = []
    mod.__package__ = name
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    # 부모 패키지에 자식 속성 등록
    parts = name.rsplit(".", 1)
    if len(parts) == 2:
        parent = sys.modules.get(parts[0])
        if parent:
            setattr(parent, parts[1], mod)
    return mod

_fake_settings = MagicMock(
    mariadb_service_url="sqlite+aiosqlite:///:memory:",
    debug=False,
    webhook_base_url="http://localhost",
)
_stub("common")
_stub("common.config", get_settings=MagicMock(return_value=_fake_settings))
from sqlalchemy.orm import DeclarativeBase
class _MariaBase(DeclarativeBase):
    pass

_stub("common.database")
_stub("common.database.base_mariadb", MariaBase=_MariaBase)
_stub("common.database.mariadb_service", get_maria_service_db=MagicMock())
_stub("common.database.mariadb_auth", get_maria_auth_db=MagicMock())
_stub("common.logger", get_logger=MagicMock(return_value=MagicMock()))
_stub("common.log_utils", send_user_log=AsyncMock())
_stub("common.dependencies", get_current_user=MagicMock())
_stub("common.http_dependencies", extract_http_info=MagicMock(return_value={}))
_stub("dotenv", load_dotenv=MagicMock())

# httpx stub
_fake_httpx = MagicMock()
_fake_client = AsyncMock()
_fake_client.__aenter__ = AsyncMock(return_value=_fake_client)
_fake_client.__aexit__ = AsyncMock(return_value=False)
_fake_resp = MagicMock()
_fake_resp.json.return_value = {"payment_id": "pay_test"}
_fake_resp.raise_for_status = MagicMock()
_fake_client.post = AsyncMock(return_value=_fake_resp)
_fake_httpx.AsyncClient.return_value = _fake_client
_fake_httpx.RequestError = Exception
sys.modules["httpx"] = _fake_httpx
