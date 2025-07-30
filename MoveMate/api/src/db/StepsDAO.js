const db = require('./DBConnection');
const Steps = require('./models/steps');

module.exports = {
    getSteps: (id) => {
        return db.query('SELECT * FROM steps_tracking WHERE stt_usr_id=? ORDER BY stt_date DESC', [id])
        .then(rows => {
            let currentStep = null;
            const stepCounts = [];

            rows.forEach(step => {
                currentStep = new Steps(step);
                stepCounts.push(currentStep);
            });

            return stepCounts;
        });
    },

    getStepsAmount(id) {
        return db.query('SELECT SUM(stt_steps) AS totalSteps FROM steps_tracking WHERE stt_usr_id = ?', [id])
            .then(result => {
                if (result.length > 0) {
                    return result[0].totalSteps || 0;
                }
                return 0;
            });
    },

    postSteps: (stepData) => {
        return db.query('INSERT INTO steps_tracking (stt_usr_id, stt_item, stt_steps, stt_date) VALUES (?, ?, ?, ?)', 
            [stepData.userId, stepData.itemName, stepData.steps, new Date()]
        ).then(result => {
            return 'Posted'
        });
    },

    deleteSteps(sttId) {
        return db.query('DELETE FROM steps_tracking WHERE stt_id = ?', [sttId]).then(result => {
            console.log('Steps entry deleted successfully.');
            resolve(true);
        });
    }
}