import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from "react-router-dom";
import { useCsrfToken } from "../../hooks/useCsrfToken";

function Footer() {
    const csrfToken = useCsrfToken();
    const [loggedInUser, setLoggedInUser] = useState("");
    const [isAdmin, setIsAdmin] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/debuggingUser/", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include"
        })
            .then(response => response.json())
            .then(data => {
                if (data.auth === false) {
                    navigate("/login");
                }

                if (data.groups == "Administrator") {
                    setIsAdmin(true);
                }

                setLoggedInUser(data.message);
            })
            .catch(error => console.error("Fetch error:", error));
    }, []);

    return (
        <footer className="bg-green-800 w-full mt-auto p-4 flex flex-col lg:flex-row justify-between items-center lg:items-start space-y-4 lg:space-y-0 z-10">
            <div className="flex flex-col items-center lg:items-start text-center lg:text-left">
                <Link to="/home" className="text-2xl font-bold text-white mb-2">
                    SustainabilityEDU
                </Link>
            </div>
            <nav className="flex flex-wrap justify-center lg:justify-end space-x-4 lg:space-x-6 text-center">
                {isAdmin && (
                    <Link to="/admin" className="text-white">
                        Admin
                    </Link>  
                )}
                <Link to="/create" className="text-white">
                    Create
                </Link>
                <Link to="/search" className="text-white">
                    Search
                </Link>
                <Link to="/about" className="text-white">
                    About
                </Link>
                <Link to="/myactivities" className="text-white">
                    My Activities
                </Link>
                <Link to="/profile" className="text-white">
                    Edit Profile
                </Link>
            </nav>
        </footer>
    );
}

export default Footer;
