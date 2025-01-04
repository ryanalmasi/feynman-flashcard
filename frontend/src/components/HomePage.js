import React, { useRef, useState } from 'react';
import './style/HomePage.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChevronLeft, faChevronRight } from '@fortawesome/free-solid-svg-icons';
import feynmanLogo from '../assets/images/feynman.png';
import flashcardLogo from '../assets/images/flashcard_graphic.png';
import learningLogo from '../assets/images/learning.png';
import SignUp from './SignUp';
import SignIn from './SignIn';
import AuthPage from './AuthPage';

const HomePage = () => {
    const carouselRef = useRef(null);
    const overlayRef = useRef(null);
    const descriptionRef = useRef(null);
    const homeRef = useRef(null);
    const [activePage, setActivePage] = useState("home");
    const [activeTab, setActiveTab] = useState("signUp");

    const CARD_WIDTH = 290;
    const GAP = 20;
    const OFFSET = CARD_WIDTH + GAP;

    const scrollToDescription = () => {
        descriptionRef.current.scrollIntoView({ 
            behavior: 'smooth',
            block: 'start', 
        });
    };

    const scrollToHome = () => {
        homeRef.current.scrollIntoView({ 
            behavior: 'smooth',
            block: 'end', 
        });
    };

    const adjustAtEnd = (container) => {
        if (container.scrollLeft + container.offsetWidth >= container.scrollWidth) {
            const firstChild = container.firstElementChild;
            container.appendChild(firstChild);
            container.scrollLeft -= OFFSET;
        }
    };

    const adjustAtStart = (container) => {
        if (container.scrollLeft <= 0) {
            const lastChild = container.lastElementChild;
            container.insertBefore(lastChild, container.firstElementChild);
            container.scrollLeft += OFFSET;
        }
    };

    const scrollLeft = () => {
        if (carouselRef.current) {
            const container = carouselRef.current;
            adjustAtStart(container); // Adjust at the start first
            container.scrollBy({ left: -OFFSET, behavior: 'smooth' });
            setTimeout(() => {
            }, 400);
        }
    };

    const scrollRight = () => {
        if (carouselRef.current) {
            const container = carouselRef.current;
            adjustAtEnd(container);
            container.scrollBy({ left: OFFSET, behavior: 'smooth' });
            setTimeout(() => {
            }, 400);
        }
    };

    const startSpotlight = (event) => {
        const overlay = overlayRef.current;
        const textBox = document.querySelector('.section-text');
        const textBoxRect = textBox.getBoundingClientRect();

        overlay.classList.add('spotlight-active');

        const spotlightX = textBoxRect.left + textBoxRect.width / 2;
        const spotlightY = textBoxRect.top + textBoxRect.height / 2;

        overlay.style.background = `radial-gradient(
            ellipse at ${spotlightX}px ${spotlightY}px,
            rgba(255, 255, 255, 0.1) 8%,
            rgba(0, 0, 0, 0.85) 28%
        )`;
        overlay.style.transition = "opacity 0.3s ease, background-position 0.3s ease";
        window.addEventListener('scroll', maintainSpotlightPosition);
    };

    const stopSpotlight = () => {
        const overlay = overlayRef.current;
        overlay.classList.remove('spotlight-active');
        window.removeEventListener('scroll', maintainSpotlightPosition);
    };

    const maintainSpotlightPosition = () => {
        const overlay = overlayRef.current;
        const textBox = document.querySelector('.section-text');
        const textBoxRect = textBox.getBoundingClientRect();
    
        const spotlightX = textBoxRect.left + textBoxRect.width / 2;
        const spotlightY = textBoxRect.top + textBoxRect.height / 2;
    
        overlay.style.background = `radial-gradient(
            ellipse at ${spotlightX}px ${spotlightY}px,
            rgba(255, 255, 255, 0.1) 8%,
            rgba(0, 0, 0, 0.85) 28%
        )`;
    };

    const openSignUp = () => {
        setActiveTab("signUp");
        setActivePage("signUp")
    };
    const openSignIn = () => {
        setActiveTab("signIn");    
        setActivePage("signIn")
    };
    
    const closeAuthPage = () => {
        const authContent = document.querySelector('.auth-content');

        if (authContent) {
            authContent.classList.add('slide-out');
        }

        setTimeout(() => {
            setActivePage("home");
        }, 300);
    };

    const onTabSwitch = (tab) => {
        setActiveTab(tab);
        setActivePage(tab);

        console.log('activeTab:', activeTab);
        console.log('activePage:', activePage);
    };

    console.log('activePage:', activePage);
    console.log("Active Tab:", activeTab);
    console.log("AuthPage Props in HomePage:", { activeTab, onTabSwitch });

    return (
        <div className='homepage-content-container'>
            {(activePage === "signIn" || activePage === "signUp") && (
                <div className={`auth-overlay open`}>
                    <div className={`auth-content`}>
                        <AuthPage
                            key={activeTab}
                            title={activeTab === "signUp" ? "Sign up for free" : "Log in to your account"}
                            closeAuthPage={closeAuthPage}
                            activeTab={activeTab}
                            onTabSwitch={onTabSwitch}
                        >
                            {activeTab === "signIn" && <SignIn 
                                closeAuthPage={closeAuthPage}
                                onTabSwitch={onTabSwitch}
                                activeTab={activeTab}
                            />}
                            {activeTab === "signUp" && <SignUp 
                                closeAuthPage={closeAuthPage}
                                onTabSwitch={onTabSwitch}
                                activeTab={activeTab}
                            />}
                        </AuthPage>
                    </div>
                </div>
            )}

            <div className='homepage-header' ref={homeRef}>
                <div className='homepage-header-content'>
                    <h1>Feynman Flashcards</h1>
                        <ul className='homepage-nav'>
                            <li><a href='/'>Home</a></li>
                            <li><a href='#' onClick={scrollToDescription}>About</a></li>
                            <li><a href='#' onClick={openSignIn}>Sign in</a></li>
                            <li><a href='/contact'>Contact</a></li>
                        </ul>
                    <li className='getStarted'>
                            <a href="/sets">
                                <span className="icon">➜</span>
                                <span className="text">Get Started</span>
                            </a>
                    </li>
                </div>
            </div>
            <div className='homepage-content'>
                <div className='homepage-title-container'>
                    <h1 className='title1'>Feynman Flashcard Helps You</h1>
                    <h1 className='title2'>Study Effectively Using the Feynman Technique via AI</h1>
                    <p>Learning Made Easy</p>
                </div>
                <button className='title-button' onClick={openSignUp}>Sign up for free</button>

                <div className='features-carousel'>
                    <button class="carousel-button left" onClick={scrollLeft}>
                        <FontAwesomeIcon icon={faChevronLeft} />
                    </button>
                    <div className='carousel-content'>
                        <div className="features-container" ref={carouselRef}>
                            <div className="feature-card learn">
                                <h2>Learn</h2>
                                <p>Interactive lessons for active learning.</p>
                            </div>
                            <div className="feature-card flashcards">
                                <h2>Flashcards</h2>
                                <p>Organized study sets at your fingertips.</p>
                            </div>
                            <div className="feature-card evaluation">
                                <h2>Feynman Evaluation</h2>
                                <p>Assess your understanding using self teaching via the Feynman Technique.</p>
                            </div>
                            <div className="feature-card teaching">
                                <h2>Self-Teaching</h2>
                                <p>Master concepts by teaching yourself.</p>
                            </div>
                            <div className="feature-card ai-learning">
                                <h2>AI Learning</h2>
                                <p>Personalized learning through AI.</p>
                            </div>
                        </div>
                    </div>
                    <button class="carousel-button right" onClick={scrollRight}>
                        <FontAwesomeIcon icon={faChevronRight} />
                    </button>
                </div>
            </div>
            <div className='homepage-description-container' ref={descriptionRef}>
                <div className='homepage-section reverse spotlight-section'>
                    <div className='section-text'>
                        <h2>What is the Feynman Technique?</h2>
                        <p>
                            The Feynman Technique is a mental model that was coined by Nobel-prize winning physicist Richard Feynman. 
                            It is a technique used to learn concepts quickly and effectively by teaching them to someone else in simple terms. 
                            The idea is that if you can explain a concept in simple terms, then you truly understand it. The Feynman Technique is 
                            a powerful tool that can be used to learn new concepts, study for exams, and improve your understanding of complex topics.
                        </p>
                    </div>
                    <div className='section-image spotlight-image' onMouseEnter={startSpotlight} onMouseLeave={stopSpotlight}>
                        <img className='feynman-image' src={feynmanLogo} alt="Feynman Graphic" />
                    </div>
                </div>
                <div className='dark-overlay spotlight' ref={overlayRef} />
                <div className='homepage-section'>
                    <div className='section-text'>
                        <h2>How Does Feynman Flashcards Work?</h2>
                        <p>
                            Feynman Flashcards is an online platform that helps you study effectively using the Feynman Technique.
                            With Feynman Flashcards, you can organize your notes, create personalized study guides, and improve
                            your understanding by breaking down complex concepts into simple, teachable steps.
                        </p>
                        <div className='section-button'>
                            <button className='get-started-button' onClick={openSignUp}>
                                Try it out
                            </button>
                        </div>
                    </div>
                    <div className='section-image'>
                        <img className='flashcard-image' src={flashcardLogo} alt="Flashcard Graphic" />
                    </div>
                </div>

                <div className='homepage-section reverse'>
                    <div className='section-text'>
                        <h2>Why Use Feynman Flashcards?</h2>
                        <p>
                            Feynman Flashcards is a powerful study tool that can help you learn faster and retain information longer.
                            By using the Feynman Technique, you can improve your understanding of complex topics, boost your memory,
                            and enhance your problem-solving skills. With Feynman Flashcards, you can take control of your learning and
                            achieve your academic goals. Sign up for free today and start studying smarter with Feynman Flashcards!
                        </p>
                        <div className='section-button'>
                            <button className='get-started-button' onClick={openSignUp}>
                                Sign up for free
                            </button>
                        </div>
                    </div>
                    <div className='section-image'>
                        <img className='learning-image' src={learningLogo} alt="Learning Graphic" />
                    </div>
                </div>
            </div>
            <div className='homepage-footer'>
                <div className='footer-content'>
                    <div className='footer-section about'>
                        <h3>About Feynman Flashcards</h3>
                        <p>Feynman Flashcards is an innovative platform to help you learn efficiently using the Feynman Technique. Start your journey to mastering complex concepts today!</p>
                    </div>
                    <div className='footer-section links'>
                        <h3>Quick Links</h3>
                        <ul>
                            <li><a href='#' onClick={scrollToHome}>Home</a></li>
                            <li><a href='#' onClick={scrollToDescription}>About</a></li>
                            <li><a href='#' onClick={openSignUp}>Sign Up</a></li>
                            <li><a href='/contact'>Contact</a></li>
                        </ul>
                    </div>
                    <div className='footer-section social'>
                        <h3>Follow Us</h3>
                        <ul className='social-links'>
                            <li><a href='#'><i className="fab fa-facebook"></i> Facebook</a></li>
                            <li><a href='#'><i className="fab fa-twitter"></i> Twitter</a></li>
                            <li><a href='#'><i className="fab fa-instagram"></i> Instagram</a></li>
                        </ul>
                    </div>
                </div>
                <div className='footer-bottom'>
                    <p>&copy; {new Date().getFullYear()} Feynman Flashcards. All Rights Reserved.</p>
                </div>
            </div>
        </div>
    );
};

export default HomePage;