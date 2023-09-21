There's multiple entities participating in the chain of validating a Checkbox snap.

```mermaid
sequenceDiagram
    participant Pipeline as Checkbox Validation Pipeline
    participant Jenkins as Jenkins Job
    participant TServer as Testflinger Server
    participant TAgent as Testflinger Agent
    participant Docker as Docker container (Checkbox Controller)
    participant Device as Device Under Test
    participant CAgent as Checkbox Agent
    note over Device,CAgent: Same device

    Pipeline->>Jenkins: Trigger Jenkins Job
    activate Pipeline
    Jenkins->>TServer: Submit Testing Job
    activate TServer
    loop Poll for Job
        TAgent-->>TServer: Check for Available Jobs
    end
    activate TAgent
    TAgent->>Device: Provision Device & Start Checkbox Agent
    activate Device
    activate CAgent
    TAgent->>Docker: Run Checkbox Controller
    activate Docker
    Docker->>CAgent: Start Canary Test Plan
    CAgent-->>Docker: Return Test Results
    deactivate CAgent
    Docker-->>TAgent: Report Results
    deactivate Docker
    TAgent-->>TServer: Job Completion Status
    deactivate TAgent
    TServer-->>Jenkins: Inform Jenkins of Outcome
    deactivate TServer
    Jenkins-->>Pipeline: Update Pipeline with Job Outcome
    deactivate Pipeline
```
