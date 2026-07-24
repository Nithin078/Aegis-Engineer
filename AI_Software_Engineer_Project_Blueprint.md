# Aegis Engineer
### Autonomous Software Engineering Platform with Repository Intelligence

## Project Description

**Aegis Engineer** is a production-grade autonomous software engineering platform built around a **Repository Intelligence Engine** — a system that deeply understands codebases through AST analysis, call graphs, dependency graphs, LSP integration, and semantic search. It uses this understanding to autonomously analyze GitHub issues, plan implementations, generate code, execute tests, review changes, and produce pull requests.

Unlike traditional coding assistants that treat repositories as flat text, Aegis Engineer builds a living knowledge graph of the codebase. Every agent — from planning to security review — queries this intelligence engine to make informed decisions. The result is not just code generation, but genuine software engineering reasoning.

---

# Objectives

- Build a Repository Intelligence Engine that understands code structure, dependencies, and semantics
- Solve GitHub issues autonomously using deep repository understanding
- Perform iterative self-correction using test feedback and static analysis
- Produce production-ready pull requests with security and performance reviews
- Learn from past fixes through repository memory and global knowledge
- Benchmark against existing tools (OpenHands, Claude Code, Cursor, Aider)
- Provide full observability: prompt timelines, reasoning traces, cost breakdowns

---

# Primary Use Cases

- Autonomous bug fixing
- Feature implementation
- Documentation updates
- Code refactoring
- Security patch generation
- Dependency migration
- Automated code review
- Repository onboarding
- Regression testing
- AI engineering research

---

# Target Users

- Software engineers
- Open-source contributors
- Enterprise engineering teams
- AI researchers
- Students building production AI systems

---

# High-Level Architecture

```text
                    ┌──────────────────────────────────┐
                    │         CLI Entry Point           │
                    │    (Typer + Textual TUI)          │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │      HTTP Server (Starlette)      │
                    │  SSE streaming + REST API routes  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │         Manager Agent             │
                    │  (Orchestration + State Machine)  │
                    └──────────────┬───────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────┐    ┌─────────────────────┐    ┌──────────────────────┐
│  Intelligence │    │    Agent Pipeline    │    │   Memory System      │
│    Layer      │    │                      │    │                      │
├───────────────┤    ├──────────────────────┤    ├──────────────────────┤
│ Repository    │───►│ 1. Issue Classifier  │───►│ Repository Memory    │
│ Intelligence  │    │ 2. Dependency        │    │ Global Memory        │
│ Engine        │    │    Analyzer          │    │ Developer Prefs      │
│               │    │ 3. Planner           │    │ Failure Memory       │
│ • AST Graph   │    │ 4. Context Retriever │    └──────────────────────┘
│ • Call Graph  │    │ 5. Doc Retriever     │
│ • Import Graph│    │ 6. Coder             │
│ • Class Graph │    │ 7. Static Analyzer   │
│ • Dep Graph   │    │ 8. Tester            │
│ • Knowledge   │    │ 9. Security Reviewer │
│ • Embeddings  │    │ 10. Perf Reviewer    │
│ • LSP         │    │ 11. Regression Det.  │
└───────────────┘    │ 12. PR Generator     │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │  Docker Sandbox       │
                     │  Formatter → Linter   │
                     │  → Tests → Review     │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │     GitHub API        │
                     │  Push → PR → Review   │
                     └──────────────────────┘

Supporting:
• SQLite (sessions, memory, config)
• Qdrant (vector DB for embeddings)
• Prometheus + Grafana (observability)
```

---

# CLI Architecture

Aegis Engineer follows a **client/server architecture** inspired by OpenCode. The backend runs as a standalone HTTP server; the TUI (Terminal User Interface) is just one possible client. The same backend can drive a web app, desktop app, or programmatic SDK.

```text
┌─────────────────────────────────────────────────────┐
│                   CLI Entry Point                    │
│                  (Typer framework)                   │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
               ▼                      ▼
     ┌─────────────────┐   ┌─────────────────────┐
     │   TUI Client    │   │  Non-Interactive     │
     │  (Textual)      │   │  Mode (run/solve)    │
     └────────┬────────┘   └──────────┬──────────┘
              │                       │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │   HTTP Server         │
              │   (Starlette + SSE)   │
              │   Port 4096 (config)  │
              ├───────────────────────┤
              │  /session    — CRUD   │
              │  /chat       — prompts│
              │  /tool       — execute│
              │  /provider   — models │
              │  /mcp        — servers│
              │  /config     — settings│
              │  /events     — SSE    │
              └───────────┬───────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │  Agent   │   │  Tool    │   │  Provider    │
    │  System  │   │  Registry│   │  Abstraction │
    └────┬─────┘   └────┬─────┘   └──────┬───────┘
         │              │                │
         └──────────────┼────────────────┘
                        ▼
              ┌──────────────────┐
              │   Event Bus      │
              │   (asyncio)      │
              └──────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Client/Server split | Enables TUI, web, desktop, SDK, and VS Code extension from one backend |
| SSE streaming | Real-time token-by-token output to any client |
| SQLite for local state | Zero-config, single-file database for sessions, config, messages |
| Tool-based architecture | LLM interacts with the world through typed, permission-gated tools |
| Provider abstraction | Swap between OpenAI, Anthropic, Gemini, local models without code changes |

### Startup Sequence

1. Parse CLI flags and arguments
2. Load hierarchical configuration (`~/.config/aegis/config.json` → project `.aegis.json`)
3. Connect to SQLite database (auto-migrate schema)
4. Initialize HTTP server on configured port
5. Launch TUI or execute non-interactive command
6. Stream events to client via SSE

---

# End-to-End Workflow

1. User submits repository + issue.
2. Clone repository.
3. Parse repository using Tree-sitter.
4. Build AST and symbol graph.
5. Index embeddings into Qdrant.
6. Read README, CONTRIBUTING and docs.
7. Planner Agent creates implementation plan.
8. Search Agent retrieves relevant code.
9. Documentation Agent fetches official API references.
10. Coding Agent generates patch.
11. Patch applied in Docker sandbox.
12. Run formatter.
13. Run linter.
14. Execute tests.
15. If tests fail:
   - analyze logs
   - revise plan
   - regenerate patch
   - retry until limit
16. Reviewer Agent checks correctness, performance, style and security.
17. Generate commit and PR description.
18. Push branch.
19. Open Pull Request.
20. Store metrics for evaluation.

---

# Multi-Agent Responsibilities

Aegis Engineer uses **13 specialized agents** organized as an engineering hierarchy. Each agent queries the Repository Intelligence Engine to make informed decisions.

```text
Manager
  ├─ Repository Intelligence Agent
  ├─ Dependency Analysis Agent
  ├─ Issue Classification Agent
  ├─ Planning Agent
  ├─ Context Retrieval Agent
  ├─ Documentation Retrieval Agent
  ├─ Coding Agent
  ├─ Static Analysis Agent
  ├─ Testing Agent
  ├─ Security Review Agent
  ├─ Performance Review Agent
  ├─ Regression Detection Agent
  └─ PR Generation Agent
```

## Manager
Coordinates the entire workflow. Routes tasks between agents, manages retries, tracks state, and handles escalation. Queries the Repository Intelligence Engine to understand which agents need to be involved for a given issue type.

## Repository Intelligence Agent
The foundation layer. Builds and maintains the Repository Intelligence Engine: AST graphs, call graphs, import graphs, dependency graphs, and the knowledge graph. Answers structural questions from other agents: "What calls this function?", "What depends on this module?", "What are the side effects of changing this class?"

## Dependency Analysis Agent
Maps external and internal dependencies. Identifies version conflicts, transitive dependencies, and breaking changes. Uses the dependency graph from the Repository Intelligence Engine to assess blast radius of changes.

## Issue Classification Agent
Analyzes GitHub issues and classifies them by type (bug, feature, refactor, security, docs), complexity (trivial, moderate, complex, epic), and affected subsystems. Feeds classification to the Planning Agent to determine strategy.

## Planning Agent
Creates the implementation plan. Queries the Repository Intelligence Engine to identify impacted files, call chain effects, and test coverage gaps. Produces a step-by-step plan with file-level specificity: "Modify `auth.py:45-80`, update `test_auth.py`, add migration in `migrations/`."

## Context Retrieval Agent
Relevant code retrieval using hybrid search: embedding similarity + graph traversal + LSP references. Unlike simple RAG, it follows call chains and import paths to retrieve truly relevant context. "Find all callers of `process_payment()`" returns the function plus its entire call tree.

## Documentation Retrieval Agent
Fetches official framework documentation, API references, and examples. Supplements code context with external knowledge: "How does FastAPI handle dependency injection?" or "What changed in Django 5.0?"

## Coding Agent
Generates patches while preserving project conventions. Uses the Repository Intelligence Engine to understand coding patterns, naming conventions, and architectural decisions. Never generates code in isolation — always aware of the surrounding codebase.

## Static Analysis Agent
Runs type checkers (pyright, mypy), linters (ruff, eslint), and formatters (black, prettier) on generated code. Returns structured diagnostics with file:line references. Catches type errors, style violations, and potential bugs before tests.

## Testing Agent
Runs language-specific test suites and interprets failures. Analyzes test output to identify root causes: "Test failed because mock wasn't updated" vs "Test failed due to actual logic error." Feeds results back to Coding Agent for targeted fixes.

## Security Review Agent
Reviews changes for security vulnerabilities: SQL injection, XSS, path traversal, hardcoded secrets, insecure deserialization. Uses the Repository Intelligence Engine to trace data flow from user input to sensitive operations.

## Performance Review Agent
Reviews changes for performance issues: O(n²) loops, unnecessary allocations, N+1 queries, missing indexes. Uses call graphs to estimate impact on hot paths and benchmarks critical operations.

## Regression Detection Agent
Compares current changes against past fixes stored in Repository Memory. Warns if a new change might reintroduce a previously fixed bug. "This change to `auth/token.py` resembles the pattern that caused issue #234 — previous fix used `jwt.verify()` instead."

## PR Generation Agent
Creates commits, PR titles, descriptions, and links issues. Uses the Repository Intelligence Engine to generate accurate change summaries that reference affected modules and their relationships.

---

# System Prompts

Every agent has a fixed system prompt that defines its role, available tools, and output format. These are injected into every LLM call for that agent.

## Manager Agent

```
You are the Manager Agent for Aegis Engineer, an autonomous software engineering platform.

Your role: Coordinate the workflow between specialized agents. You decide which agents to invoke, in what order, and when to retry.

Available agents: {agent_list}
Available tools: {tool_list}

When you receive a task:
1. Break it into subtasks
2. Assign each subtask to the appropriate agent
3. Monitor progress and handle failures
4. Escalate to the user if needed

Output format: Always respond with a JSON object containing:
- "action": "assign" | "retry" | "escalate" | "complete"
- "agent": agent name (if assigning)
- "task": task description
- "context": any relevant context for the agent
```

## Repository Intelligence Agent

```
You are the Repository Intelligence Agent for Aegis Engineer.

Your role: Build and maintain the Repository Intelligence Engine — a knowledge graph of the codebase.

You have access to the Repository Intelligence Engine with these graph types:
- AST Graph: Full syntax tree per file (functions, classes, variables, imports)
- Call Graph: Which functions call which, entry points, call chains
- Import Graph: Module dependency tree, circular dependencies
- Class Graph: OOP relationships, inheritance, interfaces
- Dependency Graph: External package dependencies, version constraints
- Knowledge Graph: Semantic relationships between concepts

When asked to analyze:
1. Query the relevant graphs
2. Return structured results with file:line references
3. Explain relationships between code elements

Always respond with JSON containing:
- "graph_type": which graph was queried
- "results": structured query results
- "relationships": relevant connections found
```

## Issue Classification Agent

```
You are the Issue Classification Agent for Aegis Engineer.

Your role: Analyze GitHub issues and classify them for the Planning Agent.

You have access to the Repository Intelligence Engine to understand which subsystems exist.

When classifying an issue:
1. Read the issue title, body, and comments
2. Identify the issue type: bug | feature | refactor | security | docs | dependency
3. Assess complexity: trivial | moderate | complex | epic
4. Identify affected subsystems by querying the knowledge graph
5. Estimate affected files

Output format:
{
  "type": "bug|feature|refactor|security|docs|dependency",
  "complexity": "trivial|moderate|complex|epic",
  "subsystems": ["auth", "payments"],
  "estimated_files": ["src/auth.py", "tests/test_auth.py"],
  "summary": "One-line summary of the issue"
}
```

## Planning Agent

```
You are the Planning Agent for Aegis Engineer.

Your role: Create a detailed implementation plan for the classified issue.

You have access to:
- Repository Intelligence Engine (call graphs, import graphs, impact analysis)
- Memory System (past fixes for similar issues)
- Developer Preferences (coding conventions)

When creating a plan:
1. Query the Repository Intelligence Engine to identify impacted files
2. Check Memory for similar past fixes
3. Analyze call chains and side effects
4. Create a step-by-step plan with file-level specificity

Output format:
{
  "steps": [
    {
      "step": 1,
      "description": "Read auth.py to understand current token generation",
      "files": ["src/auth.py"],
      "tools": ["read", "graph_query"],
      "expected_output": "Understanding of current JWT implementation"
    },
    ...
  ],
  "estimated_tokens": 15000,
  "estimated_cost_usd": 0.045,
  "risk_level": "low|medium|high",
  "rollback_plan": "git checkout src/auth.py tests/test_auth.py"
}
```

## Context Retrieval Agent

```
You are the Context Retrieval Agent for Aegis Engineer.

Your role: Retrieve the most relevant code context for the current task.

You have access to:
- Repository Intelligence Engine (graph traversal + embedding search)
- LSP (type information, references, definitions)

When retrieving context:
1. Query the Repository Intelligence Engine for related code
2. Follow call chains and import paths
3. Use LSP to find references and type information
4. Return the most relevant code snippets with file:line ranges

Output format:
{
  "context": [
    {
      "file": "src/auth.py",
      "lines": "45-80",
      "content": "...",
      "reason": "This function generates JWT tokens — directly related to the issue"
    },
    ...
  ],
  "call_chain": ["create_token -> jwt.sign -> expires_in"],
  "total_tokens_estimated": 4200
}
```

## Coding Agent

```
You are the Coding Agent for Aegis Engineer.

Your role: Generate code patches that fix the issue while preserving project conventions.

You have access to:
- Repository Intelligence Engine (coding patterns, conventions)
- Developer Preferences (naming, formatting, style)
- Tools: read, write, edit, apply_patch

When generating code:
1. Read the existing code to understand context
2. Follow the project's coding conventions exactly
3. Make minimal, focused changes
4. Preserve existing imports, formatting, and structure
5. Write the patch using edit (preferred) or write

Output format:
{
  "changes": [
    {
      "file": "src/auth.py",
      "action": "edit",
      "old_code": "exp = 3600",
      "new_code": "exp = 86400",
      "reason": "Change JWT expiration from 1 hour to 24 hours"
    }
  ],
  "summary": "Changed JWT token expiration from 1 hour to 24 hours"
}
```

## Static Analysis Agent

```
You are the Static Analysis Agent for Aegis Engineer.

Your role: Run type checkers, linters, and formatters on generated code.

You have access to:
- Bash tool for running commands
- Read tool for inspecting files

When analyzing:
1. Run pyright on modified Python files
2. Run ruff for linting
3. Run black for formatting
4. Return structured diagnostics

Output format:
{
  "passed": true|false,
  "errors": [
    {"file": "src/auth.py", "line": 67, "column": 5, "message": "Type mismatch", "severity": "error"}
  ],
  "warnings": [...],
  "formatted_files": ["src/auth.py"]
}
```

## Testing Agent

```
You are the Testing Agent for Aegis Engineer.

Your role: Run tests and interpret failures.

You have access to:
- Bash tool for running test commands
- Read tool for inspecting test files and source code

When testing:
1. Run the project's test suite (detect framework: pytest, jest, etc.)
2. If tests fail, analyze the failure output
3. Determine root cause: logic error vs mock issue vs configuration issue
4. Report structured results

Output format:
{
  "passed": true|false,
  "total": 14,
  "passed_count": 13,
  "failed_count": 1,
  "failures": [
    {
      "test": "test_auth.py::test_token_expiration",
      "error": "AssertionError: expected 86400, got 3600",
      "root_cause": "test expectation not updated",
      "fix_suggestion": "Update test_auth.py line 23 to expect 86400"
    }
  ]
}
```

## Security Review Agent

```
You are the Security Review Agent for Aegis Engineer.

Your role: Review code changes for security vulnerabilities.

You have access to:
- Repository Intelligence Engine (data flow tracing)
- Read tool for inspecting source code

When reviewing:
1. Read the changed files
2. Trace data flow from user input to sensitive operations
3. Check for: SQL injection, XSS, path traversal, hardcoded secrets, insecure deserialization, SSRF, CSRF
4. Rate severity: critical | high | medium | low | info

Output format:
{
  "passed": true|false,
  "vulnerabilities": [
    {
      "file": "src/auth.py",
      "line": 72,
      "type": "hardcoded_secret",
      "severity": "high",
      "description": "JWT secret is hardcoded in source code",
      "fix": "Move to environment variable"
    }
  ]
}
```

## Performance Review Agent

```
You are the Performance Review Agent for Aegis Engineer.

Your role: Review code changes for performance issues.

You have access to:
- Repository Intelligence Engine (call graphs, hot paths)
- Read tool for inspecting source code

When reviewing:
1. Read the changed files and their callers
2. Check for: O(n²) loops, unnecessary allocations, N+1 queries, missing indexes, blocking I/O
3. Estimate impact on hot paths
4. Rate severity: critical | high | medium | low

Output format:
{
  "passed": true|false,
  "issues": [
    {
      "file": "src/auth.py",
      "line": 89,
      "type": "n_plus_one_query",
      "severity": "medium",
      "description": "Query inside loop — fetch all at once instead",
      "fix": "Use bulk query before the loop"
    }
  ]
}
```

## Regression Detection Agent

```
You are the Regression Detection Agent for Aegis Engineer.

Your role: Check if current changes might reintroduce previously fixed bugs.

You have access to:
- Repository Memory (past fixes and their patterns)
- Repository Intelligence Engine (call graphs)

When checking:
1. Read the current changes
2. Query Repository Memory for similar past fixes
3. Compare the current patch against past fix patterns
4. Warn if the change resembles a pattern that caused a previous bug

Output format:
{
  "regression_risk": "none|low|medium|high",
  "warnings": [
    {
      "past_issue": "#234",
      "past_fix": "Changed jwt.verify() to jwt.decode()",
      "current_change": "Modified token validation in auth.py",
      "risk": "Medium — same file, different function",
      "recommendation": "Verify that token validation still uses jwt.decode()"
    }
  ]
}
```

## PR Generation Agent

```
You are the PR Generation Agent for Aegis Engineer.

Your role: Create a commit and pull request description for the changes.

You have access to:
- Repository Intelligence Engine (module relationships)
- Read tool for inspecting the diff

When generating:
1. Read the git diff
2. Analyze which modules were affected and their relationships
3. Write a descriptive commit message
4. Write a detailed PR description with context

Output format:
{
  "commit_message": "fix(auth): increase JWT token expiration to 24 hours\n\nFixes #42",
  "pr_title": "Fix JWT token expiration to 24 hours",
  "pr_body": "## Summary\n...",
  "related_modules": ["auth", "tokens", "security"],
  "testing_done": "Ran full test suite — 14/14 passed"
}
```

---

# Agent Loop

Every agent follows the same core loop: **call LLM → receive response → execute tools → repeat until done**.

```python
async def agent_loop(
    agent: Agent,
    task: str,
    provider: LLMProvider,
    tools: ToolRegistry,
    max_iterations: int = 20,
) -> AgentResult:
    """Core agent loop that every agent uses."""
    
    messages = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "user", "content": task},
    ]
    
    for iteration in range(max_iterations):
        # 1. Call LLM
        response = await provider.chat(
            messages=messages,
            model=agent.model,
            tools=tools.list_for_agent(agent.permissions),
            stream=True,
        )
        
        # 2. Collect response (text + tool calls)
        text_parts = []
        tool_calls = []
        
        async for chunk in response:
            if chunk.delta:
                text_parts.append(chunk.delta)
            if chunk.tool_call:
                tool_calls.append(chunk.tool_call)
        
        # 3. Add assistant message
        assistant_message = {
            "role": "assistant",
            "content": "".join(text_parts),
            "tool_calls": tool_calls,
        }
        messages.append(assistant_message)
        
        # 4. If no tool calls, we're done
        if not tool_calls:
            return AgentResult(
                output="".join(text_parts),
                messages=messages,
                iterations=iteration + 1,
            )
        
        # 5. Execute each tool call
        for tool_call in tool_calls:
            tool = tools.get(tool_call.name)
            
            # Check permissions
            permission = await check_permission(tool, agent)
            if permission == "deny":
                result = ToolResult(output="Permission denied", error=True)
            elif permission == "ask":
                result = await prompt_user_for_permission(tool, tool_call.params)
            else:
                # Execute with timeout
                result = await asyncio.wait_for(
                    tool.execute(tool_call.params, ToolContext(agent=agent)),
                    timeout=agent.tool_timeout,
                )
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result.output,
            })
            
            # Record in observability
            await record_tool_call(agent, tool_call, result)
    
    return AgentResult(
        output="Max iterations reached",
        messages=messages,
        iterations=max_iterations,
        error="max_iterations_exceeded",
    )
```

---

# Orchestration State Machine

The Manager Agent operates as a finite state machine that coordinates the entire workflow.

## States

```text
                    ┌─────────────┐
                    │   IDLE      │
                    └──────┬──────┘
                           │ Issue received
                           ▼
                    ┌─────────────┐
                    │ CLASSIFY    │ Issue Classification Agent
                    └──────┬──────┘
                           │ Classification complete
                           ▼
                    ┌─────────────┐
                    │   PLAN      │ Planning Agent
                    └──────┬──────┘
                           │ Plan approved
                           ▼
                    ┌─────────────┐
                    │  RETRIEVE   │ Context Retrieval + Doc Retrieval
                    └──────┬──────┘
                           │ Context ready
                           ▼
                    ┌─────────────┐
                    │    CODE     │ Coding Agent
                    └──────┬──────┘
                           │ Patch generated
                           ▼
                    ┌─────────────┐
                    │   ANALYZE   │ Static Analysis Agent
                    └──────┬──────┘
                      ┌────┴────┐
                      │ pass    │ fail → back to CODE
                      ▼         │
                    ┌─────────────┐
                    │    TEST     │ Testing Agent
                    └──────┬──────┘
                      ┌────┴────┐
                      │ pass    │ fail → back to CODE (retry++)
                      ▼         │
                ┌─────────────────┐
                │    REVIEW       │ Security + Performance + Regression
                └────────┬────────┘
                   ┌─────┴─────┐
                   │ pass      │ fail → back to CODE
                   ▼           │
                    ┌─────────────┐
                    │    PR       │ PR Generation Agent
                    └──────┬──────┘
                           │ PR created
                           ▼
                    ┌─────────────┐
                    │  COMPLETE   │
                    └─────────────┘
```

## Transitions

| From | To | Condition |
|------|----|-----------|
| IDLE | CLASSIFY | Issue received |
| CLASSIFY | PLAN | Classification complete |
| PLAN | RETRIEVE | Plan approved |
| RETRIEVE | CODE | Context ready |
| CODE | ANALYZE | Patch generated |
| ANALYZE | CODE | Analysis failed (fix errors) |
| ANALYZE | TEST | Analysis passed |
| TEST | CODE | Tests failed (retry < max) |
| TEST | REVIEW | Tests passed |
| REVIEW | CODE | Review failed (fix issues) |
| REVIEW | PR | All reviews passed |
| PR | COMPLETE | PR created |

## Retry Logic

```python
MAX_RETRIES = 3
RETRY_DELAY = [1, 2, 4]  # Exponential backoff in seconds

async def orchestrate(issue: GitHubIssue) -> WorkflowResult:
    state = "IDLE"
    retries = 0
    context = WorkflowContext(issue=issue)
    
    while state != "COMPLETE":
        match state:
            case "IDLE":
                state = "CLASSIFY"
            
            case "CLASSIFY":
                context.classification = await issue_classifier.classify(issue)
                state = "PLAN"
            
            case "PLAN":
                context.plan = await planner.create_plan(context)
                state = "RETRIEVE"
            
            case "RETRIEVE":
                context.context = await context_retriever.retrieve(context)
                context.docs = await doc_retriever.retrieve(context)
                state = "CODE"
            
            case "CODE":
                context.patch = await coder.generate(context)
                state = "ANALYZE"
            
            case "ANALYZE":
                analysis = await static_analyzer.analyze(context)
                if analysis.passed:
                    state = "TEST"
                else:
                    state = "CODE"
                    retries += 1
            
            case "TEST":
                test_result = await tester.test(context)
                if test_result.passed:
                    state = "REVIEW"
                else:
                    state = "CODE"
                    retries += 1
            
            case "REVIEW":
                reviews = await review_all(context)  # security + perf + regression
                if all(r.passed for r in reviews):
                    state = "PR"
                else:
                    state = "CODE"
                    retries += 1
            
            case "PR":
                context.pr = await pr_generator.generate(context)
                state = "COMPLETE"
        
        if retries >= MAX_RETRIES:
            return WorkflowResult(
                state="FAILED",
                error="Max retries exceeded",
                context=context,
            )
    
    return WorkflowResult(state="COMPLETE", context=context)
```

---

# Error Handling Strategy

Every component has a defined failure mode and recovery path.

## Error Categories

| Category | Examples | Recovery |
|----------|----------|----------|
| **LLM Errors** | Rate limit, timeout, invalid response | Retry with backoff, fallback to alternate provider |
| **Tool Errors** | Command failure, file not found, permission denied | Return error to agent, let agent reason about fix |
| **Docker Errors** | Container crash, image pull failure | Restart container, fallback to local execution |
| **Network Errors** | API timeout, DNS failure | Retry with exponential backoff |
| **Intelligence Errors** | Graph build failure, LSP crash | Skip graph queries, use fallback search |
| **State Errors** | Invalid transition, corrupted session | Log error, reset to safe state |

## LLM Error Handling

```python
async def call_llm_with_retry(
    provider: LLMProvider,
    messages: list[Message],
    max_retries: int = 3,
    fallback_provider: LLMProvider | None = None,
) -> ChatResponse:
    for attempt in range(max_retries):
        try:
            return await provider.chat(messages)
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
        except TimeoutError:
            if attempt < max_retries - 1:
                continue
        except (APIError, AuthenticationError) as e:
            if fallback_provider and attempt == max_retries - 1:
                return await fallback_provider.chat(messages)
            raise
    
    raise LLMExhaustedError(f"All {max_retries} attempts failed")
```

## Tool Error Handling

```python
async def execute_tool_with_timeout(
    tool: ToolDefinition,
    params: dict,
    timeout: float = 30.0,
) -> ToolResult:
    try:
        result = await asyncio.wait_for(
            tool.execute(params, ctx),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        return ToolResult(
            output=f"Tool {tool.name} timed out after {timeout}s",
            error=True,
            metadata={"error_type": "timeout"},
        )
    except ToolExecutionError as e:
        return ToolResult(
            output=f"Tool {tool.name} failed: {str(e)}",
            error=True,
            metadata={"error_type": "execution_error"},
        )
```

## Docker Error Handling

```python
async def run_in_sandbox(code: str, language: str) -> SandboxResult:
    container = None
    try:
        container = await docker.containers.run(
            image=f"aegis-sandbox:{language}",
            command=code,
            timeout=120,
            mem_limit="512m",
        )
        return SandboxResult(output=container.output, exit_code=0)
    except ContainerCrashError:
        if container:
            await container.remove(force=True)
        return SandboxResult(output="Container crashed", exit_code=1)
    except ImageNotFoundError:
        # Pull the image and retry once
        await docker.images.pull(f"aegis-sandbox:{language}")
        return await run_in_sandbox(code, language)
```

## Escalation

When automated recovery fails, the Manager Agent escalates to the user:

```python
async def escalate_to_user(context: WorkflowContext, reason: str):
    await event_bus.publish("agent.escalation", {
        "issue": context.issue.number,
        "reason": reason,
        "state": context.state,
        "retries": context.retries,
        "options": [
            "Retry with different approach",
            "Skip and move to next issue",
            "Abort and clean up",
        ],
    })
```

---

# Concurrency Model

Aegis Engineer uses Python's `asyncio` for concurrency. All I/O-bound operations are async; CPU-bound work is offloaded to thread/process pools.

## Agent Concurrency

```text
Sequential (default):
Manager → Classifier → Planner → Retriever → Coder → Reviewer → PR

Parallel (when possible):
                     ┌─ Security Reviewer ─┐
Context Retriever ───┤                     ├──► PR Generator
                     └─ Performance Review ─┘

                    ┌─ Doc Retriever ─┐
Planner ───────────┤                 ├──► Coder
                    └─ Memory Query ──┘
```

## Implementation

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

# Thread pool for CPU-bound work (Tree-sitter parsing, graph building)
CPU_POOL = ProcessPoolExecutor(max_workers=4)

class AgentRunner:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(10)  # Max 10 concurrent tool calls
    
    async def run_parallel(self, agents: list[AgentTask]) -> list[AgentResult]:
        """Run multiple agents in parallel."""
        async def run_one(task):
            async with self.semaphore:
                return await agent_loop(task.agent, task.input, task.provider)
        
        return await asyncio.gather(*[run_one(t) for t in agents])
    
    async def run_cpu_bound(self, func, *args):
        """Run CPU-bound work in process pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(CPU_POOL, func, *args)
```

## Timeouts

| Component | Timeout | Action on Timeout |
|-----------|---------|-------------------|
| LLM call | 120s | Retry, then fallback provider |
| Tool execution | 30s | Return timeout error to agent |
| Docker container | 120s | Kill container, return error |
| Intelligence build | 300s | Cache partial results, continue |
| Agent loop | 600s | Force stop, return partial results |

## Rate Limiting

```python
# Per-provider rate limits
RATE_LIMITS = {
    "openai": {"rpm": 500, "tpm": 150_000},
    "anthropic": {"rpm": 100, "tpm": 100_000},
    "google": {"rpm": 60, "tpm": 60_000},
}

# Global concurrency limits
MAX_CONCURRENT_SESSIONS = 5
MAX_CONCURRENT_AGENTS = 10
MAX_CONCURRENT_TOOL_CALLS = 20
```

---

# Repository Intelligence Engine

The **Repository Intelligence Engine** is the defining innovation of Aegis Engineer. Unlike tools that treat codebases as flat text files, this engine builds a living, queryable knowledge graph of the entire repository.

## What It Builds

```text
Repository
    │
    ├──► AST Graph (Tree-sitter)
    │       Full syntax tree per file
    │       Functions, classes, variables, imports
    │
    ├──► Call Graph
    │       Which functions call which
    │       Entry points and call chains
    │       Side effect propagation
    │
    ├──► Import Graph
    │       Module dependency tree
    │       Circular dependency detection
    │       Import cost analysis
    │
    ├──► Class/Inheritance Graph
    │       OOP relationships
    │       Interface implementations
    │       MRO (Method Resolution Order)
    │
    ├──► Dependency Graph
    │       External package dependencies
    │       Version constraints
    │       Transitive dependency tree
    │
    ├──► LSP Integration
    │       Type information
    │       Go-to-definition
    │       Find references
    │       Diagnostics
    │
    ├──► Embedding Search
    │       Semantic code similarity
    │       Natural language queries
    │       Concept matching
    │
    └──► Knowledge Graph (the fusion layer)
            Semantic relationships between concepts
            "auth module" → "uses jwt library" → "depends on crypto utils"
            "User model" → "has many Orders" → "validated by schemas"
```

## Architecture

```python
class RepositoryIntelligenceEngine:
    """The central intelligence layer that all agents query."""
    
    def __init__(self, repo_path: str):
        self.ast_graph = ASTGraph(repo_path)         # Tree-sitter
        self.call_graph = CallGraph(repo_path)       # Static analysis
        self.import_graph = ImportGraph(repo_path)   # Module deps
        self.class_graph = ClassGraph(repo_path)     # OOP relationships
        self.dep_graph = DependencyGraph(repo_path)  # External deps
        self.knowledge_graph = KnowledgeGraph()       # Fusion layer
        self.embedding_index = EmbeddingIndex(repo_path)  # Semantic search
        self.lsp_clients = {}                         # Per-language LSP
    
    async def query(self, q: IntelligenceQuery) -> IntelligenceResult:
        """Unified query interface for all agents."""
        pass
    
    async def find_callers(self, function_name: str) -> list[CodeLocation]:
        """Who calls this function? Follow the call graph."""
        pass
    
    async def find_impact(self, file_path: str, line_range: tuple) -> ImpactAnalysis:
        """If I change this code, what else is affected?"""
        pass
    
    async def search_semantic(self, query: str) -> list[CodeSnippet]:
        """Find code matching a natural language description."""
        pass
    
    async def get_context(self, issue: GitHubIssue) -> RepositoryContext:
        """Build full context for an issue using all graph layers."""
        pass
```

## How Agents Use It

| Agent | Query | Intelligence Used |
|-------|-------|-------------------|
| **Repository Intelligence** | Build/update all graphs | AST, call, import, class, dependency graphs |
| **Dependency Analysis** | What depends on this package? | Dependency graph, import graph |
| **Issue Classification** | What subsystems are affected? | Knowledge graph, import graph |
| **Planning** | What files need to change? | Call graph, import graph, LSP references |
| **Context Retrieval** | Find all related code | Embedding search + call graph traversal |
| **Coding** | What patterns does this project use? | AST graph, knowledge graph |
| **Static Analysis** | What types are involved? | LSP, AST graph |
| **Security Review** | Trace data flow from input | Call graph, AST graph |
| **Performance Review** | What's on the hot path? | Call graph, embedding search |
| **Regression Detection** | Does this change affect past fixes? | Repository memory + call graph |
| **PR Generation** | Summarize all affected modules | Knowledge graph, dependency graph |

## Building the Graph

```bash
# Build intelligence for current repo
aegis intelligence build

# Query the graph
aegis intelligence query "who calls process_payment?"
aegis intelligence impact src/auth.py:45-80
aegis intelligence search "authentication middleware"
aegis intelligence graph --type call    # Visualize call graph

# Auto-build on clone
aegis solve https://github.com/org/repo/issues/42
# → Automatically builds intelligence engine first
```

## Incremental Updates

The intelligence engine doesn't rebuild from scratch on every change:
1. On initial clone: full build (seconds to minutes depending on repo size)
2. On file change: incremental update of affected graphs
3. On new commit: update knowledge graph with new patterns
4. Cache graph data in `.aegis/intelligence/` directory

---

# Tool System

Every agent interacts with the world through **typed tools**. Tools are the bridge between LLM reasoning and real-world actions (file I/O, shell commands, web requests, etc.).

## Tool Definition Pattern

```python
from pydantic import BaseModel, Field

class ToolDefinition:
    name: str                    # Unique identifier
    description: str             # Shown to the LLM
    parameters: type[BaseModel]  # Pydantic schema — validated before execute
    permissions: list[str]       # Required permissions (e.g., "shell", "write")

    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult:
        """Run the tool and return structured output."""
        return ToolResult(
            output="text result",
            title="human-readable summary",
            metadata={"key": "value"},  # structured data
            attachments=[]              # images, file diffs, etc.
        )
```

## Core Tools

| Tool | Description | Permission Required |
|------|-------------|-------------------|
| `bash` | Shell command execution via PTY | `shell` |
| `read` | File read with line-range support | `read` |
| `write` | File write (create/overwrite) | `write` |
| `edit` | Targeted string replacement in files | `write` |
| `apply_patch` | Unified diff application | `write` |
| `glob` | File pattern matching | `read` |
| `grep` | Regex search across files | `read` |
| `codesearch` | Semantic/keyword code search (RAG) | `read` |
| `graph_query` | Query Repository Intelligence Engine (call graph, impact analysis, semantic search) | `read` |
| `webfetch` | HTTP fetch for web pages | `network` |
| `websearch` | Web search integration | `network` |
| `task` | Spawn subagent for parallel work | `agent` |
| `todowrite` | Todo item tracking | `internal` |
| `skill` | Execute skill scripts | `internal` |
| `lsp` | Language Server Protocol queries | `read` |

## Conditional Tools

| Tool | Condition | Description |
|------|-----------|-------------|
| `question` | Interactive mode only | Prompt user for input |
| `plan_enter` | Plan mode enabled | Enter read-only planning mode |
| `plan_exit` | Plan mode enabled | Exit planning, apply changes |

## Tool Registry

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_for_agent(self, agent_permissions: list[str]) -> list[ToolDefinition]:
        return [t for t in self._tools.values()
                if all(p in agent_permissions for p in t.permissions)]
```

## Tool Execution Flow

```text
LLM generates tool call
        │
        ▼
Validate parameters against Pydantic schema
        │
        ▼
Check permissions (allow/deny/ask)
        │
        ▼
Execute tool with timeout
        │
        ▼
Capture output, metadata, attachments
        │
        ▼
Return ToolResult to LLM as message part
        │
        ▼
LLM reasons about result, decides next action
```

---

# Provider System

Aegis Engineer supports multiple LLM providers through a unified abstraction layer.

## Provider Abstraction

```python
class LLMProvider(ABC):
    name: str
    models: list[ModelInfo]

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: str,
        tools: list[ToolDefinition],
        stream: bool = True,
    ) -> AsyncIterator[ChatChunk]:
        """Stream chat completion from the provider."""
        pass

    @abstractmethod
    async def count_tokens(self, messages: list[Message], model: str) -> TokenCount:
        """Count tokens for a message list."""
        pass
```

## Supported Providers

| Provider | Models | Auth Method |
|----------|--------|-------------|
| OpenAI | GPT-4o, GPT-5, o1, o3 | API key |
| Anthropic | Claude 3.5, Claude 4 | API key |
| Google | Gemini 2.5, Gemini 3 | API key / Vertex AI |
| Azure | OpenAI models via Azure | Endpoint + key |
| Ollama | Local models (Llama, Qwen, etc.) | Local URL |
| LiteLLM | Proxy for 100+ providers | Proxy URL |

## Model Selection

```json
{
  "provider": "anthropic",
  "model": "claude-4-sonnet",
  "fallback_provider": "openai",
  "fallback_model": "gpt-5"
}
```

## Streaming Response Format

```python
@dataclass
class ChatChunk:
    delta: str | None          # Text delta (token-by-token)
    tool_call: ToolCall | None # Tool call delta
    finish_reason: str | None  # "stop", "tool_use", "length"
    usage: TokenUsage | None   # Prompt/completion token counts
    cost_usd: float | None     # Estimated cost in USD
```

## Token Tracking

Every LLM call records:
- Input tokens (prompt + system + tools)
- Output tokens (response + tool calls)
- Estimated cost in USD
- Latency in milliseconds
- Model and provider used

This data feeds into the Metrics Service for benchmarking and cost analysis.

---

# Permission Engine

The permission engine controls what tools agents can use and when they need user approval.

## Permission Levels

| Level | Behavior |
|-------|----------|
| `allow` | Tool executes without prompting |
| `deny` | Tool is blocked entirely |
| `ask` | User must approve each execution |

## Configuration

```json
{
  "permissions": {
    "default": "ask",
    "rules": [
      {"tool": "read", "agent": "*", "level": "allow"},
      {"tool": "glob", "agent": "*", "level": "allow"},
      {"tool": "grep", "agent": "*", "level": "allow"},
      {"tool": "write", "agent": "coding", "level": "allow"},
      {"tool": "write", "agent": "reviewer", "level": "deny"},
      {"tool": "bash", "agent": "coding", "level": "ask"},
      {"tool": "bash", "agent": "test", "level": "allow"},
      {"tool": "webfetch", "agent": "*", "level": "ask"}
    ]
  }
}
```

## Permission Flow

```text
Agent requests tool execution
        │
        ▼
Look up permission rule (tool + agent)
        │
        ▼
┌───────┴───────┐
│ allow │ deny  │ ask
│       │       │
▼       ▼       ▼
Execute Block  Send PermissionRequest
                  │
                  ▼
              TUI prompts user
              (approve/deny/always)
                  │
                  ▼
              Execute or block
```

## Trust Modes

| Mode | Description |
|------|-------------|
| `interactive` | Default — prompts for `ask` rules |
| `yolo` | All `ask` rules become `allow` |
| `readonly` | Only `read`/`glob`/`grep` allowed |
| `ci` | No prompting, `ask` rules become `deny` |

---

# Session Management

Sessions persist conversation state, tool calls, and agent interactions across runs.

## Session Lifecycle

```text
Create Session → Add Messages → LLM Reasoning → Tool Execution → ...
      │                                                    │
      ▼                                                    ▼
  Save to SQLite ◄──────────────────────────────────── Save
      │
      ▼
  Resume / Compact / Delete
```

## Session Schema

```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    created_at  TIMESTAMP,
    updated_at  TIMESTAMP,
    model       TEXT,
    provider    TEXT,
    token_count INTEGER,
    cost_usd    REAL
);

CREATE TABLE messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT REFERENCES sessions(id),
    role        TEXT,  -- user, assistant, tool, system
    content     TEXT,
    tool_calls  JSONB,
    tool_result JSONB,
    tokens      INTEGER,
    cost_usd    REAL,
    created_at  TIMESTAMP
);
```

## Compaction

When message history exceeds token limits, older messages are summarized:
1. Identify messages older than threshold
2. LLM generates summary of conversation so far
3. Replace old messages with compact summary
4. Preserve recent messages verbatim

## Session Commands (CLI)

```bash
aegis session list                    # List all sessions
aegis session resume <session-id>     # Resume a previous session
aegis session delete <session-id>     # Delete a session
aegis session export <session-id>     # Export as JSON
```

---

# Memory System

Aegis Engineer learns from every issue it solves. The memory system transforms it from a stateless assistant into a system that improves over time.

## Memory Types

### Repository Memory
Per-repository knowledge that accumulates as issues are solved:
- Successful patches and their reasoning chains
- Repository-specific patterns (e.g., "this project uses dataclasses, not Pydantic")
- Common failure modes and their fixes
- Code conventions and architectural decisions

```python
class RepositoryMemory:
    repo_id: str
    solved_issues: list[SolvedIssue]      # Issue → patch → reasoning
    code_patterns: list[CodePattern]       # Detected conventions
    common_fixes: list[CommonFix]          # Recurring fix patterns
    architecture_notes: list[str]          # Human-readable notes

class SolvedIssue:
    issue_number: int
    title: str
    classification: IssueType
    reasoning_chain: list[ReasoningStep]   # What the agent thought
    patch: str                             # Final diff
    files_changed: list[str]
    tests_passed: bool
    tokens_used: int
    cost_usd: float
    solved_at: datetime
```

### Global Memory
Cross-repository learnings that apply everywhere:
- Common bug patterns across Python/JS/Go projects
- Framework-specific gotchas (Django migrations, React hooks rules)
- Security vulnerability patterns
- Performance anti-patterns

```python
class GlobalMemory:
    common_patterns: list[Pattern]         # Across all repos
    security_rules: list[SecurityRule]     # Learned vulnerability patterns
    framework_gotchas: list[Gotcha]       # Framework-specific traps
    success_strategies: list[Strategy]    # What works for different issue types
```

### Developer Preferences
Learned from the codebase and optional user configuration:
- Naming conventions (snake_case, camelCase)
- Import style (absolute, relative)
- Docstring format (Google, NumPy, Sphinx)
- Testing framework (pytest, unittest, jest)
- Linter/formatter preferences

### Failure Memory
What didn't work, so we don't repeat mistakes:
- Patches that failed tests
- Approaches that were rejected in code review
- Patterns that caused regressions
- Incorrect assumptions about the codebase

```python
class FailureMemory:
    failed_attempts: list[FailedAttempt]
    
class FailedAttempt:
    issue_type: str
    approach: str                          # What was tried
    reason_for_failure: str                # Why it failed
    files_involved: list[str]
    suggested_alternative: str             # What to try instead
```

## Memory Flow

```text
Issue Solved Successfully
        │
        ▼
Extract Reasoning Chain
        │
        ▼
┌───────┴───────┐
│               │
▼               ▼
Store in      Store in
Repo Memory   Global Memory
│               │
▼               ▼
Update Code    Update Pattern
Patterns       Library
        │
        ▼
Next Issue
        │
        ▼
Query Memory for Context
        │
        ▼
Better Planning + Fewer Mistakes
```

## Memory-Enhanced Planning

When the Planning Agent receives a new issue:

1. **Query Repository Memory**: "Have we solved similar issues before?"
2. **Query Global Memory**: "What patterns apply to this type of bug?"
3. **Query Failure Memory**: "What approaches should we avoid?"
4. **Query Developer Preferences**: "What conventions does this project follow?"
5. **Generate Plan**: Informed by all historical context

## Memory CLI

```bash
aegis memory list <repo>               # Show stored memory for a repo
aegis memory show <repo> --issue 42    # Show memory for specific issue
aegis memory forget <repo>             # Clear memory for a repo
aegis memory export                    # Export all memory as JSON
aegis memory import <file.json>        # Import memory from file
```

---

# Event Bus

The event bus enables decoupled communication between the agent system and clients (TUI, web, desktop).

## Event Types

| Event | Source | Destination | Description |
|-------|--------|-------------|-------------|
| `agent.start` | Agent | Client | Agent begins processing |
| `agent.thinking` | Agent | Client | LLM is generating |
| `agent.tool_call` | Agent | Client | Tool execution started |
| `agent.tool_result` | Agent | Client | Tool execution completed |
| `agent.done` | Agent | Client | Agent finished processing |
| `agent.error` | Agent | Client | Agent encountered error |
| `permission.request` | Tool | Client | Needs user approval |
| `permission.response` | Client | Tool | User approved/denied |
| `session.update` | Session | Client | Session state changed |
| `message.add` | Session | Client | New message added |
| `log.info` | System | Client | Informational log |
| `log.error` | System | Client | Error log |

## SSE Stream Format

```
event: agent.tool_call
data: {"tool":"bash","params":{"command":"npm test"},"agent":"coding"}

event: agent.tool_result
data: {"tool":"bash","output":"3 tests passed","duration_ms":1250}

event: agent.thinking
data: {"tokens":245,"model":"claude-4-sonnet"}
```

## Implementation

```python
class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable):
        self._subscribers[event_type].append(callback)

    async def publish(self, event_type: str, data: dict):
        for callback in self._subscribers[event_type]:
            await callback(event_type, data)
```

---

# Observability

Full observability into every aspect of the agent's reasoning and execution. This is not just logging — it's a complete audit trail of how the agent solved (or failed to solve) an issue.

## Prompt Timeline

Every LLM call is logged with full context:

```json
{
  "step": 3,
  "agent": "planner",
  "timestamp": "2026-07-24T10:32:15Z",
  "model": "claude-4-sonnet",
  "system_prompt_tokens": 2450,
  "user_prompt_tokens": 1820,
  "total_tokens": 4270,
  "cost_usd": 0.0128,
  "latency_ms": 2340,
  "response_tokens": 890,
  "tool_calls": [
    {"name": "graph_query", "params": {"query": "callers of process_payment"}},
    {"name": "read", "params": {"file": "src/auth.py", "lines": "45-80"}}
  ],
  "reasoning": "The issue mentions JWT expiration. I need to trace how tokens are generated and validated..."
}
```

## Tool Timeline

Complete record of every tool execution:

```text
┌─────┬────────────────┬──────────┬──────────┬─────────────────────────────┐
│ Step│ Tool           │ Duration │ Tokens   │ Output Summary              │
├─────┼────────────────┼──────────┼──────────┼─────────────────────────────┤
│ 1   │ graph_query    │ 120ms    │ 0        │ Found 3 callers of jwt.sign │
│ 2   │ read           │ 45ms     │ 0        │ Read auth.py lines 45-80    │
│ 3   │ grep           │ 89ms     │ 0        │ Found 12 matches for "exp"  │
│ 4   │ lsp            │ 230ms    │ 0        │ Type: dict → TokenPayload   │
│ 5   │ write          │ 34ms     │ 0        │ Updated auth.py             │
│ 6   │ bash           │ 4500ms   │ 0        │ pytest: 14/14 passed        │
└─────┴────────────────┴──────────┴──────────┴─────────────────────────────┘
```

## Agent Decision Tree

Visual trace of how the agent reasoned through the problem:

```text
Issue: JWT tokens expire too early
│
├─► Issue Classification Agent
│   └─► Type: Bug | Complexity: Moderate | Subsystem: Auth
│
├─► Repository Intelligence Agent
│   └─► Found: auth.py, token_utils.py, test_auth.py
│
├─► Planning Agent
│   ├─► Step 1: Understand current token generation
│   ├─► Step 2: Find where expiration is set
│   ├─► Step 3: Modify expiration logic
│   └─► Step 4: Update tests
│
├─► Context Retrieval Agent
│   └─► Retrieved: jwt.sign(), token_payload schema, test fixtures
│
├─► Coding Agent
│   ├─► Modified: src/auth.py:67 (changed exp from 3600 to 86400)
│   └─► Modified: tests/test_auth.py:23 (updated test expectation)
│
├─► Static Analysis Agent
│   └─► No type errors, no lint issues
│
├─► Testing Agent
│   └─► 14/14 tests passed
│
└─► PR Generation Agent
    └─► Created PR #45: "Fix JWT token expiration to 24 hours"
```

## Cost Breakdown

Detailed cost analysis per session:

```text
┌─────────────────────┬─────────┬──────────┬───────────┐
│ Phase               │ Tokens  │ Cost USD │ % of Total│
├─────────────────────┼─────────┼──────────┼───────────┤
│ Issue Classification│ 2,400   │ $0.0072  │ 5.4%      │
│ Planning            │ 8,200   │ $0.0246  │ 18.6%     │
│ Context Retrieval   │ 4,100   │ $0.0123  │ 9.3%      │
│ Coding              │ 12,500  │ $0.0375  │ 28.4%     │
│ Static Analysis     │ 1,800   │ $0.0054  │ 4.1%      │
│ Testing             │ 3,200   │ $0.0096  │ 7.3%      │
│ Security Review     │ 2,100   │ $0.0063  │ 4.8%      │
│ Performance Review  │ 1,900   │ $0.0057  │ 4.3%      │
│ PR Generation       │ 2,800   │ $0.0084  │ 6.4%      │
│ Retries (1x)        │ 5,000   │ $0.0150  │ 11.4%     │
├─────────────────────┼─────────┼──────────┼───────────┤
│ TOTAL               │ 44,000  │ $0.1320  │ 100%      │
└─────────────────────┴─────────┴──────────┴───────────┘
```

## Latency Map

Time spent in each phase:

```text
┌─────────────────────┬──────────┬───────────────────────────────────┐
│ Phase               │ Duration │ Visual                            │
├─────────────────────┼──────────┼───────────────────────────────────┤
│ Intelligence Build  │ 12.3s    │ ████████████████████████▌         │
│ Issue Classification│ 2.1s     │ ████                              │
│ Planning            │ 4.5s     │ █████████                         │
│ Context Retrieval   │ 3.2s     │ ██████▍                           │
│ Coding              │ 8.7s     │ ██████████████████▍               │
│ Static Analysis     │ 1.8s     │ ███▌                              │
│ Testing             │ 15.2s    │ ██████████████████████████████▍   │
│ Security Review     │ 3.1s     │ ██████▎                           │
│ Performance Review  │ 2.8s     │ █████▋                            │
│ PR Generation       │ 1.9s     │ ███▊                              │
├─────────────────────┼──────────┼───────────────────────────────────┤
│ TOTAL               │ 55.6s    │                                   │
└─────────────────────┴──────────┴───────────────────────────────────┘
```

## Reasoning Trace

Full chain-of-thought log for debugging:

```text
[10:32:15] PLANNER: Analyzing issue #42 "JWT tokens expire too early"
[10:32:15] PLANNER: Querying Repository Intelligence for auth module...
[10:32:16] PLANNER: Found auth.py (450 lines), token_utils.py (120 lines)
[10:32:16] PLANNER: Call graph shows: create_token() → jwt.sign() → expires_in param
[10:32:17] PLANNER: Plan: 1) Read token generation code, 2) Find expiration config, 3) Modify, 4) Test
[10:32:17] CONTEXT: Retrieving auth.py:45-80 (token generation function)
[10:32:18] CONTEXT: Retrieved jwt.sign() call with exp=3600 (1 hour)
[10:32:18] CODER: Modifying auth.py:67 — changing exp from 3600 to 86400
[10:32:19] CODER: Updating test_auth.py:23 — changing expected expiration
[10:32:20] STATIC: Running pyright on modified files...
[10:32:21] STATIC: No type errors found
[10:32:21] TEST: Running pytest tests/test_auth.py...
[10:32:36] TEST: 14/14 tests passed
[10:32:36] SECURITY: Reviewing auth changes for vulnerabilities...
[10:32:38] SECURITY: No security issues found
[10:32:38] PR: Generating PR description...
[10:32:39] PR: Created PR #45
```

## Observability CLI

```bash
aegis observe session <session-id>          # Full session trace
aegis observe prompt <session-id> --step 3  # Prompt at specific step
aegis observe cost <session-id>             # Cost breakdown
aegis observe timeline <session-id>         # Latency map
aegis observe reasoning <session-id>        # Reasoning trace
aegis observe export <session-id> -o trace.json  # Export full trace
```

---

# MCP & LSP Integration

## Model Context Protocol (MCP)

MCP allows Aegis Engineer to connect to external tool servers for extended capabilities.

```json
{
  "mcp": {
    "servers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "database": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env": {"DATABASE_URL": "postgresql://..."}
      },
      "custom-tools": {
        "url": "http://localhost:3000/mcp",
        "transport": "http"
      }
    }
  }
}
```

### MCP Tool Discovery

1. Connect to each configured MCP server
2. List available tools via `tools/list`
3. Register discovered tools in ToolRegistry
4. Tools appear alongside built-in tools for LLM use

## Language Server Protocol (LSP)

LSP provides code intelligence for the repository being worked on.

| Language | Server |
|----------|--------|
| Python | `pyright`, `pylsp` |
| TypeScript/JS | `typescript-language-server` |
| Go | `gopls` |
| Rust | `rust-analyzer` |
| Java | `jdtls` |
| C/C++ | `clangd` |
| Ruby | `solargraph` |
| PHP | `php-language-server` |

### LSP Operations (Exposed as `lsp` Tool)

| Operation | Description |
|-----------|-------------|
| `goToDefinition` | Navigate to symbol definition |
| `findReferences` | Find all usages of a symbol |
| `hover` | Get type info and docs |
| `diagnostics` | Get errors and warnings |
| `completion` | Code completions |
| `symbols` | Document/workspace symbols |

### Lazy Initialization

```
1. Agent calls lsp tool with file path and query type
2. Check if LSP server exists for file extension
3. If not running, spawn server (lazy init)
4. Route query to LSP client connection
5. Return structured results
```

---

# Plugin System

Plugins extend Aegis Engineer behavior at well-defined hooks.

## Plugin Structure

```python
from aegis.plugins import Plugin, hook

class MyPlugin(Plugin):
    name = "my-plugin"
    version = "1.0.0"

    @hook("system.prompt.transform")
    async def modify_system_prompt(self, prompt: str, ctx: HookContext) -> str:
        return prompt + "\n\nAlways respond in Spanish."

    @hook("tool.execute.before")
    async def before_tool(self, tool_name: str, params: dict, ctx: HookContext):
        log.info(f"About to execute {tool_name}")

    @hook("tool.execute.after")
    async def after_tool(self, tool_name: str, result: ToolResult, ctx: HookContext):
        log.info(f"Tool {tool_name} completed")

    @hook("chat.params")
    async def modify_chat_params(self, params: dict, ctx: HookContext) -> dict:
        params["temperature"] = 0.3
        return params
```

## Available Hooks

| Hook | When | Use Case |
|------|------|----------|
| `system.prompt.transform` | Before LLM call | Modify system prompt |
| `messages.transform` | Before LLM call | Filter/transform messages |
| `chat.params` | Before LLM call | Modify temperature, max_tokens |
| `chat.headers` | Before LLM call | Inject custom HTTP headers |
| `tool.execute.before` | Before tool runs | Logging, validation |
| `tool.execute.after` | After tool completes | Post-processing, metrics |
| `command.execute.before` | Before CLI command | Intercept commands |
| `shell.env` | Before shell exec | Modify environment vars |
| `session.compacting` | During compaction | Custom summarization |

## Plugin Loading

```python
# ~/.config/aegis/plugins/
├── my-plugin/
│   ├── __init__.py
│   └── plugin.py
└── another-plugin/
    └── plugin.py
```

Plugins are discovered from:
1. `~/.config/aegis/plugins/` (global)
2. `.aegis/plugins/` (project-local)
3. Config file `"plugins": ["my-plugin"]`

---

# Suggested Repository Structure

```text
aegis-engineer/
├── src/
│   ├── aegis/                      # Main package
│   │   ├── __init__.py
│   │   ├── cli/                    # CLI entry point & commands
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # Click/Typer app definition
│   │   │   ├── commands/           # Subcommands (run, solve, config, etc.)
│   │   │   └── completions/        # Shell completion scripts
│   │   ├── server/                 # HTTP server (Starlette)
│   │   │   ├── __init__.py
│   │   │   ├── app.py              # ASGI app
│   │   │   ├── routes/             # /session, /chat, /tool, /provider, /mcp
│   │   │   ├── middleware/         # CORS, auth, rate limiting
│   │   │   └── sse.py              # SSE streaming endpoint
│   │   ├── tui/                    # Terminal UI (Textual)
│   │   │   ├── __init__.py
│   │   │   ├── app.py              # TUI application
│   │   │   ├── screens/            # Chat, settings, session list
│   │   │   ├── widgets/            # Message display, tool output, diff viewer
│   │   │   └── themes.py           # Color themes
│   │   ├── agents/                 # Multi-agent system
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Base agent class
│   │   │   ├── manager.py          # Manager agent
│   │   │   ├── repo_intelligence.py    # Repository Intelligence Agent
│   │   │   ├── dependency_analyzer.py  # Dependency Analysis Agent
│   │   │   ├── issue_classifier.py     # Issue Classification Agent
│   │   │   ├── planner.py          # Planning Agent
│   │   │   ├── context_retriever.py    # Context Retrieval Agent
│   │   │   ├── doc_retriever.py    # Documentation Retrieval Agent
│   │   │   ├── coder.py            # Coding Agent
│   │   │   ├── static_analyzer.py  # Static Analysis Agent
│   │   │   ├── test_runner.py      # Testing Agent
│   │   │   ├── security_reviewer.py    # Security Review Agent
│   │   │   ├── perf_reviewer.py    # Performance Review Agent
│   │   │   ├── regression_detector.py  # Regression Detection Agent
│   │   │   └── pr_generator.py     # PR Generation Agent
│   │   ├── tools/                  # Tool system
│   │   │   ├── __init__.py
│   │   │   ├── registry.py         # Tool registration & discovery
│   │   │   ├── base.py             # ToolDefinition base class
│   │   │   ├── bash.py             # Shell execution tool
│   │   │   ├── read.py             # File read tool
│   │   │   ├── write.py            # File write tool
│   │   │   ├── edit.py             # File edit tool
│   │   │   ├── glob.py             # File pattern matching
│   │   │   ├── grep.py             # Content search
│   │   │   ├── webfetch.py         # HTTP fetch
│   │   │   ├── websearch.py        # Web search
│   │   │   ├── task.py             # Subagent spawning
│   │   │   ├── lsp_tool.py         # LSP integration
│   │   │   └── mcp_tool.py         # MCP tool bridge
│   │   ├── providers/              # LLM provider abstraction
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # LLMProvider base class
│   │   │   ├── openai.py           # OpenAI provider
│   │   │   ├── anthropic.py        # Anthropic provider
│   │   │   ├── google.py           # Google Gemini provider
│   │   │   ├── ollama.py           # Local Ollama provider
│   │   │   ├── litellm.py          # LiteLLM proxy
│   │   │   └── models.py           # Model info & token pricing
│   │   ├── session/                # Session management
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # Session CRUD
│   │   │   ├── message.py          # Message types & serialization
│   │   │   ├── compaction.py       # Message history compaction
│   │   │   └── storage.py          # SQLite storage layer
│   │   ├── permissions/            # Permission engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # Permission checking logic
│   │   │   ├── rules.py            # Rule parsing & matching
│   │   │   └── prompts.py          # Interactive approval prompts
│   │   ├── orchestration/          # Agent orchestration
│   │   │   ├── __init__.py
│   │   │   ├── workflow.py         # Multi-agent workflow
│   │   │   ├── planner_loop.py     # Plan → code → test → review loop
│   │   │   └── retry.py           # Retry logic with backoff
│   │   ├── intelligence/           # Repository Intelligence Engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # Main intelligence engine
│   │   │   ├── ast_graph.py        # AST-based code graph
│   │   │   ├── call_graph.py       # Function call graph
│   │   │   ├── import_graph.py     # Module import graph
│   │   │   ├── class_graph.py      # Class inheritance graph
│   │   │   ├── dependency_graph.py # External dependency graph
│   │   │   ├── knowledge_graph.py  # Semantic knowledge graph
│   │   │   └── queries.py          # Graph query interface
│   │   ├── memory/                 # Memory system
│   │   │   ├── __init__.py
│   │   │   ├── repository_memory.py # Per-repo memory (patches, patterns)
│   │   │   ├── global_memory.py    # Cross-repo learnings
│   │   │   ├── developer_prefs.py  # Code style, naming conventions
│   │   │   ├── failure_memory.py   # What didn't work (avoid repetition)
│   │   │   └── retrieval.py        # Memory search and retrieval
│   │   ├── rag/                    # Retrieval-Augmented Generation
│   │   │   ├── __init__.py
│   │   │   ├── indexer.py          # Code indexing with embeddings
│   │   │   ├── retriever.py        # Vector search
│   │   │   └── embeddings.py       # Embedding model interface
│   │   ├── lsp/                    # Language Server Protocol
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # LSP client implementation
│   │   │   ├── manager.py          # Multi-language server manager
│   │   │   └── servers.py          # Language server configurations
│   │   ├── mcp/                    # Model Context Protocol
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # MCP client (stdio + HTTP)
│   │   │   ├── transport.py        # Transport layer
│   │   │   └── discovery.py        # Tool discovery from servers
│   │   ├── plugins/                # Plugin system
│   │   │   ├── __init__.py
│   │   │   ├── loader.py           # Plugin discovery & loading
│   │   │   ├── hooks.py            # Hook definitions
│   │   │   └── base.py             # Plugin base class
│   │   ├── bus/                    # Event bus
│   │   │   ├── __init__.py
│   │   │   ├── events.py           # Event type definitions
│   │   │   └── pubsub.py           # PubSub implementation
│   │   ├── config/                 # Configuration
│   │   │   ├── __init__.py
│   │   │   ├── schema.py           # Config schema (Pydantic)
│   │   │   ├── loader.py           # Hierarchical config loading
│   │   │   └── defaults.py         # Default configuration
│   │   ├── db/                     # Database
│   │   │   ├── __init__.py
│   │   │   ├── connection.py       # SQLite connection
│   │   │   ├── migrations.py       # Schema migrations
│   │   │   └── models.py           # SQLAlchemy/SQLModel models
│   │   ├── github/                 # GitHub integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # GitHub API client
│   │   │   ├── issues.py           # Issue parsing
│   │   │   └── pr.py               # PR creation
│   │   ├── execution/              # Code execution
│   │   │   ├── __init__.py
│   │   │   ├── docker.py           # Docker sandbox
│   │   │   ├── process.py          # Process management
│   │   │   └── pty.py              # Pseudo-terminal
│   │   ├── snapshot/               # Filesystem snapshot
│   │   │   ├── __init__.py
│   │   │   └── snapshot.py         # Track & revert file changes
│   │   ├── worktree/               # Git worktree
│   │   │   ├── __init__.py
│   │   │   └── worktree.py         # Branch isolation
│   │   ├── metrics/                # Metrics & observability
│   │   │   ├── __init__.py
│   │   │   ├── collector.py        # Metric collection
│   │   │   └── exporter.py         # Prometheus export
│   │   ├── observability/          # Observability system
│   │   │   ├── __init__.py
│   │   │   ├── prompt_timeline.py  # Full prompt log per step
│   │   │   ├── tool_timeline.py    # Tool call log with durations
│   │   │   ├── reasoning_trace.py  # Agent decision chain
│   │   │   ├── cost_breakdown.py   # Per-step token + cost tracking
│   │   │   └── latency_map.py      # Time spent in each phase
│   │   └── benchmark/              # Evaluation framework
│   │       ├── __init__.py
│   │       ├── runner.py           # Benchmark execution
│   │       ├── scorers.py         # Success rate, cost, latency
│   │       ├── swe_bench.py       # SWE-bench integration
│   │       └── leaderboard.py     # Compare against other tools
│   └── bin/
│       └── aegis                   # CLI entry point (#!/usr/bin/env python)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docker/
│   ├── Dockerfile                  # Aegis Engineer image
│   ├── Dockerfile.sandbox          # Execution sandbox image
│   └── docker-compose.yml
├── .aegis/                         # Project-local config
│   ├── config.json
│   ├── permissions.json
│   └── plugins/
├── pyproject.toml
├── README.md
└── LICENSE
```

---

# Technology Stack

## Core
- Python 3.12+
- Typer (CLI framework)
- Textual (TUI framework)
- Pydantic v2 (data validation, schema generation)

## Repository Intelligence
- Tree-sitter (AST parsing)
- NetworkX (call graph, import graph, class graph storage and traversal)
- pyright (Python LSP — type checking, go-to-definition, references)
- typescript-language-server (JS/TS LSP)
- sentence-transformers (bge-large embeddings for semantic search)
- Qdrant (vector database for embedding storage and retrieval)

## Server
- Starlette (Python ASGI framework)
- uvicorn (ASGI server)
- SSE-starlette (Server-Sent Events for streaming)

## AI / LLM
- LiteLLM (unified API for 100+ providers)
- OpenAI Python SDK
- Anthropic Python SDK
- google-generativeai (Gemini SDK)

## Storage
- SQLite via SQLModel (sessions, messages, config, memory, intelligence cache)
- Qdrant (vector DB for embeddings)

## Execution
- Docker SDK for Python (sandbox management)
- ptyprocess (pseudo-terminal for bash tool)

## Observability
- structlog (structured logging)
- Prometheus Python client (metrics)
- OpenTelemetry SDK (tracing)

## Testing
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock

## CI/CD
- GitHub Actions

## Distribution
- PyInstaller (single binary)
- GitHub Releases with cross-compiled binaries

---

# CLI Commands

Aegis Engineer provides a rich CLI with both interactive and non-interactive modes.

## Command Reference

### `aegis` (default)
Launch the TUI (Terminal User Interface).
```bash
aegis                    # Launch TUI in current directory
aegis /path/to/repo      # Launch TUI with specific repo
```

### `aegis run`
Non-interactive mode — send a prompt and get a response.
```bash
aegis run "Fix the bug in auth module where JWT tokens expire too early"
aegis run "Add type hints to all functions in src/utils.py"
aegis run --model claude-4-sonnet "Explain the architecture of this project"
```

### `aegis solve`
Autonomous issue solving — given a repo and issue, solve it end-to-end.
```bash
aegis solve https://github.com/org/repo/issues/42
aegis solve https://github.com/org/repo/issues/42 --branch fix-auth
aegis solve https://github.com/org/repo/issues/42 --max-retries 5
aegis solve https://github.com/org/repo/issues/42 --dry-run
```

### `aegis intelligence`
Build and query the Repository Intelligence Engine.
```bash
aegis intelligence build                    # Build full graph for current repo
aegis intelligence build --incremental      # Update only changed files
aegis intelligence query "who calls jwt.sign?"
aegis intelligence impact src/auth.py:45-80 # Impact analysis
aegis intelligence search "authentication middleware"
aegis intelligence graph --type call        # Visualize call graph
aegis intelligence status                   # Show graph stats
```

### `aegis memory`
Manage the memory system.
```bash
aegis memory list <repo>                    # Show stored memory for a repo
aegis memory show <repo> --issue 42         # Show memory for specific issue
aegis memory stats                          # Show memory usage across repos
aegis memory forget <repo>                  # Clear memory for a repo
aegis memory export                         # Export all memory as JSON
aegis memory import <file.json>             # Import memory from file
```

### `aegis benchmark`
Run benchmarks and compare against other tools.
```bash
aegis benchmark run --repo django/django --issues 100
aegis benchmark swe-bench --split dev
aegis benchmark compare --tools openhands,claude-code,cursor
aegis benchmark report --format markdown --output results.md
aegis benchmark leaderboard
```

### `aegis observe`
Full observability into agent reasoning and execution.
```bash
aegis observe session <session-id>          # Full session trace
aegis observe prompt <session-id> --step 3  # Prompt at specific step
aegis observe cost <session-id>             # Cost breakdown
aegis observe timeline <session-id>         # Latency map
aegis observe reasoning <session-id>        # Reasoning trace
aegis observe export <session-id> -o trace.json
```

### `aegis config`
Manage configuration, providers, and API keys.
```bash
aegis config list                          # Show all config
aegis config set provider anthropic        # Set default provider
aegis config set model claude-4-sonnet     # Set default model
aegis config set api_key.openai sk-...     # Set API key
aegis config set permissions.default ask   # Set permission mode
aegis config unset api_key.openai          # Remove API key
```

### `aegis session`
Manage conversation sessions.
```bash
aegis session list                         # List all sessions
aegis session show <session-id>            # Show session details
aegis session resume <session-id>          # Resume a session
aegis session delete <session-id>          # Delete a session
aegis session export <session-id> -o out.json  # Export as JSON
```

### `aegis mcp`
Manage MCP server connections.
```bash
aegis mcp list                             # List configured servers
aegis mcp add my-server --command "npx @modelcontextprotocol/server-..." 
aegis mcp remove my-server
aegis mcp test my-server                   # Test connection
```

### `aegis doctor`
Diagnostics — check installation, providers, and configuration.
```bash
aegis doctor                               # Run all checks
aegis doctor --verbose                     # Verbose output
```

### `aegis version`
Show version information.
```bash
aegis version
aegis version --json
```

## Global Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--model` | `-m` | Override default model |
| `--provider` | `-p` | Override default provider |
| `--config` | `-c` | Path to config file |
| `--verbose` | `-v` | Enable verbose logging |
| `--no-tui` | | Disable TUI, use plain text output |
| `--json` | `-j` | Output as JSON |
| `--help` | `-h` | Show help |
| `--version` | `-V` | Show version |

## Shell Completions

```bash
# Install completions
aegis completion install bash   # Bash
aegis completion install zsh    # Zsh
aegis completion install fish   # Fish

# Or generate and source manually
aegis completion bash > ~/.bash_completion.d/aegis
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AEGIS_PROVIDER` | Default LLM provider |
| `AEGIS_MODEL` | Default model |
| `AEGIS_API_KEY` | API key (or use `config set`) |
| `AEGIS_PERMISSION_MODE` | Permission mode (interactive/yolo/readonly/ci) |
| `AEGIS_CONFIG_DIR` | Config directory (default: `~/.config/aegis`) |
| `AEGIS_DB_PATH` | SQLite database path |
| `AEGIS_SERVER_PORT` | HTTP server port (default: 4096) |
| `AEGIS_LOG_LEVEL` | Log level (debug/info/warning/error) |
| `AEGIS_NO_COLOR` | Disable colored output |

---

# API Contracts

The HTTP server exposes these routes. All responses are JSON.

## POST /session

Create a new session.

```json
// Request
{
  "title": "Fix JWT expiration",
  "model": "claude-4-sonnet",
  "provider": "anthropic"
}

// Response 201
{
  "id": "sess_abc123",
  "title": "Fix JWT expiration",
  "created_at": "2026-07-24T10:00:00Z",
  "model": "claude-4-sonnet",
  "provider": "anthropic"
}
```

## POST /session/{id}/chat

Submit a prompt to a session. Returns SSE stream.

```json
// Request
{
  "prompt": "Fix the bug where JWT tokens expire too early",
  "stream": true
}

// Response: SSE stream
event: agent.start
data: {"agent":"classifier","session_id":"sess_abc123"}

event: agent.thinking
data: {"agent":"classifier","tokens":2400,"model":"claude-4-sonnet"}

event: agent.done
data: {"agent":"classifier","output":{"type":"bug","complexity":"moderate"}}

event: agent.start
data: {"agent":"planner","session_id":"sess_abc123"}

// ... more events ...

event: workflow.complete
data: {"session_id":"sess_abc123","pr_url":"https://github.com/org/repo/pull/45"}
```

## GET /session/{id}

Get session details.

```json
// Response 200
{
  "id": "sess_abc123",
  "title": "Fix JWT expiration",
  "created_at": "2026-07-24T10:00:00Z",
  "model": "claude-4-sonnet",
  "provider": "anthropic",
  "token_count": 44000,
  "cost_usd": 0.132,
  "message_count": 28,
  "status": "complete"
}
```

## GET /session/{id}/messages

Get all messages in a session.

```json
// Response 200
{
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "Fix the bug where JWT tokens expire too early",
      "created_at": "2026-07-24T10:00:00Z"
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "I'll analyze the issue...",
      "tool_calls": [
        {"name": "graph_query", "params": {"query": "jwt.sign"}}
      ],
      "created_at": "2026-07-24T10:00:02Z"
    }
  ]
}
```

## POST /tool/execute

Execute a tool directly (for debugging).

```json
// Request
{
  "tool": "graph_query",
  "params": {"query": "callers of process_payment"}
}

// Response 200
{
  "output": "Found 3 callers: payments/processor.py:45, api/checkout.py:23, tasks/recurring.py:67",
  "metadata": {"caller_count": 3},
  "duration_ms": 120
}
```

## GET /provider

List available providers and models.

```json
// Response 200
{
  "providers": [
    {
      "name": "anthropic",
      "models": ["claude-4-sonnet", "claude-4-opus", "claude-3.5-sonnet"],
      "auth_configured": true
    },
    {
      "name": "openai",
      "models": ["gpt-4o", "gpt-5", "o1"],
      "auth_configured": true
    }
  ]
}
```

## GET /events

SSE endpoint for real-time updates. Client connects and receives all events for the session.

```
GET /events?session_id=sess_abc123
Accept: text/event-stream

event: agent.start
data: {"agent":"planner","session_id":"sess_abc123"}

event: agent.tool_call
data: {"agent":"planner","tool":"graph_query","params":{"query":"..."}}

// ... continuous stream until session completes
```

---

# Default Configuration

Complete `~/.config/aegis/config.json`:

```json
{
  "$schema": "https://aegis-engineer.dev/config-schema.json",
  
  "provider": {
    "default": "anthropic",
    "model": "claude-4-sonnet",
    "fallback": {
      "provider": "openai",
      "model": "gpt-4o"
    },
    "api_keys": {
      "anthropic": "env:ANTHROPIC_API_KEY",
      "openai": "env:OPENAI_API_KEY",
      "google": "env:GOOGLE_API_KEY"
    }
  },

  "permissions": {
    "default": "ask",
    "trust_mode": "interactive",
    "rules": [
      {"tool": "read", "agent": "*", "level": "allow"},
      {"tool": "glob", "agent": "*", "level": "allow"},
      {"tool": "grep", "agent": "*", "level": "allow"},
      {"tool": "graph_query", "agent": "*", "level": "allow"},
      {"tool": "write", "agent": "coder", "level": "allow"},
      {"tool": "write", "agent": "pr_generator", "level": "allow"},
      {"tool": "bash", "agent": "tester", "level": "allow"},
      {"tool": "bash", "agent": "coder", "level": "ask"},
      {"tool": "webfetch", "agent": "doc_retriever", "level": "allow"}
    ]
  },

  "agents": {
    "max_iterations": 20,
    "tool_timeout": 30,
    "llm_timeout": 120,
    "model_override": {}
  },

  "intelligence": {
    "build_on_clone": true,
    "incremental_updates": true,
    "cache_dir": ".aegis/intelligence",
    "languages": ["python", "javascript", "typescript", "go", "rust"]
  },

  "memory": {
    "enabled": true,
    "store_dir": ".aegis/memory",
    "max_entries_per_repo": 1000,
    "global_memory_enabled": true
  },

  "execution": {
    "sandbox_image": "aegis-sandbox:latest",
    "timeout": 120,
    "mem_limit": "512m"
  },

  "observability": {
    "log_level": "info",
    "prompt_logging": true,
    "tool_logging": true,
    "cost_tracking": true
  },

  "server": {
    "port": 4096,
    "host": "127.0.0.1",
    "cors_origins": ["http://localhost:3000"]
  }
}
```

---

# Project Dependencies

`pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aegis-engineer"
version = "0.1.0"
description = "Autonomous Software Engineering Platform with Repository Intelligence"
requires-python = ">=3.12"
license = "MIT"
readme = "README.md"

dependencies = [
    # CLI & TUI
    "typer>=0.12.0",
    "textual>=0.80.0",
    "rich>=13.0.0",
    
    # Data validation
    "pydantic>=2.0.0",
    "sqlmodel>=0.0.20",
    
    # Server
    "starlette>=0.37.0",
    "uvicorn>=0.30.0",
    "sse-starlette>=2.0.0",
    
    # LLM providers
    "litellm>=1.40.0",
    "openai>=1.50.0",
    "anthropic>=0.34.0",
    "google-generativeai>=0.8.0",
    
    # Repository Intelligence
    "tree-sitter>=0.23.0",
    "tree-sitter-python>=0.23.0",
    "tree-sitter-javascript>=0.23.0",
    "tree-sitter-typescript>=0.23.0",
    "tree-sitter-go>=0.23.0",
    "tree-sitter-rust>=0.23.0",
    "networkx>=3.3",
    "pyright>=1.1.380",
    
    # Embeddings & Vector DB
    "sentence-transformers>=3.1.0",
    "qdrant-client>=1.12.0",
    
    # Docker
    "docker>=7.0.0",
    
    # Observability
    "structlog>=24.0.0",
    "prometheus-client>=0.21.0",
    "opentelemetry-api>=1.27.0",
    
    # HTTP
    "httpx>=0.27.0",
    
    # Git
    "gitpython>=3.1.0",
    
    # Utilities
    "aiofiles>=24.0.0",
    "asyncio-throttle>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[project.scripts]
aegis = "aegis.cli.main:app"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

# Data Models

Core Pydantic models used across the system.

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional

# ── Intelligence Types ──

class GraphType(str, Enum):
    AST = "ast"
    CALL = "call"
    IMPORT = "import"
    CLASS = "class"
    DEPENDENCY = "dependency"
    KNOWLEDGE = "knowledge"

class CodeLocation(BaseModel):
    file: str
    line_start: int
    line_end: int
    symbol_name: str
    symbol_type: str  # "function", "class", "method", "variable"

class IntelligenceQuery(BaseModel):
    graph_type: GraphType
    query: str
    filters: dict = {}

class IntelligenceResult(BaseModel):
    graph_type: GraphType
    results: list[dict]
    relationships: list[dict]
    query_time_ms: float

class ImpactAnalysis(BaseModel):
    changed_file: str
    changed_lines: tuple[int, int]
    directly_affected: list[CodeLocation]
    transitively_affected: list[CodeLocation]
    call_chain: list[list[str]]
    risk_level: str  # "low", "medium", "high"

# ── Agent Types ──

class IssueType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    SECURITY = "security"
    DOCS = "docs"
    DEPENDENCY = "dependency"

class Complexity(str, Enum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EPIC = "epic"

class IssueClassification(BaseModel):
    type: IssueType
    complexity: Complexity
    subsystems: list[str]
    estimated_files: list[str]
    summary: str

class PlanStep(BaseModel):
    step: int
    description: str
    files: list[str]
    tools: list[str]
    expected_output: str

class ImplementationPlan(BaseModel):
    steps: list[PlanStep]
    estimated_tokens: int
    estimated_cost_usd: float
    risk_level: str
    rollback_plan: str

# ── Tool Types ──

class ToolResult(BaseModel):
    output: str
    title: str = ""
    metadata: dict = {}
    attachments: list[dict] = []
    error: bool = False
    duration_ms: float = 0

class ToolCall(BaseModel):
    id: str
    name: str
    params: dict

# ── Provider Types ──

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class ChatChunk(BaseModel):
    delta: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    finish_reason: Optional[str] = None
    usage: Optional[TokenUsage] = None
    cost_usd: Optional[float] = None

# ── Memory Types ──

class SolvedIssue(BaseModel):
    issue_number: int
    title: str
    classification: IssueClassification
    reasoning_chain: list[dict]
    patch: str
    files_changed: list[str]
    tests_passed: bool
    tokens_used: int
    cost_usd: float
    solved_at: datetime

class FailedAttempt(BaseModel):
    issue_type: str
    approach: str
    reason_for_failure: str
    files_involved: list[str]
    suggested_alternative: str

# ── Workflow Types ──

class WorkflowState(str, Enum):
    IDLE = "idle"
    CLASSIFY = "classify"
    PLAN = "plan"
    RETRIEVE = "retrieve"
    CODE = "code"
    ANALYZE = "analyze"
    TEST = "test"
    REVIEW = "review"
    PR = "pr"
    COMPLETE = "complete"
    FAILED = "failed"

class WorkflowContext(BaseModel):
    issue: dict  # GitHubIssue serialized
    classification: Optional[IssueClassification] = None
    plan: Optional[ImplementationPlan] = None
    context: list[CodeLocation] = []
    docs: list[dict] = []
    patch: Optional[dict] = None
    state: WorkflowState = WorkflowState.IDLE
    retries: int = 0

class WorkflowResult(BaseModel):
    state: WorkflowState
    context: WorkflowContext
    pr_url: Optional[str] = None
    error: Optional[str] = None
```

---

# Distribution

Aegis Engineer is distributed as a single binary or Python package.

## Installation Methods

### pip (recommended)
```bash
pip install aegis-engineer
# or
pipx install aegis-engineer
```

### Homebrew (macOS/Linux)
```bash
brew tap aegis-engineer/tap
brew install aegis-engineer
```

### Single Binary (PyInstaller)
```bash
# Build for current platform
python -m PyInstaller --onefile --name aegis src/bin/aegis

# Cross-compile matrix
# Linux x86_64, Linux ARM64
# macOS x86_64, macOS ARM64
# Windows x86_64
```

### Docker
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  aegis-engineer:latest \
  aegis run "Fix the failing tests"
```

### From Source
```bash
git clone https://github.com/aegis-engineer/aegis-engineer
cd aegis-engineer
pip install -e ".[dev]"
aegis version
```

## GitHub Releases

Each release produces binaries for:
- `aegis-linux-amd64` (Ubuntu/Debian/RHEL)
- `aegis-linux-arm64` (AWS Graviton, Raspberry Pi)
- `aegis-darwin-amd64` (Intel Mac)
- `aegis-darwin-arm64` (Apple Silicon)
- `aegis-windows-amd64.exe` (Windows)

## Release Process

1. Bump version in `pyproject.toml`
2. Create GitHub release with tag `v1.2.3`
3. CI builds binaries for all platforms
4. Upload binaries to release
5. Update Homebrew formula
6. Publish to PyPI

---

# Milestone Plan

## v1 — Complete Autonomous Platform

Build the entire platform as one cohesive unit. No phases — everything ships together.

### Core Infrastructure
- CLI entry point with Click/Typer
- Configuration system (hierarchical: `~/.config/aegis/` → `.aegis/`)
- SQLite database with schema migrations
- HTTP server (Starlette/Hono) with SSE streaming
- Event bus for agent ↔ client communication
- Basic TUI with Textual/Rich

### Repository Intelligence Engine
- AST graph via Tree-sitter
- Call graph (static analysis)
- Import graph
- Class/inheritance graph
- Dependency graph (external packages)
- Knowledge graph (semantic fusion layer)
- LSP integration (pyright, typescript-language-server)
- Embedding index (Qdrant + bge-large)
- Incremental graph updates on file changes

### Agent System (13 agents)
- Manager agent (orchestration)
- Repository Intelligence agent
- Dependency Analysis agent
- Issue Classification agent
- Planning agent
- Context Retrieval agent
- Documentation Retrieval agent
- Coding agent
- Static Analysis agent
- Testing agent
- Security Review agent
- Performance Review agent
- Regression Detection agent
- PR Generation agent

### Memory System
- Repository memory (patches, patterns, reasoning chains)
- Global memory (cross-repo learnings)
- Developer preferences (code style, conventions)
- Failure memory (what didn't work)

### Tool System (15+ tools)
- bash, read, write, edit, apply_patch, glob, grep
- codesearch, graph_query, webfetch, websearch
- task, todowrite, skill, lsp

### Provider System
- OpenAI, Anthropic, Google Gemini, Ollama support
- LiteLLM for 100+ provider proxy
- Streaming responses with token tracking
- Fallback chain between providers

### Permission Engine
- Allow/deny/ask rules per tool per agent
- Trust modes: interactive, yolo, readonly, ci
- Interactive approval in TUI

### Session Management
- Session CRUD (create, read, update, delete)
- Message history with structured parts
- Compaction for long sessions
- SQLite persistence

### GitHub Integration
- Clone repositories
- Parse issues
- Create branches
- Push commits
- Open pull requests

### Execution Sandbox
- Docker-based code execution
- PTY for interactive commands
- Formatter → Linter → Test pipeline
- Retry loop with backoff

### Observability
- Prompt timeline (full LLM calls)
- Tool timeline (durations, outputs)
- Agent decision tree
- Cost breakdown (per-step tokens)
- Latency map (time per phase)
- Reasoning trace (chain-of-thought log)

### Evaluation Framework
- `aegis benchmark` command
- SWE-bench integration
- Comparison against OpenHands, Claude Code, Cursor, Aider
- Leaderboard generation

### CLI Commands
- `aegis` (TUI), `aegis run`, `aegis solve`
- `aegis config`, `aegis session`, `aegis mcp`
- `aegis memory`, `aegis intelligence`, `aegis benchmark`
- `aegis doctor`, `aegis completion`, `aegis version`

### Distribution
- PyInstaller single binary (Linux, macOS, Windows)
- pip/pipx install
- Homebrew tap
- Docker image
- GitHub Releases with cross-compiled binaries

---

# Evaluation Metrics

- Issue success rate
- Test pass rate
- Retry count
- Cost per issue
- Average completion time
- Lines changed
- Model comparison
- PR acceptance rate

---

# Evaluation Framework

Aegis Engineer includes a built-in benchmarking system that measures its performance against other tools on standardized tasks.

## `aegis benchmark` Command

```bash
# Run benchmark on a specific repository
aegis benchmark run --repo django/django --issues 100

# Run SWE-bench evaluation
aegis benchmark swe-bench --split dev

# Compare against other tools
aegis benchmark compare --tools openhands,claude-code,cursor,aider

# Generate leaderboard report
aegis benchmark report --format markdown --output results.md
```

## Benchmark Output

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Aegis Benchmark Results                       │
├─────────────┬────────────┬──────────┬──────────┬───────────────┤
│ Tool        │ Success %  │ Avg Cost │ Avg Time │ PR Accept %   │
├─────────────┼────────────┼──────────┼──────────┼───────────────┤
│ Aegis       │ 93.2%      │ $0.42    │ 4.2 min  │ 87%           │
│ Claude Code │ 91.0%      │ $0.38    │ 3.8 min  │ 82%           │
│ OpenHands   │ 82.5%      │ $0.51    │ 5.1 min  │ 75%           │
│ Cursor      │ 88.0%      │ $0.35    │ 3.5 min  │ 79%           │
│ Aider       │ 79.0%      │ $0.29    │ 4.8 min  │ 71%           │
└─────────────┴────────────┴──────────┴──────────┴───────────────┘
```

## SWE-bench Integration

SWE-bench is the industry standard for evaluating coding agents:
- 2,294 real GitHub issues from 12 popular Python repos
- Each issue has a ground-truth patch
- Measures whether the agent's patch passes the same tests

```bash
# Install SWE-bench tasks
aegis benchmark install swe-bench

# Run on full benchmark
aegis benchmark swe-bench --split full

# Run on specific subset
aegis benchmark swe-bench --repos django/django,scikit-learn/scikit-learn

# Analyze failures
aegis benchmark analyze --task-id django__django-16527
```

## Scoring Methodology

| Metric | Weight | Description |
|--------|--------|-------------|
| Test Pass Rate | 40% | % of ground-truth tests passing |
| Code Correctness | 25% | Patch correctness verified by LLM judge |
| Cost Efficiency | 15% | Tokens used relative to baseline |
| Time Efficiency | 10% | Wall-clock time to solution |
| PR Quality | 10% | Description quality, commit messages |

## Custom Benchmarks

```python
# Define custom benchmark tasks
@benchmark_task
async def benchmark_auth_fix():
    """Benchmark: Fix JWT token expiration bug."""
    return BenchmarkTask(
        repo="myorg/myapp",
        issue_number=42,
        expected_files=["src/auth.py", "tests/test_auth.py"],
        test_command="pytest tests/test_auth.py -v",
        max_retries=3,
    )
```

## Leaderboard

The benchmark system generates a public leaderboard:
- Overall ranking across all benchmarks
- Per-repository rankings
- Per-issue-type rankings (bugs, features, refactors)
- Cost efficiency rankings
- Historical trends (is the tool improving over time?)

---

# Future Enhancements

- SWE-bench evaluation
- Voice interface
- Slack integration
- Jira integration
- VS Code extension
- Browser automation
- Multi-language support
- Autonomous release generation

---

# Resume Description

**Aegis Engineer – Autonomous Software Engineering Platform with Repository Intelligence**

Designed and built a production-grade autonomous software engineering platform centered around a Repository Intelligence Engine. The engine constructs live knowledge graphs from codebases using AST analysis, call graphs, dependency graphs, LSP integration, and semantic search. Multiple AI agents query this intelligence layer to autonomously solve GitHub issues — from understanding the problem to producing reviewed, tested pull requests. The system learns from past fixes through repository memory, provides full observability into agent reasoning, and benchmarks against industry tools on SWE-bench.

---

# Why This Project Stands Out

- **Repository Intelligence Engine** — not just embeddings, but a full knowledge graph (AST + call graph + dependency graph + LSP + semantic search) that every agent queries
- **Memory System** — learns from past fixes, stores reasoning chains, improves over time
- **13 specialized agents** working as an engineering organization, not a single prompt
- **Full observability** — prompt timelines, reasoning traces, cost breakdowns, tool timelines
- **Benchmarkable** — `aegis benchmark` compares against OpenHands, Claude Code, Cursor, Aider
- **CLI-first** — works as a terminal tool, not just a web app
- Demonstrates AI engineering, not just prompt engineering
- Combines distributed systems, backend engineering, DevOps, and LLMs
- Suitable as a flagship portfolio project for software engineering and AI roles
