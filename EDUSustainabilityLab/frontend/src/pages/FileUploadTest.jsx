import React, {useState, useEffect, useRef} from 'react';
import axios from 'axios';
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


function App() {

  const [file, setFile] = useState()

    const navigate = useNavigate();
    const isLoggedIn = useRef(false);
    const [loggedInUser, setloggedInUser] = useState("");

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

  function handleChange(event) {
    setFile(event.target.files[0])
  }
  
  async function handleSubmit(event) {
    event.preventDefault()
    const url = process.env.REACT_APP_BACKEND_URL + '/api/files/';
    const formData = new FormData();
    formData.append('file', file);
    formData.append('fileName', file.name);
    //console.log(formData);
    for (var [key, value] of formData.entries()) { 
        console.log(key, value);
    }
    console.log(file);
    const fileResponse = await fetch(url, {
        method: 'POST',
        body: file,
        headers: {
            "content-type": file.type,
            "X-CSRFToken": getCookie('csrftoken')
        }
    });

    if (!fileResponse.ok) {
        throw new Error('Oh no!');
    }

    // const config = {
    //   headers: {
    //     'content-type': 'multipart/form-data',
    //     "X-CSRFToken": getCookie('csrftoken')
    //   },
    // };
    // axios.post(url, formData, config, {withCredentials: true}).then((response) => {
    //   console.log(response.data);
    // });

  }

  return (
    <div className="App">
        <form onSubmit={handleSubmit}>
          <h1>React File Upload</h1>
          <input type="file" onChange={handleChange}/>
          <button type="submit">Upload</button>
        </form>
    </div>
  );
}

export default App;