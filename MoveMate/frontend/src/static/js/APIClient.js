import HTTPClient from './HTTPClient.js';

// Authentication

const registerUser = (username, password) => {
    return HTTPClient.post('./api/register', { username, password });
};

const authenticateUser = (username, password) => {
    return HTTPClient.post('./api/login', { username, password });
};

const logoutUser = () => {
    return HTTPClient.post('./api/logout');
}

const getAuthenticatedUser = () => {
    return HTTPClient.get('./api/users/current');
}



// Calories

const getCalorieItems = () => {
    return HTTPClient.get('./api/calories');
}

const getCalorieAmount = () => {
    return HTTPClient.get('./api/calories/amount');
}

const addCalorieItem = (userId, name, amount) => {
    return HTTPClient.post('./api/calories', { userId, name, amount });
}

const deleteCalorieItem = (calorieId) => {
    return HTTPClient.delete('./api/calories/' + calorieId );
}




// Water

const getWaterItems = () => {
    return HTTPClient.get('./api/water');
}

const getWaterAmount = () => {
    return HTTPClient.get('./api/water/amount');
}

const addWaterItem = (userId, name, amount) => {
    return HTTPClient.post('./api/water', { userId, name, amount });
}

const deleteWaterItem = (waterId) => {
    return HTTPClient.delete('./api/water/' + waterId );
}



// Sleep

const getSleepItems = () => {
    return HTTPClient.get('./api/sleep');
}

const getSleepAmount = () => {
    return HTTPClient.get('./api/sleep/amount');
}

const addSleepItem = (userId, name, amount) => {
    return HTTPClient.post('./api/sleep', { userId, name, amount });
}

const deleteSleepItem = (sleepId) => {
    return HTTPClient.delete('./api/sleep/' + sleepId );
}



// Steps

const getStepsItems = () => {
    return HTTPClient.get('./api/steps');
}

const getStepsAmount = () => {
    return HTTPClient.get('./api/steps/amount');
}

const addStepsItem = (userId, name, amount) => {
    return HTTPClient.post('./api/steps', { userId, name, amount });
}

const deleteStepsItem = (stepsId) => {
    return HTTPClient.delete('./api/steps/' + stepsId );
}



// Reminders

const getReminders = () => {
    return HTTPClient.get('./api/reminders');
}

const postReminders = (userId, title, time, completed, category) => {
    const data = {
        "userId": userId,
        "title": title,
        "time": time,
        "completed": completed,
        "category": category
    }
    return HTTPClient.post('./api/reminders', data);
}

const putReminders = (reminderId, completed) => {
    const data = {
        "id": reminderId,
        "completed": completed
    }
    return HTTPClient.put('./api/reminders', data);
}



// Goals

const getGoals = () => {
    return HTTPClient.get('./api/goals');
}

const editGoal = (category, target) => {
    return HTTPClient.post('./api/goals', { category, target });
}

// Streaks

const getStreaks = () => {
    return HTTPClient.get('./api/streaks');
}

// Exports

const postUserGoals = (userId, title, completed, recommendations) => {
    const data = {
        "userId": userId,
        "title": title,
        "completed": completed,
        "recommendations": recommendations
    }
    return HTTPClient.post('./api/userGoals', data);
}

const getUserGoals = () => {
    return HTTPClient.get('./api/userGoals');
}

export default {
    registerUser,
    authenticateUser,
    logoutUser,
    getAuthenticatedUser,
    getCalorieItems,
    getCalorieAmount,
    addCalorieItem,
    deleteCalorieItem,
    getWaterItems,
    getWaterAmount,
    addWaterItem,
    deleteWaterItem,
    getSleepItems,
    getSleepAmount,
    addSleepItem,
    deleteSleepItem,
    getStepsItems,
    getStepsAmount,
    addStepsItem,
    deleteStepsItem,
    getReminders,
    postReminders,
    putReminders,
    getGoals,
    editGoal,
    getStreaks,
    postUserGoals,
    getUserGoals,
};