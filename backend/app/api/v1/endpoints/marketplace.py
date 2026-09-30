"""
Workflow template endpoints: the catalogue behind "Start from a template" on
the New Workflow page.

The URL prefix is still ``/marketplace`` because the frontend and any API
client already call it there. The rest of the old template marketplace — agent
templates, reviews, the installation list and the category index — was removed
with the dashboard's Marketplace page, its only caller. The agent-template
install route in particular created agents in the caller's *first* workspace
rather than the current one and skipped the plan's agent limit, so it was not
something to leave reachable with no UI in front of it. Agent templates in the
product come from ``GET /agents/templates/list``.
"""

from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    get_current_org_id,
    get_db,
)
from app.core.entitlement_guard import require_entitlement
from app.models.user import User
from app.models.template import WorkflowTemplate, TemplateInstallation
from app.models.integration import Workflow
from app.schemas.workflow import TriggerType
from app.services.billing import catalog
from app.services.workflows.graph import normalize_graph
# Reused rather than reimplemented: installing a template has to satisfy the
# same trigger rules as creating a workflow by hand, and it is what generates
# a webhook key for a webhook-triggered template.
from app.api.v1.endpoints.workflows import _prepare_trigger_config
from app.core.time import UTCDatetime

router = APIRouter()

#: Routes that must stay reachable without a workspace context — carrier and
#: payment-provider webhooks, and the public embed surfaces. They live on their
#: own router so the authenticated router can carry a blanket permission guard
#: (see app.api.v1.api) without accidentally locking these out.
public_router = APIRouter()


# ==================== Schemas ====================


class WorkflowTemplateResponse(BaseModel):
    """Workflow template response."""

    id: uuid.UUID
    name: str
    slug: str
    description: str
    long_description: Optional[str]
    category: str
    tags: List[str]
    version: str
    icon: Optional[str]
    banner_image: Optional[str]
    author_name: str
    is_official: bool
    is_featured: bool
    is_free: bool
    price: Optional[float]
    install_count: int
    average_rating: float
    review_count: int
    required_integrations: Optional[List[str]]
    published_at: Optional[UTCDatetime]


class WorkflowTemplateDetailResponse(WorkflowTemplateResponse):
    """Detailed workflow template response."""

    workflow_definition: dict
    trigger_type: str
    trigger_config: dict
    setup_guide: Optional[str]
    use_cases: Optional[List]
    compatible_agents: Optional[List[str]]
    is_installed: bool = False


def _workflow_template_detail(
    template: WorkflowTemplate, is_installed: bool = False
) -> "WorkflowTemplateDetailResponse":
    """Serialize a workflow template with its graph and setup guide."""
    return WorkflowTemplateDetailResponse(
        id=template.id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        long_description=template.long_description,
        category=template.category,
        tags=template.tags or [],
        version=template.version,
        icon=template.icon,
        banner_image=template.banner_image,
        author_name=template.author_name,
        is_official=template.is_official,
        is_featured=template.is_featured,
        is_free=template.is_free,
        price=float(template.price) if template.price else None,
        install_count=template.install_count,
        average_rating=float(template.average_rating),
        review_count=template.review_count,
        required_integrations=template.required_integrations,
        published_at=template.published_at,
        workflow_definition=template.workflow_definition or {},
        trigger_type=template.trigger_type,
        trigger_config=template.trigger_config or {},
        setup_guide=template.setup_guide,
        use_cases=template.use_cases,
        compatible_agents=template.compatible_agents,
        is_installed=is_installed,
    )


class InstallTemplateRequest(BaseModel):
    """Install template request."""

    customizations: Optional[dict] = Field(default=None, description="User customizations")


class InstallationResponse(BaseModel):
    """Template installation response."""

    id: uuid.UUID
    template_type: str  # always "workflow"; kept for existing clients
    template_id: uuid.UUID
    template_name: str
    installed_version: str
    created_agent_id: Optional[uuid.UUID]
    created_workflow_id: Optional[uuid.UUID]
    installed_at: UTCDatetime


# ==================== Workflow Templates ====================


@public_router.get("/templates/workflows", response_model=List[WorkflowTemplateResponse])
async def list_workflow_templates(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured_only: bool = False,
    sort_by: str = Query("popular", regex="^(popular|recent|rating)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List workflow templates."""
    query = select(WorkflowTemplate).where(WorkflowTemplate.status == "published")

    # Filters
    if category:
        query = query.where(WorkflowTemplate.category == category)

    if tag:
        query = query.where(WorkflowTemplate.tags.contains([tag]))

    if search:
        search_filter = or_(
            WorkflowTemplate.name.ilike(f"%{search}%"),
            WorkflowTemplate.description.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    if featured_only:
        query = query.where(WorkflowTemplate.is_featured == True)

    # Sorting
    if sort_by == "popular":
        query = query.order_by(WorkflowTemplate.install_count.desc())
    elif sort_by == "recent":
        query = query.order_by(WorkflowTemplate.published_at.desc())
    elif sort_by == "rating":
        query = query.order_by(WorkflowTemplate.average_rating.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        WorkflowTemplateResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            description=t.description,
            long_description=t.long_description,
            category=t.category,
            tags=t.tags,
            version=t.version,
            icon=t.icon,
            banner_image=t.banner_image,
            author_name=t.author_name,
            is_official=t.is_official,
            is_featured=t.is_featured,
            is_free=t.is_free,
            price=float(t.price) if t.price else None,
            install_count=t.install_count,
            average_rating=float(t.average_rating),
            review_count=t.review_count,
            required_integrations=t.required_integrations,
            published_at=t.published_at,
        )
        for t in templates
    ]


@public_router.get(
    "/templates/workflows/{slug}", response_model=WorkflowTemplateDetailResponse
)
async def get_workflow_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get one workflow template, including its graph and setup guide."""
    result = await db.execute(
        select(WorkflowTemplate).where(
            and_(
                WorkflowTemplate.slug == slug,
                WorkflowTemplate.status == "published",
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    return _workflow_template_detail(template)


@router.post(
    "/templates/workflows/{slug}/install",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_entitlement(
                feature=catalog.WORKFLOWS, limit=catalog.LIMIT_WORKFLOWS
            )
        )
    ],
)
async def install_workflow_template(
    slug: str,
    request: InstallTemplateRequest,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a workflow in this workspace from a template.

    The template's ``workflow_definition`` is already a v2 graph, so it is
    copied straight into ``workflow_steps`` and opens in the builder as an
    ordinary workflow — there is no template runtime, and nothing keeps the two
    linked afterwards. Editing the installed workflow is the intended next
    step, which is why it is a copy rather than a reference.

    Installed **inactive**, always. A template that needs a connection picked
    would otherwise start firing against a blank ``connection_id`` the moment
    it landed, and a schedule would start running before anyone had read it.

    Unlike agent templates, installing the same workflow template twice is
    allowed: templates here are starting points, and wanting two workflows from
    one shape (a digest for two teams, say) is ordinary rather than a mistake.
    """
    result = await db.execute(
        select(WorkflowTemplate).where(
            and_(
                WorkflowTemplate.slug == slug,
                WorkflowTemplate.status == "published",
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    customizations = request.customizations or {}

    # Validate the template's own trigger before writing it. A template is
    # authored data, so a bad one is a deployment bug rather than user error —
    # but it would otherwise surface much later, as a workflow that silently
    # never fires.
    try:
        trigger_type = TriggerType(template.trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Template '{slug}' declares an unknown trigger type "
                f"'{template.trigger_type}'."
            ),
        )

    trigger_config = _prepare_trigger_config(
        trigger_type, dict(template.trigger_config or {})
    )

    workflow = Workflow(
        user_id=current_user.id,
        organization_id=org_id,
        name=customizations.get("name") or template.name,
        description=customizations.get("description") or template.description,
        trigger_type=trigger_type.value,
        trigger_config=trigger_config,
        workflow_steps=normalize_graph(template.workflow_definition or {}),
        # Never active on arrival — see the docstring.
        is_active=False,
        execution_mode="sequential",
        error_handling="stop",
        max_retries=3,
        retry_delay=60,
    )

    db.add(workflow)
    await db.flush()

    installation = TemplateInstallation(
        organization_id=org_id,
        workflow_template_id=template.id,
        installed_version=template.version,
        customizations=request.customizations,
        created_workflow_id=workflow.id,
    )
    db.add(installation)

    await db.execute(
        update(WorkflowTemplate)
        .where(WorkflowTemplate.id == template.id)
        .values(install_count=WorkflowTemplate.install_count + 1)
    )

    await db.commit()
    await db.refresh(installation)

    return InstallationResponse(
        id=installation.id,
        template_type="workflow",
        template_id=template.id,
        template_name=template.name,
        installed_version=installation.installed_version,
        created_agent_id=None,
        created_workflow_id=workflow.id,
        installed_at=installation.installed_at,
    )
