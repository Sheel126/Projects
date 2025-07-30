const db = require('./DBConnection');

const Sleep = require('./models/sleep');

module.exports = {
    getSleep: (id) => {
        return db.query('SELECT * FROM sleep_tracking WHERE slt_usr_id=? ORDER BY slt_date DESC', [id])
        .then(rows => {
            let currentSleep = null;
            const sleepCounts = [];

            rows.forEach(step => {
                currentSleep = new Sleep(step);
                sleepCounts.push(currentSleep);
            });

            return sleepCounts;
        });
    }, 

    getSleepAmount(id) {
        return db.query('SELECT SUM(slt_sleep) AS totalSleep FROM sleep_tracking WHERE slt_usr_id = ?', [id])
            .then(result => {
                if (result.length > 0) {
                    return result[0].totalSleep || 0;
                }
                return 0;
            });
    },

    postSleep: (sleepData) => {
        return db.query('INSERT INTO sleep_tracking (slt_usr_id, slt_item, slt_sleep, slt_date) VALUES (?, ?, ?, ?)', 
            [sleepData.userId, sleepData.itemName, sleepData.sleep, new Date()]
        ).then(result => {
            return 'Posted'
        });
    },

    deleteSleep(sltId) {
        return db.query('DELETE FROM sleep_tracking WHERE slt_id = ?', [sltId]).then(result => {
            console.log('Sleep entry deleted successfully.');
            resolve(true);
        });
    }
}