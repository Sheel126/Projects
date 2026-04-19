module.exports = class Recommendations {
    id = null;
    userId = null;
    title = null;
    completed = null;
    recommendations = null;

    constructor(data) {
        this.id = data.user_goal_id;
        this.userId = data.usr_id;
        this.title = data.user_goal_title;
        this.completed = data.user_goal_completed;
        this.recommendations = data.user_goal_recommendation;
    }
}