module.exports = class Goals {
    constructor(data) {
        this.id = data.goal_id;
        this.userId = data.goal_usr_id;
        this.category = data.goal_category;
        this.target = data.goal_target;
    }
}