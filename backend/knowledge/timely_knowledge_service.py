"""时效性知识库服务 V1.0 (2026-07-31)

管理 location/food/weather/travel/review 等时效性知识的存储、检索、过期检测。

与权威知识库(mysql_service.py)的区别：
- 不做权威校验（L1-L4质检流程），只做时效性检查
- TTL=30天，过期标记is_stale=True
- 用户再次提问时，命中过期条目则触发web search更新
- 查询时优先返回未过期条目，过期条目单独标记供上层决定是否刷新

核心方法：
- search(query, category) → 查询（返回fresh + stale列表）
- store(query, content, category) → 存储新条目并设置TTL
- mark_stale_expired() → 批量标记过期条目（定时任务调用）
- delete_stale(category) → 清理过期条目
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 默认TTL：30天
DEFAULT_TTL_DAYS = 30


def _detect_category(query: str) -> str:
    """根据查询关键词自动识别分类"""
    if not query:
        return "other"
    q = query.lower()
    # 美食类
    food_keywords = ["美食", "餐厅", "小吃", "吃什么", "推荐菜", "牛街", "火锅",
                     "烤肉", "面馆", "川菜", "粤菜", "日料", "西餐", "甜品",
                     "breakfast", "lunch", "dinner", "food", "restaurant"]
    # 地点类
    location_keywords = ["地点", "哪里", "位置", "地址", "在哪", "怎么走",
                         "景点", "公园", "商场", "超市", "location", "place"]
    # 旅行类
    travel_keywords = ["旅游", "旅行", "攻略", "游玩", "行程", "打卡",
                       "景点推荐", "一日游", "travel", "trip", "tour"]
    # 天气类
    weather_keywords = ["天气", "气温", "下雨", "温度", "穿衣", "weather",
                        "forecast", "rain", "temperature"]
    # 评价类
    review_keywords = ["评价", "口碑", "怎么样", "好不好", "评分",
                       "大众点评", "小红书", "review", "rating"]

    for kw in food_keywords:
        if kw in q:
            return "food"
    for kw in location_keywords:
        if kw in q:
            return "location"
    for kw in travel_keywords:
        if kw in q:
            return "travel"
    for kw in weather_keywords:
        if kw in q:
            return "weather"
    for kw in review_keywords:
        if kw in q:
            return "review"
    return "other"


class TimelyKnowledgeService:
    """时效性知识库服务"""

    def __init__(self, db: Session = None, ttl_days: int = DEFAULT_TTL_DAYS):
        self._db = db
        self.ttl_days = ttl_days

    def _get_db(self) -> Session:
        if self._db is not None:
            return self._db
        from app.database import get_global_session
        self._db = get_global_session()
        return self._db

    def search(self, query: str, category: Optional[str] = None,
               limit: int = 5) -> Dict[str, Any]:
        """查询时效性知识库

        Returns:
            {
                "fresh": List[Dict],  # 未过期条目
                "stale": List[Dict],  # 已过期条目（供上层决定是否刷新）
                "has_fresh": bool,
                "has_stale": bool,
            }
        """
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            db = self._get_db()
            cat = category or _detect_category(query)

            # 模糊匹配查询：query 关键词包含或被包含
            like_pattern = f"%{query[:50]}%"
            q = db.query(TimelyKnowledgeItem).filter(
                TimelyKnowledgeItem.query.ilike(like_pattern)
            )
            if cat != "other":
                q = q.filter(TimelyKnowledgeItem.category == cat)
            items = q.order_by(
                TimelyKnowledgeItem.created_at.desc()
            ).limit(limit).all()

            fresh, stale = [], []
            for item in items:
                data = {
                    "id": item.id,
                    "query": item.query,
                    "content": item.content,
                    "category": item.category,
                    "source": item.source,
                    "confidence": item.confidence,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                    "is_stale": item.is_stale,
                }
                if item.is_stale:
                    stale.append(data)
                else:
                    fresh.append(data)

            return {
                "fresh": fresh,
                "stale": stale,
                "has_fresh": len(fresh) > 0,
                "has_stale": len(stale) > 0,
                "category": cat,
            }
        except Exception as e:
            logger.warning(f"TimelyKnowledge search 失败: {e}")
            return {"fresh": [], "stale": [], "has_fresh": False, "has_stale": False, "category": category or "other"}

    def store(self, query: str, content: str, category: Optional[str] = None,
              source: str = "web_search", confidence: int = 70) -> Dict[str, Any]:
        """存储新的时效性知识条目（自动设置TTL）"""
        db = None
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            db = self._get_db()
            cat = category or _detect_category(query)

            now = datetime.now()
            expires_at = now + timedelta(days=self.ttl_days)

            item = TimelyKnowledgeItem(
                query=query[:255],
                content=content,
                category=cat,
                source=source,
                confidence=confidence,
                created_at=now,
                expires_at=expires_at,
                is_stale=False,
            )
            db.add(item)
            db.commit()
            db.refresh(item)

            logger.info(
                f"[TimelyKnowledge] 存入: id={item.id}, query='{query[:30]}', "
                f"category={cat}, expires_at={expires_at.isoformat()}"
            )
            return {
                "status": "ok",
                "id": item.id,
                "category": cat,
                "expires_at": expires_at.isoformat(),
            }
        except Exception as e:
            logger.error(f"[TimelyKnowledge] store 失败: {e}")
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
            return {"status": "error", "message": str(e)}

    def mark_stale_expired(self) -> int:
        """批量标记已过期但is_stale仍为False的条目

        供定时任务调用（如AuditScheduler每次触发时调用）
        Returns: 标记的条目数
        """
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            db = self._get_db()
            now = datetime.now()
            count = db.query(TimelyKnowledgeItem).filter(
                TimelyKnowledgeItem.expires_at < now,
                TimelyKnowledgeItem.is_stale == False,  # noqa: E712
            ).update({TimelyKnowledgeItem.is_stale: True})
            db.commit()
            if count > 0:
                logger.info(f"[TimelyKnowledge] 标记 {count} 条过期条目为 stale")
            return count
        except Exception as e:
            logger.warning(f"[TimelyKnowledge] mark_stale_expired 失败: {e}")
            return 0

    def delete_stale(self, category: Optional[str] = None) -> int:
        """清理已过期的条目（物理删除）"""
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            db = self._get_db()
            q = db.query(TimelyKnowledgeItem).filter(
                TimelyKnowledgeItem.is_stale == True  # noqa: E712
            )
            if category:
                q = q.filter(TimelyKnowledgeItem.category == category)
            count = q.delete()
            db.commit()
            logger.info(f"[TimelyKnowledge] 清理 {count} 条过期条目 (category={category or 'all'})")
            return count
        except Exception as e:
            logger.warning(f"[TimelyKnowledge] delete_stale 失败: {e}")
            return 0

    def refresh_entry(self, entry_id: int, new_content: str,
                      new_source: str = "web_search") -> bool:
        """刷新过期条目的内容（web search更新后调用）

        重置 created_at 和 expires_at，is_stale=False
        """
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            db = self._get_db()
            now = datetime.now()
            expires_at = now + timedelta(days=self.ttl_days)
            count = db.query(TimelyKnowledgeItem).filter(
                TimelyKnowledgeItem.id == entry_id
            ).update({
                TimelyKnowledgeItem.content: new_content,
                TimelyKnowledgeItem.source: new_source,
                TimelyKnowledgeItem.created_at: now,
                TimelyKnowledgeItem.expires_at: expires_at,
                TimelyKnowledgeItem.is_stale: False,
            })
            db.commit()
            return count > 0
        except Exception as e:
            logger.warning(f"[TimelyKnowledge] refresh_entry 失败: {e}")
            return False

    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        try:
            from models.timely_knowledge import TimelyKnowledgeItem
            from sqlalchemy import func as sql_func
            db = self._get_db()
            total = db.query(sql_func.count(TimelyKnowledgeItem.id)).scalar() or 0
            stale = db.query(sql_func.count(TimelyKnowledgeItem.id)).filter(
                TimelyKnowledgeItem.is_stale == True  # noqa: E712
            ).scalar() or 0
            by_category = {}
            rows = db.query(
                TimelyKnowledgeItem.category,
                sql_func.count(TimelyKnowledgeItem.id)
            ).group_by(TimelyKnowledgeItem.category).all()
            for cat, cnt in rows:
                by_category[cat] = cnt
            return {
                "total": total,
                "stale": stale,
                "fresh": total - stale,
                "by_category": by_category,
                "ttl_days": self.ttl_days,
            }
        except Exception as e:
            logger.warning(f"[TimelyKnowledge] stats 失败: {e}")
            return {"total": 0, "stale": 0, "fresh": 0, "by_category": {}, "ttl_days": self.ttl_days}


# 单例（延迟初始化）
_service_instance: Optional[TimelyKnowledgeService] = None


def get_timely_knowledge_service(ttl_days: Optional[int] = None) -> TimelyKnowledgeService:
    """获取时效性知识库服务单例

    Args:
        ttl_days: 可选 TTL（天）。未指定时从 settings.timely_knowledge_ttl_days 读取，
                  再回退到 DEFAULT_TTL_DAYS=30
    """
    global _service_instance
    if _service_instance is None:
        if ttl_days is None:
            try:
                from app.config import settings
                ttl_days = int(getattr(settings, "timely_knowledge_ttl_days", DEFAULT_TTL_DAYS))
            except Exception:
                ttl_days = DEFAULT_TTL_DAYS
        _service_instance = TimelyKnowledgeService(ttl_days=ttl_days)
    return _service_instance
