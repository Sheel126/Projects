import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useFeedback } from "../components/FeedbackContext/FeedbackContext";
import backgroundImage from "../images/background.webp";

function Login() {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [loginStatus, setLoginStatus] = useState(null);
  const [loginAttempted, setLoginAttempted] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [csrftoken, setCsrfToken] = useState("");
  const navigate = useNavigate();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const { showMessage } = useFeedback();

  // Function to get the CSRF token from cookies
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

  // Fetch CSRF token on component mount
  useEffect(() => {

    const fetchCsrfToken = async () => {
      const response = await fetch(process.env.REACT_APP_BACKEND_URL + "/api/login/", {
        method: "GET",
        credentials: "include",
      });
      console.log("response", response);
      setCsrfToken(getCookie("csrftoken"));
    };

    fetchCsrfToken();
  }, []);

  function loginValidation() {
    setLoginAttempted(true);
    let isValid = true;
    if (!userId || userId === '' || !emailRegex.test(userId)) {
      setErrorMessage("Please enter a valid email");
      isValid = false;
    } else if (!password || password === '') {
      setErrorMessage("Please enter a valid password");
      isValid = false;
    }

    return isValid;
  }

  const handleLogin = async () => {
    if (!loginValidation()) {
      return;
    }

    const response = await fetch(process.env.REACT_APP_BACKEND_URL + "/api/login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken,  // Send the CSRF token in the headers
      },
      credentials: "include",  // Ensure cookies are included in the request
      body: JSON.stringify({ userId, password }),
      //body: { userId, password },
    });

    const data = await response.json();

    if (response.ok) {
      console.log("ok", data.message)
      setLoginStatus(true); // true if login is successful
      showMessage('Login Successful', 'success');
      navigate('/home');
      setTimeout(() => {
        showMessage('Login Successful', 'success');
      }, 300)
      
    } else if(response.status === 401) {
      console.log('Credential error')
      setErrorMessage("Invalid credentials, try again"); // error message if login fails
    } else {
      console.log("error", data.message)
      console.log(response)
      setLoginStatus(false);
      // showMessage('Unable to log in', 'error');
      setErrorMessage("Server Error. Please try again later"); // error message if login fails
    }

  };

  return (
    <div className={`flex h-screen w-screen justify-center robotoMono`} >
        <div 
            style={{ backgroundImage: `url(${backgroundImage})` }} 
            className="flex-grow bg-cover bg-no-repeat bg-center bg-fixed flex items-center justify-center relative"
        >
        <div className=' sm:w-[400px] lg:w-[400px] bg-white h-fit pb-10 rounded-lg bg-opacity-90 self-center'>
          <div className={``}>
            <div className="ml-4 mt-6">
              <Link 
                to='/'
                className="cursor-pointer py-2 px-4 rounded-full text-center transition duration-300 border-2 text-green-700 border-green-700 hover:text-white hover:bg-green-800 hover:border-green-800 md:self-start w-max"
              >
                ← Go Back
              </Link>
            </div>
            <div className='px-20'>
              <div className={'text-3xl font-bold text-center mt-10'}>
                <h2>Login</h2>
              </div>
              <form 
                className="flex flex-col gap-4"
                onSubmit={(e) => { e.preventDefault(); handleLogin(); }}
              >
                <div>
                  <label className={'text-xl'}>Email</label>
                  <input
                    className='border border-gray-300 text-gray-900 text-m rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-1.5 '
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className={'text-xl'}>Password</label>
                  <input
                    className='border border-gray-300 text-gray-900 text-m rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-1.5 '
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                <div className={'flex-column text-xl courier text-center'}>
                  <button type='submit' className='mb-2 font-semibold text-xl bg-green-700 hover:bg-green-800 text-white px-4 py-2 rounded-lg w-full'>Login</button>
                    <a className='mb-2 text-xl text-green-700 hover:text-green-800 hover:cursor-pointer hover:underline' onClick={() => navigate('/register')}>Create an account</a>
                  </div>
                <div className={`flex py-3 justify-center`}>
                  <p className='text-red-500'> {loginAttempted && errorMessage}</p>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
