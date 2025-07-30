import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from "react-router-dom";
import { useCsrfToken } from "../../hooks/useCsrfToken";
import { useFeedback } from '../FeedbackContext/FeedbackContext';

export default function Header() {
    const csrfToken = useCsrfToken();
    const [loggedInUser, setLoggedInUser] = useState("");
    const [isAdmin, setIsAdmin] = useState(false);
    const [isPending, setIsPending] = useState(false)
    const navigate = useNavigate();
    const { showMessage } = useFeedback();
    const location = useLocation();
    const [dropdownVisible, setDropdownVisible] = useState(false);
    const dropdownRef = useRef(null);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

                if (data.groups == "Pending") {
                    setIsPending(true);
                }

                setLoggedInUser(data.message);
            })
            .catch(error => console.error("Fetch error:", error));
    }, []);

    const logoutHandler = () => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/logout/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include"
        })
            .then(response => response.json())
            .then(() => {
                showMessage('You have been logged out successfully', 'success');
                navigate('/');
            })
            .catch(error => console.error("Logout error:", error));
    };

    useEffect(() => {
        function handleClickOutside(event) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setDropdownVisible(false);
            }
        }
        document.addEventListener("click", handleClickOutside);
        return () => document.removeEventListener("click", handleClickOutside);
    }, []);
    
    return (
        <header className="fixed top-0 left-0 w-full bg-zinc-50 shadow-md z-50">
            <div className="flex justify-between items-center px-6 py-4">
                <Link to="/home" className="text-2xl font-bold text-green-700">
                    SustainabilityEDU
                </Link>
                <nav className="hidden md:flex items-center space-x-6">
                    {isAdmin && (
                        <Link
                            to="/admin"
                            className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/admin" ? "font-bold" : ""}`}
                        >
                            Admin
                        </Link>
                    )}
                    {!isPending && (
                        <Link
                            to="/create"
                            className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/create" ? "font-bold" : ""}`}
                        >
                            Create
                        </Link>
                    )}
                    <Link
                        to="/search"
                        className={`text-lg text-green-700 hover:scale-110 transition ${["/search", "/activityView"].includes(location.pathname) ? "font-bold" : ""}`}
                    >
                        Search
                    </Link>
                    <Link
                        to="/about"
                        className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/about" ? "font-bold" : ""}`}
                    >
                        About
                    </Link>
                    <div className="relative hidden md:block">
                        <button
                            onClick={(event) => {
                                event.stopPropagation();
                                setDropdownVisible((prev) => !prev);
                            }}
                            className="text-lg font-bold bg-zinc-50 hover:bg-zinc-50 text-green-700 hover:scale-110 transition"
                        >
                            {loggedInUser}
                        </button>

                        {dropdownVisible && (
                            <div ref={dropdownRef} className="absolute right-0 mt-2 w-40 bg-zinc-50 border shadow-lg rounded-lg">
                                <Link to="/myactivities">
                                    <div className={`text-lg px-4 py-2 text-center text-green-700 hover:bg-zinc-100 cursor-pointer ${location.pathname === "/profile" ? "font-bold" : ""}`}>
                                        My Activities
                                    </div>
                                </Link>
                                <Link to="/profile">
                                    <div className={`text-lg px-4 py-2 text-center text-green-700 hover:bg-zinc-100 cursor-pointer ${location.pathname === "/profile" ? "font-bold" : ""}`}>
                                        Edit Profile
                                    </div>
                                </Link>
                                <div
                                    onClick={logoutHandler}
                                    className="text-lg px-4 py-2 text-center text-red-500 hover:bg-zinc-100 cursor-pointer rounded-b-lg"
                                >
                                    Logout
                                </div>
                            </div>
                        )}
                    </div>
                </nav>
                <button 
                    onClick={() => setMobileMenuOpen(!mobileMenuOpen)} 
                    className="md:hidden text-green-700 bg-zinc-50 hover:bg-zinc-100 text-3xl w-10 h-10 flex items-center justify-center"
                >
                    {mobileMenuOpen ? "x" : "☰"}
                </button>
            </div>
            {mobileMenuOpen && (
                <div className="md:hidden absolute top-16 left-0 w-full bg-zinc-50 shadow-lg py-4">
                    <nav className="flex flex-col items-center space-y-4">
                        {isAdmin && (
                            <Link 
                                to="/admin" 
                                onClick={() => setMobileMenuOpen(false)} 
                                className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/admin" ? "font-bold" : ""}`}
                            >
                                Admin
                            </Link>
                        )}
                        <Link 
                            to="/create" 
                            onClick={() => setMobileMenuOpen(false)} 
                            className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/create" ? "font-bold" : ""}`}
                        >
                            Create
                        </Link>
                        <Link 
                            to="/search" 
                            onClick={() => setMobileMenuOpen(false)} 
                            className={`text-lg text-green-700 hover:scale-110 transition ${["/search", "/activityView"].includes(location.pathname) ? "font-bold" : ""}`}
                        >
                            Search
                        </Link>
                        <Link 
                            to="/about" 
                            onClick={() => setMobileMenuOpen(false)} 
                            className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/about" ? "font-bold" : ""}`}
                        >
                            About
                        </Link>
                        <Link 
                            to="/profile" 
                            onClick={() => setMobileMenuOpen(false)} 
                            className={`text-lg text-green-700 hover:scale-110 transition ${location.pathname === "/profile" ? "font-bold" : ""}`}
                        >
                            Edit Profile
                        </Link>
                        <button 
                            onClick={logoutHandler} 
                            className="text-lg text-red-500 bg-zinc-50 hover:bg-zinc-50 hover:scale-110 transition pt-0"
                        >
                            Logout
                        </button>
                    </nav>
                </div>
            )}
        </header>
    );
}