"""
Template marketplace endpoints.
"""

from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User, OrganizationMember
from app.models.template import (
    AgentTemplate,
    WorkflowTemplate,
    TemplateInstallation,
    TemplateReview,
)
from app.models.agent import Agent
from app.models.integration import Workflow

router = APIRouter()


# ==================== Schemas ====================


class AgentTemplateResponse(BaseModel):
    """Agent template response."""

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
    screenshots: Optional[List]
    author_name: str
    author_organization: Optional[str]
    is_official: bool
    is_featured: bool
    is_free: bool
    price: Optional[float]
    install_count: int
    average_rating: float
    review_count: int
    required_integrations: Optional[List[str]]
    published_at: Optional[datetime]


class AgentTemplateDetailResponse(AgentTemplateResponse):
    """Detailed agent template response."""

    system_prompt: str
    first_message: Optional[str]
    functions: Optional[List]
    customizable_fields: Optional[List]
    setup_guide: Optional[str]
    use_cases: Optional[List]
    demo_url: Optional[str]
    is_installed: bool = False


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
    published_at: Optional[datetime]


class WorkflowTemplateDetailResponse(WorkflowTemplateResponse):
    """Detailed workflow template response."""

    workflow_definition: dict
    trigger_config: dict
    setup_guide: Optional[str]
    use_cases: Optional[List]
    compatible_agents: Optional[List[str]]
    is_installed: bool = False


class InstallTemplateRequest(BaseModel):
    """Install template request."""

    customizations: Optional[dict] = Field(default=None, description="User customizations")


class TemplateReviewRequest(BaseModel):
    """Create/update review request."""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    title: Optional[str] = Field(None, max_length=255)
    review_text: Optional[str] = None


class TemplateReviewResponse(BaseModel):
    """Template review response."""

    id: uuid.UUID
    rating: int
    title: Optional[str]
    review_text: Optional[str]
    verified_installation: bool
    helpful_count: int
    created_at: datetime
    updated_at: datetime


class InstallationResponse(BaseModel):
    """Template installation response."""

    id: uuid.UUID
    template_type: str  # agent or workflow
    template_id: uuid.UUID
    template_name: str
    installed_version: str
    created_agent_id: Optional[uuid.UUID]
    created_workflow_id: Optional[uuid.UUID]
    installed_at: datetime


# ==================== Agent Templates ====================


@router.get("/templates/agents", response_model=List[AgentTemplateResponse])
async def list_agent_templates(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    featured_only: bool = False,
    sort_by: str = Query("popular", regex="^(popular|recent|rating)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List agent templates.

    Args:
        category: Filter by category
        tag: Filter by tag
        search: Search in name and description
        featured_only: Show only featured templates
        sort_by: Sort order (popular, recent, rating)
        limit: Maximum results
        offset: Pagination offset
        db: Database session

    Returns:
        List of agent templates
    """
    query = select(AgentTemplate).where(AgentTemplate.status == "published")

    # Filters
    if category:
        query = query.where(AgentTemplate.category == category)

    if tag:
        query = query.where(AgentTemplate.tags.contains([tag]))

    if search:
        search_filter = or_(
            AgentTemplate.name.ilike(f"%{search}%"),
            AgentTemplate.description.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    if featured_only:
        query = query.where(AgentTemplate.is_featured == True)

    # Sorting
    if sort_by == "popular":
        query = query.order_by(AgentTemplate.install_count.desc())
    elif sort_by == "recent":
        query = query.order_by(AgentTemplate.published_at.desc())
    elif sort_by == "rating":
        query = query.order_by(AgentTemplate.average_rating.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        AgentTemplateResponse(
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
            screenshots=t.screenshots,
            author_name=t.author_name,
            author_organization=t.author_organization,
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


@router.get("/templates/agents/{slug}", response_model=AgentTemplateDetailResponse)
async def get_agent_template(
    slug: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent template details.

    Args:
        slug: Template slug
        current_user: Current authenticated user
        db: Database session

    Returns:
        Agent template details
    """
    result = await db.execute(
        select(AgentTemplate).where(
            and_(
                AgentTemplate.slug == slug,
                AgentTemplate.status == "published",
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    # Get user's organization
    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    org_member = org_result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(
            status_code=400,
            detail="User is not associated with any organization"
        )

    # Check if user has installed this template
    result = await db.execute(
        select(TemplateInstallation).where(
            and_(
                TemplateInstallation.agent_template_id == template.id,
                TemplateInstallation.organization_id == org_member.organization_id,
                TemplateInstallation.is_active == True,
            )
        )
    )
    installation = result.scalar_one_or_none()

    return AgentTemplateDetailResponse(
        id=template.id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        long_description=template.long_description,
        category=template.category,
        tags=template.tags,
        version=template.version,
        icon=template.icon,
        banner_image=template.banner_image,
        screenshots=template.screenshots,
        author_name=template.author_name,
        author_organization=template.author_organization,
        is_official=template.is_official,
        is_featured=template.is_featured,
        is_free=template.is_free,
        price=float(template.price) if template.price else None,
        install_count=template.install_count,
        average_rating=float(template.average_rating),
        review_count=template.review_count,
        required_integrations=template.required_integrations,
        published_at=template.published_at,
        system_prompt=template.system_prompt,
        first_message=template.first_message,
        functions=template.functions,
        customizable_fields=template.customizable_fields,
        setup_guide=template.setup_guide,
        use_cases=template.use_cases,
        demo_url=template.demo_url,
        is_installed=installation is not None,
    )


@router.post(
    "/templates/agents/{slug}/install",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def install_agent_template(
    slug: str,
    request: InstallTemplateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Install an agent template.

    Args:
        slug: Template slug
        request: Installation request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Installation details
    """
    # Get template
    result = await db.execute(
        select(AgentTemplate).where(
            and_(
                AgentTemplate.slug == slug,
                AgentTemplate.status == "published",
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    # Get user's organization
    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    org_member = org_result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(
            status_code=400,
            detail="User is not associated with any organization"
        )

    # Check if already installed
    result = await db.execute(
        select(TemplateInstallation).where(
            and_(
                TemplateInstallation.agent_template_id == template.id,
                TemplateInstallation.organization_id == org_member.organization_id,
                TemplateInstallation.is_active == True,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template already installed",
        )

    # Create agent from template
    agent_config = template.agent_config.copy() if template.agent_config else {}

    # Apply customizations
    if request.customizations:
        for field, value in request.customizations.items():
            if field in (template.customizable_fields or []):
                agent_config[field] = value

    # Create agent
    agent = Agent(
        organization_id=org_member.organization_id,
        name=agent_config.get("name", template.name),
        description=agent_config.get("description", template.description),
        system_prompt=template.system_prompt,
        first_message=template.first_message,
        voice_id=agent_config.get("voice_id"),
        language=agent_config.get("language", "en-US"),
        temperature=agent_config.get("temperature", 0.7),
        max_tokens=agent_config.get("max_tokens", 150),
        is_active=True,
    )

    db.add(agent)
    await db.flush()

    # Create installation record
    installation = TemplateInstallation(
        organization_id=org_member.organization_id,
        agent_template_id=template.id,
        installed_version=template.version,
        customizations=request.customizations,
        created_agent_id=agent.id,
    )

    db.add(installation)

    # Increment install count
    await db.execute(
        update(AgentTemplate)
        .where(AgentTemplate.id == template.id)
        .values(install_count=AgentTemplate.install_count + 1)
    )

    await db.commit()
    await db.refresh(installation)

    return InstallationResponse(
        id=installation.id,
        template_type="agent",
        template_id=template.id,
        template_name=template.name,
        installed_version=installation.installed_version,
        created_agent_id=installation.created_agent_id,
        created_workflow_id=None,
        installed_at=installation.installed_at,
    )


# ==================== Workflow Templates ====================


@router.get("/templates/workflows", response_model=List[WorkflowTemplateResponse])
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


# ==================== Reviews ====================


@router.get("/templates/agents/{slug}/reviews", response_model=List[TemplateReviewResponse])
async def get_agent_template_reviews(
    slug: str,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get reviews for an agent template."""
    # Get template
    result = await db.execute(
        select(AgentTemplate).where(AgentTemplate.slug == slug)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    # Get reviews
    result = await db.execute(
        select(TemplateReview)
        .where(
            and_(
                TemplateReview.agent_template_id == template.id,
                TemplateReview.is_approved == True,
            )
        )
        .order_by(TemplateReview.helpful_count.desc())
        .offset(offset)
        .limit(limit)
    )
    reviews = result.scalars().all()

    return [
        TemplateReviewResponse(
            id=r.id,
            rating=r.rating,
            title=r.title,
            review_text=r.review_text,
            verified_installation=r.verified_installation,
            helpful_count=r.helpful_count,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in reviews
    ]


@router.post(
    "/templates/agents/{slug}/reviews",
    response_model=TemplateReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_template_review(
    slug: str,
    request: TemplateReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a review for an agent template."""
    # Get template
    result = await db.execute(
        select(AgentTemplate).where(AgentTemplate.slug == slug)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    # Check if user already reviewed
    result = await db.execute(
        select(TemplateReview).where(
            and_(
                TemplateReview.agent_template_id == template.id,
                TemplateReview.user_id == current_user.id,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this template",
        )

    # Get user's organization
    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    org_member = org_result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(
            status_code=400,
            detail="User is not associated with any organization"
        )

    # Check if user has installed the template
    result = await db.execute(
        select(TemplateInstallation).where(
            and_(
                TemplateInstallation.agent_template_id == template.id,
                TemplateInstallation.organization_id == org_member.organization_id,
            )
        )
    )
    installation = result.scalar_one_or_none()

    # Create review
    review = TemplateReview(
        organization_id=org_member.organization_id,
        user_id=current_user.id,
        agent_template_id=template.id,
        rating=request.rating,
        title=request.title,
        review_text=request.review_text,
        verified_installation=installation is not None,
    )

    db.add(review)

    # Update template rating
    result = await db.execute(
        select(func.avg(TemplateReview.rating), func.count(TemplateReview.id)).where(
            TemplateReview.agent_template_id == template.id
        )
    )
    avg_rating, count = result.one()

    await db.execute(
        update(AgentTemplate)
        .where(AgentTemplate.id == template.id)
        .values(
            average_rating=float(avg_rating) if avg_rating else 0.0,
            review_count=count,
        )
    )

    await db.commit()
    await db.refresh(review)

    return TemplateReviewResponse(
        id=review.id,
        rating=review.rating,
        title=review.title,
        review_text=review.review_text,
        verified_installation=review.verified_installation,
        helpful_count=review.helpful_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


# ==================== User Installations ====================


@router.get("/my-installations", response_model=List[InstallationResponse])
async def get_my_installations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's template installations."""
    # Get user's organization
    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    org_member = org_result.scalar_one_or_none()

    if not org_member:
        raise HTTPException(
            status_code=400,
            detail="User is not associated with any organization"
        )

    result = await db.execute(
        select(TemplateInstallation)
        .where(
            and_(
                TemplateInstallation.organization_id == org_member.organization_id,
                TemplateInstallation.is_active == True,
            )
        )
        .order_by(TemplateInstallation.installed_at.desc())
    )
    installations = result.scalars().all()

    responses = []
    for inst in installations:
        if inst.agent_template_id:
            # Get agent template
            result = await db.execute(
                select(AgentTemplate).where(AgentTemplate.id == inst.agent_template_id)
            )
            template = result.scalar_one()

            responses.append(
                InstallationResponse(
                    id=inst.id,
                    template_type="agent",
                    template_id=template.id,
                    template_name=template.name,
                    installed_version=inst.installed_version,
                    created_agent_id=inst.created_agent_id,
                    created_workflow_id=None,
                    installed_at=inst.installed_at,
                )
            )
        elif inst.workflow_template_id:
            # Get workflow template
            result = await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.id == inst.workflow_template_id
                )
            )
            template = result.scalar_one()

            responses.append(
                InstallationResponse(
                    id=inst.id,
                    template_type="workflow",
                    template_id=template.id,
                    template_name=template.name,
                    installed_version=inst.installed_version,
                    created_agent_id=None,
                    created_workflow_id=inst.created_workflow_id,
                    installed_at=inst.installed_at,
                )
            )

    return responses


# ==================== Categories ====================


@router.get("/categories")
async def get_categories():
    """Get available template categories."""
    return {
        "agent_categories": [
            {
                "id": "customer_support",
                "name": "Customer Support",
                "description": "Help desk and customer service agents",
                "icon": "🎧",
            },
            {
                "id": "sales",
                "name": "Sales & Lead Qualification",
                "description": "Sales assistants and lead qualification",
                "icon": "💼",
            },
            {
                "id": "scheduling",
                "name": "Appointment Scheduling",
                "description": "Book appointments and manage calendars",
                "icon": "📅",
            },
            {
                "id": "ecommerce",
                "name": "E-commerce",
                "description": "Product recommendations and order tracking",
                "icon": "🛒",
            },
            {
                "id": "healthcare",
                "name": "Healthcare",
                "description": "Patient intake and appointment reminders",
                "icon": "🏥",
            },
            {
                "id": "real_estate",
                "name": "Real Estate",
                "description": "Property inquiries and showings",
                "icon": "🏠",
            },
        ],
        "workflow_categories": [
            {
                "id": "lead_capture",
                "name": "Lead Capture",
                "description": "Capture and qualify leads",
                "icon": "🎯",
            },
            {
                "id": "notifications",
                "name": "Notifications",
                "description": "Send alerts and reminders",
                "icon": "🔔",
            },
            {
                "id": "data_sync",
                "name": "Data Sync",
                "description": "Sync data between systems",
                "icon": "🔄",
            },
        ],
    }
