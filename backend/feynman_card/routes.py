from flask import Flask, request, jsonify, session
from flask_session import Session
import pandas as pd
import numpy as np
from flask_cors import CORS
from config import AppConfig
from models import db, Users, Flashcards, FlashcardSets
from bcrypt import hashpw, gensalt


app = Flask(__name__)
app.config.from_object(AppConfig)
server_session = Session(app)

db.init_app(app)
with app.app_context():
    db.create_all()


CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://127.0.0.1:3000"]
    }
})


@app.route('/@me')
def get_current_user():
    user = session.get('user')
    if user:
        return jsonify(user), 200  # Explicitly return a 200 status code
    else:
        return jsonify({'message': 'Unauthorized!'}), 401

@app.route('/register', methods=['POST'])
def register():
    from methods import register_user
    data = request.json
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    birthday = data.get('birthday')
    
    if not all([email, username, password, birthday]):
        return jsonify({'message': 'Missing fields!'}), 400
    
    hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
    result = register_user(email, username, hashed_password, birthday)
    return jsonify(result)

@app.route('/login', methods=['POST'])
def login():
    from methods import login_user
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not all([email, password]):
        return jsonify({'message': 'Missing fields!'}), 400
    
    result = login_user(email, password)
    if result["success"]:
        session['user'] = result['user']
        print("Session:", session)
        return jsonify(result)
    return jsonify(result), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully!'})

@app.route('/api/sets', methods=['GET', 'POST'])
def handle_flashcard_sets():
    from methods import create_flashcard_set
    print("Session data in /api/sets:", session)  # Log session data    
    user = session.get('user')
    if not user:
        print("Unauthorized access attempt")
        return jsonify({'message': 'Unauthorized!'}), 401
    
    user_id = user.get('id')
    if not user_id:
        print("User ID not found in session")
        return jsonify({'message': 'Unauthorized!'}), 401

    if request.method == 'GET':
        flashcard_sets = FlashcardSets.query.filter_by(user_id=user_id).all()
        return jsonify([flashcard_set.to_dict() for flashcard_set in flashcard_sets])
    
    elif request.method == 'POST':
        data = request.json
        set_name = data.get('set_name')
        
        if not set_name:
            return jsonify({'message': 'Set name not provided!'}), 400
        
        user = session.get('user')
        if not user:
            print("Unauthorized access attempt")
            return jsonify({'message': 'Unauthorized!'}), 401
        
        user_id = user.get('id')
        if not user_id:
            print("User ID not found in session")
            return jsonify({'message': 'Unauthorized!'}), 401
        
        result = create_flashcard_set(user_id, set_name)
        print("create_flashcard_set:", result)
        return jsonify(result)
    
@app.route('/api/sets/select', methods=['POST'])
def select_flashcard_set():
    print("Session data before selecting a set:", session)
    user = session.get('user')
    if not user:
        print("Unauthorized access attempt")
        return jsonify({'message': 'Unauthorized!'}), 401
    
    user_id = user.get('id') if user else None
    if not user_id:
        print("User ID not found in session")
        return jsonify({'message': 'Unauthorized!'}), 401
    
    data = request.json
    set_id = data.get('set_id')
    
    if not set_id:
        print("Set ID not provided in request")
        return jsonify({'message': 'Set ID not provided!'}), 400
    
    flashcard_set = FlashcardSets.query.filter_by(id=set_id).first()
    if not flashcard_set:
        print("Flashcard set not found or does not belong to the user")
        return jsonify({'message': 'Set not found or does not belong to user!'}), 404
    
    session['selected_set'] = flashcard_set.to_dict()
    print("Session data after selecting a set:", session)
    
    return jsonify({'success': True, 'message': 'Set selected successfully!', 'set': flashcard_set.to_dict()})
    
@app.route('/api/sets/<set_name>/add', methods=['POST'])
def add_flashcard_to_set(set_name):
    from methods import add_flashcard
    user = session.get('user')

    if not user:
        print("Unauthorized access attempt")
        return jsonify({'message': 'Unauthorized!'}), 401
    
    set = session.get('selected_set')
    if not set:
        print("Set not found in session")
        return jsonify({'message': 'Set not found in session!'}), 401
    
    set_id = set.get('id')
    if not set_id:
        print("Set ID not found in session")
        return jsonify({'message': 'Set ID not found in session!'}), 401
    
    data = request.json
    concept = data.get('concept')
    definition = data.get('definition')
    if not concept or not definition:
        return jsonify({'message': 'Concept or definition not provided!'}), 400
    
    result = add_flashcard(set_id, concept, definition)
    return jsonify(result)

@app.route('/api/sets/<set_name>', methods=['GET'])
def get_flashcard_set(set_name):
    from methods import get_flashcard_from_set
    user = session.get('user')
    if not user:
            print("Unauthorized access attempt")
            return jsonify({'message': 'Unauthorized!'}), 401

    user_id = user.get('id')
    if not user_id:
        print("User ID not found in session")
        return jsonify({'message': 'Unauthorized!'}), 401
    
    flashcard_set = session.get('selected_set')
    flashcard_set_id = flashcard_set.get('id')
    
    if not flashcard_set:
        print("Set not found in session")
        return jsonify({'message': 'Set not found in session!'}), 401
    if not flashcard_set_id:
        print("Set ID not found in session")
        return jsonify({'message': 'Set ID not found in session!'}), 401
    
    return jsonify(get_flashcard_from_set(flashcard_set_id))


@app.route('/evaluate', methods=['POST'])
def evaluate_response():
    from methods import evaluate_user_response
    data = request.json  
    card_index = data.get('index')
    set_name = data.get('setName')
    user_response = request.json['response']
    
    flashcard_set = session.get('selected_set')
    
    if not flashcard_set:
        return jsonify({'message': 'Set not found in session!'}), 401
    
    flashcard_set_id = flashcard_set.get('id')
    existing_flashcard_sets = FlashcardSets.query.filter_by(id=flashcard_set_id).all()
    flashcards = Flashcards.query.filter_by(set_id=flashcard_set_id).all()
    
    if not user_response or card_index is None:
        return jsonify({'message': 'Set name or user response not provided!'}), 400
    
    if not existing_flashcard_sets:
        return jsonify({'message': 'Set not found or no flashcards available in the set!'}), 404
    if card_index >= len(flashcards) or card_index < 0:
        return jsonify({'message': 'Card index out of range!'}), 400
    
    flashcard = flashcards[card_index]
    if not flashcard:
        return jsonify({'message': 'Flashcard not found!'}), 404
    
    reference_definition = flashcard.definition
    score, feedback = evaluate_user_response(user_response, reference_definition)
    
    return jsonify({'score': score, 'feedback': feedback})


if __name__ == '__main__':
    app.run(debug=True)