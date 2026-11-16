
from src import MovieStorage


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload(client, uploaded_movies):
    assert uploaded_movies["rows"] == 20
    assert uploaded_movies["columns"] == 4


def test_get_movies(client, uploaded_movies):
    response = client.get("/movies?limit=2")

    assert response.status_code == 200
    assert response.json()["total_rows"] == 20
    assert len(response.json()["data"]) == 2


def test_search_movies(client, uploaded_movies):
    response = client.get(
        "/movies/search",
        params=[
            ("columns", "title"),
            ("columns", "rating"),
            ("min_rating", 8.5),
            ("limit", 2)
        ]
    )

    assert response.status_code == 200

    assert response.json() == [
        {"id": 4, "title": "Movie C", "rating": 9.0},
        {"id": 2, "title": "Movie B", "rating": 8.5}
    ]


def test_movies_persist(client, test_storage, uploaded_movies):
    reopened_storage = MovieStorage(test_storage.db_path)

    assert reopened_storage.count_movies() == 20
