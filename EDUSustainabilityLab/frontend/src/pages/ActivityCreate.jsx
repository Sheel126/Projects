import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from "react-router-dom";
import { useFeedback } from '../components/FeedbackContext/FeedbackContext';
import ImageUpload from '../components/ActivityCreate/ImageUpload';
import FileUpload from '../components/ActivityCreate/FileUpload';
import Details from '../components/ActivityCreate/Details';
import EditableBarChart from '../components/ActivityCreate/EditableBarChart';

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

const ActivityCreate = () => {
    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setLoggedInUser] = useState({ userId: '', userType: '' });
    const [message, setMessage] = useState('Error submitting activity. Please try again.');
    const { showMessage } = useFeedback();

    // Ensure user login
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
                if (data.groups == "Pending") {
                    navigate("/home");        
                    showMessage('Your account has not been approved. Please wait for admin approval.')
                }
            })
            .catch(error => console.error("Fetch error:", error));
        }
    }, []);

    const [formData, setFormData] = useState({
        title: '',
        description: '',
        file: null,
        targetDiscipline: '',
        educationLevel: '',
        classSize: '',
        duration: '',
        activityType: '',
        activityFormat: ''
    });

    const [imageFile, setImageFile] = useState(null);
    const [activityFile, setActivityFile] = useState(null);
    const [pillarsData, setPillarsData] = useState({
        "Environment":Math.round(34),
        "Social":Math.round(33),
        "Economic":Math.round(33),
    })
    const [entrepreneurshipData, setEntrepreneurshipData] = useState({
        "Curiosity":Math.round(34),
        "Connections":Math.round(33),
        "Creating Val":Math.round(33)
    })
    const [pillarsDescription, setPillarsDescription] = useState('');
    const [entrepreneurshipDescription, setEntrepreneurshipDescription] = useState('');
    const [errors, setErrors] = useState({});
    const formRef = useRef(null);

    const handleChange = (e) => {
        const { name, value, files } = e.target;
        if (name === 'file') {
            setFormData({ ...formData, [name]: files[0] });
        } else {
            setFormData({ ...formData, [name]: value });
        }
        setErrors(prevErrors => ({ ...prevErrors, [name]: value ? "" : prevErrors[name] }));
    };

    const handleImageUpload = (file) => {
        setImageFile(file);
    };

    const [isLoading, setIsLoading] = useState(false);

    const generateAiImage = async (desc) => {
        setIsLoading(true);

        if (desc === '') {
            desc = 'Classroom activity based on sustainabilty';
        }

        try {
            const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/files/generate', {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie('csrftoken')
                },
                body: JSON.stringify({ description: desc }),
                credentials: "include",
            });

            if (!response.ok) throw new Error("Failed to generate AI image");

            const aiImageBlob = await response.blob();
            const aiImageFile = new File([aiImageBlob], "ai_generated_image.jpg", { type: "image/jpeg" });

            setImageFile(aiImageFile);
        } catch (error) {
            console.error("AI Image Generation Error:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleActivityFileUpload = (file) => {
        setActivityFile(file);
    };

    const validateForm = () => {
        let formErrors = {};
        if (!formData.title) formErrors.title = 'Title is required';
        if (!formData.description) formErrors.description = 'Description is required';
        if (!formData.educationLevel) formErrors.educationLevel = 'Education Level is required';
        if (!formData.classSize) formErrors.classSize = 'Class size is required';
        if (!formData.targetDiscipline) formErrors.targetDiscipline = 'Target Discipline is required';
        if (!formData.duration) formErrors.duration = 'Duration is required';
        if (!formData.activityType) formErrors.activityType = 'Activity type is required';
        if (!formData.activityFormat) formErrors.activityFormat = 'Activity format is required';

        setErrors(formErrors);
        return Object.keys(formErrors).length === 0;
    };

    const uploadFile = async (file) => {
        if (!file) return null;

        const fileFormData = new FormData();
        fileFormData.append('file', file);
        fileFormData.append('title', file.name);

        try {
            const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/files/', {
                method: 'POST',
                headers: { "X-CSRFToken": getCookie('csrftoken') },
                body: fileFormData,
                credentials: 'include',
            });

            if (!response.ok) throw new Error('File upload failed');
            const data = await response.json();
            return data.fileId;
        } catch (error) {
            console.error("File upload error:", error);
            alert("File Size too large. Must be less than 100 MB")
            return null;
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!validateForm()) return;

        try {
            const fileId = await uploadFile(activityFile);
            const imageId = await uploadFile(imageFile);

            console.log("Uploaded fileId:", fileId);
            console.log("Uploaded imageFileId:", imageId);

            if (!fileId) {
                console.warn("Main file not uploaded. Proceeding without it.");
            }

            if (!imageId) {
                console.warn("Image file not uploaded. Proceeding without it.");
            }

            const activityData = {
                ...formData,
                fileId: fileId,
                imageId: imageId,
                Environment: pillarsData.Environment,
                Social: pillarsData.Social,
                Economy: pillarsData.Economic,
                Curiosity: entrepreneurshipData.Curiosity,
                Connections: entrepreneurshipData.Connections,
                "Creating Value":entrepreneurshipData["Creating Val"],
                pillarObjective: pillarsDescription,
                entrepreneurialObjective: entrepreneurshipDescription
            };

            // TODO Check for data verification based on activity manager 
            if (activityData.title.length > 200 || activityData.title.length == 0) {
                const errorMsg = 'Activity title must be between 0 and 200 characters long';
                setMessage(errorMsg);
                setErrors({ serverError: errorMsg });
                return;
            } else if (activityData.description.length > 1000 || activityData.description.length == 0) {
                const errorMsg = 'Activity description must be between 0 and 1000 characters long';
                setMessage(errorMsg);
                setErrors({ serverError: errorMsg });
                return;
            } else if (activityData.Environment == 0 && activityData.Social == 0 && activityData.Economy == 0 &&
                        activityData.Curiosity == 0 && activityData.Connections == 0 && activityData['Creating Value'] == 0) {
                const errorMsg = 'Atleast one pillar must be non-zero ';
                setMessage(errorMsg);
                setErrors({ serverError: errorMsg });
                return;
            }

            console.log("Final Activity Data:", activityData);

            const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/activities/', {
                method: 'POST',
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie('csrftoken')
                },
                body: JSON.stringify(activityData),
                credentials: 'include',
            });

            if (!response.ok) throw new Error('Activity creation failed');
            
            showMessage("Activity Pending Approval", "success");
            navigate("/home");
        } catch (error) {
            //console.error("Error submitting form:", error);
            console.log('Message', message)
            setErrors({ serverError: message });
        }
    };

    return (
        <>
            <form className="flex flex-col gap-4 max-w-4xl w-full mx-auto items-center justify-center" encType="multipart/form-data" ref={formRef} onSubmit={handleSubmit}>
                <div className="flex flex-col md:flex-row gap-10 justify-center items-center w-full">
                    {/* Image Upload & Basic Info */}
                    <div className="w-full md:w-1/2 flex flex-col gap-4 max-w-lg mx-auto p-6 bg-white rounded-lg shadow-lg h-[800px] items-center">
                        <ImageUpload 
                            desc={formData.description} 
                            onImageUpload={handleImageUpload}
                            generateAiImage={generateAiImage} 
                            aiImageFile={imageFile}
                            isLoading={isLoading}
                        />
                        <div className="flex flex-col gap-2 w-full">
                            <div className="flex flex-col">
                                <label className="font-semibold">Title</label>
                                <input
                                    type="text"
                                    name="title"
                                    className={`p-2 rounded-lg border-2
                                        ${errors.title ? "border-red-400" : "border-gray-300"}`}
                                    placeholder="Enter title"
                                    value={formData.title}
                                    onChange={handleChange}
                                />
                                {errors.title && <div className="text-red-500 min-h-[20px]">{errors.title}</div>}
                            </div>
                            <div className="flex flex-col">
                                <label className="font-semibold">Author</label>
                                <p className='p-2 rounded-lg border-2 border-gray-300'>{loggedInUser.userId}</p>
                            </div>
                            <div className="flex flex-col">
                                <label className="font-semibold">Description</label>
                                <textarea
                                    name="description"
                                    className={`p-2 rounded-lg border-2 resize-none
                                        ${errors.description ? "border-red-400" : "border-gray-300"}`}
                                    placeholder="Enter description"
                                    value={formData.description}
                                    onChange={handleChange}
                                    rows="5"
                                />
                                {errors.description && <div className="text-red-500 min-h-[20px]">{errors.description}</div>}
                            </div>
                        </div>
                    </div>
                    {/* File Upload */}
                    <div className="w-full md:w-1/2 flex justify-center md:justify-end h-[800px] max-w-lg mx-auto">
                        <FileUpload onFileUpload={handleActivityFileUpload} />
                    </div>
                </div>

                {/* Bar Charts */}
                <div className="flex flex-col md:flex-row gap-10 justify-start items-start w-full">
                    <div className="w-full md:w-1/2 flex flex-col gap-4 bg-white rounded-lg shadow-lg h-[650px] items-start max-w-lg self-center">
                        <EditableBarChart 
                            title="Pillars"
                            value1="Environment"
                            value2="Social"
                            value3="Economic"
                            frameworkData={pillarsData}
                            setFrameworkData={setPillarsData}
                            description={pillarsDescription}
                            setDescription={setPillarsDescription}
                        />
                    </div>
                    <div className="w-full md:w-1/2 flex flex-col gap-4 bg-white rounded-lg shadow-lg h-[650px] items-start max-w-lg self-center">
                        <EditableBarChart 
                            title="Entrepreneurship"
                            value1="Curiosity"
                            value2="Connections"
                            value3="Creating Val"
                            frameworkData={entrepreneurshipData}
                            setFrameworkData={setEntrepreneurshipData}
                            description={entrepreneurshipDescription}
                            setDescription={setEntrepreneurshipDescription}
                        />
                    </div>
                </div>

                {/* Details */}
                <div className="w-full max-w-lg md:max-w-4xl mx-auto">
                    <Details formData={formData} setFormData={setFormData} errors={errors} setErrors={setErrors} />
                </div>
                {/* Submit Button */}
                <div className="w-full">
                    <button 
                        type="submit" 
                        className="cursor-pointer py-4 text-lg font-bold rounded-lg text-center transition duration-300 border-2 bg-green-700 text-white border-green-700 hover:border-green-800 hover:bg-green-800 w-full"
                    >
                        Submit
                    </button>
                </div>
                {errors.serverError && <div className="text-red-500 min-h-[20px]">{errors.serverError}</div>}
            </form>
            {loggedInUser.userType[0] === 'Pending' && (
                <p className="text-red-500 text-center mt-4">
                    Your Account Must Be Approved In Order to Use The Website
                </p>
            )}
        </>
    );
};

export default ActivityCreate;