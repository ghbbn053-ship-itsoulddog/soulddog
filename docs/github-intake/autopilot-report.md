# GitHub Autopilot Report

- Generated at: 2026-04-21 22:30:58
- Detected topics: rag, skill_plugin, multi_agent, workflow, mcp, evaluation

## Top Repositories

| Repo | Topic | Score | Stars | Size(KB) | Pushed | License |
|---|---|---:|---:|---:|---|---|
| openai/openai-agents-python | multi_agent | 1.0201 | 24276 | 27799 | 2026-04-21 | MIT |
| langchain-ai/langchain | rag | 1.0200 | 134349 | 537245 | 2026-04-21 | MIT |
| neuml/txtai | rag | 0.9822 | 12410 | 55761 | 2026-04-21 | Apache-2.0 |
| microsoft/agent-framework | multi_agent | 0.9679 | 9658 | 90051 | 2026-04-21 | MIT |
| langchain-ai/langgraph | rag | 0.9518 | 29863 | 517445 | 2026-04-21 | MIT |
| raga-ai-hub/RagaAI-Catalyst | rag | 0.9498 | 16140 | 58519 | 2026-02-11 | Apache-2.0 |
| pathwaycom/pathway | rag | 0.9341 | 63445 | 141829 | 2026-04-21 | NOASSERTION |
| deepset-ai/haystack | rag | 0.9215 | 24932 | 60792 | 2026-04-21 | Apache-2.0 |
| darrenhinde/OpenAgentsControl | multi_agent | 0.8936 | 3612 | 5191 | 2026-03-25 | MIT |
| blazickjp/arxiv-mcp-server | mcp | 0.8831 | 2571 | 305 | 2026-04-06 | Apache-2.0 |
| guy-hartstein/company-research-agent | multi_agent | 0.8663 | 1684 | 32374 | 2026-04-17 | Apache-2.0 |
| yzhao062/pyod | workflow | 0.8657 | 9809 | 45120 | 2026-04-16 | BSD-2-Clause |
| cocoindex-io/cocoindex | rag | 0.8491 | 6924 | 109255 | 2026-04-21 | Apache-2.0 |
| utensils/mcp-nixos | mcp | 0.7987 | 597 | 2958 | 2026-04-03 | MIT |
| GongRzhe/Office-PowerPoint-MCP-Server | mcp | 0.7924 | 1654 | 69663 | 2025-12-31 | MIT |
| cheshire-cat-ai/core | skill_plugin | 0.7768 | 3030 | 15026 | 2026-03-14 | GPL-3.0 |
| ModelEngine-Group/fit-framework | skill_plugin | 0.7552 | 2111 | 16867 | 2026-03-13 | MIT |
| PySpur-Dev/pyspur | workflow | 0.7502 | 5713 | 86943 | 2025-07-20 | Apache-2.0 |
| loonghao/photoshop-python-api-mcp-server | mcp | 0.7471 | 206 | 1193 | 2026-04-15 | MIT |
| joenorton/comfyui-mcp-server | mcp | 0.7264 | 286 | 371 | 2026-02-17 | Apache-2.0 |
| BlazeUp-AI/Observal | evaluation | 0.7084 | 570 | 4567 | 2026-04-21 | NOASSERTION |
| InfinitiBit/graphbit | workflow | 0.7000 | 529 | 118280 | 2026-04-15 | Apache-2.0 |
| dedalus-labs/dedalus-mcp-python | mcp | 0.6775 | 154 | 2118 | 2026-01-28 | MIT |
| kreuzberg-dev/kreuzberg | rag | 0.6746 | 7616 | 627300 | 2026-04-21 | NOASSERTION |
| oxwhirl/pymarl | multi_agent | 0.6340 | 2180 | 283 | 2022-12-08 | Apache-2.0 |

## Integration Recommendations

1. `openai/openai-agents-python` -> 接入 backend/app/services/agent_runtime.py，扩展 framework 分派与路由策略 (stars=24276, pushed=2026-04-21, lang=Python)
2. `langchain-ai/langchain` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=134349, pushed=2026-04-21, lang=Python)
3. `neuml/txtai` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=12410, pushed=2026-04-21, lang=Python)
4. `microsoft/agent-framework` -> 接入 backend/app/services/agent_runtime.py，扩展 framework 分派与路由策略 (stars=9658, pushed=2026-04-21, lang=Python)
5. `langchain-ai/langgraph` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=29863, pushed=2026-04-21, lang=Python)
6. `raga-ai-hub/RagaAI-Catalyst` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=16140, pushed=2026-02-11, lang=Python)
7. `pathwaycom/pathway` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=63445, pushed=2026-04-21, lang=Python)
8. `deepset-ai/haystack` -> 映射到 backend/app/services/vector_store.py 与检索过滤策略 (stars=24932, pushed=2026-04-21, lang=MDX)
9. `darrenhinde/OpenAgentsControl` -> 接入 backend/app/services/agent_runtime.py，扩展 framework 分派与路由策略 (stars=3612, pushed=2026-03-25, lang=TypeScript)
10. `blazickjp/arxiv-mcp-server` -> 映射到 backend/app/services/mcp_registry.py，新增 registry adapter (stars=2571, pushed=2026-04-06, lang=Python)

## Clone Status

- `openai/openai-agents-python`: ok (exists)
- `langchain-ai/langchain`: ok (exists)
- `neuml/txtai`: fail (Cloning into 'C:\Users\ASUS\Desktop\智能体构建\project_20260404_235124\vendor\autopilot\neuml__txtai'...
error: RPC failed; curl 18 transfer closed with outstanding read data remaining
error: 5481 bytes of body are still expected
fetch-pack: unexpected disconnect while reading sideband packet
fatal: early EOF
fatal: fetch-pack: invalid index-pack output)