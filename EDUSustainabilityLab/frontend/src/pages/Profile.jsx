import React, { useState, useEffect } from 'react';
import { useFeedback } from "../components/FeedbackContext/FeedbackContext";

function editProfile() {
    const [formData, setFormData] = useState({email: ''});
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [showModal, setShowModal] = useState(false);
    const { showMessage } = useFeedback();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    useEffect(() => {
        const showMessage1 = sessionStorage.getItem('profileUpdateSuccess')
        const showMessage2 = sessionStorage.getItem('passwordUpdateSuccess')
        if (showMessage1) {
            showMessage('Profile updated successfully!', 'success')
            sessionStorage.removeItem('profileUpdateSuccess')
        }
        if (showMessage2) {
            showMessage('Password updated successfully!', 'success')
            sessionStorage.removeItem('passwordUpdateSuccess')
        }
    })

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === name + "=") {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Password Change Form State
    const [passwordData, setPasswordData] = useState({
        currentPass: '',
        newPass: '',
        confirmPass: '',
    });

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handlePasswordChange = (e) => {
        setPasswordData({ ...passwordData, [e.target.name]: e.target.value });
    };

    const handleClear = (e) => {
        setPasswordData({
            currentPass: '',
            newPass: '',
            confirmPass: '',
        })
    };

    // Profile Update
    const handleSubmit = async (e) => {
        e.preventDefault();
        setMessage('');
        setError('');

        try {
            let validEmailRegex = false
            if(!emailRegex.test(formData.email)) {
                showMessage('Please enter a valid email','error')
                console.log('aaaaaaaaaaaaa')
            } else {
                validEmailRegex = true;
            }
            let response = null;
            if (validEmailRegex) {
                response = await fetch('/api/updateProfile/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json',
                                "X-CSRFToken": getCookie('csrftoken')
                    },
                    credentials: 'include',
                    body: JSON.stringify(formData),
                });
            } else {
                return;
            }
            
            const result = await response.json();

            if (response.status == 200) {
                sessionStorage.setItem('profileUpdateSuccess', 'true') 
                window.location.reload()
            } else {
                // if (result.error == 'Username') {
                //    showMessage('Username already in use. Please input a different username.', 'error')
                if (result.error == 'Email') {
                    showMessage('Email already in use. Please input a different email.', 'error')
                } else {
                    setError(result.error || 'An error occurred')
                }
            }
            
        } catch (error) {
            console.log(error.message)
            if (error.message == 'Format') {
                showMessage('Please enter a valid email','error')
            } else {
                showMessage('An error occurred while updating your profile', 'error')
            }
        }
    };

    // Password Change Submission
    const handlePasswordSubmit = async (e) => {
        e.preventDefault();
        setMessage('');
        setError('');

        try {
        const response = await fetch('/api/changePassword/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                        "X-CSRFToken": getCookie('csrftoken')
             },
            credentials: 'include',
            body: JSON.stringify(passwordData),
        });

        const result = await response.json();
        if (response.status == 200) {
            sessionStorage.setItem('passwordUpdateSuccess', 'true')
            window.location.reload()
            // setShowModal(false); // Close modal on success
        } else {
            if (result.error == 'Match') {
                console.log(result)
                showMessage('Passwords do not match. Please try again.', 'error')
                handleClear()
            } else if (result.error == 'Current') {
                console.log(result)
                showMessage('Current password is incorrect. Please try again.', 'error')
                handleClear()
            } else {
                setError(result.error || 'An error occurred')
            }
            
        }
        } catch (error) {
            setError('An error occurred while changing your password')
        }
    };

    return (
        <div>
            {error && <p style={{ color: 'red' }}>{error}</p>}
            
            {/* Show the Profile Form if the Modal is not open */}
            {!showModal ? ( 
                <>
                    <h2 className="text-lg text-center font-semibold mb-4">Edit Profile</h2>
                    <form onSubmit={handleSubmit} className="flex flex-col space-y-3">   

                        {/*
                         The following is part of a previous implementation for allowing the user to change their username. We (Semester 2 Team 1) have decided to remove this functionality due
                         to how Django performs login authentication. During user registration, the semester 1 team decided to request an email and password from the user, nothing more. Once
                         the user's profile is approved by an admin, it sets their username to be the same as their email. Django authenticates users by checking if their email matches their
                         username for some reason. So when you login, we ask for an email and password. Django authetication checks to see if the given email matches the username it has on file.
                         This means, if you change one of the two and log out, you won't be able to log back in beacuse Django won't be able to authenticate your account. As such, we have decided to
                         make it so that users can change their email and not their username. Upon changing their email, their username is changed to match it so as to preserve a user's abilit to
                         log back in to the system. We didn't implement a work-around to this problem because we discovered it with only one week left in the semester and determined we didn't have
                         ample time to properly implement the solution we formulated, which is to create a new authentication method to bypass Django's default authenticate method.

                         With that said, I advise not allowing users to change their email and username separately until you have such a work-around in place, otherwise you will have to reset the
                         database every time you get a user locked out of the system.

                         Thanks for reading, and good luck 
                         - Reed Morgan, Lavoine Semester 2 Team 1


                        <label className="font-semibold">Username: </label>
                        <input 
                            name="username" 
                            value={formData.username} 
                            onChange={handleChange}
                            placeholder="Username"
                            className="p-2 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>

                        */}
                        <label className="font-semibold">Email: </label>
                        <input 
                            name="email" 
                            value={formData.email} 
                            onChange={handleChange}
                            placeholder="Email"
                            className="p-2 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>

                        <label className="font-semibold">Password: </label>
                        <button 
                            onClick={() => setShowModal(true)}
                            className="cursor-pointer py-2 text-lg font-bold rounded-lg text-center transition duration-300
                            border-2 border-black bg-gray-400 hover:bg-[#e4e8e9] hover:border-black"
                            >Change Password</button>

                        <button 
                            type="submit" 
                            className="cursor-pointer py-2 text-lg font-bold rounded-lg text-center transition duration-300 
                            border-2 bg-green-700 text-white border-green-700 hover:border-green-800 hover:bg-green-800"
                            >Update Profile</button>
                    </form>
                </>
            ) : ( 
                // Show Password Change Modal
                <div className="modal">
                    <div className="modal-content">
                        <h2 className="text-lg text-center font-semibold mb-4">Change Password</h2>
                        <form onSubmit={handlePasswordSubmit} className="flex flex-col space-y-3">
                            <label className="flex flex-col font-semibold">Current Password:</label>
                            <input 
                                name="currentPass" 
                                type="password" 
                                value={passwordData.currentPass} 
                                onChange={handlePasswordChange}
                                placeholder="Current Password"
                                className="p-2 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>
                        
                            <label className="flex flex-col font-semibold">New Password:</label>
                            <input 
                                name="newPass" 
                                type="password" 
                                value={passwordData.newPass} 
                                onChange={handlePasswordChange} 
                                placeholder="New Password"
                                className="p-2 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>
                        
                            <label className="flex flex-col font-semibold">Confirm New Password:</label>
                            <input 
                                name="confirmPass" 
                                type="password" 
                                value={passwordData.confirmPass} 
                                onChange={handlePasswordChange} 
                                placeholder="New Password"
                                className="p-2 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>
                        
                            <button 
                                type="submit"
                                className="cursor-pointer py-2 text-lg font-bold rounded-lg text-center transition duration-300 
                                border-2 bg-green-700 text-white border-green-700 hover:border-green-800 hover:bg-green-800"
                                >Submit</button>
                            <button 
                                onClick={() => setShowModal(false)}
                                className="cursor-pointer py-2 text-lg font-bold rounded-lg text-center transition duration-300
                                border-2 bg-gray-400 border-black hover:bg-[#e4e8e9] hover:border-2 hover:border-black"
                                >Cancel</button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default editProfile;