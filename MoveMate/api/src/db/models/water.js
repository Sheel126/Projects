module.exports = class Water {
    id = null;
    userId = null;
    itemName = null;
    amount = null;

    constructor(data) {
        this.id = data.wt_id;
        this.userId = data.wt_usr_id;
        this.itemName = data.wt_item;
        this.amount = data.wt_water;
        this.date = data.wt_date;
    }
}