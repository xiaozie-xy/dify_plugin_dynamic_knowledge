"""Call the Dify knowledge-base service API and shape retrieval results."""

from __future__ import annotations

import ast
import json
import uuid
import urllib.error
import urllib.request
from typing import Any

QUERY_MAX_LENGTH = 250
DEFAULT_TIMEOUT = 60


class DatasetApiError(Exception):
    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(format_api_error(status, payload))


def format_api_error(status: int, payload: Any) -> str:
    if isinstance(payload, dict):
        code = payload.get("code") or payload.get("error") or ""
        message = payload.get("message") or payload.get("error_msg") or ""
        if code and message:
            return f"知识库接口错误 {status} {code}: {message}"
        if message:
            return f"知识库接口错误 {status}: {message}"
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return f"知识库接口错误 {status}: {text}"


def normalize_base_url(api_base: str | None) -> str:
    if not api_base or not str(api_base).strip():
        raise ValueError("请填写 API 地址，例如 https://api.dify.ai/v1 或 http://api:5001/v1")
    base = str(api_base).strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("API 地址需要以 http:// 或 https:// 开头")
    if base.endswith("/datasets"):
        base = base[: -len("/datasets")]
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def normalize_dataset_id(dataset_id: str | None) -> str:
    if dataset_id is None or not str(dataset_id).strip():
        raise ValueError("dataset_id 不能为空。请把本次要检索的知识库 ID 绑到这个参数。")
    raw = str(dataset_id).strip()
    try:
        return str(uuid.UUID(raw))
    except ValueError as exc:
        raise ValueError("dataset_id 需要是知识库 UUID。") from exc


def normalize_query(query: str | None) -> str:
    if query is None or not str(query).strip():
        raise ValueError("查询文本不能为空。")
    text = str(query).strip()
    if len(text) > QUERY_MAX_LENGTH:
        raise ValueError(
            f"查询文本最长 {QUERY_MAX_LENGTH} 个字符，当前 {len(text)} 个。"
            "请缩短检索词，把提取规则留在后续 LLM 节点。"
        )
    return text


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"top_k 需要是整数，当前为 {value}") from exc


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"分数阈值需要是数字，当前为 {value}") from exc


def parse_literal(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None


def parse_mapping(value: str) -> dict[str, Any] | None:
    """Dify 有时把 model-selector 传成 Python 字典字符串，单引号，不是 JSON。"""
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        loaded = None
    if isinstance(loaded, dict):
        return loaded
    try:
        loaded = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def parse_rerank_selector(value: Any) -> tuple[str, str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        value = parse_mapping(text)
    if not isinstance(value, dict):
        return None
    provider = str(
        value.get("provider") or value.get("reranking_provider_name") or ""
    ).strip()
    model_name = str(
        value.get("model")
        or value.get("model_name")
        or value.get("name")
        or value.get("reranking_model_name")
        or ""
    ).strip()
    if not provider or not model_name:
        return None
    return provider, model_name


METADATA_OPERATORS = {
    "contains",
    "not contains",
    "start with",
    "end with",
    "is",
    "is not",
    "empty",
    "not empty",
    "in",
    "not in",
    "=",
    "≠",
    ">",
    "<",
    "≥",
    "≤",
    "before",
    "after",
}
NUMERIC_OPERATORS = {"=", "≠", ">", "<", "≥", "≤"}
LIST_OPERATORS = {"in", "not in"}
EMPTY_OPERATORS = {"empty", "not empty"}


def metadata_condition_value(operator: str, raw_value: Any) -> Any:
    if operator in EMPTY_OPERATORS:
        return None
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError("元数据条件缺少比较值。empty 和 not empty 可以不填 value。")
    text = str(raw_value).strip()
    if operator in LIST_OPERATORS:
        values = [part.strip() for part in text.split(",") if part.strip()]
        if not values:
            raise ValueError("in 和 not in 的过滤值要用逗号分隔，至少包含一项。")
        return values
    if operator in NUMERIC_OPERATORS:
        try:
            number = float(text)
        except ValueError as exc:
            raise ValueError(f"数值比较的过滤值需要是数字，当前为 {text}") from exc
        if number.is_integer():
            return int(number)
        return number
    return text


def parse_attachment_ids(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        items = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("["):
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                loaded = None
            items = loaded if isinstance(loaded, list) else text.split(",")
        else:
            items = text.split(",")
    ids = [str(item).strip() for item in items if str(item).strip()]
    return ids or None


def hybrid_weights(weight_type: str, vector_weight: Any) -> tuple[float, float]:
    if weight_type == "semantic_first":
        return 0.7, 0.3
    if weight_type == "keyword_first":
        return 0.3, 0.7
    if weight_type != "customized":
        raise ValueError(f"不支持的混合检索权重：{weight_type}")
    vector = as_float(vector_weight)
    if vector is None:
        vector = 0.7
    if vector < 0 or vector > 1:
        raise ValueError("语义权重需要在 0 到 1 之间。")
    vector = round(float(vector), 4)
    return vector, round(1 - vector, 4)


def apply_hybrid_weights(
    model: dict[str, Any],
    parameters: dict[str, Any],
    dataset: dict[str, Any] | None,
    rerank_enabled: bool,
) -> None:
    weight_type = str(parameters.get("hybrid_weight_type") or "follow_dataset").strip() or "follow_dataset"
    if weight_type == "follow_dataset" or model.get("search_method") != "hybrid_search":
        return
    vector_weight, keyword_weight = hybrid_weights(weight_type, parameters.get("vector_weight"))
    dataset = dataset or {}
    existing = model.get("weights") if isinstance(model.get("weights"), dict) else {}
    vector_setting = existing.get("vector_setting") if isinstance(existing.get("vector_setting"), dict) else {}
    provider = str(
        dataset.get("embedding_model_provider") or vector_setting.get("embedding_provider_name") or ""
    ).strip()
    embedding_name = str(
        dataset.get("embedding_model") or vector_setting.get("embedding_model_name") or ""
    ).strip()
    if not provider or not embedding_name:
        raise ValueError("该知识库没有嵌入模型，无法设置混合检索权重。")
    model["weights"] = {
        "weight_type": weight_type,
        "vector_setting": {
            "vector_weight": vector_weight,
            "embedding_provider_name": provider,
            "embedding_model_name": embedding_name,
        },
        "keyword_setting": {"keyword_weight": keyword_weight},
    }
    if not rerank_enabled:
        model["reranking_enable"] = False
        model["reranking_mode"] = "weighted_score"


def metadata_condition(name: str, operator: str, raw_value: Any) -> dict[str, Any]:
    if operator not in METADATA_OPERATORS:
        raise ValueError(f"不支持的元数据比较符：{operator}")
    return {
        "name": name,
        "comparison_operator": operator,
        "value": metadata_condition_value(operator, raw_value),
    }


def conditions_from_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError(
            "多条元数据条件需要是 JSON 数组，例如 "
            '[{"name":"year","comparison_operator":"is","value":"2024"}]。'
        )
    conditions: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("每条元数据条件都需要是对象，并包含 name 和 comparison_operator。")
        name = str(item.get("name") or "").strip()
        operator = str(item.get("comparison_operator") or item.get("operator") or "is").strip() or "is"
        if not name:
            raise ValueError("元数据条件缺少字段名 name。")
        conditions.append(metadata_condition(name, operator, item.get("value")))
    return conditions


def build_metadata_filter(parameters: dict[str, Any]) -> dict[str, Any] | None:
    extra = parameters.get("metadata_conditions")
    if isinstance(extra, str):
        extra = extra.strip()
    if extra in (None, ""):
        return None
    parsed = extra if isinstance(extra, list) else parse_literal(str(extra))
    conditions = conditions_from_list(parsed)
    if not conditions:
        return None

    logical_operator = str(parameters.get("metadata_logical_operator") or "and").strip() or "and"
    if logical_operator not in {"and", "or"}:
        raise ValueError("元数据组合方式只支持 and 或 or。")
    return {"logical_operator": logical_operator, "conditions": conditions}


def default_retrieval_model() -> dict[str, Any]:
    return {
        "search_method": "semantic_search",
        "reranking_enable": False,
        "reranking_mode": "reranking_model",
        "reranking_model": {
            "reranking_provider_name": "",
            "reranking_model_name": "",
        },
        "top_k": 4,
        "score_threshold_enabled": False,
    }


def build_retrieval_model(
    dataset_model: dict[str, Any] | None,
    parameters: dict[str, Any],
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = dict(dataset_model or default_retrieval_model())
    search_method = str(parameters.get("search_method") or "follow_dataset")
    if search_method != "follow_dataset":
        model["search_method"] = search_method

    top_k = as_int(parameters.get("top_k"), 4)
    if top_k is None or top_k < 1:
        raise ValueError("top_k 需要是大于 0 的整数。")
    model["top_k"] = top_k

    # 关闭时保留知识库自己的 Rerank / 阈值。打开后才用本节点选择的模型覆盖。
    rerank_enabled = as_bool(parameters.get("reranking_enable"), False)
    if rerank_enabled:
        selected = parse_rerank_selector(parameters.get("reranking_model"))
        if selected is None:
            raise ValueError("已开启 Rerank，请在模型列表中选择一个 Rerank 模型。")
        provider_name, model_name = selected
        model["reranking_enable"] = True
        model["reranking_mode"] = "reranking_model"
        model["reranking_model"] = {
            "reranking_provider_name": provider_name,
            "reranking_model_name": model_name,
        }

    if as_bool(parameters.get("score_threshold_enabled"), False):
        threshold = as_float(parameters.get("score_threshold"))
        if threshold is None:
            raise ValueError("已开启分数阈值，请填写 score_threshold。")
        model["score_threshold_enabled"] = True
        model["score_threshold"] = threshold

    apply_hybrid_weights(model, parameters, dataset, rerank_enabled)

    metadata_filter = build_metadata_filter(parameters)
    if metadata_filter is not None:
        model["metadata_filtering_conditions"] = metadata_filter

    if (
        model.get("search_method") == "hybrid_search"
        and not model.get("weights")
        and not model.get("reranking_enable")
    ):
        raise ValueError(
            "混合检索需要该知识库已保存的权重，或在插件中开启 Rerank。"
            "请先在该知识库的检索设置里保存混合检索，或把检索方式改为向量检索。"
        )
    return {key: value for key, value in model.items() if value is not None}


def map_child_chunks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    chunks: list[dict[str, Any]] = []
    for chunk in raw:
        if not isinstance(chunk, dict):
            continue
        chunks.append(
            {
                "id": chunk.get("id") or "",
                "content": str(chunk.get("content") or ""),
                "position": chunk.get("position"),
                "score": chunk.get("score"),
            }
        )
    return chunks


def map_files(raw: Any) -> list[dict[str, Any]] | None:
    if not isinstance(raw, list):
        return None
    files: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        files.append(
            {
                "id": item.get("id") or "",
                "name": item.get("name") or "",
                "extension": item.get("extension") or "",
                "mime_type": item.get("mime_type") or "",
                "size": item.get("size"),
                "source_url": item.get("source_url") or "",
            }
        )
    return files or None


def map_summary(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def map_records(
    payload: dict[str, Any],
    dataset_id: str = "",
    dataset_name: str = "",
) -> list[dict[str, Any]]:
    records = payload.get("records") or []
    if not isinstance(records, list):
        raise ValueError("知识库接口返回的 records 不是数组。")

    result: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        segment = record.get("segment") if isinstance(record.get("segment"), dict) else {}
        document = segment.get("document") if isinstance(segment.get("document"), dict) else {}
        metadata = document.get("doc_metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        result.append(
            {
                "content": str(segment.get("content") or segment.get("answer") or ""),
                "title": document.get("name") or "",
                "score": record.get("score"),
                "metadata": metadata,
                "document_id": segment.get("document_id") or document.get("id") or "",
                "segment_id": segment.get("id") or "",
                "dataset_id": dataset_id,
                "dataset_name": dataset_name,
                "position": index,
                "segment_position": segment.get("position"),
                "segment_word_count": segment.get("word_count"),
                "segment_hit_count": segment.get("hit_count"),
                "child_chunks": map_child_chunks(record.get("child_chunks")),
                "files": map_files(record.get("files")),
                "summary": map_summary(record.get("summary")),
            }
        )
    return result


def join_context(result: list[dict[str, Any]]) -> str:
    parts = [str(item.get("content") or "").strip() for item in result]
    return "\n\n".join(part for part in parts if part)


def request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    if not api_key or not str(api_key).strip():
        raise ValueError("请填写知识库 API Key。")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {str(api_key).strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        raise DatasetApiError(exc.code, parsed) from exc
    except urllib.error.URLError as exc:
        raise ValueError(
            "无法连接知识库 API。"
            "请确认插件进程能访问所填地址。自部署常见写法是 http://api:5001/v1。"
            f"原因: {exc.reason}"
        ) from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("知识库接口返回的不是 JSON。") from exc


def validate_credentials(credentials: dict[str, Any]) -> None:
    base = normalize_base_url(credentials.get("api_base"))
    api_key = str(credentials.get("dataset_api_key") or "")
    try:
        request_json("GET", f"{base}/datasets?page=1&limit=1", api_key)
    except DatasetApiError as exc:
        if exc.status == 401:
            raise ValueError("知识库 API Key 无效。") from exc
        if exc.status == 403:
            raise ValueError(
                "当前密钥不能列出知识库。要检索运行时指定的知识库，请使用范围是「全部知识库」的知识库 API Key。"
            ) from exc
        raise


def retrieve(
    credentials: dict[str, Any],
    parameters: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    base = normalize_base_url(credentials.get("api_base"))
    api_key = str(credentials.get("dataset_api_key") or "")
    dataset_id = normalize_dataset_id(parameters.get("dataset_id"))
    query = normalize_query(parameters.get("query"))

    dataset = request_json("GET", f"{base}/datasets/{dataset_id}", api_key, timeout=timeout)
    if not isinstance(dataset, dict):
        raise ValueError("获取知识库详情失败。")
    stored_model = dataset.get("retrieval_model")
    if stored_model is not None and not isinstance(stored_model, dict):
        stored_model = None
    retrieval_model = build_retrieval_model(stored_model, parameters, dataset)
    payload: dict[str, Any] = {"query": query, "retrieval_model": retrieval_model}
    attachment_ids = parse_attachment_ids(parameters.get("attachment_ids"))
    if attachment_ids:
        payload["attachment_ids"] = attachment_ids
    retrieved = request_json(
        "POST",
        f"{base}/datasets/{dataset_id}/retrieve",
        api_key,
        payload,
        timeout=timeout,
    )
    if not isinstance(retrieved, dict):
        raise ValueError("知识库检索返回的不是对象。")
    result = map_records(retrieved, dataset_id, str(dataset.get("name") or ""))
    return {
        "dataset_id": dataset_id,
        "query": query,
        "result": result,
        "context": join_context(result),
    }
