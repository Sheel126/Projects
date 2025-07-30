const db = require('./DBConnection');
const Calories = require('./models/calories');

module.exports = {
    getCaloriesUserId: (id) => {
        return db.query('SELECT * FROM calorie_tracking WHERE ct_usr_id=? ORDER BY ct_date DESC', [id]).then(rows => {
            let currentCalories = null;
            const userCalories = [];

            rows.forEach(calorieRow => {
                currentCalories = new Calories(calorieRow);
                userCalories.push(currentCalories);
            });

            return userCalories;
        });
    },

    getCalorieAmount(id) {
        return db.query('SELECT SUM(ct_calories) AS totalCalories FROM calorie_tracking WHERE ct_usr_id = ?', [id])
            .then(result => {
                if (result.length > 0) {
                    return result[0].totalCalories || 0;
                }
                return 0;
            });
    },

    postCalories: (caloriesData) => {
        return new Promise((resolve, reject) => {
            db.query('INSERT INTO calorie_tracking (ct_usr_id, ct_item, ct_calories, ct_date) VALUES (?, ?, ?, ?)',
                [caloriesData.userId, caloriesData.itemName, caloriesData.calories, new Date()]).then(result => {
                    resolve({message: "Added calories data successfully"});
                }).catch(err => {
                    reject({ message: "Failed to add calories data", code: 500 });
                });
        });
    },

    deleteCalories(ctId) {
        return db.query('DELETE FROM calorie_tracking WHERE ct_id = ?', [ctId]).then(result => {
            console.log('Calorie entry deleted successfully.');
            return true;
        });
    }
    
}