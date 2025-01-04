import React, { useState } from "react";
import AuthPage from "./AuthPage";
import "@fortawesome/fontawesome-free/css/all.min.css";
import Select from "react-select";
import axios from "axios";


const SignUp = ({ closeAuthPage, onTabSwitch, activeTab }) => {
    const [formData, setFormData] = useState({ 
        email: "",
        username: "",
        password: "",
        birthday: { month: "", day: "", year: "" },
    });
    const monthOptions = [
        { value: "01", label: "January" },
        { value: "02", label: "February" },
        { value: "03", label: "March" },
        { value: "04", label: "April" },
        { value: "05", label: "May" },
        { value: "06", label: "June" },
        { value: "07", label: "July" },
        { value: "08", label: "August" },
        { value: "09", label: "September" },
        { value: "10", label: "October" },
        { value: "11", label: "November" },
        { value: "12", label: "December" },
    ];

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData((prevData) => ({
            ...prevData,
            [name]: value,
        }));
    };

    const handleBirthdayChange = (field, selectedOption) => {
        setFormData((prevData) => ({
            ...prevData,
            birthday: {
                ...prevData.birthday,
                [field]: selectedOption.value,
            },
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        const { email, username, password, birthday } = formData;

        try {
            const response = await axios.post("http://127.0.0.1:5000/register", {
                email,
                username,
                password,
                birthday: `${birthday.year}-${birthday.month}-${birthday.day}`,
            }, { withCredentials: true });

            if (response.data.success) {
                alert("Account created successfully!");
                onTabSwitch("signIn");
            } else {
                alert(response.data.message || "Registration failed.");
            }
        } catch (error) {
            console.error("Error during registration:", error);
            alert("An error occurred. Please try again later.");
        }
    };
    
    const dayOptions = Array.from({ length: 31 }, (_, index) => ({
        value: index + 1,
        label: index + 1,
    }));
    
    const yearOptions = Array.from(
        { length: 100 },
        (_, index) => ({
            value: new Date().getFullYear() - index,
            label: new Date().getFullYear() - index,
        })
    );

    return (
        <AuthPage 
            title={
                <>
                    The best way to study <br /> Sign up for free
                </>
            } 
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
                <div className="auth-divider">or email</div>
                <div className="auth-birthday">
                    <h3>Birthday</h3>
                    <div className="auth-birthday-label">
                        <Select 
                            className='select' 
                            options={monthOptions} 
                            placeholder="Month" 
                            onChange={(selectedOption) => handleBirthdayChange("month", selectedOption)}
                        />
                        <Select 
                            className='select' 
                            options={dayOptions} 
                            placeholder="Day" 
                            onChange={(selectedOption) => handleBirthdayChange("day", selectedOption)}   
                        />
                        <Select 
                            className='select' 
                            options={yearOptions} 
                            placeholder="Year" 
                            onChange={(selectedOption) => handleBirthdayChange("year", selectedOption)}
                        />
                    </div>
                </div>
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
                    <h3>Username</h3>
                    <input 
                        type="text" 
                        name="username"
                        placeholder="Username" 
                        value={formData.username}
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
                <div className="auth-checkbox">
                    <input type="checkbox" id="terms" />
                    <label htmlFor="terms">
                        I accept the <a href="/terms">Terms of Service</a> and <a href="/privacy">Privacy Policy</a>
                    </label>
                </div>
                <button className="auth-submit">Sign up</button>
                <button 
                    className="auth-button auth-switch" 
                    onClick={() => onTabSwitch("signIn")}
                >
                    Already have an account? Log in
                </button>
            </form>
        </AuthPage>
    );
};

export default SignUp;