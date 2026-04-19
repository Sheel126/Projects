import api from './APIClient.js';

const registerForm = document.querySelector('#registerForm');
const username = registerForm.querySelector('#username');
const password = registerForm.querySelector('#password');
const registerButton = registerForm.querySelector('#registerBtn');

const errorBox = document.querySelector('#errorbox');

registerButton.addEventListener('click', e => {
    e.preventDefault();

    if (!username.value || !password.value || !confirmPassword.value) {
        console.log('Fields are required');
        errorBox.classList.remove('hidden');
        errorBox.textContent = "Fields are required";
    } else if (password.value != confirmPassword.value) {
        console.log('Passwords must match');
        errorBox.classList.remove('hidden');
        errorBox.textContent = "Passwords must match";
    } else {
        api.registerUser(username.value, password.value).then(user => {
            console.log(user);
            document.location = './';
        }).catch(error => {
            errorBox.classList.remove('hidden');
            errorBox.textContent = error.status == 409 ? "An account with this username already exists" : "Failed to create your account";
            password.value = '';
            confirmPassword.value = '';
        });
    }
});
