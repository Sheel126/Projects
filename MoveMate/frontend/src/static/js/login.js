import api from './APIClient.js';

const loginForm = document.querySelector('#loginForm');
const username = loginForm.querySelector('#username');
const password = loginForm.querySelector('#password');
const loginButton = loginForm.querySelector('#loginBtn');

const errorBox = document.querySelector('#errorbox');

loginButton.addEventListener('click', e => {
    e.preventDefault();

    if (!username.value || !password.value) {
        console.log('Fields are required');
        errorBox.classList.remove('hidden');
        errorBox.textContent = "Fields are required";
    } else {
        api.authenticateUser(username.value, password.value).then(user => {
            console.log(user);
            document.location = './';
        }).catch(error => {
            console.log(error);
            errorBox.classList.remove('hidden');
            errorBox.textContent = "Invalid credentials";
            password.value = '';
        });
    }
});
