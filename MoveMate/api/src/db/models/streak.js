module.exports = class Streak {
    id = null;
    userId = null;
    streaks = null;

    constructor(data) {
        this.id = data.streak_id;
        this.userId = data.streak_usr_id;
        this.streaks = data.streaks;
    }
}