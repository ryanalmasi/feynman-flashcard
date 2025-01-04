import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const FlashcardSets = () => {
    const [sets, setSets] = useState([]);
    const [newSetName, setNewSetName] = useState('');
    const [error, setError] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        axios.get("http://127.0.0.1:5000/api/sets", { withCredentials: true })
            .then(response => {
                console.log('Flashcard sets fetched:', response.data);

                const data = response.data;
                //const setsArray = data && typeof data === 'object' ? Object.keys(data).map((key) => ({ set_name: data[key]["set_name"], flashcards: data[key] })) : [];
                const setsArray = data.map(set => ({
                    id: set.id,
                    set_name: set.set_name,
                    flashcards: set.flashcards || []
                }));
                setSets(setsArray);
            })
            .catch(error => {
                console.log('Error fetching flashcard sets:', error);
                setError(error);
            });
    }, []);

    if (error) {
        console.log('Error loading data:', error);
        return <p>Error loading data: {error.message}</p>;
    }
    if (!sets) {
        console.log('Loading...');
        return <p>Loading...</p>
    }

    const addSet = () => {
        axios.post("http://127.0.0.1:5000/api/sets", { set_name: newSetName}, { withCredentials: true })
            .then(resonse => {
                console.log('Set added:', resonse.data);
                setSets([...sets, { set_name: newSetName, flashcards: [] }]);
                setNewSetName('');
            })
            .catch(error => {
                console.log('Error adding set:', error)
                setError(error)
            });
    };

    const handleSetClick = (setName, setId) => {
        console.log(`Set clicked: setName=${setName}, setId=${setId}`);
        axios.post(
            "http://127.0.0.1:5000/api/sets/select",
            { set_id: setId },
            { withCredentials: true }
        )
        .then(response => {
            console.log('Set selected:', response.data);
            navigate(`/sets/${setName}`);
        })
        .catch(error => {
            console.error('Error selecting set:', error.response?.data || error.message);
            alert('Could not select set. Please try again.');
        });
    };

    return (
        <div>
            <h2>Your Flashcard Sets</h2>
            <ul>
                {sets.length > 0 ? (
                    sets.map((set, index) => (
                        <li key={index}
                            onClick={() => handleSetClick(set.set_name, set.id)}
                            style={{ cursor: 'pointer', color: 'blue', textDecoration: 'underline' }}
                        >
                            {set.set_name} ({set.flashcards.length} flashcards)
                        </li>
                    ))
                ) : (
                    <p>No flashcard sets available. Please create one.</p>
                )}
            </ul>
            <input 
                value={newSetName}
                onChange={(e) => setNewSetName(e.target.value)}
                placeholder='Enter a new set name...'
            />
            <button onClick={addSet}>Add New Set</button>
        </div>
    );
};

export default FlashcardSets;