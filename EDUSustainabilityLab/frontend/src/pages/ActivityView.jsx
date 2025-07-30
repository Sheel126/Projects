import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from "react-router-dom";
import { useCsrfToken } from '../hooks/useCsrfToken';
import { useFeedback } from '../components/FeedbackContext/FeedbackContext';
import ImageView from '../components/ActivityView/ImageView.jsx';
import FileDownload from '../components/ActivityView/FileDownload.jsx';
import Details from '../components/ActivityView/Details.jsx';
import EditableBarChart from '../components/ActivityView/EditableBarChart.jsx';

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

const ActivityView = () => {
    const { activityId } = useParams();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setLoggedInUser] = useState({ userId: '', userType: '' });
    const [isAdmin, setIsAdmin] = useState(false);
    const [activity, setActivity] = useState(null);
    const csrfToken = useCsrfToken();
    const { showMessage } = useFeedback();
    const navigate = useNavigate();
    
    useEffect(() => {
        if (!isLoggedIn.current) {
            fetch(process.env.REACT_APP_BACKEND_URL + "/api/debuggingUser/", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                credentials: "include"
            })
            .then(response => response.json())
            .then(data => {
                setLoggedInUser({ userId: data.message, userType: data.groups })

                if(data.groups == "Administrator") {
                    setIsAdmin(true);
                }
            })
            .catch(error => console.error("Fetch error:", error));
        }
    }, []);

    useEffect(() => {
        if (!activityId) return;

        fetch(`${process.env.REACT_APP_BACKEND_URL}/api/activity/${activityId}`, {
            method: 'GET',
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie('csrftoken')
            },
            credentials: 'include',
        })
        .then(response => response.json())
        .then(data => setActivity(data))
        .catch(error => console.error("Fetch error:", error));
    }, [activityId]);

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
                    navigate("/pendingActivities");
                }
            })
            .catch(error => console.error("Approval Request Failed:", error));
    }

    console.log(activity);

    return (
        <>  
            {!isAdmin && !activity?.isApproved ? (
                /* Block non admin users from viewing pending activities */
                <p>Activity not available</p>
            ) : (
                /* Activity View */
                <div className="flex flex-col gap-4 max-w-4xl w-full mx-auto items-center justify-center">
                    {/* Back Button */}
                    <button 
                        onClick={() => navigate(-1)}
                        className="cursor-pointer py-2 px-4 rounded-full text-center transition duration-300 border-2 text-white bg-green-700 hover:bg-green-800 md:self-start w-max"
                    >
                        ← Go Back
                    </button>
                    <div className="flex flex-col md:flex-row gap-10 justify-center items-center w-full">
                        {/* Image & Basic Info */}
                        <div className="w-full md:w-1/2 flex flex-col gap-4 max-w-lg mx-auto p-6 bg-white rounded-lg shadow-lg h-[800px] items-center">
                            <ImageView imageFileId={activity?.image_id} />
                            <div className="flex flex-col gap-2 w-full mt-16">
                                <div className="flex flex-col">
                                    <label className="font-semibold">Title</label>
                                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white">
                                        {activity?.title || "N/A"}
                                    </p>
                                </div>
                                <div className="flex flex-col">
                                    <label className="font-semibold">Author</label>
                                    <p className="p-2 rounded-lg border-2 border-gray-300 bg-white">
                                        {activity?.creator_name || "N/A"}
                                    </p>
                                </div>
                                <div className="flex flex-col">
                                    <label className="font-semibold">Description</label>
                                    <textarea 
                                        className="p-2 rounded-lg border-2 border-gray-300 bg-white overflow-y-auto break-words whitespace-pre-line resize-none"
                                        rows="5"
                                        value={activity?.description || "N/A"}
                                        readOnly
                                    >
                                    </textarea>
                                </div>
                            </div>
                        </div>
                        {/* File Download */}
                        <div className="w-full md:w-1/2 flex justify-center md:justify-end h-[800px] max-w-lg mx-auto">
                            <FileDownload fileId={activity?.file_id} />
                        </div>
                    </div>

                    {/* Bar Chart */}
                    <div className="flex flex-col md:flex-row gap-10 justify-start items-start w-full">
                        <div className="w-full md:w-1/2 flex flex-col gap-4 bg-white rounded-lg shadow-lg h-[650px] items-start max-w-lg self-center">
                            <EditableBarChart 
                                activity={activity}
                                framework="Pillars"
                                value1="Environment"
                                value2="Social"
                                value3="Economic"
                            />
                        </div>
                        <div className="w-full md:w-1/2 flex flex-col gap-4 bg-white rounded-lg shadow-lg h-[650px] items-start max-w-lg self-center">
                            <EditableBarChart 
                                activity={activity}
                                framework="Entrepreneurship"
                                value1="Curiosity"
                                value2="Connections"
                                value3="Creating Val"
                            />
                        </div>
                    </div>

                    {/* Details */}
                    <div className="w-full max-w-lg md:max-w-4xl mx-auto">
                        <Details activity={activity} />
                    </div>

                    {/* Approve Button for Admin */}
                    {!activity?.isApproved && ( 
                        <div className="w-full">
                            <button 
                                onClick={() => { handleApproveActivity(activity.id) }}
                                className="cursor-pointer py-4 text-lg font-bold rounded-lg text-center transition duration-300 border-2 bg-green-700 text-white border-green-700 hover:border-green-800 hover:bg-green-800 w-full"
                            >
                                Approve
                            </button>
                        </div>
                    )}
                </div>
            )}          
            
            {loggedInUser.userType[0] === 'Pending' && (
                <p className="text-red-500 text-center mt-4">
                    Your Account Must Be Approved In Order to Use The Website
                </p>
            )}
        </>
    );
};

export default ActivityView;
