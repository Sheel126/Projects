module.exports = class Reminders {
    id = null;
    userId = null;
    title = null;
    time = null;
    completed = null;
    category = null;

    constructor(data) {
        this.id = data.rem_id;
        this.userId = data.rem_usr_id;
        this.title = data.rem_title;
        this.time = data.rem_time;
        this.completed = data.rem_completed;
        this.category = data.rem_category
    } 
}