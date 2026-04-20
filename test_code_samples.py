import os
import subprocess
import hashlib
import pickle


def process_user_input(user_input):
    query = "SELECT * FROM users WHERE id = " + user_input
    return query


def execute_command(filename):
    os.system(f"cat {filename}")


def deserialize_data(data):
    obj = pickle.loads(data)
    return obj


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def get_config():
    API_KEY = "sk-1234567890abcdef"
    DB_PASSWORD = "admin123"
    return {"api_key": API_KEY, "db_password": DB_PASSWORD}


class UserController:
    def get_user(self, user_id):
        query = f"SELECT * FROM users WHERE id = {user_id}"
        return query

    def delete_user(self, user_id):
        query = f"DELETE FROM users WHERE id = {user_id}"
        return query
