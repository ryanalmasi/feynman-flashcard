import React from "react";
import { BrowserRouter as Router, Route, Routes} from "react-router-dom";
import HomePage from "./components/HomePage";
import FlashcardSets from "./components/FlashcardSets";
import Flashcard from "./components/Flashcard";
import axios from "axios";

function App() {
    console.log("App component rendered");
    axios.defaults.withCredentials = true;

    return (
        <Router>
            <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/sets" element={<FlashcardSets />} />
                <Route path="/sets/:setName" element={<Flashcard />} />
            </Routes>
        </Router>
    );
}

export default App;