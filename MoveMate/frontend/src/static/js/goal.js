import api from "./APIClient.js";

const calorieAmount = document.querySelector('#calorieAmount');
const calorieTarget = document.querySelector('#calorieTarget');

const waterAmount = document.querySelector('#waterAmount');
const waterTarget = document.querySelector('#waterTarget');

const sleepAmount = document.querySelector('#sleepAmount');
const sleepTarget = document.querySelector('#sleepTarget');

const stepsAmount = document.querySelector('#stepsAmount');
const stepsTarget = document.querySelector('#stepsTarget');

const editButton = document.querySelector('#editButton');

api.getGoals().then((goals) => {
    const goalMap = {};
    goals.forEach(goal => {
        goalMap[goal.category] = goal.target;
    });

    const sections = [
        {
            amountElement: calorieAmount,
            targetElement: calorieTarget,
            apiFetchAmount: api.getCalorieAmount,
            category: 'Calories',
        },
        {
            amountElement: waterAmount,
            targetElement: waterTarget,
            apiFetchAmount: api.getWaterAmount,
            category: 'Water',
        },
        {
            amountElement: sleepAmount,
            targetElement: sleepTarget,
            apiFetchAmount: api.getSleepAmount,
            category: 'Sleep',
        },
        {
            amountElement: stepsAmount,
            targetElement: stepsTarget,
            apiFetchAmount: api.getStepsAmount,
            category: 'Steps',
        },
    ];

    sections.forEach(({ amountElement, targetElement, apiFetchAmount, category }) => {
        if (amountElement) {
            apiFetchAmount().then((amount) => {
                amountElement.textContent = Intl.NumberFormat('en-US').format(amount);
            });
        }

        if (targetElement) {
            targetElement.textContent = Intl.NumberFormat('en-US').format(goalMap[category]);

            if (editButton) {
                editButton.addEventListener('click', () => {
                    toggleEditable(targetElement, category);
                });
            }
        }
    });

    if (document.querySelector(".streaks")) {
        api.getStreaks().then((streaks) => {
            document.getElementById("calStreak").textContent = streaks.calorieStreak ? `Last ${streaks.calorieStreak} Days` : "No streak";
            document.getElementById("sleepStreak").textContent = streaks.sleepStreak ? `Last ${streaks.sleepStreak} Days` : "No streak";
            document.getElementById("waterStreak").textContent = streaks.waterStreak ? `Last ${streaks.waterStreak} Days` : "No streak";
            document.getElementById("stepsStreak").textContent = streaks.stepsStreak ? `Last ${streaks.stepsStreak} Days` : "No streak";

        });
    }
});

function toggleEditable(target, category) {
    if (target.contentEditable === "true") {
        target.contentEditable = "false";
        editButton.textContent = "Edit";

        api.editGoal(category, target.textContent.replace(/[^0-9]/g, ''));
    } else {
        target.contentEditable = "true";
        editButton.textContent = "Save";
        target.focus();
    }
}
