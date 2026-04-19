import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from "react-router-dom";

const Home = () => {
    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [isPending, setIsPending] = useState(false)
    

    const [loggedInUser, setloggedInUser] = useState({userId:'', userType:''});

    useEffect(() => {
        console.log("isLoggedIn", isLoggedIn);
        if (!isLoggedIn.current) {
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
                    console.log("Home, ", data);
                    setloggedInUser({userId: data.message, userType: data.groups});

                    if (data.groups == "Pending") {
                        setIsPending(true);
                    }
                })
                .catch(error => {
                    console.error("There was a problem with the fetch operation:", error);
                });
        }
    }, []);

    return (
        <>
            {loggedInUser.userType[0] === 'Pending' && (
                <p className="text-2xl">
                    Your Account Must Be Approved In Order to Use The Website
                </p>
            )}
            <div className="flex flex-col md:flex-row justify-center gap-6 md:gap-10 items-center md:items-stretch w-full ">
                <Link
                    to={isPending ? "#" : "/create"}
                    className={`flex flex-col justify-center items-center text-center gap-4 shadow-lg rounded-lg p-10 w-full max-w-sm h-[240px] transition ${
                        isPending ? "bg-gray-300 cursor-not-allowed" : "hover:scale-105 bg-zinc-50"
                    }`}
                >
                    <div className="text-4xl font-semibold">Create</div>
                    <div className="flex-1 flex items-center">
                        <div className="text-lg text-grey">
                            Create a new activity to share with other educators.
                        </div>
                    </div>
                    <div className={`text-2xl font-semibold ${isPending ? "text-gray-500" : "text-green-700"}`}>
                        Go →
                    </div>
                </Link>
                <Link to="/search" className="flex flex-col justify-center items-center text-center gap-4 shadow-lg rounded-lg p-10 w-full max-w-sm h-[240px] hover:scale-105 transition bg-zinc-50">
                    <div className="text-4xl font-semibold">Search</div>
                        <div className="flex-1 flex items-center">
                            <div className="text-lg text-grey">
                                Search for activities created by other educators for some inspiration.
                            </div>
                        </div>
                    <div className="text-2xl font-semibold text-green-700">
                        Go →
                    </div>
                </Link>
            </div>

        </>
    );
};

export default Home;

