import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from "react-router-dom";
import { useFeedback } from "../components/FeedbackContext/FeedbackContext";
import backgroundImage from "../images/background.webp";

const Register = () => {

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const { showMessage } = useFeedback();

  const navigate = useNavigate();

  useEffect(() => {
    console.log(message, "message");
    //navigate to login page after 1.5 seconds 
    if (message == 'Registration successful') {
      console.log(message, "successful");
      setTimeout(navigate('/login'), 1500);
    }
  }, [message, navigate]);


  const handleRegister = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setError('');

    const data = {
      email,
      password,
    };

    try {
      const response = await fetch(process.env.REACT_APP_BACKEND_URL + '/api/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        console.log(response)
        const errorData = await response.json();
        console.log(errorData)
        throw new Error(errorData.message || 'Something went wrong');
      }

      setMessage('Registration Successful');
      showMessage('Your Account has been created!', 'success');
      navigate('/login');
    } catch (error) {
      console.log(error)
      setError(error.message);
    }
  };

  <div class="container">
    <div class="Title"></div>
    <div class="Name"></div>
    <div class="Name-Text"></div>
    <div class="Password"></div>
    <div class="Password-Text"></div>
    <div class="Submit"></div>
  </div>

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

              <h2>Register</h2>
            </div>
            <form 
                className='flex flex-col gap-4'
                onSubmit={(e) => { e.preventDefault(); handleRegister(e); }}
            >
              <div>
                <label className={'text-xl'}>Email</label>
                <input
                  className='border border-gray-300 text-gray-900 text-m rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-1.5 '
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
              <div>
                <label className={'text-xl'}>Confirm Password:</label>
                <input
                  className='border border-gray-300 text-gray-900 text-m rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-1.5 '
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
              <div className={'flex-column text-xl courier text-center'}>
                <button type='submit' className='mb-2 text-xl font-semibold bg-green-700 hover:bg-green-800 text-white px-4 py-2 rounded-lg w-full'>Register</button>
                <a className='mb-2 text-xl text-green-700 hover:text-green-800 hover:cursor-pointer hover:underline' onClick={() => navigate('/login')}>Already have an account?</a>
              </div>
              <div className={`flex py-3 justify-center`}>
                <p className='text-red-500'> {error}</p>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
  );
};

export default Register;