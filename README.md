The Movie API is a FastAPI application that allows users to upload, retrieve, search, and then process movie data from a CSV. SQLite is used to store the movie data and allowing it to remain available after the appplication restarts. Everytime a CSV is uploaded the existing movie collection is replaced with newly uploaded data. The data pipeline modules validate and clean through the data. Cache uses the FakeRedis module to store responses for 90 seconds from the GET /movies endpoint. Each limit value has a seperate cache key and as uploads and processing requests are successful, the cache is invalidated such that users can interact with the movie data. 

Starting the API: python -m uvicorn main:app --reload
Running tests: python -m pytest tests -v

Sample processing request: Upload this JSON into the POST/upload
{
  "validation": {
    "required_columns": [
      "title",
      "release_year",
      "rating",
      "genre"
    ],
    "numeric_columns": [
      "release_year",
      "rating"
    ]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}

Expected outcome:  
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
