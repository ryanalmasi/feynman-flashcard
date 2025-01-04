from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from uuid import uuid4

db = SQLAlchemy()

def get_uuid():
    return uuid4().hex

class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    email = db.Column(db.String(345), unique=True, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    dob = db.Column(db.Date, nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "dob": self.dob.isoformat(),
        }

class Flashcards(db.Model):
    __tablename__ = 'flashcards'
    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    set_id = db.Column(db.String(32), db.ForeignKey('flashcard_sets.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    concept = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    
    def to_dict(self):
        return {
            "id": self.id,
            "set_id": self.set_id,
            "date_created": self.date_created.isoformat(),
            "concept": self.concept,
            "definition": self.definition,
        }

class FlashcardSets(db.Model):
    __tablename__ = 'flashcard_sets'
    id = db.Column(db.String(32), primary_key=True, unique=True, default=get_uuid)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    set_name = db.Column(db.String(255), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "set_name": self.set_name,
            "date_created": self.date_created.isoformat(),
        }   