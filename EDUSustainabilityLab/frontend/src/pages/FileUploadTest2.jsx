import React, { useState, useEffect, useRef } from 'react';
import '../index.css';
import { useNavigate  } from "react-router-dom";

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
    console.log("cookieValue", cookieValue);
    return cookieValue;
}

const ActivityCreate = () => {
    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setloggedInUser] = useState("");

    // Handles enabling the sliders vi the checkboxes
    const [enabledSliders, setEnabledSliders] = useState({});

    // Ensure user login
    useEffect(() => {
 
        console.log("isLoggedIn", isLoggedIn);
        if(!isLoggedIn.current){
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
                console.log("User Data:", data);
                setloggedInUser(data.message);
            })
            .catch(error => {
                console.error("There was a problem with the fetch operation:", error);
            });
        }
    },[]);

    const validateForm = () => {
        return true;
    };
  
    const handleSubmit = async (e) => {
        e.preventDefault();

        if (validateForm()) {
            alert('Form submitted successfully!');
            try {
                const fileFormData = new FormData();
                const fileInput = document.querySelector('#fileUpload');
                fileFormData.append('file', fileInput.files[0]);
                fileFormData.append('title', "My file");
                //fileFormData.append('file', formData.file);
                //fileFormData.append('title', formData.file.name);
                console.log(fileInput.files[0]);
                for (var [key, value] of fileFormData.entries()) { 
                    console.log(key, value);
                }
                const fileResponse = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/files/', {
                    method: 'POST',
                    headers: {
                        "X-CSRFToken": getCookie('csrftoken')
                    },
                    body: fileFormData,
                    credentials: 'include', 
                });

                if (!fileResponse.ok) {
                    throw new Error('Oh no!');
                }

                //console.log("data", data);

                //Merge all data together
                const allFormData = new FormData();
                allFormData.append('title', formData.title);
                allFormData.append('decription', formData.description);
                //allFormData.append('file', formData.file);
                allFormData.append('targetDiscipline', formData.targetDiscipline);
                allFormData.append('educationLevel', formData.educationLevel);
                allFormData.append('classSize', formData.classSize);
                allFormData.append('duration', formData.duration);
                allFormData.append('activityType', formData.activityType);
                allFormData.append('activityFormat', formData.activityFormat);
                allFormData.append('pillarObjective', pillarObjective);
                allFormData.append('entrepreneurialObjective', entrepreneurialObjective);
                allFormData.append('targetPhaseObjective', targetPhaseObjective);
                allFormData.append('tensionAmount', tension);
                
                // const tensionObj = {"tensionAmount": tension};
                // const pillarObjectiveObj = {"pillarObjective": pillarObjective};
                // const entrepreneurialObjectiveObj = {"entrepreneurialObjective": entrepreneurialObjective};
                // const targetPhaseObjectiveObj = {"targetPhaseObjective": targetPhaseObjective}
                // const mergedData = Object.assign({}, formData, pillarPercent, entrepreneurialPercent, 
                //     targetPhasePercent, tensionObj, pillarObjectiveObj, entrepreneurialObjectiveObj, targetPhaseObjectiveObj);
                // const jsonData = JSON.stringify(mergedData);
                // console.log(jsonData);

                const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/activities/', {
                  method: 'POST',
                  headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie('csrftoken') 
                  },
                  body: allFormData,
                  credentials: 'include', 
                });
            
                if (!response.ok) {
                  throw new Error('Oh no!');
                }
            
                console.log("Successfully posted activity")
                // Navigate somewhere and display a success message
            } catch (error) {
                // Correctly handle the error
                console.log(error);
                console.log("Could not post activity")
            }
        }
        console.log("submitted", formData, pillarPercent, entrepreneurialPercent, targetPhasePercent);
    };

    return (
    <div>
        <div className={style.mainbody}>
            {/* <div className={"text-2xl p-20"}> */}
            {/* <div> */}
            <form className="flex flex-col gap-3" encType="multipart/form-data" method="post" onSubmit={handleSubmit} style={{ margin: 'auto' }}>
                <div className={style.upperformcontainer}>
                    <div className="flex justify-between">
                        {/* File Upload */}
                        <div style={{ marginBottom: '10px' }}>
                            <div className={style.formgroup}>
                                <label>Upload File</label>
                                <input className="mt-2" id="fileUpload" type="file" name="file" />
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <button type="submit" onClick={handleSubmit} className={style.formbutton} >Submit</button>
                </div>
            </form>

            <a href="http://localhost:8001/api/download/1/"> Download Document </a>
        </div>
    </div>
    )
};

export default ActivityCreate;