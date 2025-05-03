import mysql.connector
import os
from urllib.parse import urlparse

def get_db_connection():
    # Get the MySQL URL from environment variables
    db_url = os.getenv('MYSQL_URL')

    if db_url is None:
        raise ValueError("MySQL connection URL is not set in environment variables.")

    # Parse the URL into its components
    url = urlparse(db_url)

    # Extract the components of the MySQL connection URL
    host = url.hostname
    user = url.username
    password = url.password
    database = url.path[1:]  # Remove leading slash from database name
    port = url.port

    # Connect to the MySQL database using the components
    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port
    )
