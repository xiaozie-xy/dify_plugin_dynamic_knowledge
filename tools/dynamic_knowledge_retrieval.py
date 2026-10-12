from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import retrieve


class DynamicKnowledgeRetrievalTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        retrieved = retrieve(self.runtime.credentials, tool_parameters)
        yield self.create_variable_message("result", retrieved["result"])
        yield self.create_variable_message("context", retrieved["context"])
        yield self.create_json_message(
            {
                "dataset_id": retrieved["dataset_id"],
                "query": retrieved["query"],
                "result": retrieved["result"],
            }
        )
        yield self.create_text_message(retrieved["context"] or "未检索到分段。")
