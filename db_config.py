import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vinay@8585",
        database="contact_manager"
    )
