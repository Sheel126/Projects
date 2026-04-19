module.exports = class Calories {
    id = null;
    userId = null;
    itemName = null;
    amount = null;

    constructor(data) {
        this.id = data.ct_id,
        this.userId = data.ct_usr_id;
        this.itemName = data.ct_item;
        this.amount = data.ct_calories;
        this.date = data.ct_date;
    }
};