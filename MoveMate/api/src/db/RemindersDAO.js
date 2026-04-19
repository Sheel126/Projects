const db = require('./DBConnection');
const Reminders = require('./models/reminder');

module.exports = {
    getReminders: (id) => {
        return db.query('SELECT * FROM reminders WHERE rem_usr_id=?', [id]).then(rows => {
            let currenReminders = null;
            const reminders = [];

            rows.forEach(reminderRow => {
                currenReminders = new Reminders(reminderRow);
                reminders.push(currenReminders);
            });

            return reminders;
        });
    },

    postReminders: (reminderData) => {
        return db.query('INSERT INTO reminders (rem_usr_id, rem_title, rem_time, rem_completed, rem_category) VALUES (?, ?, ?, ?, ?)', 
            [reminderData.userId, reminderData.title, reminderData.time, reminderData.completed, reminderData.category]).then(result => {
                return 'Posted';
            });
        
    },

    updateCompleted: (reminderData) => {
        return db.query('UPDATE reminders SET rem_completed=? WHERE rem_id=?', [reminderData.completed, reminderData.id]).then(result => {
            return 'Reminder Updated';
        });
    }
}