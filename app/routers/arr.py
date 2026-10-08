from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import User
from app.schemas.arr import ArrEpisode, ArrMovie, ArrSeries
from app.services import arr as arr_service
from app.services.arr import ArrError, ArrNotConfigured, ArrNotFound
from app.services.arr_cache import arr_cache
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/arr", tags=["arr"])


def _map_arr_error(exc: ArrError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _map_not_configured(exc: ArrNotConfigured) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
    )


def _map_not_found(exc: ArrNotFound) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/series", response_model=list[ArrSeries])
async def list_series(
    refresh: bool = False,
    _user: User = Depends(get_current_user),
):
    try:
        if refresh:
            arr_cache.delete("arr:series:list")
        return await arr_service.get_series()
    except ArrNotConfigured as exc:
        raise _map_not_configured(exc) from exc
    except ArrError as exc:
        raise _map_arr_error(exc) from exc


@router.get("/series/{sonarr_id}", response_model=ArrSeries)
async def get_series(
    sonarr_id: int,
    refresh: bool = False,
    _user: User = Depends(get_current_user),
):
    try:
        if refresh:
            arr_cache.delete(f"arr:series:{sonarr_id}")
        return await arr_service.get_series_detail(sonarr_id)
    except ArrNotConfigured as exc:
        raise _map_not_configured(exc) from exc
    except ArrNotFound as exc:
        raise _map_not_found(exc) from exc
    except ArrError as exc:
        raise _map_arr_error(exc) from exc


@router.get("/series/{sonarr_id}/episodes", response_model=list[ArrEpisode])
async def get_series_episodes(
    sonarr_id: int,
    refresh: bool = False,
    _user: User = Depends(get_current_user),
):
    try:
        if refresh:
            arr_cache.delete(f"arr:series:{sonarr_id}:episodes")
        return await arr_service.get_episodes(sonarr_id)
    except ArrNotConfigured as exc:
        raise _map_not_configured(exc) from exc
    except ArrNotFound as exc:
        raise _map_not_found(exc) from exc
    except ArrError as exc:
        raise _map_arr_error(exc) from exc


@router.get("/movies", response_model=list[ArrMovie])
async def list_movies(
    refresh: bool = False,
    _user: User = Depends(get_current_user),
):
    try:
        if refresh:
            arr_cache.delete("arr:movies:list")
        return await arr_service.get_movies()
    except ArrNotConfigured as exc:
        raise _map_not_configured(exc) from exc
    except ArrError as exc:
        raise _map_arr_error(exc) from exc


@router.get("/movies/{radarr_id}", response_model=ArrMovie)
async def get_movie(
    radarr_id: int,
    refresh: bool = False,
    _user: User = Depends(get_current_user),
):
    try:
        if refresh:
            arr_cache.delete(f"arr:movies:{radarr_id}")
        return await arr_service.get_movie(radarr_id)
    except ArrNotConfigured as exc:
        raise _map_not_configured(exc) from exc
    except ArrNotFound as exc:
        raise _map_not_found(exc) from exc
    except ArrError as exc:
        raise _map_arr_error(exc) from exc
