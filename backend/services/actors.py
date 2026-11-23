"""请求级身份解析，与任何业务模块解耦。

历史上 `actor()` 放在 `services/automation.py`（旧批量志愿链路）里，导致 17 个
模块为了拿"当前登录用户"而依赖整个志愿模块：旧链路一旦下线，证书、材料、规则、
计分、排名等蓝图会被一起打断。

这里只保留与业务无关的鉴权原语；志愿批次特有的 `authorize()` 仍留在
`services/automation.py`，随旧链路一起处理。
"""
from flask import abort, session

from extensions import db
from models import User


def actor():
    """当前登录且状态为 active 的用户；否则 401。"""
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if not user or user.status != "active":
        abort(401, description="请先登录")
    return user
