from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from models import db, Users, Flashcards, FlashcardSets
from bcrypt import checkpw
from datetime import datetime
from uuid import uuid4


model = SentenceTransformer('bert-base-nli-mean-tokens')

def register_user(email, username, password, dob):
    existing_user = Users.query.filter_by(email=email).first()
    if existing_user:
        return {"success": False, "message": "User already exists!"}
    
    user_id = str(uuid4().hex)
    
    new_user = Users(id=user_id, 
                    email=email, 
                    username=username, 
                    password=password, 
                    dob=dob, 
                    date_created=datetime.now()
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {"success": False, "message": f"Error while saving user to the database: {str(e)}"}
        
    return {"success": True, "message": "User registered successfully!"}

def login_user(email, password):
    user = Users.query.filter_by(email=email).first()
    
    if not user:
        return {"success": False, "message": "User not found!"}
    
    if not checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        return {"success": False, "message": "Incorrect password!"}
    
    return {"success": True, "message": "Login successful!", "user": user.to_dict()}

def create_flashcard_set(user_id, set_name):
    existing_set = FlashcardSets.query.filter_by(user_id=user_id, set_name=set_name).first()

    if existing_set:
        return {"success": False, "message": "Set already exists!"}
    
    new_set_id = str(uuid4().hex)
    new_set = FlashcardSets(id=new_set_id, 
                            user_id=user_id, 
                            set_name=set_name, 
                            date_created=datetime.now()
    )
    
    db.session.add(new_set)
    db.session.commit()
    
    return {"success": True, "message": "Set created successfully!", "set": new_set.to_dict()}

def add_flashcard(set_id, concept, definition):
    existing_flashcard = Flashcards.query.filter_by(set_id=set_id, concept=concept).first()
    
    if existing_flashcard:
        return {"success": False, "message": "Flashcard with given concept name already exists!"}
    
    new_flashcard_id = str(uuid4().hex)
    new_flashcard = Flashcards(id=new_flashcard_id, 
                                set_id=set_id, 
                                concept=concept, 
                                definition=definition, 
                                date_created=datetime.now()
    )
    
    db.session.add(new_flashcard)
    db.session.commit()
    
    return {"success": True, "message": "Flashcard added successfully!", "flashcard": new_flashcard.to_dict()}

def get_flashcard_from_set(set_id):
    flashcards = Flashcards.query.filter_by(set_id=set_id).all()
    return [{"index": idx, "concept": flashcard.concept, "definition": flashcard.definition} for idx, flashcard in enumerate(flashcards)]


def evaluate_user_response(response, reference):
    embeddings = model.encode([response, reference])
    similarity_score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    similarity_score = float(similarity_score)
    
    feedback = "Good explanation!" if similarity_score > 0.8 else "Try to add more details."
    
    return similarity_score, feedback