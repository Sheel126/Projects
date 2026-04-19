const db = require('./DBConnection');
const Goal = require('./models/goal');

module.exports = {
    getGoals: (userId) => {
        return new Promise((resolve, reject) => {
            db.query('SELECT * FROM goals WHERE goal_usr_id=?', [userId]).then(rows => {
                if (rows.length != 0) {
                    let goals = [];
                    rows.forEach(row => {
                        goals.push(new Goal(row));
                    });

                    resolve(goals);
                } else {
                    reject({ message: "No goals exist for the provided user.", code: 404 });
                }
            });
        });
    },

    postPutGoal: (goalData) => {
        return new Promise((resolve, reject) => {
            const cat = goalData.category;
            if (!cat || (cat != "Calories" &&
                cat != "Water" &&
                cat != "Steps" &&
                cat != "Sleep")) {
                reject({ message: "The provided category is invalid.", code: 400 });
                return;
            }

            if (goalData.target == 0) {
                reject({ message: "The provided target must not be 0.", code: 400 });
                return;
            }

            return db.query('SELECT * FROM goals WHERE goal_usr_id = ? AND goal_category = ?',
                [goalData.userId, goalData.category]
            ).then(result => {
                if (result.length > 0) {
                    return db.query('UPDATE goals SET goal_target = ? WHERE goal_usr_id = ? AND goal_category = ?',
                        [goalData.target, goalData.userId, goalData.category]
                    ).then(() => {
                        resolve({ message: "Goal successfully updated.", code: 200 });
                    }).catch(err => {
                        reject({ message: "Failed to update the goal", code: 500 });
                    });
                } else {
                    return db.query('INSERT INTO goals (goal_usr_id, goal_category, goal_target) VALUES (?, ?, ?)',
                        [goalData.userId, goalData.category, goalData.target]
                    ).then(() => {
                        resolve({ message: "Goal successfully created.", code: 200 });
                    }).catch(err => {
                        reject({ message: "Failed to add the goal", code: 500 });
                    });
                }
            }).catch(err => {
                reject({ message: "Failed to check for existing goal", code: 500 });
            });
        });
    }
}