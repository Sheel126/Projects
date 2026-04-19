import api from './APIClient.js';


const calorieForm = document.getElementById("calorieForm");
const sleepForm = document.getElementById("sleepForm");
const waterForm = document.getElementById("waterForm");
const stepsForm = document.getElementById("stepsForm");

await api.getReminders().then(reminders => {
    const calorieReminders = document.getElementById("calorieReminders");
    const sleepReminders = document.getElementById("sleepReminders");
    const waterReminders = document.getElementById("waterReminders");
    const stepsReminders = document.getElementById("stepsReminders");
    const historyReminders = document.getElementById("historyReminders");

    reminders.forEach(reminder => {
        const reminderDiv = document.createElement('div');
        reminderDiv.className = "checklist-item"
        reminderDiv.classList.add('reminder');

        const checkbox = document.createElement('input');
        checkbox.className = "reminderCheckbox";
        checkbox.type = 'checkbox';
        checkbox.value = reminder.title;
        checkbox.checked = reminder.completed;

        checkbox.setAttribute("data-id", reminder.id);

        const label = document.createElement('label');
        label.textContent = reminder.title;

        if (reminder.completed === 0) {
            reminderDiv.appendChild(checkbox);
            reminderDiv.appendChild(label);
            if (reminder.category === 'Calories') {
                calorieReminders.appendChild(reminderDiv);
            } else if (reminder.category === 'Sleep') {
                sleepReminders.appendChild(reminderDiv);
            } else if (reminder.category === 'Water') {
                waterReminders.appendChild(reminderDiv);
            } else {
                stepsReminders.appendChild(reminderDiv);
            }
        } else {
            const historyDiv = document.createElement('div');
            historyDiv.className = 'history-reminders';
            const content = document.createElement('h3');
            content.className = 'historyContent';
            content.textContent = reminder.title;
            const historyButton = document.createElement('button');
            historyButton.className = 'history-reminder-button';
            historyButton.innerHTML = '+';
            historyButton.setAttribute("data-id", reminder.id);
            historyDiv.appendChild(content);
            historyDiv.appendChild(historyButton);
            historyReminders.appendChild(historyDiv);
        }
    });

});

const reminderCheckboxs = document.querySelectorAll('.reminderCheckbox');

reminderCheckboxs.forEach((reminderCheckbox) => {
    reminderCheckbox.addEventListener('change', async (event) => {
        const isChecked = event.target.checked;
        const id = event.target.getAttribute("data-id");
        console.log(isChecked);
        if (isChecked) {
            await api.putReminders(id, 1).then(res => {
                console.log(res);
            });
        }
        location.reload();
    });
});

const historyRevertButtons = document.querySelectorAll(".history-reminder-button");
historyRevertButtons.forEach((historyButton) => {
    historyButton.addEventListener('click', async (event) => {
        const id = event.target.getAttribute("data-id");
        console.log(id);
        await api.putReminders(id, 0).then(res => {
            console.log(res);
        });
        location.reload();
    });
});

const historyToggle = document.querySelector('.history-toggle-button');
const history  = document.querySelector('.history');
historyToggle.addEventListener('click', (event) => {
    history.classList.toggle('active');
});

const calorieButton = document.querySelector('.calorie-reminder-button');
calorieButton.addEventListener("click", () => {    
    calorieForm.style.display = calorieForm.style.display === "none" || calorieForm.style.display === "" ? "block" : "none";
});

const sleepButton = document.querySelector('.sleep-reminder-button');
sleepButton.addEventListener("click", () => {    
    sleepForm.style.display = sleepForm.style.display === "none" || sleepForm.style.display === "" ? "block" : "none";
});

const waterButton = document.querySelector('.water-reminder-button');
waterButton.addEventListener("click", () => {    
    waterForm.style.display = waterForm.style.display === "none" || waterForm.style.display === "" ? "block" : "none";
});

const stepsButton = document.querySelector('.steps-reminder-button');
stepsButton.addEventListener("click", () => {    
    stepsForm.style.display = stepsForm.style.display === "none" || stepsForm.style.display === "" ? "block" : "none";
});


calorieForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const user = await api.getAuthenticatedUser();
    console.log(user);

    api.postReminders(user.id, event.target.reminderTitleCalorie.value, event.target.calorieDate.value, false, "Calories").then(res => {
        console.log(res);
    });

    location.reload();

});

sleepForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const user = await api.getAuthenticatedUser();
    console.log(user);

    api.postReminders(user.id, event.target.sleepTitle.value, event.target.sleepDate.value, false, "Sleep").then(res => {
        console.log(res);
    });

    location.reload();

});

waterForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const user = await api.getAuthenticatedUser();
    console.log(user);

    api.postReminders(user.id, event.target.waterTitle.value, event.target.waterDate.value, false, "Water").then(res => {
        console.log(res);
    });

    location.reload();

});

stepsForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const user = await api.getAuthenticatedUser();
    console.log(user);

    api.postReminders(user.id, event.target.stepsTitle.value, event.target.stepsDate.value, false, "Steps").then(res => {
        console.log(res);
    });

    location.reload();

});