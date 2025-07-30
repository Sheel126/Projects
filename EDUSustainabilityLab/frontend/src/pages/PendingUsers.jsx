import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCsrfToken } from '../hooks/useCsrfToken';
import { useFeedback } from '../components/FeedbackContext/FeedbackContext';

/**
 * displays information of pending users
 * 
 * name:String 
 * email:String 
 * joined:String 
 * 
 * clicking a button on this components will call api/approveUser with user's name
 */
function UserComponent(props) {
    const csrfToken = useCsrfToken();
    const { showMessage } = useFeedback();

    const usersToApprove = [{ email: props.name }];

    function handleApproveUser() {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/approveUsers/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken, // Include the CSRF token here
            },
            credentials: "include",
            body: JSON.stringify({ pendingApproval: usersToApprove }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Approval Error:", data.error);
                } else {
                    showMessage("User Successfully Approved", "success");
                    props.setRefresh(prev => !prev);
                }
            })
            .catch(error => console.error("Approval Request Failed:", error));
    }

    const formatDateToEST = (isoString) => {
        const date = new Date(isoString);
      
        const options = {
          timeZone: "America/New_York",
          month: "2-digit",
          day: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hour12: true,
        };
      
        return date.toLocaleString("en-US", options);
    };

    return (
        <div className="bg-zinc-50 grid w-full grid-cols-[1fr_1fr_1fr_1fr] items-center px-4 py-2 rounded-lg shadow gap-4">
            <div className="overflow-hidden text-ellipsis whitespace-nowrap w-full">
                {props.name}
            </div>
            <div className="overflow-hidden text-ellipsis whitespace-nowrap w-full">
                {props.email}
            </div>
            <div className='w-full'>
                {formatDateToEST(props.joined)}
            </div>
            <button className="text-white bg-green-700 hover:bg-green-800 font-semibold px-4 py-2 w-full rounded-lg" onClick={handleApproveUser}>
                Approve
            </button>
        </div>
    )
}

export default function Users() {
    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setloggedInUser] = useState("");
    const [pendingUsers, setPendingUsers] = useState([]);
    const [refresh, setRefresh] = useState(false);
    const csrfToken = useCsrfToken();

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
                   
                    if (data.groups == "Administrator") {
                        navigate("/pendingUsers");
                    } else {
                        navigate("/home");
                    }
                })
                .catch(error => {
                    console.error("There was a problem with the fetch operation:", error);
                });   
        }
    },[navigate]);

    useEffect(() => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/pendingUsers/", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken 
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
                console.log("User Data:", data);
                setPendingUsers(data.users);

            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error);
            });
    }, [refresh])

    return (
        <div className='max-w-4xl w-full'>
            {/* Back Button */}
            <Link 
                to='/admin'
                className="cursor-pointer py-2 px-4 rounded-full text-center transition duration-300 border-2 border-green-700 text-green-700 bg-transparent hover:bg-green-800 hover:text-white hover:border-green-800 md:self-start w-max"
            >
                ← Go Back
            </Link>
            {/* Pending Users */}
            <div className='flex flex-col gap-2 mt-5'>
                {pendingUsers.length == 0 && <label>There are currently no pending users</label>}
                {pendingUsers.length > 0 && pendingUsers.map((user) => (
                    <UserComponent
                        key={user.name}
                        name={user.name}
                        email={user.email}
                        joined={user.joined}
                        setRefresh={setRefresh}
                    />
                ))}
            </div>
        </div>
    );
}