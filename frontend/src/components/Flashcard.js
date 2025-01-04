import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Modal from 'react-modal';
import './style/Flashcard.css';
import { useParams } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus } from '@fortawesome/free-solid-svg-icons';

const Flashcard = () => {
    const { setName } = useParams();
    const [flashcardSet, setFlashcardSet] = useState([]);
    const [concept, setConcept] = useState('');
    const [definition, setDefinition] = useState('');
    const [response, setResponse] = useState('');
    const [score, setScore] = useState(null);
    const [feedback, setFeedback] = useState('');
    const [showFeynman, setShowFeynman] = useState(false);
    const [selectedFlashcard, setSelectedFlashcard] = useState(null);
    const [flippedStates, setFlippedStates] = useState({});
    const [error, setError] = useState(null);
    const [modalIsOpen, setModalIsOpen] = useState(false);

    // Fetch flashcards for the selected set
    useEffect(() => {
        axios.get(`http://127.0.0.1:5000/api/sets/${setName}`, { withCredentials: true })
            .then(response => {
                console.log(`Flashcards for set ${setName} fetched:`, response.data);
                setFlashcardSet(response.data);
            })
            .catch(error => {
                console.log('Error fetching flashcard set:', error);
                setError(error);
            });
    }, [setName]);

    // Add a new flashcard to the set
    const addFlashcard = () => {
        axios.post(`http://127.0.0.1:5000/api/sets/${setName}/add`, { concept, definition }, { withCredentials: true })
            .then(() => {
                const newFlashcard = { index: flashcardSet.length + 1, concept, definition };
                if (newFlashcard) {
                    console.log('Flashcard added:', newFlashcard);
                    setFlashcardSet([...flashcardSet, newFlashcard]);
                    setConcept('');
                    setDefinition('');
                    setShowFeynman(false);
                    setModalIsOpen(false);
                } else {
                    console.log('Error: Flashcard not added in response:', response.data);
                }
            })
            .catch(error => {
                console.log('Error adding flashcard:', error);
                setError(error);
            });
    };

    // Handle Feynman-style evaluation
    const handleEvaluate = () => {
        if (selectedFlashcard) {
            const payload = { setName, index: selectedFlashcard.index, response };
            console.log('Payload:', payload);
            axios.post('http://127.0.0.1:5000/evaluate', payload, { withCredentials: true })
                .then(res => {
                    setScore(res.data.score);
                    setFeedback(res.data.feedback);
                    setShowFeynman(false); // Reset Feynman mode after evaluation
                    setSelectedFlashcard(null); // Allow selection of a new card for evaluation
                })
                .catch(error => console.log(error));
        }
    };
    

    // Flip flashcard to show definition
    const handleFlip = (index) => {
        if (!showFeynman) {
            setFlippedStates((prevState) => ({
                ...prevState,
                [index]: !prevState[index]
            }));
        }
    };
    
    // Select a flashcard to start the Feynman process
    const selectFlashcard = (flashcard) => {
        setSelectedFlashcard(flashcard);
        setConcept(flashcard.concept);
        setDefinition(flashcard.definition);

        setFlippedStates((prevState) => ({ 
            ...prevState, 
            [flashcard.index]: false
        }));
        
        setShowFeynman(true)
    };

    if (error) {
        return <p>Error loading data: {error.message}</p>;
    }

    return (
        <div className="flashcard-container">
        
        <div className='flashcard-page-header'>
            <h2>Flashcards in Set: {setName}</h2>
        </div>

            <div className='flashcard-body'>

                <ul className="flashcard-list">
                    {flashcardSet.map(flashcard => (
                        <li key={flashcard.index} style={{ cursor: 'pointer' }}>
                            <div
                                className={`flashcard-item ${flippedStates[flashcard.index] ? 'flipped' : ''}`}
                                onClick={() => handleFlip(flashcard.index)}
                            >
                                <p>
                                    {flippedStates[flashcard.index] ? flashcard.definition : `${flashcard.index}: ${flashcard.concept}`}
                                </p>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation(); // Prevent flip on button click
                                        selectFlashcard(flashcard);
                                    }}
                                >
                                    Feynman
                                </button>
                            </div>
                        </li>
                    ))}
                </ul>

                <Modal
                    isOpen={modalIsOpen}
                    onRequestClose={() => setModalIsOpen(false)}
                    contentLabel="Add Flashcard"
                    className="flashcard-modal"
                >
                    <h2>Add New Flashcard</h2>
                    <input
                        type="text"
                        placeholder="Enter Term/Concept"
                        value={concept}
                        onChange={(e) => setConcept(e.target.value)}
                        className="flashcard-input"
                    />
                    <textarea
                        placeholder="Enter Definition"
                        value={definition}
                        onChange={(e) => setDefinition(e.target.value)}
                        className="flashcard-input"
                    />
                    <button onClick={addFlashcard}>Add Flashcard</button>
                    <button onClick={() => setModalIsOpen(false)}>Close</button>
                </Modal>
            </div>

            <div className='flashcard-button-container'>
                <button onClick={() => setModalIsOpen(true)} className="add-flashcard-button">
                    <FontAwesomeIcon icon={faPlus} />
                </button>
            </div>

            <div className='flashcard-feedback-container'>
                {showFeynman && selectedFlashcard && (
                    <div className="feynman-section">
                        <h2>Feynman Technique</h2>
                        <h3>Explain the concept in your own words</h3>
                        <textarea
                            value={response}
                            onChange={(e) => setResponse(e.target.value)}
                            placeholder="Your Explanation..."
                            className="feynman-input"
                        />
                        <button 
                            style={{ cursor: 'pointer' }}
                            onClick={handleEvaluate}>Submit Explanation    
                         </button>
                    </div>
                )}

                <div className="feedback-section">
                    {score !== null && <p><strong>Score:</strong> {score}</p>}
                    {feedback && <p><strong>Feedback:</strong> {feedback}</p>}
                </div>
            </div>
        </div>
    );
};

export default Flashcard;