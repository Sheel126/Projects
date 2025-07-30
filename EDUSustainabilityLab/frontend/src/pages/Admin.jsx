import React, { useState, useEffect, useRef } from 'react';
import { useNavigate  } from "react-router-dom";

const Admin = () => {
  const navigate = useNavigate();
  //getting user name and displaying 
  // logout handler 
  const isLoggedIn = useRef(false);
  const [loggedInUser, setloggedInUser] = useState("");
  
    useEffect(() => {
        if(!isLoggedIn.current) {
            fetch(process.env.REACT_APP_BACKEND_URL + "/api/debuggingUser/", {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    // "X-CSRFToken": getCookie('csrftoken') 
                },
                credentials: "include" 
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error("Network response was not ok");
                    }
                    console.log("User response:", response);
                    return response.json();
                })
                .then(data => {
                    console.log("User Data:", data.groups);
                    setloggedInUser(data.message);
                    if(data.groups == "Administrator") {
                        navigate("/admin");
                    } else {
                        navigate("/home");
                    }
                })
                .catch(error => {
                    console.error("There was a problem with the fetch operation:", error);
                });   
        }
    },[navigate]);

    return (
        <div>
            <title>Admin Page</title>
            <div className="bg-none w-full flex flex-col justify-center gap-10">
                <button className='w-full text-2xl px-8 py-6 font-semibold text-white bg-green-700 hover:bg-green-800 rounded-lg shadow' onClick={() => navigate('/pendingUsers')}>
                    Pending Users
                </button>
                <button className='w-full text-2xl px-8 py-6 font-semibold text-white bg-green-700 hover:bg-green-800 rounded-lg shadow' onClick={() => navigate('/pendingActivities')}>
                    Pending Activities
                </button>
            </div>
        </div>
    );
};

export default Admin;

