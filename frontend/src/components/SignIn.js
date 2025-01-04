import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthPage from "./AuthPage";
import "@fortawesome/fontawesome-free/css/all.min.css";
import axios from "axios";

const SignIn = ({ closeAuthPage, onTabSwitch, activeTab }) => {
    const [formData, setFormData] = useState({ 
        email: "",
        password: "",
    });
    const navigate = useNavigate();

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData((prevData) => ({
            ...prevData,
            [name]: value,
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        const { email, password } = formData;

        try {
            const response = await axios.post("http://127.0.0.1:5000/login", {
                email,
                password,
            }, { withCredentials: true });

            console.log(response.data);
            if (response.data.success) {
                alert("Logged in successfully!");
                navigate("/sets");
            } else {
                alert(response.data.message || "An error occurred. Please try again.");
            }
        } catch (error) {
            console.error("Error during login:", error);
            alert("An error occurred. Please try again later.");
        }
    };


    return (
        <AuthPage 
            title="Log back in to keep making progress" 
            closeAuthPage={closeAuthPage}
            onTabSwitch={onTabSwitch}
            activeTab={activeTab}
        >
            <form className="auth-form" onSubmit={handleSubmit}>
                <div className="auth-form-header">
                    <h2
                        className={`auth-tab ${activeTab === "signUp" ? "active-tab" : ""}`}
                        onClick={() => onTabSwitch("signUp")}
                    >
                        Sign up
                    </h2>
                    <h2
                        className={`auth-tab ${activeTab === "signIn" ? "active-tab" : ""}`}
                        onClick={() => onTabSwitch("signIn")}
                    >
                        Log in
                    </h2>
                </div>
                <button className="auth-button google">
                    <i class="fab fa-google"></i> Continue with Google
                </button>
                <button className="auth-button facebook">
                    <i class="fab fa-facebook"></i> Continue with Facebook
                </button>
                <button className="auth-button apple">
                    <i class="fab fa-apple"></i>Log in with Apple
                </button>
                <div className="auth-divider">or email</div>
                <div className="auth-label">
                    <h3>Email</h3>
                    <input 
                        type="email" 
                        name="email"
                        placeholder="Email" 
                        value={formData.email}
                        onChange={handleInputChange}
                    />
                </div>
                <div className="auth-label">
                    <h3>Password</h3>
                    <input 
                        type="password" 
                        name="password"
                        placeholder="Password" 
                        value={formData.password}
                        onChange={handleInputChange}
                    />
                </div>
                <a className="forgot-password" href="/forgot-password">Forgot password?</a>
                <button className="auth-submit">Log in</button>
                <button className="auth-button auth-switch" onClick={() => onTabSwitch("signUp")}>
                    Don't have an account? Sign up
                </button>
            </form>
        </AuthPage>
    );
};

export default SignIn;