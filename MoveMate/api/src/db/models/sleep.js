module.exports = class Sleep {
    id = null;
    userId = null;
    itemName = null;
    amount = null;

    constructor(data) {
        this.id = data.slt_id;
        this.userId = data.slt_usr_id;
        this.itemName = data.slt_item;
        this.amount = data.slt_sleep;
        this.date = data.slt_date;
    }
}