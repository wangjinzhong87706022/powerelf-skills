"""
知识检索框架 — 开放、可扩展的多后端知识库检索

支持的 Provider:
- mysql: MySQL kb_knowledge_base 表 LIKE 搜索（默认，无需额外服务）
- ragflow: RAGFlow 语义检索（需要部署 RAGFlow）
- elasticsearch: Elasticsearch 全文检索（需要部署 ES）
- chroma: ChromaDB 向量检索（需要部署 Chroma）
- http: 自定义 HTTP API（任意 REST 接口）

使用方式:
    from knowledge import search_knowledge, create_provider

    # 默认使用 MySQL
    results = search_knowledge(conn, "水位传感器故障")

    # 指定 provider
    results = search_knowledge(conn, "水位传感器故障", provider="ragflow")

    # 注册自定义 provider
    register_provider("my_api", MyApiProvider(config))
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ====== 数据模型 ======

@dataclass
class KnowledgeResult:
    """知识检索结果"""
    title: str                          # 文档标题
    content: str                        # 匹配内容片段
    source: str = ""                    # 来源（文件名/URL）
    score: float = 0.0                  # 相关性分数 (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "metadata": self.metadata,
        }


# ====== Provider 接口 ======

class KnowledgeProvider(ABC):
    """知识检索 Provider 抽象基类"""

    @abstractmethod
    def search(self, query: str, top_k: int = 5, **kwargs) -> List[KnowledgeResult]:
        """检索知识库

        Args:
            query: 查询文本
            top_k: 返回结果数量
            **kwargs: Provider 特定参数

        Returns:
            list of KnowledgeResult
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查 Provider 是否可用"""
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


# ====== MySQL Provider ======

class MySQLProvider(KnowledgeProvider):
    """MySQL kb_knowledge_base 表 LIKE 搜索（默认 Provider）"""

    def __init__(self):
        pass

    def search(self, query: str, top_k: int = 5, conn=None, **kwargs) -> List[KnowledgeResult]:
        if not conn:
            return []

        cur = conn.cursor()
        keywords = query.split()
        conditions = []
        params = []
        for kw in keywords:
            conditions.append("(k.name LIKE %s OR k.doc_name LIKE %s)")
            params.extend([f"%{kw}%", f"%{kw}%"])

        if not conditions:
            return []

        where = " OR ".join(conditions)
        sql = f"""
            SELECT k.id, k.name, k.doc_name, k.doc_path, k.date_year, k.date
            FROM kb_knowledge_base k
            WHERE k.deleted = 0 AND ({where})
            ORDER BY k.date DESC
            LIMIT %s
        """
        params.append(top_k)

        try:
            cur.execute(sql, params)
            results = []
            for row in cur.fetchall():
                cols = [d[0] for d in cur.description]
                entry = dict(zip(cols, row))
                results.append(KnowledgeResult(
                    title=entry.get("name", ""),
                    content=entry.get("doc_name", ""),
                    source=entry.get("doc_path", ""),
                    score=0.5,  # LIKE 搜索无评分
                    metadata={"id": entry.get("id"), "year": entry.get("date_year")},
                ))
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        return True  # MySQL 始终可用


# ====== RAGFlow Provider ======

class RAGFlowProvider(KnowledgeProvider):
    """RAGFlow 语义检索 Provider"""

    def __init__(self, config: Dict):
        self.api_url = config.get("api_url", "http://localhost:9380")
        self.dataset_id = config.get("dataset_id", "")
        self.api_key = config.get("api_key", "")

    def search(self, query: str, top_k: int = 5, **kwargs) -> List[KnowledgeResult]:
        try:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = requests.post(
                f"{self.api_url}/api/v1/retrieval",
                json={
                    "question": query,
                    "dataset_ids": [self.dataset_id],
                    "top_k": top_k,
                },
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for chunk in data.get("chunks", []):
                results.append(KnowledgeResult(
                    title=chunk.get("document_name", ""),
                    content=chunk.get("content", ""),
                    source=chunk.get("document_url", ""),
                    score=chunk.get("similarity", 0.0),
                    metadata={"chunk_id": chunk.get("id")},
                ))
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        try:
            import requests
            resp = requests.get(f"{self.api_url}/api/v1/datasets", timeout=5)
            return resp.status_code == 200
        except:
            return False


# ====== Elasticsearch Provider ======

class ElasticsearchProvider(KnowledgeProvider):
    """Elasticsearch 全文检索 Provider"""

    def __init__(self, config: Dict):
        self.host = config.get("host", "http://localhost:9200")
        self.index = config.get("index", "knowledge")
        self.username = config.get("username", "elastic")
        self.password = config.get("password", "")

    def search(self, query: str, top_k: int = 5, **kwargs) -> List[KnowledgeResult]:
        try:
            import requests
            auth = (self.username, self.password) if self.username else None
            resp = requests.post(
                f"{self.host}/{self.index}/_search",
                json={
                    "query": {"match": {"content": query}},
                    "size": top_k,
                    "highlight": {"fields": {"content": {"fragment_size": 500}}},
                },
                auth=auth,
                verify=False,
                timeout=30,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for hit in data.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                highlight = hit.get("highlight", {}).get("content", [""])[0]
                results.append(KnowledgeResult(
                    title=source.get("meta", {}).get("title", ""),
                    content=highlight or source.get("content", "")[:500],
                    source=source.get("file", {}).get("filename", ""),
                    score=hit.get("_score", 0.0),
                    metadata={"id": hit.get("_id")},
                ))
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        try:
            import requests
            auth = (self.username, self.password) if self.username else None
            resp = requests.get(f"{self.host}/_cluster/health", auth=auth, verify=False, timeout=5)
            return resp.status_code == 200
        except:
            return False


# ====== ChromaDB Provider ======

class ChromaProvider(KnowledgeProvider):
    """ChromaDB 向量检索 Provider"""

    def __init__(self, config: Dict):
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8000)
        self.collection = config.get("collection", "knowledge")

    def search(self, query: str, top_k: int = 5, **kwargs) -> List[KnowledgeResult]:
        try:
            import chromadb
            client = chromadb.HttpClient(host=self.host, port=self.port)
            collection = client.get_collection(self.collection)
            results = collection.query(query_texts=[query], n_results=top_k)

            knowledge_results = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                distance = results.get("distances", [[]])[0][i] if results.get("distances") else 1.0
                knowledge_results.append(KnowledgeResult(
                    title=metadata.get("title", ""),
                    content=doc,
                    source=metadata.get("source", ""),
                    score=max(0, 1 - distance),  # 距离转分数
                    metadata=metadata,
                ))
            return knowledge_results
        except Exception:
            return []

    def is_available(self) -> bool:
        try:
            import chromadb
            client = chromadb.HttpClient(host=self.host, port=self.port)
            return client.heartbeat() > 0
        except:
            return False


# ====== HTTP 自定义 Provider ======

class HTTPProvider(KnowledgeProvider):
    """自定义 HTTP API Provider — 对接任意 REST 接口"""

    def __init__(self, config: Dict):
        self.url = config.get("url", "")
        self.method = config.get("method", "POST")
        self.headers = config.get("headers", {})
        self.query_field = config.get("query_field", "question")
        self.result_path = config.get("result_path", "data")
        self.title_field = config.get("title_field", "title")
        self.content_field = config.get("content_field", "content")
        self.score_field = config.get("score_field", "score")

    def search(self, query: str, top_k: int = 5, **kwargs) -> List[KnowledgeResult]:
        try:
            import requests
            body = {self.query_field: query, "top_k": top_k}
            resp = requests.request(
                method=self.method,
                url=self.url,
                json=body,
                headers=self.headers,
                timeout=30,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            # 按 result_path 提取结果列表
            items = data
            for key in self.result_path.split("."):
                if key:
                    items = items.get(key, [])

            results = []
            for item in items:
                results.append(KnowledgeResult(
                    title=item.get(self.title_field, ""),
                    content=item.get(self.content_field, ""),
                    source=item.get("source", ""),
                    score=float(item.get(self.score_field, 0)),
                    metadata=item,
                ))
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        return bool(self.url)


# ====== Provider 注册中心 ======

class ProviderRegistry:
    """Provider 注册中心"""

    def __init__(self):
        self._providers: Dict[str, KnowledgeProvider] = {}
        self._default = "mysql"

    def register(self, name: str, provider: KnowledgeProvider):
        """注册 Provider"""
        self._providers[name] = provider

    def get(self, name: str) -> Optional[KnowledgeProvider]:
        """获取 Provider"""
        return self._providers.get(name)

    def get_default(self) -> KnowledgeProvider:
        """获取默认 Provider"""
        return self._providers.get(self._default, MySQLProvider())

    def list_providers(self) -> List[str]:
        """列出所有已注册的 Provider"""
        return list(self._providers.keys())

    def set_default(self, name: str):
        """设置默认 Provider"""
        self._default = name

    def auto_detect(self) -> str:
        """自动检测可用的最佳 Provider"""
        # 优先级: ragflow > chroma > elasticsearch > mysql
        priority = ["ragflow", "chroma", "elasticsearch", "http", "mysql"]
        for name in priority:
            provider = self._providers.get(name)
            if provider and provider.is_available():
                return name
        return "mysql"


# ====== 全局注册中心 ======

_registry = ProviderRegistry()

# 注册默认 Provider
_registry.register("mysql", MySQLProvider())


def register_provider(name: str, provider: KnowledgeProvider):
    """注册自定义 Provider"""
    _registry.register(name, provider)


def register_ragflow(config: Dict):
    """注册 RAGFlow Provider"""
    _registry.register("ragflow", RAGFlowProvider(config))


def register_elasticsearch(config: Dict):
    """注册 Elasticsearch Provider"""
    _registry.register("elasticsearch", ElasticsearchProvider(config))


def register_chroma(config: Dict):
    """注册 ChromaDB Provider"""
    _registry.register("chroma", ChromaProvider(config))


def register_http(config: Dict):
    """注册自定义 HTTP Provider"""
    _registry.register("http", HTTPProvider(config))


# ====== 统一检索接口 ======

def search_knowledge(
    query: str,
    top_k: int = 5,
    provider: str = None,
    conn=None,
    **kwargs,
) -> List[KnowledgeResult]:
    """统一知识检索接口

    Args:
        query: 查询文本
        top_k: 返回结果数量
        provider: Provider 名称（None=自动检测）
        conn: MySQL 连接（MySQL Provider 需要）
        **kwargs: Provider 特定参数

    Returns:
        list of KnowledgeResult
    """
    if provider:
        p = _registry.get(provider)
    else:
        p = _registry.get_default()

    if not p:
        p = MySQLProvider()

    # MySQL provider 需要 conn 参数
    if isinstance(p, MySQLProvider):
        return p.search(query, top_k=top_k, conn=conn, **kwargs)

    return p.search(query, top_k=top_k, **kwargs)


def list_providers() -> List[Dict]:
    """列出所有 Provider 及其状态"""
    result = []
    for name in _registry.list_providers():
        p = _registry.get(name)
        result.append({
            "name": name,
            "available": p.is_available() if p else False,
            "type": type(p).__name__,
        })
    return result
