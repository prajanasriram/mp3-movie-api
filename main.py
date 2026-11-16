
import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from src import (
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    MovieCache,
    HealthResponse,
    ProcessConfig,
    log_requests,
    setup_logging,
)

from src.storage import MOVIE_COLUMNS

from data_pipeline import (
    create_cleaning_report,
    process_data,
    validate_dataframe,
)


setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)

storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()

    if extension != ".csv":
        logger.warning(
            "Unsupported file format: %s",
            extension
        )

        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    contents = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(contents))

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError
    ) as error:

        logger.warning("Cannot read CSV: %s", error)

        raise HTTPException(
            status_code=400,
            detail=f"Cannot read CSV: {error}"
        ) from error

    if (
        set(df.columns) != set(MOVIE_COLUMNS)
        or len(df.columns) != len(MOVIE_COLUMNS)
    ):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain exactly the four movie columns"
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain at least one data row"
        )

    df = df[MOVIE_COLUMNS]

    storage.save(df)
    cache.invalidate()

    logger.info(
        f"Uploaded movies: filename={file.filename}, "
        f"rows={len(df)}"
    )

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns)
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    cached_response = cache.get(limit)

    if cached_response is not None:
        logger.info(f"Cache hit: limit={limit}")
        return cached_response

    records = storage.select_columns(
        MOVIE_COLUMNS,
        limit
    )

    total_rows = storage.count_movies()

    response = {
        "data": records,
        "total_rows": total_rows
    }

    cache.set(limit, response)

    logger.info(
        f"Retrieved movies: returned_rows={len(records)}"
    )

    return response


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    try:
        rows = storage.query_movies(
            columns,
            min_rating,
            limit
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

    logger.info(
        f"Queried movies: columns={columns}, "
        f"min_rating={min_rating}, "
        f"returned_rows={len(rows)}"
    )

    return rows


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    df = storage.get()

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No movies to process"
        )

    config_dict = config.model_dump()

    validation = config_dict["validation"]

    for column in validation["numeric_columns"]:
        if column not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Numeric column not found: {column}"
            )

    try:
        validated_df = validate_dataframe(
            df,
            required_columns=validation["required_columns"],
            numeric_columns=validation["numeric_columns"]
        )

        validation_rows_removed = len(df) - len(validated_df)

        validated_copy = validated_df.copy()

        processed_df = process_data(
            validated_df,
            config_dict
        )

        if list(processed_df.columns) != MOVIE_COLUMNS:
            raise ValueError(
                "Processing must preserve all movie columns"
            )

        cleaning_report = create_cleaning_report(
            validated_copy,
            processed_df
        )

    except ValueError as error:
        logger.warning(
            "Processing failed: %s",
            error
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

    storage.save(processed_df)
    cache.invalidate()

    logger.info(
        f"Processed movies: "
        f"validation_removed={validation_rows_removed}, "
        f"rows_before={len(validated_copy)}, "
        f"rows_after={len(processed_df)}"
    )

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report
    }
