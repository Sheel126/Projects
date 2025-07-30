import api from './APIClient.js';


function displayUserInHeader(user) {
    document.getElementById('username').textContent = user.username;
    document.getElementById("user-info").style.visibility = "visible";
}

function displayContent() {
    const splash = document.getElementById("temp-splash");

    if (splash) {
        splash.style.display = "none";
    }

    const header = document.querySelector('header');
    const main = document.querySelector('main');

    header.style.display = "block";
    main.style.display = "flex";
}

function logoutUser() {
    api.logoutUser().then(() => {
        document.location = "./login";
    });
}

api.getAuthenticatedUser().then(user => {
    displayUserInHeader(user);
    displayContent();

}).catch(error => {
    console.log(error);
    if (error.status === 401) {
        document.location = './login';
    }
    else {
        console.log(`${error.status}`, error);
    }
});

const logoutBtn = document.getElementById("logout-button");

if (logoutBtn) {
    logoutBtn.addEventListener("click", logoutUser);
}
