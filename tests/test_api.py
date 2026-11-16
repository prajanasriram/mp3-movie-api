
import pytest

from src import MovieStorage
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    reopened_storage = MovieStorage(test_storage.db_path)

    df = reopened_storage.get()

    assert reopened_storage.count_movies() == 20
    assert len(df) == 20

    assert list(df.columns) == [
        "title",
        "release_year",
        "rating",
        "genre"
    ]

    expected_titles = [
        "Movie A",
        "Movie B",
        "Movie B",
        "Movie C",
        "Movie D",
        "Movie D",
        "Movie E",
        "Movie F",
        "Movie G",
        "Movie H",
        "Movie I",
        "Movie J",
        "Movie K",
        "Movie L",
        "Movie M",
        "Movie N",
        "Movie O",
        "Movie P",
        "Movie Q",
        "Movie R"
    ]

    assert df["title"].tolist() == expected_titles

    stored_movies = reopened_storage.select_columns(
        ["title", "release_year", "rating", "genre"],
        limit=100
    )

    stored_ids = [
        movie["id"] for movie in stored_movies
    ]

    response = client.get("/movies?limit=100")

    assert response.status_code == 200

    response_body = response.json()

    api_ids = [
        movie["id"] for movie in response_body["data"]
    ]

    assert response_body["total_rows"] == 20
    assert stored_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))
    assert stored_ids == api_ids


def test_cache_and_processing(
    client,
    uploaded_movies,
    processing_body
):
    response_100 = client.get("/movies?limit=100")
    response_1 = client.get("/movies?limit=1")

    assert response_100.status_code == 200
    assert response_1.status_code == 200

    body_100 = response_100.json()
    body_1 = response_1.json()

    assert main.cache.get(100) == body_100
    assert main.cache.get(1) == body_1

    repeated_response = client.get("/movies?limit=100")

    assert repeated_response.status_code == 200
    assert repeated_response.json() == body_100

    process_response = client.post(
        "/movies/process",
        json=processing_body
    )

    assert process_response.status_code == 200

    report = process_response.json()

    assert report["validation_rows_removed"] == 0

    assert report["cleaning_report"] == {
        "rows_before": 20,
        "rows_after": 16,
        "rows_removed": 4,
        "columns_before": 4,
        "columns_after": 4,
        "columns_removed": 0
    }

    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    updated_response = client.get("/movies?limit=100")

    assert updated_response.status_code == 200

    updated_body = updated_response.json()

    assert updated_body["total_rows"] == 16
    assert len(updated_body["data"]) == 16

    expected_titles = [
        f"Movie {letter}"
        for letter in "ABCDEFGHIJKLMNOP"
    ]

    actual_titles = [
        movie["title"]
        for movie in updated_body["data"]
    ]

    assert actual_titles == expected_titles

    actual_ids = [
        movie["id"]
        for movie in updated_body["data"]
    ]

    assert actual_ids == list(range(1, 17))

    assert main.cache.get(100) == updated_body


def test_cache_hit_skips_database(
    client,
    uploaded_movies,
    monkeypatch
):
    first_response = client.get("/movies?limit=100")

    assert first_response.status_code == 200

    first_body = first_response.json()

    def fail_if_called(*args, **kwargs):
        pytest.fail(
            "Database should not be accessed on a cache hit"
        )

    monkeypatch.setattr(
        main.storage,
        "select_columns",
        fail_if_called
    )

    monkeypatch.setattr(
        main.storage,
        "count_movies",
        fail_if_called
    )

    second_response = client.get("/movies?limit=100")

    assert second_response.status_code == 200
    assert second_response.json() == first_body
