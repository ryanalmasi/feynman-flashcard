import React from "react";
import './style/AuthPage.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faClose } from "@fortawesome/free-solid-svg-icons";

const AuthPage = ({ title, children, closeAuthPage, activeTab, onTabSwitch }) => {
    console.log('AuthPage Props:', { title, children, closeAuthPage, activeTab, onTabSwitch });
    
    return (
        <div className="auth-overlay open">
            <div className="auth-content slide-in">
                <button className="close-button" onClick={closeAuthPage}>
                    <FontAwesomeIcon icon={faClose} />
                </button>
                <div className="auth-left">
                    <h1>{title}</h1>
                </div>
                <div className="auth-right">
                    {children}
                </div>
            </div>
        </div>
    );
};

export default AuthPage;