from flask_sqlalchemy import SQLAlchemy

# Single shared db instance — imported by models and app.py
db = SQLAlchemy()