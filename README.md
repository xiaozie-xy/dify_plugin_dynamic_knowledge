# Dynamic Knowledge Retrieval

**Author:** xiaozie-xy  
**Version:** 0.0.1  
**Type:** Tool plugin

## Overview

Dynamic Knowledge Retrieval is a Dify tool plugin. It searches the knowledge base identified by a dataset ID passed in at runtime.

The built-in knowledge retrieval node stores dataset IDs in the workflow graph, so one run cannot switch to another dataset. This plugin adds a `dataset_id` parameter. Pass the knowledge base ID that matches the current task.

## Features

- **Runtime dataset selection.** Each run searches the knowledge base given by `dataset_id`.
- **Search method.** Follow the dataset setting, or override it with semantic, full-text, keyword, or hybrid search.
- **Result size and score.** Set top K and an optional score threshold.
- **Rerank.** Pick a rerank model configured in the workspace. When rerank is off, the dataset setting is kept.
- **Hybrid weights.** Follow the saved dataset weights, or use semantic-first, keyword-first, or custom weights. Embedding model names come from the dataset.
- **Metadata filters.** Optional. Pass conditions as a JSON array. Each item has a field name, comparison operator, and value. Combine them with and or or. Leave the array empty to skip filtering.
- **Attachments.** Optionally pass attachment IDs for multimodal retrieval.
- **Two outputs.** `result` is the chunk list. `context` is the joined text.

## Installation

Upload `dynamic_knowledge-0.0.1.difypkg` on the Dify plugins page. If a self-hosted instance rejects the unsigned local package, turn off forced plugin signature checks in the deployment configuration and install it again. Then enter the knowledge API base URL and an API key scoped to all knowledge bases.

## Configuration

### Provider credentials

Configure these once. This key is not an application API key.

| Parameter | Description | Required |
|-----------|-------------|:--------:|
| `api_base` | Knowledge service API base URL, including `/v1`. Cloud: `https://api.dify.ai/v1`. From the plugin daemon in Docker Compose, usually `http://api:5001/v1`. | Yes |
| `dataset_api_key` | Create it under Knowledge → Service API. Scope it to all knowledge bases when each run may search a different dataset. A key scoped to one dataset can access only that dataset. | Yes |

### Tool parameters

**Bound from workflow variables**

| Parameter | Description | Required |
|-----------|-------------|:--------:|
| `dataset_id` | UUID of the knowledge base to search. Pass the ID that matches the current task. | Yes |
| `query` | Search text, up to 250 characters. Put only what to look up here. Leave formatting or extraction instructions to the downstream LLM node. | Yes |
| `attachment_ids` | Optional comma-separated attachment IDs. Example: `3f1c2a90-xxx-xxx,8c0d1e2f-xxx-xxx`. Leave empty for text-only search. | No |
| `metadata_conditions` | Optional JSON string. Example: `[{"name":"year","comparison_operator":"is","value":"2024"}]`. Operators are listed below. Leave empty to skip metadata filtering. | No |

**Set on the tool node**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `search_method` | Follow the dataset, or use semantic, full-text, keyword, or hybrid search. | Follow dataset |
| `top_k` | Maximum number of chunks, from 1 to 50. | 4 |
| `score_threshold_enabled` | Off keeps the dataset score setting. On uses the threshold below. | Off |
| `score_threshold` | Score threshold from 0 to 1. Used only when the threshold is enabled. | None |
| `reranking_enable` | Off keeps the dataset rerank setting. On uses the selected model. | Off |
| `reranking_model` | A rerank model configured in this workspace. | None |
| `hybrid_weight_type` | Follow dataset, semantic first, keyword first, or custom. | Follow dataset |
| `vector_weight` | Semantic weight from 0 to 1 when weights are custom. Keyword weight is 1 minus this value. | 0.7 |
| `metadata_logical_operator` | How to combine conditions: and or or. | and |

## Screenshots

Bind the dataset ID and query for the current run. Leave attachment IDs and metadata conditions empty when they are not needed. Search method follows the dataset by default.

![Inputs and search method](_assets/workflow-inputs.png)

Top K, score threshold, the rerank model, and hybrid weights are set in the node's retrieval settings.

![Retrieval settings](_assets/workflow-settings.png)

## Examples

Search one knowledge base for the current task:

```text
dataset_id: 550e8400-e29b-41d4-a716-446655440000
query: search text
search_method: follow_dataset
top_k: 4
```

Include two attachments:

```text
attachment_ids: 3f1c2a90-xxx-xxx,8c0d1e2f-xxx-xxx
```

Hybrid search with custom weights and two metadata conditions:

```text
search_method: hybrid_search
hybrid_weight_type: customized
vector_weight: 0.6
metadata_logical_operator: and
metadata_conditions: [{"name":"category","comparison_operator":"is","value":"report"},{"name":"year","comparison_operator":"is","value":"2024"}]
```

Semantic first uses semantic weight 0.7 and keyword weight 0.3. Keyword first reverses those values. When rerank is off, the plugin sends weighted-score mode.

### Metadata comparison operators

Field definitions follow the official docs: [metadata filtering conditions](https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval#body-retrieval-model-metadata-filtering-conditions-one-of-0).

`comparison_operator` must be one of the values below.

| Operator | Meaning | Example |
|----------|---------|---------|
| `contains` | Contains the text | `{"name":"title","comparison_operator":"contains","value":"report"}` |
| `not contains` | Does not contain the text | `{"name":"title","comparison_operator":"not contains","value":"draft"}` |
| `start with` | Starts with the text | `{"name":"code","comparison_operator":"start with","value":"A"}` |
| `end with` | Ends with the text | `{"name":"filename","comparison_operator":"end with","value":".pdf"}` |
| `is` | Equals | `{"name":"year","comparison_operator":"is","value":"2024"}` |
| `is not` | Does not equal | `{"name":"status","comparison_operator":"is not","value":"draft"}` |
| `empty` | Is empty. `value` may be omitted | `{"name":"author","comparison_operator":"empty"}` |
| `not empty` | Is not empty. `value` may be omitted | `{"name":"author","comparison_operator":"not empty"}` |
| `in` | Is one of the values. Separate items with commas | `{"name":"category","comparison_operator":"in","value":"report,notice"}` |
| `not in` | Is none of the values | `{"name":"category","comparison_operator":"not in","value":"draft,test"}` |
| `=` `≠` `>` `<` `≥` `≤` | Numeric comparison. `value` must be a number | `{"name":"score","comparison_operator":"≥","value":"80"}` |
| `before` | Earlier than | `{"name":"date","comparison_operator":"before","value":"2024-01-01"}` |
| `after` | Later than | `{"name":"date","comparison_operator":"after","value":"2023-12-31"}` |

## Workflow

```text
Start
  dataset_id = knowledge base ID for this task
  query      = text to look up
        |
        v
Dynamic Knowledge Retrieval
  Read the dataset's saved retrieval settings
  Overlay the parameters for this call
  Call the knowledge retrieve API
        |
        v
Downstream LLM
  Use context as the retrieved text
  Use result when scores, titles, or document IDs are needed
```

Creating, uploading, waiting for indexing, and deleting datasets stay with the caller. The target dataset's indexing status should be completed before this tool runs.

## Outputs

| Output | Description |
|--------|-------------|
| `result` | Array of chunks. Each item has `content`, `title`, `score`, `metadata`, `document_id`, `segment_id`, `dataset_id`, `dataset_name`, `position`, `segment_position`, `segment_word_count`, `segment_hit_count`, `child_chunks`, `files`, and `summary`. `metadata` is the document's own metadata. `content` is the parent chunk. Child chunks stay in `child_chunks`. `files` and `summary` are null when the segment has none. |
| `context` | Chunk `content` values joined with blank lines, ready for an LLM prompt. |
| Text message | Same as `context`. When nothing matches, the text says that no chunks were retrieved. |

## Limitations

- The query is limited to 250 characters.
- Retrieval can return nothing, or the API can report that the dataset is still initializing, while indexing is incomplete.
- Hybrid search needs saved dataset weights, rerank enabled in the plugin, or a hybrid weight choice.
- Custom weights replace the dataset setting only when the search method is hybrid.
- This plugin does not create, upload to, or delete knowledge bases.
- The retrieve API records the query on the knowledge base hit-testing page.

## Requirements

- Dify 1.17.1. Developed against this version. Test other versions yourself.
- Python 3.12

## License

[Apache License 2.0](https://github.com/xiaozie-xy/dify_plugin_dynamic_knowledge/blob/main/LICENSE).

## Links

- [Source repository](https://github.com/xiaozie-xy/dify_plugin_dynamic_knowledge)
- [Retrieve Chunks from a Knowledge Base / Test Retrieval](https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval)
- [Metadata filtering conditions](https://docs.dify.ai/en/api-reference/knowledge-bases/retrieve-chunks-from-a-knowledge-base-test-retrieval#body-retrieval-model-metadata-filtering-conditions-one-of-0)
- [Knowledge API guide](https://docs.dify.ai/en/api-reference/guides/knowledge)
- [Dify](https://dify.ai/)
