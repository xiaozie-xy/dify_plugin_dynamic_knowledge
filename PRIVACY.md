## Privacy Policy

This plugin sends the configured knowledge-base API key, the runtime `dataset_id`, and the search query to the Dify service API address you enter. It does not add another storage service.

### Data Collection

- The knowledge-base API key is stored by Dify as a plugin credential.
- Each invocation sends `dataset_id`, the query text, and the retrieval settings to that Dify API.
- The plugin process does not write queries or retrieved chunks to its own database.

### Data Usage

Retrieved chunks are returned to the Dify workflow that invoked the tool. The only external endpoint is the Dify knowledge-base API URL configured in the plugin credentials.

### Data Retention

The plugin does not retain request or response bodies after the tool invocation finishes. Credential storage and workflow logs follow the Dify instance where the plugin is installed.

### Contact

Maintainer: xiaozie-xy@foxmail.com

You can also open an issue at https://github.com/xiaozie-xy/dify_plugin_dynamic_knowledge/issues.

Privacy questions about a local installation should also go to the operator of that Dify instance.
