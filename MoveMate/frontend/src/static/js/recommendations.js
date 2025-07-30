import api from './APIClient.js';

const submitGoals = document.querySelector('.createGoalButton');
const goalTitle = document.querySelector('.enterGoals');

await api.getUserGoals().then(goals => {
    console.log("user goals: ", goals );
    const goalTemplate = document.querySelector('#goal-template');
    const customGoals = document.querySelector('.goals');
    
    goals.forEach(goal => {
        console.log("GOALS: " + goal);
        const goalElement = goalTemplate.content.cloneNode(true);
        const goalDiv = goalElement.querySelector('.goal');
        goalDiv.querySelector('.title').textContent = goal.title;
        goalDiv.querySelector('.recommendations').textContent = goal.recommendations;
        customGoals.appendChild(goalElement);
    })
});

submitGoals.addEventListener('click', async (event) => {
    console.log(goalTitle.value);

    const user = await api.getAuthenticatedUser();

    api.postUserGoals(user.id, goalTitle.value, false, null).then(res => {
        console.log(res);
    });

    location.reload();

});