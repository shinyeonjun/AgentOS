# AgentOS Diagrams v0.2

작성일: 2026-06-16

This document contains Mermaid diagrams for core AgentOS design.

## 1. System Context

```mermaid
flowchart LR
    U[Human User] --> A[External AI Agent<br/>Codex CLI first]
    A --> P[AgentOS Plugin API]
    P --> R[AgentOS Core Runtime]
    R --> S[AI OS Sandbox Session]
    S --> RP[Review Package]
    RP --> A
    A --> U
    U --> AP[Approval Decision]
    AP --> R
    R --> T[Approved Sync Target]
    R --> D[Destroy Sandbox]
```

## 2. Runtime Components

```mermaid
flowchart TD
    API[Plugin API] --> SM[Session Manager]
    SM --> TM[Task Manifest Manager]
    TM --> CR[Capability Resolver]
    CR --> IC[Image Composer]
    IC --> SB[Sandbox Manager]
    SB --> WS[AI OS Workspace]
    WS --> ET[Execution Tracker]
    WS --> CT[Change Tracker]
    ET --> AM[Artifact Manager]
    CT --> AM
    AM --> RB[Review Package Builder]
    RB --> AV[Approval Manager]
    AV --> SY[Sync Manager]
    SY --> CL[Cleanup Manager]
```

## 3. Session State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> INPUT_IMPORTED
    INPUT_IMPORTED --> WORKSPACE_PREPARED
    WORKSPACE_PREPARED --> RUNNING
    RUNNING --> WORK_COMPLETED
    RUNNING --> FAILED
    WORK_COMPLETED --> REVIEW_READY
    FAILED --> REVIEW_READY
    REVIEW_READY --> APPROVED
    REVIEW_READY --> DISCARDED
    REVIEW_READY --> REVISION_REQUESTED
    APPROVED --> SYNCED
    SYNCED --> DESTROYED
    DISCARDED --> DESTROYED
    REVISION_REQUESTED --> RUNNING
    DESTROYED --> [*]
```

## 4. Main Sequence

```mermaid
sequenceDiagram
    participant User
    participant Agent as External AI Agent
    participant API as AgentOS Plugin API
    participant Runtime as AgentOS Runtime
    participant Sandbox as AI OS Sandbox
    participant Store as Metadata/Artifact Store

    User->>Agent: "Fix this project"
    Agent->>API: create_session(task)
    API->>Runtime: create state
    Runtime->>Store: persist session
    Agent->>API: import_input(path)
    Runtime->>Sandbox: copy input into workspace
    Runtime->>Store: baseline manifest
    Agent->>Sandbox: work inside sandbox
    Runtime->>Store: record execution/logs
    Runtime->>Store: collect diffs/artifacts
    Agent->>API: review(session)
    API-->>Agent: review package
    Agent-->>User: summary + "sync?"
    User->>Agent: approve
    Agent->>API: approve(session)
    Agent->>API: sync(session)
    Runtime->>Store: sync event
    Runtime->>Sandbox: destroy workspace
    API-->>Agent: synced + destroyed
```

## 5. Capability Composition

```mermaid
flowchart LR
    T[Task Request] --> A[Task Analyzer]
    A --> C[Required Capabilities]
    C --> B[Base AI OS]
    C --> CODE[Code Capability]
    C --> DATA[Data Capability]
    C --> DOC[Document Capability]
    C --> REP[Report Capability]
    B --> COMP[Composed AI OS Environment]
    CODE --> COMP
    DATA --> COMP
    DOC --> COMP
    REP --> COMP
    COMP --> S[Sandbox Session]
```

## 6. Approval Boundary

```mermaid
flowchart LR
    O[Host Original Files] -- copy only --> W[Sandbox Workspace]
    W --> R[Review Package]
    R --> G{User Approval?}
    G -- No --> X[Discard / Destroy]
    G -- Yes --> Y[Sync Approved Results]
    Y --> H[Host Sync Target]
```

## 7. Context Efficiency Flow

```mermaid
flowchart TD
    P[Project Input] --> M[Workspace Manifest]
    M --> R[Relevant File Selection]
    R --> L[Load Needed Content]
    L --> E[Agent Work]
    E --> D[Diff Generation]
    E --> LOG[Log Artifacts]
    D --> REV[Compact Review Package]
    LOG --> REV
    REV --> CHAT[Short Chat Approval Message]
```
