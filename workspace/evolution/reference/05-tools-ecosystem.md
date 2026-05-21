# 全球开发者工具生态 — MCP/Agent/Skills 汇总

## 生态规模 (2026年5月)
- 公开MCP服务器: ~17,500+
- SDK月下载: ~9700万次
- 治理: Linux Foundation Agentic AI Foundation
- 共同发起: Anthropic, OpenAI, Google, Microsoft, AWS, GitHub, Cloudflare, Block

## 我们当前已接入的MCP工具
- Claude Preview (预览/截图/控制台/网络)
- Claude in Chrome (浏览器自动化)
- CCD Session (会话管理/工作区)
- Scheduled Tasks (定时任务)
- Playwright (浏览器操作)
- Baton (检查点/日总结)

## 尚未接入但应该学习的顶级工具

### 开发类
| 工具 | 用途 | 为什么重要 |
|------|------|-----------|
| GitHub MCP | 仓库管理、PR、Issues | 网络通后第一时间接入 |
| Firecrawl MCP | 网页抓取(85K⭐) | 替代WebSearch做更深度研究 |
| Context7 MCP | 版本化库文档(3500+框架) | 实时最新技术文档 |
| E2B MCP | 安全云沙箱 | 隔离执行危险代码 |

### 推理类
| 工具 | 用途 | 为什么重要 |
|------|------|-----------|
| Sequential Thinking MCP | 结构化逐步推理 | 增强我们自身的推理链 |
| Memory MCP | 持久化知识图谱 | 补充我们的文件记忆系统 |

### 自动化类
| 工具 | 用途 | 为什么重要 |
|------|------|-----------|
| n8n MCP (183K⭐) | 400+集成的工作流 | 我们自己的自动化的标杆 |
| Dify (137K⭐) | 开源LLM应用平台 | Agent编排参考 |

## Agent框架对比 (2026)
| 框架 | 特点 | 能借鉴什么 |
|------|------|-----------|
| Claude Code | Agent harness, MCP原生 | 我们的基础 |
| Hermes Agent v0.11 | 可插拔传输层, 子Agent | 模块化Agent架构 |
| CrewAI | 多Agent角色协作 | Alpha/Beta以外的协作模式 |
| LangGraph | 图状态机编排 | 复杂工作流可视化 |
| OpenAI Agents SDK | 原生Agent训练 | 工具调用DAG模式 |

## 关键趋势
1. **远程MCP爆发**: 自2025年5月以来增长4倍
2. **MCP工具搜索**: Claude Code将工具定义token从77K降到8.7K(降85%)
3. **Agent脚手架>模型**: 同样的模型, 好的脚手架能多22分
4. **OAuth替换API Key**: 安全范式迁移

## 我们的待接入清单 (网络通后)
1. Sequential Thinking MCP → 增强推理链
2. Context7 MCP → 实时技术文档
3. Memory MCP → 知识图谱持久化
4. GitHub MCP → 代码仓库管理
5. n8n/Dify → 工作流自动化参考
