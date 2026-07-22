"""
Workflow Schemas.

Pydantic schemas for workflow API validation.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enums
class TriggerType(str, Enum):
    """Workflow trigger types."""
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    CALL_COMPLETED = "call_completed"
    CALL_STARTED = "call_started"
    INTEGRATION_EVENT = "integration_event"


class StepType(str, Enum):
    """Workflow step types."""
    # Backend automation steps
    ACTION = "action"
    CONDITION = "condition"
    SWITCH = "switch"
    FILTER = "filter"
    MERGE = "merge"
    LOOP = "loop"
    TRANSFORM = "transform"
    CODE = "code"
    DELAY = "delay"
    # Voice call-flow builder steps (must match frontend builder STEP_TYPES)
    SPEAK = "speak"
    ASK = "ask"
    TRANSFER = "transfer"
    TOOL = "tool"
    WEBHOOK = "webhook"
    AI = "ai"
    END = "end"


class WorkflowStatus(str, Enum):
    """Workflow status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Step Schemas
class WorkflowStepBase(BaseModel):
    """Base workflow step."""
    id: str = Field(..., description="Step ID (unique within workflow)")
    name: str = Field(..., description="Step name")
    type: StepType = Field(..., description="Step type")
    description: Optional[str] = Field(None, description="Step description")


class ActionStepConfig(BaseModel):
    """Action step configuration."""
    connection_id: str = Field(..., description="Integration connection ID")
    action: str = Field(..., description="Action to execute (e.g., 'create_contact')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    retry_on_failure: bool = Field(True, description="Retry on failure")
    timeout_seconds: int = Field(30, description="Timeout in seconds")


class ConditionStepConfig(BaseModel):
    """Condition step configuration."""
    condition: str = Field(..., description="Condition expression (e.g., '{{trigger.status}} == \"completed\"')")
    on_true: List[str] = Field(default_factory=list, description="Step IDs to execute if true")
    on_false: List[str] = Field(default_factory=list, description="Step IDs to execute if false")


class LoopStepConfig(BaseModel):
    """Loop step configuration."""
    items: str = Field(..., description="Items to iterate over (variable reference)")
    steps: List[str] = Field(..., description="Step IDs to execute for each item")
    max_iterations: int = Field(100, description="Maximum iterations")


class TransformStepConfig(BaseModel):
    """Transform step configuration."""
    transformations: Dict[str, str] = Field(..., description="Variable transformations")


class DelayStepConfig(BaseModel):
    """Delay step configuration."""
    delay_seconds: int = Field(..., description="Delay in seconds")


class WorkflowStep(WorkflowStepBase):
    """Workflow step with config."""
    config: Union[
        ActionStepConfig,
        ConditionStepConfig,
        LoopStepConfig,
        TransformStepConfig,
        DelayStepConfig,
        Dict[str, Any]
    ] = Field(..., description="Step configuration")
    next_step_id: Optional[str] = Field(None, description="Next step ID (for sequential execution)")


# Trigger Schemas
class TriggerConfigBase(BaseModel):
    """Base trigger configuration."""
    pass


class ManualTriggerConfig(TriggerConfigBase):
    """Manual trigger configuration."""
    pass


class ScheduleTriggerConfig(TriggerConfigBase):
    """Schedule trigger configuration."""
    cron: str = Field(..., description="Cron expression")
    timezone: str = Field("UTC", description="Timezone")


class WebhookTriggerConfig(TriggerConfigBase):
    """Webhook trigger configuration."""
    webhook_url: Optional[str] = Field(None, description="Generated webhook URL")
    secret: Optional[str] = Field(None, description="Webhook secret for verification")


class CallCompletedTriggerConfig(TriggerConfigBase):
    """Call completed trigger configuration."""
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    duration_min: Optional[int] = Field(None, description="Minimum call duration (seconds)")


class IntegrationEventTriggerConfig(TriggerConfigBase):
    """Integration event trigger configuration."""
    connection_id: str = Field(..., description="Integration connection ID")
    event_type: str = Field(..., description="Event type to listen for")


# Workflow Schemas
class WorkflowCreate(BaseModel):
    """Create workflow schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")

    trigger_type: TriggerType = Field(..., description="Trigger type")
    trigger_config: Dict[str, Any] = Field(..., description="Trigger configuration")

    workflow_steps: List[WorkflowStep] = Field(
        default_factory=list, description="Legacy v1 ordered steps"
    )
    graph: Optional[Dict[str, Any]] = Field(
        None,
        description="v2 graph {schema_version, nodes, edges, viewport}. Takes "
        "precedence over workflow_steps when supplied.",
    )

    is_active: bool = Field(True, description="Whether workflow is active")
    execution_mode: str = Field("async", description="Execution mode (async, sync)")
    error_handling: str = Field("continue", description="Error handling (continue, stop)")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retries")
    retry_delay: int = Field(60, ge=0, description="Retry delay in seconds")

    @validator('workflow_steps')
    def validate_steps(cls, v):
        # Allow empty workflow steps (can be added later)
        if not v:
            return v

        # Validate step IDs are unique
        step_ids = [step.id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError('Step IDs must be unique')

        return v


class WorkflowUpdate(BaseModel):
    """Update workflow schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    trigger_config: Optional[Dict[str, Any]] = None
    workflow_steps: Optional[List[WorkflowStep]] = None
    graph: Optional[Dict[str, Any]] = Field(
        None, description="v2 graph; takes precedence over workflow_steps"
    )
    is_active: Optional[bool] = None
    error_handling: Optional[str] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay: Optional[int] = Field(None, ge=0)


class WorkflowResponse(BaseModel):
    """Workflow response schema."""
    id: str
    user_id: str
    organization_id: str
    name: str
    description: Optional[str]

    trigger_type: str
    trigger_config: Dict[str, Any]

    workflow_steps: List[Dict[str, Any]]
    # Reads the same column as workflow_steps, but exposed as the v2 graph the
    # visual builder consumes. v1 rows are migrated on read.
    #
    # validation_alias, not alias: FastAPI serializes responses with
    # by_alias=True, so a plain alias would emit this field as "workflow_steps"
    # and clobber the real step list with the graph object.
    graph: Optional[Dict[str, Any]] = Field(
        None, validation_alias="workflow_steps"
    )

    is_active: bool
    execution_mode: str
    error_handling: str
    max_retries: int
    retry_delay: int

    total_executions: int
    successful_executions: int
    failed_executions: int
    last_executed_at: Optional[datetime]

    version: int
    created_at: datetime
    updated_at: datetime

    @validator('id', 'user_id', 'organization_id', pre=True)
    def convert_uuid_to_str(cls, v):
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    @validator('workflow_steps', pre=True)
    def convert_workflow_steps(cls, v):
        if isinstance(v, dict):
            if 'steps' in v:
                return v['steps']
            # A v2 graph: expose its executable nodes so any legacy consumer
            # still sees a flat step list.
            if 'nodes' in v:
                return [n for n in v['nodes'] if n.get('type') != 'trigger']
        return v if v else []

    @validator('graph', pre=True)
    def convert_graph(cls, v):
        from app.services.workflows.graph import load_graph

        return load_graph(v if isinstance(v, dict) else None)

    class Config:
        from_attributes = True
        populate_by_name = True


class WorkflowListResponse(BaseModel):
    """List of workflows."""
    workflows: List[WorkflowResponse]
    total: int
    page: int
    page_size: int


# Execution Schemas
class WorkflowExecuteRequest(BaseModel):
    """Execute workflow request."""
    trigger_data: Dict[str, Any] = Field(default_factory=dict, description="Trigger data")
    wait_for_completion: bool = Field(False, description="Wait for workflow to complete")


class WorkflowExecutionStepResult(BaseModel):
    """Single step execution result."""
    step_id: str
    step_name: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class WorkflowExecutionResponse(BaseModel):
    """Workflow execution response."""
    id: UUID
    workflow_id: UUID
    trigger_data: Optional[Dict[str, Any]]

    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]

    steps_executed: int
    steps_successful: int
    steps_failed: int

    result_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]

    cost: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowExecutionListResponse(BaseModel):
    """List of workflow executions."""
    executions: List[WorkflowExecutionResponse]
    total: int
    page: int
    page_size: int


class WorkflowExecutionDetailResponse(WorkflowExecutionResponse):
    """Detailed execution response with step results."""
    step_results: List[WorkflowExecutionStepResult] = Field(default_factory=list)


# Template Schemas
class WorkflowTemplate(BaseModel):
    """Workflow template."""
    id: str
    name: str
    description: str
    category: str
    trigger_type: TriggerType
    workflow_steps: List[WorkflowStep]
    required_connections: List[str] = Field(default_factory=list, description="Required integration connectors")


class WorkflowTemplateListResponse(BaseModel):
    """List of workflow templates."""
    templates: List[WorkflowTemplate]
    total: int


# Statistics Schemas
class WorkflowStatsResponse(BaseModel):
    """Workflow statistics."""
    workflow_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    average_duration_ms: float
    total_cost: float
    executions_last_24h: int
    executions_last_7d: int
    executions_last_30d: int


class WorkflowUsageResponse(BaseModel):
    """Overall workflow usage."""
    total_workflows: int
    active_workflows: int
    total_executions_today: int
    total_executions_month: int
    total_cost_month: float
    most_used_workflows: List[Dict[str, Any]]
