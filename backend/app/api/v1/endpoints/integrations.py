"""
Integration API endpoints.

Handles integration connectors, connections, OAuth2 flow, and connection management.
"""
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.integration import (
    IntegrationConnector,
    IntegrationConnection,
    IntegrationLog,
)
from app.schemas.integration import (
    IntegrationConnectorCreate,
    IntegrationConnectorUpdate,
    IntegrationConnectorResponse,
    IntegrationConnectorListResponse,
    IntegrationConnectionCreate,
    IntegrationConnectionUpdate,
    IntegrationConnectionResponse,
    IntegrationConnectionListResponse,
    OAuth2AuthorizationRequest,
    OAuth2AuthorizationResponse,
    OAuth2CallbackRequest,
    OAuth2TokenRefreshRequest,
    OAuth2TokenRefreshResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    IntegrationActionRequest,
    IntegrationActionResponse,
    ConnectionStatsResponse,
    IntegrationUsageResponse,
)
from app.services.integrations.integration_manager import (
    get_integration_manager,
    IntegrationError,
    ConnectionTestError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Connector Endpoints
# ============================================================================


@router.get("/connectors", response_model=IntegrationConnectorListResponse)
async def list_connectors(
    category: Optional[str] = Query(None, description="Filter by category"),
    auth_type: Optional[str] = Query(None, description="Filter by auth type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List available integration connectors.

    Args:
        category: Filter by category (e.g., 'crm', 'email', 'calendar')
        auth_type: Filter by authentication type
        is_active: Filter by active status
        search: Search by name or description
        page: Page number
        page_size: Number of items per page
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectorListResponse: List of connectors with pagination
    """
    try:
        # Build query
        query = select(IntegrationConnector)

        # Apply filters
        filters = []
        if category:
            filters.append(IntegrationConnector.category == category)
        if auth_type:
            filters.append(IntegrationConnector.auth_type == auth_type)
        if is_active is not None:
            filters.append(IntegrationConnector.is_active == is_active)
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    IntegrationConnector.name.ilike(search_term),
                    IntegrationConnector.description.ilike(search_term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        query = query.order_by(IntegrationConnector.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute query
        result = await db.execute(query)
        connectors = result.scalars().all()

        return IntegrationConnectorListResponse(
            connectors=connectors,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Failed to list connectors: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list connectors: {str(e)}",
        )


@router.get("/connectors/{connector_id}", response_model=IntegrationConnectorResponse)
async def get_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific integration connector by ID.

    Args:
        connector_id: Connector ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectorResponse: Connector details

    Raises:
        HTTPException: If connector not found
    """
    try:
        # Validate UUID
        try:
            connector_uuid = uuid.UUID(connector_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connector ID format",
            )

        # Get connector
        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connector_uuid
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found",
            )

        return connector

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connector: {str(e)}",
        )


# ============================================================================
# OAuth2 Flow Endpoints
# ============================================================================


@router.post("/oauth/authorize", response_model=OAuth2AuthorizationResponse)
async def initiate_oauth_flow(
    request_data: OAuth2AuthorizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Initiate OAuth2 authorization flow.

    Args:
        request_data: OAuth2 authorization request
        current_user: Current authenticated user
        db: Database session

    Returns:
        OAuth2AuthorizationResponse: Authorization URL and state

    Raises:
        HTTPException: If connector not found or OAuth flow fails
    """
    try:
        # Get connector
        try:
            connector_uuid = uuid.UUID(request_data.connector_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connector ID format",
            )

        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connector_uuid
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {request_data.connector_id} not found",
            )

        if not connector.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is not active",
            )

        # Initiate OAuth flow
        manager = get_integration_manager()
        oauth_data = await manager.initiate_oauth_flow(
            connector=connector,
            user_id=str(current_user.id),
            redirect_uri=request_data.redirect_uri,
            scopes=request_data.scopes,
        )

        return OAuth2AuthorizationResponse(
            authorization_url=oauth_data["authorization_url"],
            state=oauth_data["state"],
        )

    except HTTPException:
        raise
    except IntegrationError as e:
        logger.error(f"OAuth flow initiation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {str(e)}",
        )


@router.post("/oauth/callback", response_model=IntegrationConnectionResponse)
async def handle_oauth_callback(
    callback_data: OAuth2CallbackRequest,
    redirect_uri: str = Query(..., description="Redirect URI used in OAuth flow"),
    connection_name: Optional[str] = Query(None, description="Optional connection name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Handle OAuth2 callback and create connection.

    Args:
        callback_data: OAuth2 callback data (code and state)
        redirect_uri: Redirect URI used in authorization
        connection_name: Optional name for the connection
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectionResponse: Created connection

    Raises:
        HTTPException: If OAuth completion fails
    """
    try:
        # Get connector
        try:
            connector_uuid = uuid.UUID(callback_data.connector_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connector ID format",
            )

        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connector_uuid
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {callback_data.connector_id} not found",
            )

        # Complete OAuth flow
        manager = get_integration_manager()
        connection = await manager.complete_oauth_flow(
            connector=connector,
            code=callback_data.code,
            state=callback_data.state,
            redirect_uri=redirect_uri,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
            db=db,
            connection_name=connection_name,
        )

        # Refresh to get connector relationship
        await db.refresh(connection, ["connector"])

        logger.info(f"OAuth connection created: {connection.id}")

        return connection

    except HTTPException:
        raise
    except IntegrationError as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to handle OAuth callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to handle OAuth callback: {str(e)}",
        )


@router.post("/oauth/refresh", response_model=OAuth2TokenRefreshResponse)
async def refresh_oauth_token(
    refresh_request: OAuth2TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Manually refresh OAuth2 access token.

    Args:
        refresh_request: Token refresh request
        current_user: Current authenticated user
        db: Database session

    Returns:
        OAuth2TokenRefreshResponse: Refresh result

    Raises:
        HTTPException: If refresh fails
    """
    try:
        # Get connection
        try:
            connection_uuid = uuid.UUID(refresh_request.connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {refresh_request.connection_id} not found",
            )

        # Get connector
        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connection.connector_id
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connector not found",
            )

        # Refresh token
        manager = get_integration_manager()
        success = await manager.refresh_token(
            connection=connection,
            connector=connector,
            db=db,
        )

        # Refresh connection to get updated expiry
        await db.refresh(connection)

        return OAuth2TokenRefreshResponse(
            success=success,
            message="Token refreshed successfully",
            token_expires_at=connection.token_expires_at,
        )

    except HTTPException:
        raise
    except IntegrationError as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}",
        )


# ============================================================================
# Connection Management Endpoints
# ============================================================================


@router.post("/connections", response_model=IntegrationConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    connection_data: IntegrationConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new integration connection.

    Supports OAuth2, API Key, and Basic authentication.

    Args:
        connection_data: Connection creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectionResponse: Created connection

    Raises:
        HTTPException: If connection creation fails
    """
    try:
        # Get connector
        try:
            connector_uuid = uuid.UUID(connection_data.connector_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connector ID format",
            )

        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connector_uuid
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connection_data.connector_id} not found",
            )

        if not connector.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector is not active",
            )

        manager = get_integration_manager()

        # Handle based on auth type
        if connector.auth_type == "oauth2":
            # OAuth2 requires callback flow
            if not connection_data.oauth2_auth:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth2 authentication data required",
                )

            connection = await manager.complete_oauth_flow(
                connector=connector,
                code=connection_data.oauth2_auth.code,
                state=connection_data.oauth2_auth.state or "",
                redirect_uri=connection_data.oauth2_auth.redirect_uri,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
                connection_name=connection_data.name,
            )

        elif connector.auth_type == "api_key":
            # API Key authentication
            if not connection_data.api_key_auth:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key authentication data required",
                )

            connection = await manager.connect_with_api_key(
                connector=connector,
                api_key=connection_data.api_key_auth.api_key,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
                additional_fields=connection_data.api_key_auth.additional_fields,
                connection_name=connection_data.name,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported auth type: {connector.auth_type}",
            )

        # Refresh to get connector relationship
        await db.refresh(connection, ["connector"])

        logger.info(f"Connection created: {connection.id}")

        return connection

    except HTTPException:
        raise
    except ConnectionTestError as e:
        logger.error(f"Connection test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except IntegrationError as e:
        logger.error(f"Connection creation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}",
        )


@router.get("/connections", response_model=IntegrationConnectionListResponse)
async def list_connections(
    connector_id: Optional[str] = Query(None, description="Filter by connector ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status", alias="status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List user's integration connections.

    Args:
        connector_id: Filter by connector ID
        status_filter: Filter by status (active, disconnected, error)
        is_active: Filter by active status
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectionListResponse: List of connections
    """
    try:
        # Build query
        query = select(IntegrationConnection).where(
            IntegrationConnection.user_id == current_user.id
        )

        # Apply filters
        filters = []
        if connector_id:
            try:
                connector_uuid = uuid.UUID(connector_id)
                filters.append(IntegrationConnection.connector_id == connector_uuid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid connector ID format",
                )

        if status_filter:
            filters.append(IntegrationConnection.status == status_filter)

        if is_active is not None:
            filters.append(IntegrationConnection.is_active == is_active)

        if filters:
            query = query.where(and_(*filters))

        # Order by creation date (newest first)
        query = query.order_by(desc(IntegrationConnection.created_at))

        # Execute query
        result = await db.execute(query)
        connections = result.scalars().all()

        # Load connector relationships
        for connection in connections:
            await db.refresh(connection, ["connector"])

        return IntegrationConnectionListResponse(
            connections=connections,
            total=len(connections),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list connections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list connections: {str(e)}",
        )


@router.get("/connections/{connection_id}", response_model=IntegrationConnectionResponse)
async def get_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific integration connection.

    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectionResponse: Connection details

    Raises:
        HTTPException: If connection not found
    """
    try:
        # Validate UUID
        try:
            connection_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        # Get connection (ensure it belongs to user)
        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found",
            )

        # Load connector relationship
        await db.refresh(connection, ["connector"])

        return connection

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection: {str(e)}",
        )


@router.patch("/connections/{connection_id}", response_model=IntegrationConnectionResponse)
async def update_connection(
    connection_id: str,
    update_data: IntegrationConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update an integration connection.

    Args:
        connection_id: Connection ID
        update_data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationConnectionResponse: Updated connection

    Raises:
        HTTPException: If connection not found or update fails
    """
    try:
        # Get connection
        try:
            connection_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found",
            )

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(connection, field, value)

        connection.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(connection, ["connector"])

        logger.info(f"Connection updated: {connection.id}")

        return connection

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update connection: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update connection: {str(e)}",
        )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Disconnect an integration connection.

    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If connection not found
    """
    try:
        # Get connection
        try:
            connection_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found",
            )

        # Disconnect
        manager = get_integration_manager()
        await manager.disconnect_integration(connection=connection, db=db)

        logger.info(f"Connection disconnected: {connection.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disconnect connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect connection: {str(e)}",
        )


@router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Test an integration connection.

    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        ConnectionTestResponse: Test result

    Raises:
        HTTPException: If connection not found
    """
    try:
        # Get connection
        try:
            connection_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found",
            )

        # Get connector
        query = select(IntegrationConnector).where(
            IntegrationConnector.id == connection.connector_id
        )
        result = await db.execute(query)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connector not found",
            )

        # Test connection
        manager = get_integration_manager()
        test_result = await manager.test_connection(
            connection=connection,
            connector=connector,
        )

        return ConnectionTestResponse(**test_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test connection: {str(e)}",
        )


# ============================================================================
# Statistics & Monitoring Endpoints
# ============================================================================


@router.get("/connections/{connection_id}/stats", response_model=ConnectionStatsResponse)
async def get_connection_stats(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get statistics for a specific connection.

    Args:
        connection_id: Connection ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        ConnectionStatsResponse: Connection statistics

    Raises:
        HTTPException: If connection not found
    """
    try:
        # Get connection
        try:
            connection_uuid = uuid.UUID(connection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid connection ID format",
            )

        query = select(IntegrationConnection).where(
            and_(
                IntegrationConnection.id == connection_uuid,
                IntegrationConnection.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found",
            )

        # Get logs statistics
        from datetime import timedelta

        # Total API calls
        total_query = select(func.count()).where(
            IntegrationLog.connection_id == connection_uuid
        )
        total_result = await db.execute(total_query)
        total_api_calls = total_result.scalar_one()

        # Successful calls
        success_query = select(func.count()).where(
            and_(
                IntegrationLog.connection_id == connection_uuid,
                IntegrationLog.success == True,
            )
        )
        success_result = await db.execute(success_query)
        successful_calls = success_result.scalar_one()

        # Failed calls
        failed_calls = total_api_calls - successful_calls

        # Average response time
        avg_query = select(func.avg(IntegrationLog.duration_ms)).where(
            and_(
                IntegrationLog.connection_id == connection_uuid,
                IntegrationLog.success == True,
            )
        )
        avg_result = await db.execute(avg_query)
        average_response_time_ms = avg_result.scalar_one() or 0.0

        # Last 24h calls
        last_24h = datetime.utcnow() - timedelta(hours=24)
        last_24h_query = select(func.count()).where(
            and_(
                IntegrationLog.connection_id == connection_uuid,
                IntegrationLog.created_at >= last_24h,
            )
        )
        last_24h_result = await db.execute(last_24h_query)
        last_24h_calls = last_24h_result.scalar_one()

        # Error rate
        error_rate_percent = (
            (failed_calls / total_api_calls * 100) if total_api_calls > 0 else 0.0
        )

        return ConnectionStatsResponse(
            connection_id=connection_id,
            total_api_calls=total_api_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            average_response_time_ms=average_response_time_ms,
            last_24h_calls=last_24h_calls,
            error_rate_percent=error_rate_percent,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection stats: {str(e)}",
        )


@router.get("/usage", response_model=IntegrationUsageResponse)
async def get_integration_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get overall integration usage statistics for current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        IntegrationUsageResponse: Usage statistics
    """
    try:
        from datetime import timedelta

        # Total connections
        total_query = select(func.count()).where(
            IntegrationConnection.user_id == current_user.id
        )
        total_result = await db.execute(total_query)
        total_connections = total_result.scalar_one()

        # Active connections
        active_query = select(func.count()).where(
            and_(
                IntegrationConnection.user_id == current_user.id,
                IntegrationConnection.is_active == True,
                IntegrationConnection.status == "active",
            )
        )
        active_result = await db.execute(active_query)
        active_connections = active_result.scalar_one()

        # Get user's connection IDs
        connection_ids_query = select(IntegrationConnection.id).where(
            IntegrationConnection.user_id == current_user.id
        )
        connection_ids_result = await db.execute(connection_ids_query)
        connection_ids = [row[0] for row in connection_ids_result.all()]

        # API calls today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = select(func.count()).where(
            and_(
                IntegrationLog.connection_id.in_(connection_ids),
                IntegrationLog.created_at >= today_start,
            )
        )
        today_result = await db.execute(today_query)
        total_api_calls_today = today_result.scalar_one()

        # API calls this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_query = select(func.count()).where(
            and_(
                IntegrationLog.connection_id.in_(connection_ids),
                IntegrationLog.created_at >= month_start,
            )
        )
        month_result = await db.execute(month_query)
        total_api_calls_month = month_result.scalar_one()

        # Most used connectors
        most_used_query = (
            select(
                IntegrationConnector.name,
                IntegrationConnector.slug,
                func.count(IntegrationConnection.id).label("connection_count"),
            )
            .join(IntegrationConnection, IntegrationConnection.connector_id == IntegrationConnector.id)
            .where(IntegrationConnection.user_id == current_user.id)
            .group_by(IntegrationConnector.id, IntegrationConnector.name, IntegrationConnector.slug)
            .order_by(desc("connection_count"))
            .limit(5)
        )
        most_used_result = await db.execute(most_used_query)
        most_used_connectors = [
            {"name": row[0], "slug": row[1], "connection_count": row[2]}
            for row in most_used_result.all()
        ]

        return IntegrationUsageResponse(
            total_connections=total_connections,
            active_connections=active_connections,
            total_api_calls_today=total_api_calls_today,
            total_api_calls_month=total_api_calls_month,
            most_used_connectors=most_used_connectors,
        )

    except Exception as e:
        logger.error(f"Failed to get integration usage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get integration usage: {str(e)}",
        )
