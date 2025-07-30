import MultiSelectDropdown from '../components/multiSelect.jsx';
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate  } from "react-router-dom";
import { useFeedback } from '../components/FeedbackContext/FeedbackContext.jsx';
import Card from '../components/Card.jsx'
const Search = () => {
  const isLoggedIn = useRef(false);
  const [loggedInUser, setloggedInUser] = useState("");
  const [activityList, setActivityList] = useState([]);
  const [maxActivities, setMaxActivities] = useState(14);
  const [nameFilter, setNameFilter] = useState("")
  const navigate = useNavigate();
  const { showMessage } = useFeedback();
  
  const [pillars, setPillars] = useState([]);
  const [entrepreneurial, setEntrepreneurial] = useState([]);
  const [classSizes, setClassSizes] = useState([]);
  const [durations, setDurations] = useState([]);
  const [educationLevel, seteducationLevel] = useState([]);
  const [activityTypes, setActivityTypes] = useState([]);
  const [activityFormat, setActivityFormat] = useState([]);
  const [activityDisipline, setActivityDisipline] = useState([]);

  const [dropdown1, setDropdown1] = useState(true);
  

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


  // Function to fetch additional activity data
useEffect(() => {
  const fetchData = async () => {
    try {
      console.log("isLoggedIn", isLoggedIn);
      if (!isLoggedIn.current) {
        const response = await fetch(process.env.REACT_APP_BACKEND_URL + "/api/debuggingUser/", {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("Network response was not ok");
        }

        const data = await response.json();
        setloggedInUser(data.message);
      }

      const searchPayload = JSON.stringify({
        name: nameFilter,
        pillars,
        entrepreneurial,
        classSizes,
        durations,
        educationLevel,
        activityTypes,
        activityDisipline,
        activityFormat
      });
      

      // Fetch all activities
      let activitiesResponse = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/search/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          "X-CSRFToken": getCookie('csrftoken')  
        },
        body: searchPayload,
        credentials: 'include', 
      });

      if (!activitiesResponse.ok) {
        throw new Error("Failed to fetch activities");
      }

      let activities = await activitiesResponse.json().then(act => {return act.list});
      console.log("Activities:", activities);

      // Update state
      setActivityList(activities);
    } catch (error) {
      console.error("Error in fetchData:", error);
    }
  };

  fetchData();

}, []); // Dependency array remains empty to run only once

  const handleSubmit = async (e) => {
    e.preventDefault();
  
    try {
      console.log("Searching for activities with name:", nameFilter);
  
      // Construct the search payload
      const searchPayload = JSON.stringify({
        name: nameFilter,
        pillars,
        entrepreneurial,
        classSizes,
        durations,
        educationLevel,
        activityTypes,
        activityDisipline,
        activityFormat
      });
      
  
      const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/search/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          "X-CSRFToken": getCookie('csrftoken')  
        },
        body: searchPayload,
        credentials: 'include', 
      });
  
      if (!response.ok) {
        throw new Error('Search request failed');
      }
  
      let data = await response.json().then(res => {return res.list});
  
      // Ensure data.list exists and is an array
      if (!Array.isArray(data)) {
        console.error("Expected an array but got:", data.list);
        return;
      } else if(data.length == 0) {
        showMessage('No activities found', 'error')
      }

      // Update state
      setActivityList(data);
  
      // Store results in sessionStorage for persistence
      sessionStorage.setItem('listData', JSON.stringify(data));
  
    } catch (error) {
      console.error("Error in handleSubmit:", error);
    }
  };
  
  const [isOpen, setIsOpen] = useState(false);

  
  const handleClick = () => {
      setIsOpen(!isOpen);
  };

  return (
    <div className='flex'>
      <div className="flex-col justify-center">
        <div className="">
          <div className="mb-6 text-center">
            <form onSubmit={handleSubmit}>
              <div className="flex justify-center"></div>
                <div className='mt-2 justify-center text-center font-bold'>
                  <p>Advanced filters</p>
                  <div className='flex-col flex-wrap justify-center ml-5'>
                    <div className='rounded-md p-2'>
                      <div className='flex justify-center flex-wrap'>
                        <MultiSelectDropdown
                          title="Pillars of Sustainability"
                          options={[['Environment', 'Environment'], ['Social', 'Social'], ['Economic', 'Economic']]}
                          selected={pillars}
                          setSelected={setPillars}
                        />
                        <MultiSelectDropdown
                          title="Entrepreneurial"
                          options={[['Curious', 'Curiosity'], ['Connection', 'Connection'], ['Creating Value', 'Creating Value']]}
                          selected={entrepreneurial}
                          setSelected={setEntrepreneurial}
                        />
                      </div>
                      <div className="flex-col justify-center">
                        <div>
                          <label for='activityNameInput' className="mb-2 font-semibold text-gray-900">Search Filters</label>
                        </div>
                        <div className='pb-3'>
                          <input type="text" id="activityNameInput" placeholder="Activity name" onChange={(e) => setNameFilter(e.target.value)} className="p-2 mr-2 w-60 text-gray-900 border border-gray-500 rounded-lg bg-gray-50 text-base focus:border-green-500"/>
                        </div>
                      </div>

                      <div className='flex justify-center flex-wrap'>
                        <MultiSelectDropdown
                          title="Class Size"
                          options={[
                            ['LA', 'More than 100'],
                            ['ME', '50-100'],
                            ['SM', 'Less than 50'],
                          ]}
                          selected={classSizes}
                          setSelected={setClassSizes}
                        />
                        <MultiSelectDropdown
                          title="Duration"
                          options={[
                            ['SE', 'Semester-Long Project'],
                            ['WE', 'Week-Long Project'],
                            ['LO', 'Long (Over 4 Hours)'],
                            ['MD', 'Medium (Half hour - 4 Hours)'],
                            ['SH', 'Short (Half hour or less)'],
                          ]}
                          selected={durations}
                          setSelected={setDurations}
                        />
                        <MultiSelectDropdown
                          title="Education Level"
                          options={[
                            ['FR', 'First-Year'],
                            ['SO', 'Sophomore'],
                            ['JR', 'Junior'],
                            ['SR', 'Senior'],
                            ['GA', 'Graduate'],
                            ['CE', 'Continuing Education'],
                          ]}
                          selected={educationLevel}
                          setSelected={seteducationLevel}
                        />
                        <MultiSelectDropdown
                          title="Activity Format"
                          options={[
                            ['IP', 'In-Person'],
                            ['HY', 'Hybrid'],
                            ['VI', 'Virtual'],
                          ]}
                          selected={activityFormat}
                          setSelected={setActivityFormat}
                        />
                        <MultiSelectDropdown
                          title="Activity Discipline"
                          options={[
                            ['AG', 'Agriculture & Life Science'],
                            ['DI', 'Design'],
                            ['ED', 'Education'],
                            ['EG', 'Engineering'],
                            ['HU', 'Humanities & Social Science'],
                            ['NR', 'Natural Resources'],
                            ['MA', 'Management'],
                            ['MD', 'Medicine'],
                            ['SC', 'Science'],
                            ['TX', 'Textiles'],
                            ['NA', 'Other'],
                          ]}
                          selected={activityDisipline}
                          setSelected={setActivityDisipline}
                        />
                        <MultiSelectDropdown
                          title="Activity Type"
                          options={[
                            ['MM', 'Micromoment (e.g., QFT, Think-Pair-Share, etc)'],
                            ['JS', 'Jigsaw'],
                            ['CS', 'Case Study'],
                            ['ST', 'Storytelling'],
                            ['PB', 'Problem Solving Studio / Problem-Based Learning'],
                            ['SC', 'Structured Academic Controversy'],
                            ['EL', 'Experiential Learning (hands-on, demonstration)'],
                            ['DT', 'Design Thinking'],
                            ['FA', 'Field Activity'],
                            ['LC', 'Laboratory Course'],
                            ['RM', 'Reflection / Metacognition'],
                            ['NA', 'Other'],
                          ]}
                          selected={activityTypes}
                          setSelected={setActivityTypes}
                        />
                      </div>
                    </div>
                    <button type='submit' className='text-white bg-green-700 text-nowrap hover:bg-green-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 inline-flex items-center'>Search</button>
                </div>
              </div>
            </form>
          </div>
        </div>
        <div className="flex justify-center">
            <div className="flex flex-wrap justify-center gap-4 w-full">
                  {activityList.length != 0 ? activityList.map((activity, index) => (
                      <Card key={index} activity={activity} />
                  )) : 
                  <h1 className='text-2xl mt-10'>No Activities Found</h1>}
            </div>
        </div>
      </div>

    </div>
  );
};

export default Search;
