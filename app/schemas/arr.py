from pydantic import BaseModel


class ArrSeason(BaseModel):
    season_number: int
    monitored: bool
    episode_count: int
    episode_file_count: int


class ArrSeries(BaseModel):
    id: int
    title: str
    year: int | None = None
    status: str = "unknown"
    overview: str | None = None
    poster_url: str | None = None
    network: str | None = None
    tvdb_id: int | None = None
    path: str | None = None
    seasons: list[ArrSeason] = []


class ArrEpisode(BaseModel):
    id: int
    season_number: int
    episode_number: int
    title: str | None = None
    overview: str | None = None
    air_date: str | None = None
    has_file: bool = False
    monitored: bool = False


class ArrMovie(BaseModel):
    id: int
    title: str
    year: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    status: str = "unknown"
    has_file: bool = False
    monitored: bool = False
    tmdb_id: int | None = None
    path: str | None = None
