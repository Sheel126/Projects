const db = require('./DBConnection');
const StepsDAO = require('../db/StepsDAO');
const SleepDAO = require('../db/SleepDAO');
const WaterDAO = require('../db/WaterDAO');
const GoalsDAO = require('../db/GoalsDAO');
const Streaks = require('./models/streak');
const CaloriesDAO = require('./CaloriesDAO');

module.exports = {
    getStreaks: (id) => {
        return db.query('SELECT * FROM streaks WHERE streak_usr_id=?', [id]).then(rows => {
            let currentStreaks = null;
            const streaksCount = [];
            rows.forEach(streaks => {
                currentStreaks = new Streaks(streaks);
                streaksCount.push(currentStreaks);
            });

            return streaksCount;
        });
    },

    postStreaks: (streakData) => {
        return db.query('INSERT INTO streaks (streak_usr_id, streaks) VALUES (?, ?)',
            [streakData.userId, streakData.streaks]
        ).then(result => {
            return 'Posted';
        });
    },

    calculateStreaks(id) {
        return fetchUserMetrics(id).then(([calories, sleep, water, steps, goals]) => {
            let goalsObj = {};

            goals.forEach((goal) => {
                goalsObj[goal.category] = goal.target;
            });

            let calS = 0, watS = 0, sleS = 0, steS = 0;

            let allDates = Array.from(new Set([
                ...calories.map((item) => item.date.toDateString()),
                ...sleep.map((item) => item.date.toDateString()),
                ...water.map((item) => item.date.toDateString()),
                ...steps.map((item) => item.date.toDateString()),
            ]));
            console.log(goalsObj);

            allDates.forEach((date) => {
                let dailyCal = calories.filter((item) => item.date.toDateString() === date).reduce((sum, item) => sum + item.amount, 0);
                let dailySleep = sleep.filter((item) => item.date.toDateString() === date).reduce((sum, item) => sum + item.amount, 0);
                let dailyWater = water.filter((item) => item.date.toDateString() === date).reduce((sum, item) => sum + item.amount, 0);
                let dailySteps = steps.filter((item) => item.date.toDateString() === date).reduce((sum, item) => sum + item.amount, 0);
                
                if (dailyCal >= (goalsObj.Calories || 0)) {
                    calS++;
                } else {
                    calS = 0;
                }

                if (dailySleep >= (goalsObj.Sleep || 0)) {
                    sleS++;
                } else {
                    sleS = 0;
                }

                if (dailyWater >= (goalsObj.Water || 0)) {
                    watS++;
                } else {
                    watS = 0;
                }

                if (dailySteps >= (goalsObj.Steps || 0)) {
                    steS++;
                } else {
                    steS = 0;
                }
            });

            return {
                calorieStreak: calS,
                sleepStreak: sleS,
                waterStreak: watS,
                stepsStreak: steS,
            };
        });
    }
}

function fetchUserMetrics(id) {
    return Promise.all([
        CaloriesDAO.getCaloriesUserId(id),
        SleepDAO.getSleep(id),
        WaterDAO.getWater(id),
        StepsDAO.getSteps(id),
        GoalsDAO.getGoals(id),
    ]);
}