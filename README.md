# feynman-flashcard

The Feynman Flashcard Application is a dynamic tool designed to help users create, organize, and evaluate their understanding of concepts using the Feynman technique. The application integrates a **Flask backend** with a **React frontend** to provide a seamless and engaging user experience.

## Features

- **Create and Manage Flashcards**: Users can create flashcard sets and individual flashcards.
- **Feynman Evaluation**: Apply the Feynman technique to evaluate your understanding by explaining concepts in your own words.
- **User Authentication**: Secure login and registration features.
- **Responsive UI**: Built with React for a user-friendly and intuitive interface.

---

## Prerequisites

Ensure you have the following installed:
- **Python 3.8 or higher**
- **Node.js and npm**
- **Git**

---

## Installation and Setup

Follow these steps to get the application up and running:

## Step 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-folder>
```

## Step 2. Backend Setup (Flask)
### 1. Navigate to the backend directory:
```bash
cd backend
```

### 2. Create a Python virtual environment:
```bash
python3 -m venv venv
```

### 3. Activate Virtual Environment
**On macOS/Linux**: 
```bash source 
venv/bin/activate
```
**Windows**: 
```bash
venv\Scripts\activate
```

### 4. Install the required Python dependencies:
```bash
pip install -r requirements.txt
```

### 5. Run the Flask development server:
```bash
flask run
```

The backend will start running at http://127.0.0.1:5000.

## Step 3. Frontend Setup (React)
### 1. Navigate to the frontend directory:
```bash
cd ../frontend
```

### 2. Install the required npm packages:
```bash
npm install
```

### 3. Start the React development server:
```bash
npm start
```

The frontend will start running at http://127.0.0.1:3000.

## Step 4. Development Observations
You may observe changes to the web applications by navigating to http://127.0.0.1:3000.