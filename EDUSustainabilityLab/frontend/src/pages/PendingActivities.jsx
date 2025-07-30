import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCsrfToken } from '../hooks/useCsrfToken';
import { useFeedback } from '../components/FeedbackContext/FeedbackContext';

//displays data of pendingActivity
//this components will be displaying the title of pendingActivity, creator of pendingActivity 
function PendingActivities() {
    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setloggedInUser] = useState("");
    const [refresh, setRefresh] = useState(false);
    const [pendingActivities, setPendingActivities] = useState([]);
    const csrfToken = useCsrfToken();
    const { showMessage } = useFeedback();

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
                            navigate("/pendingActivities");
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
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/activities/", {
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
                console.log("User Data:", data.pendingActivities);
                setPendingActivities(data.pendingActivities)

            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error);
            });
    }, []);

    useEffect(() => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/activities/", {
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
                console.log("User Data:", data.pendingActivities);
                setPendingActivities(data.pendingActivities)

            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error);
            });
    }, [refresh]);

    const handleApproveAll = () => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/approveAll/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include"
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Approval Error:", data.error);
                } else {
                    console.log("Success:", data.message);
                    showMessage("All Activities Successfully Approved", "success");
                    setRefresh(!refresh);
                }
            })
            .catch(error => console.error("Approval Request Failed:", error));
    }

    const handleApproveActivity = (id) => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/approveActivity/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include",
            body: JSON.stringify([{ ActivityID: id }]),
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Approval Error:", data.error);
                } else {
                    console.log("Success:", data.message);
                    showMessage("Activity Successfully Approved", "success");
                    setRefresh(!refresh);
                }
            })
            .catch(error => console.error("Approval Request Failed:", error));
    }

    const handleDenyActivity = (id) => {
        fetch(process.env.REACT_APP_BACKEND_URL + "/api/denyActivity/" + id, {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            credentials: "include"
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Denial Error:", data.error);
                } else {
                    console.log("Success:", data.message);
                    showMessage("Activity Successfully Denied", "success");
                    setRefresh(!refresh);
                }
            })
            .catch(error => console.error("Denial Request Failed:", error));
    }

    const formatDateToEST = (isoString) => {
        const date = new Date(isoString);
      
        const options = {
          month: "2-digit",
          day: "2-digit",
          year: "numeric"
        };
      
        return date.toLocaleString("en-US", options);
    };

    return (
        <div className='max-w-4xl w-full'>
            <div className='flex justify-between'>
                {/* Back Button */}
                <Link 
                    to='/admin'
                    className="cursor-pointer px-4 py-2 rounded-full text-center transition duration-300 border-2 border-green-700 text-green-700 bg-transparent hover:bg-green-800 hover:text-white hover:border-green-800 self-start w-max"
                >
                    ← Go Back
                </Link>

                {/* Approve All Button */}
                {pendingActivities.length > 0 && (
                    <div className='rounded-lg bg-white px-4 py-2'>
                         <button
                            onClick={() => { handleApproveAll() }}
                            className="cursor-pointer px-4 py-2 rounded-lg text-center transition duration-300 border-2 text-white bg-green-700 hover:bg-green-800 md:self-start w-max font-semibold"
                        >
                            Approve All
                        </button>
                    </div>
                )}
            </div>

            {/* Pending Activities */}
            <div className='flex flex-col gap-2 mt-5'>
                {pendingActivities.length == 0 && <label>There are currently no pending activities</label>}
                {pendingActivities.length > 0 && pendingActivities.map((activity) => (
                    <div className="bg-zinc-50 grid w-full grid-cols-[1fr_1fr_1fr_1fr_1fr_1fr] items-center px-4 py-2 rounded-lg shadow gap-4 justify-self-start">
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap w-full">
                            {activity.creator.username}
                        </div>
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap w-full">
                            {activity.title}
                        </div>
                        <div className='w-full'>
                            { formatDateToEST(activity.creationDate) } {/* Needs to be adjusted in backend to allow for time field */}
                        </div>
                        <Link to={`/view/${activity.id}`}>
                            <button className="border-2 border-green-700 text-white bg-green-700 hover:bg-green-800 font-semibold px-4 py-2 w-full rounded-lg">
                                View
                            </button>
                        </Link>
                        <button className="border-2 border-green-700 text-white bg-green-700 hover:bg-green-800 font-semibold px-4 py-2 w-full rounded-lg" onClick={() => { handleApproveActivity(activity.id) }}>
                            Approve
                        </button>
                        <button className="border-2 border-red-700 text-white bg-red-700 hover:bg-red-800 font-semibold px-4 py-2 w-full rounded-lg" onClick={() => { handleDenyActivity(activity.id) }}>
                            Deny
                        </button>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default PendingActivities;