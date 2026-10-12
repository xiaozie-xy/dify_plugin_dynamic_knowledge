from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.client import validate_credentials


class DynamicKnowledgeProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            validate_credentials(credentials)
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
